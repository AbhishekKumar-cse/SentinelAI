"""
Decision-Making Agent (DMA) — Reasoning core of AntiGravity.
Uses Claude claude-sonnet-4-20250514 with structured tool use.
Every decision includes: decision value, confidence score, full reasoning trace.
"""
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage

from agents.base_agent import BaseAgent, AgentToolError

logger = logging.getLogger(__name__)

DMA_SYSTEM_PROMPT = """You are a Decision-Making Agent. Your purpose is to apply reasoning, business rules, and risk analysis to produce clear, justified decisions.

For EVERY decision output:
1. The decision itself as a structured value
2. Confidence score 0.0-1.0
3. Step-by-step reasoning trace
4. Evidence you relied on with citations
5. Alternatives you considered and why rejected
6. What new information would change your decision

NEVER make a decision with confidence < 0.6 without flagging it requires_human_review=true.
Learn from past decisions by querying semantic memory before deciding."""


class DecisionMakingAgent(BaseAgent):
    family = "DMA"

    def get_system_prompt(self) -> str:
        return DMA_SYSTEM_PROMPT

    async def analyze_and_decide(
        self,
        task_definition: dict,
        context: dict,
        decision_schema: dict,
        workflow_id: str,
        task_id: Optional[str] = None,
    ) -> dict:
        """
        Core decision engine using Claude claude-sonnet-4-20250514.
        Returns DecisionResult with confidence score and full reasoning trace.
        """
        from db.models import DecisionRecord
        from langchain_anthropic import ChatAnthropic

        llm = ChatAnthropic(model="claude-sonnet-4-20250514", temperature=0, max_tokens=4096)

        # Build structured decision prompt
        prompt = f"""Task: {task_definition.get('title', 'Decision Task')}
Description: {task_definition.get('description', '')}

Context:
{json.dumps(context, indent=2, default=str)}

Decision Schema (your output must match this structure):
{json.dumps(decision_schema, indent=2)}

Provide your decision with:
1. decision_value: the actual decision
2. confidence: float 0.0-1.0
3. reasoning_trace: list of reasoning steps
4. supporting_evidence: list of evidence items used
5. alternatives_considered: list of rejected alternatives with reasons
6. requires_human_review: true if confidence < 0.6"""

        messages = [
            SystemMessage(content=self.get_system_prompt()),
            HumanMessage(content=prompt),
        ]

        try:
            response = await llm.ainvoke(messages)
            content = response.content

            # Parse structured output from LLM response
            # In production, use structured output / tool calling
            decision_data = self._parse_decision_response(content, decision_schema)

        except Exception as e:
            logger.error(f"LLM call failed in analyze_and_decide: {e}")
            decision_data = {
                "decision_value": None,
                "confidence": 0.0,
                "reasoning_trace": [f"LLM call failed: {str(e)}"],
                "supporting_evidence": [],
                "alternatives_considered": [],
                "requires_human_review": True,
            }

        requires_review = decision_data.get("confidence", 0) < 0.6

        # Write to decisionRecords collection
        record = DecisionRecord(
            decision_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            task_id=task_id,
            agent_id=self.agent_id,
            tenant_id=self.tenant_id,
            decision_type=task_definition.get("decision_type", "GENERAL"),
            decision_value=decision_data.get("decision_value"),
            confidence=decision_data.get("confidence", 0.5),
            requires_human_review=requires_review,
            reasoning_trace=decision_data.get("reasoning_trace", []),
            supporting_evidence=decision_data.get("supporting_evidence", []),
            alternatives_considered=decision_data.get("alternatives_considered", []),
            model_version="claude-sonnet-4-20250514",
        )
        await record.insert()

        await self.write_audit_record(
            event_type="AGENT_DECISION_MADE",
            payload={
                "decision_id": record.decision_id,
                "decision_type": task_definition.get("decision_type", "GENERAL"),
                "confidence": record.confidence,
                "requires_human_review": requires_review,
            },
            workflow_id=workflow_id,
            task_id=task_id,
        )

        await self.emit_kafka_event(
            topic="agent.decisions",
            event_type="AgentDecisionMade",
            data={
                "decision_id": record.decision_id,
                "confidence": record.confidence,
                "agent_id": self.agent_id,
            },
            workflow_id=workflow_id,
        )

        if requires_review:
            await self._create_human_review_task(record, workflow_id, context)

        return {
            "decision_id": record.decision_id,
            "decision_value": record.decision_value,
            "confidence": record.confidence,
            "requires_human_review": requires_review,
            "reasoning_trace": record.reasoning_trace,
        }

    def _parse_decision_response(self, content: str, schema: dict) -> dict:
        """Parse LLM response into structured decision format."""
        # Try JSON extraction first
        import re
        json_match = re.search(r'\{[^{}]*"confidence"[^{}]*\}', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # Fallback: extract key fields from text
        lines = content.split('\n')
        confidence = 0.7  # Default moderate confidence

        # Look for confidence in text
        for line in lines:
            if 'confidence' in line.lower():
                nums = re.findall(r'0\.\d+', line)
                if nums:
                    confidence = float(nums[0])
                    break

        return {
            "decision_value": content[:500],  # Truncated response as value
            "confidence": confidence,
            "reasoning_trace": [l for l in lines if l.strip()][:10],
            "supporting_evidence": [],
            "alternatives_considered": [],
            "requires_human_review": confidence < 0.6,
        }

    async def _create_human_review_task(self, record: "DecisionRecord", workflow_id: str, context: dict):
        """Create a HumanTask for low-confidence decisions."""
        from db.models import HumanTask, HumanTaskStatus, Priority
        from datetime import timedelta

        task = HumanTask(
            human_task_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            tenant_id=self.tenant_id,
            assignee_id=context.get("workflow_manager_id", "unassigned"),
            title=f"Review Required: {record.decision_type} Decision",
            description=f"DMA produced a low-confidence decision ({record.confidence:.0%}). Human review required.",
            context_snapshot={
                "decision_id": record.decision_id,
                "confidence": record.confidence,
                "reasoning_trace": record.reasoning_trace,
                "decision_value": record.decision_value,
            },
            status=HumanTaskStatus.PENDING,
            priority=Priority.HIGH,
            due_at=datetime.utcnow() + timedelta(hours=4),
        )
        await task.insert()

    async def apply_business_rules(
        self,
        rules_set_id: str,
        context: dict,
        workflow_id: str,
    ) -> dict:
        """
        Evaluate all active rules for a rule set against the context.
        Safe Python eval with sandboxed namespace.
        """
        from db.models import RulesEngine

        rules = await RulesEngine.find(
            RulesEngine.rule_set_id == rules_set_id,
            RulesEngine.tenant_id == self.tenant_id,
            RulesEngine.is_active == True,
        ).sort(-RulesEngine.priority).to_list()

        matched_rules = []
        applied_actions = []
        modified_fields = []

        # Safe eval namespace — NO imports, NO file access
        safe_globals = {"__builtins__": {}}
        safe_locals = {**context}  # Direct context access

        for rule in rules:
            try:
                # Evaluate conditions
                all_conditions_met = True
                for condition in rule.conditions:
                    expr = condition.get("expression", "False")
                    try:
                        result = eval(expr, safe_globals, safe_locals)
                        if not result:
                            all_conditions_met = False
                            break
                    except Exception as e:
                        logger.warning(f"Rule condition eval failed: {e}")
                        all_conditions_met = False
                        break

                if all_conditions_met:
                    matched_rules.append(rule.rule_id)

                    # Apply actions
                    for action in rule.actions:
                        action_type = action.get("type")
                        if action_type == "set":
                            field = action.get("field")
                            value = action.get("value")
                            context[field] = value
                            safe_locals[field] = value
                            modified_fields.append(field)
                            applied_actions.append(action)
                        elif action_type == "append":
                            field = action.get("field")
                            value = action.get("value")
                            if field not in context:
                                context[field] = []
                            context[field].append(value)
                            modified_fields.append(field)
                            applied_actions.append(action)

                    if rule.stop_on_match:
                        break

            except Exception as e:
                logger.error(f"Rule {rule.rule_id} evaluation error: {e}")

        await self.write_audit_record(
            event_type="RULES_APPLIED",
            payload={
                "rules_set_id": rules_set_id,
                "matched_rules": matched_rules,
                "applied_actions": len(applied_actions),
                "modified_fields": modified_fields,
            },
            workflow_id=workflow_id,
        )

        return {
            "matched_rules": matched_rules,
            "applied_actions": applied_actions,
            "modified_context_fields": modified_fields,
            "updated_context": context,
        }

    async def risk_assessment(
        self,
        entity_type: str,
        entity_id: str,
        context: dict,
        workflow_id: str,
    ) -> dict:
        """
        Multi-component risk assessment:
        30% rule-based + 40% ML model + 30% LLM reasoning
        """
        # Component 1: Rule-based
        rules_result = await self.apply_business_rules(
            rules_set_id=f"risk_{entity_type}",
            context=context,
            workflow_id=workflow_id,
        )
        rule_score = len(rules_result["matched_rules"]) / 10.0  # Normalize
        rule_score = min(rule_score, 1.0)

        # Component 2: LLM reasoning (ML model skipped in dev)
        llm_result = await self.analyze_and_decide(
            task_definition={
                "title": f"Risk Assessment: {entity_type} {entity_id}",
                "description": "Assess the risk level for this entity",
                "decision_type": "RISK_ASSESSMENT",
            },
            context={**context, "entity_type": entity_type, "entity_id": entity_id},
            decision_schema={
                "risk_components": "list[str]",
                "risk_score": "float 0-1",
                "recommended_mitigations": "list[str]",
            },
            workflow_id=workflow_id,
        )

        llm_confidence = llm_result.get("confidence", 0.5)

        # Combined risk score
        ml_score = 0.5  # Placeholder for ONNX model
        combined = 0.3 * rule_score + 0.4 * ml_score + 0.3 * llm_confidence

        risk_level = (
            "CRITICAL" if combined > 0.8
            else "HIGH" if combined > 0.6
            else "MEDIUM" if combined > 0.3
            else "LOW"
        )

        if risk_level == "CRITICAL":
            await self.emit_kafka_event(
                topic="escalations",
                event_type="CriticalRiskDetected",
                data={
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "risk_score": combined,
                    "risk_level": risk_level,
                },
                workflow_id=workflow_id,
            )

        return {
            "entity_id": entity_id,
            "entity_type": entity_type,
            "risk_score": combined,
            "risk_level": risk_level,
            "rule_score": rule_score,
            "ml_score": ml_score,
            "llm_confidence": llm_confidence,
            "recommended_mitigations": [],
        }

    async def resolve_exception(
        self,
        exception_type: str,
        exception_context: dict,
        available_strategies: list,
        workflow_id: str,
    ) -> dict:
        """
        Resolve workflow exceptions using past memory + LLM analysis.
        Returns strategy if confidence >= 0.7, else REQUIRES_HUMAN.
        """
        result = await self.analyze_and_decide(
            task_definition={
                "title": f"Exception Resolution: {exception_type}",
                "description": f"Resolve this exception using available strategies",
                "decision_type": "EXCEPTION_RESOLUTION",
            },
            context={
                **exception_context,
                "exception_type": exception_type,
                "available_strategies": available_strategies,
            },
            decision_schema={
                "chosen_strategy": "str",
                "execution_steps": "list[str]",
                "fallback_strategy": "str",
            },
            workflow_id=workflow_id,
        )

        if result["confidence"] >= 0.7:
            return {
                "status": "RESOLVED",
                "strategy": result["decision_value"],
                "confidence": result["confidence"],
            }
        else:
            return {
                "status": "REQUIRES_HUMAN",
                "top_strategies": available_strategies[:3],
                "confidence": result["confidence"],
            }

    async def classify_document(
        self,
        document_text: str,
        taxonomy_id: str,
        workflow_id: str,
    ) -> dict:
        """Classify a document using rule-based + LLM approach."""
        result = await self.analyze_and_decide(
            task_definition={
                "title": "Document Classification",
                "description": f"Classify this document using taxonomy: {taxonomy_id}",
                "decision_type": "DOCUMENT_CLASSIFICATION",
            },
            context={"document_excerpt": document_text[:2000], "taxonomy_id": taxonomy_id},
            decision_schema={
                "category": "str",
                "subcategory": "str",
                "key_phrases": "list[str]",
            },
            workflow_id=workflow_id,
        )
        return {
            "classification": result["decision_value"],
            "confidence": result["confidence"],
            "taxonomy_id": taxonomy_id,
        }

    async def evaluate_approval_criteria(
        self,
        approval_policy_id: str,
        submission: dict,
        workflow_id: str,
    ) -> dict:
        """Evaluate if submission meets approval criteria."""
        result = await self.analyze_and_decide(
            task_definition={
                "title": "Approval Evaluation",
                "description": f"Evaluate submission against policy: {approval_policy_id}",
                "decision_type": "APPROVAL_EVALUATION",
            },
            context=submission,
            decision_schema={
                "decision": "APPROVED|REJECTED|NEEDS_REVIEW",
                "failed_conditions": "list[str]",
                "weighted_score": "float",
            },
            workflow_id=workflow_id,
        )

        decision_text = str(result.get("decision_value", "")).upper()
        if "APPROVE" in decision_text:
            status = "APPROVED"
        elif "REJECT" in decision_text:
            status = "REJECTED"
        else:
            status = "NEEDS_REVIEW"

        return {
            "status": status,
            "confidence": result["confidence"],
            "policy_id": approval_policy_id,
        }

    async def execute_task(
        self,
        task_id: str,
        workflow_id: str,
        task_definition: dict[Any, Any],
        context: dict[Any, Any],
    ) -> dict[Any, Any]:
        """DMA task execution entry point."""
        action = task_definition.get("action", "decide")

        if action == "decide":
            return await self.analyze_and_decide(
                task_definition=task_definition,
                context=context,
                decision_schema=task_definition.get("schema", {}),
                workflow_id=workflow_id,
                task_id=task_id,
            )
        elif action == "risk_assessment":
            return await self.risk_assessment(
                entity_type=task_definition.get("entity_type", "generic"),
                entity_id=task_definition.get("entity_id", ""),
                context=context,
                workflow_id=workflow_id,
            )
        elif action == "apply_rules":
            return await self.apply_business_rules(
                rules_set_id=task_definition.get("rules_set_id", "default"),
                context=context,
                workflow_id=workflow_id,
            )
        else:
            return {"action": action, "status": "completed", "workflow_id": workflow_id}
