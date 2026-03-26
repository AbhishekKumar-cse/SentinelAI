"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { useWebSocketStore } from "@/lib/websocket-store";
import SLAHealthDashboard from "@/components/workflow/SLAHealthDashboard";
import KPICards from "@/components/dashboard/KPICards";
import ActiveWorkflowsPanel from "@/components/dashboard/ActiveWorkflowsPanel";

interface WorkflowList {
  workflows: Array<{
    workflow_id: string;
    name: string;
    status: string;
    health_score: number;
    sla_status: string;
    breach_probability: number;
    started_at: string;
  }>;
  count: number;
}

interface AgentList {
  agents: Array<{
    agent_id: string;
    family: string;
    status: string;
    current_task_id: string | null;
  }>;
  count: number;
}

export default function CommandCenterPage() {
  const { isConnected } = useWebSocketStore();

  const { data: workflows } = useQuery<WorkflowList>({
    queryKey: ["workflows", "running"],
    queryFn: () => api.get<WorkflowList>("/workflows?status=RUNNING&limit=20"),
    refetchInterval: 30000,
  });

  const { data: agents } = useQuery<AgentList>({
    queryKey: ["agents"],
    queryFn: () => api.get<AgentList>("/agents"),
    refetchInterval: 60000,
  });

  const { data: analytics } = useQuery({
    queryKey: ["analytics", "sla"],
    queryFn: () => api.get<{ series: Array<{ timestamp: string; adherence_pct: number }> }>("/analytics/sla"),
    refetchInterval: 60000,
  });

  const runningCount = workflows?.count ?? 0;
  const agentCount = agents?.count ?? 0;
  const busyAgents = agents?.agents.filter((a) => a.status === "BUSY").length ?? 0;
  const atRiskWorkflows = workflows?.workflows.filter((w) => w.breach_probability > 0.4) ?? [];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Command Center</h1>
          <p className="text-slate-400 text-sm mt-1">
            Real-time enterprise workflow orchestration
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium ${
            isConnected 
              ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" 
              : "bg-red-500/10 text-red-400 border border-red-500/20"
          }`}>
            <div className={`w-1.5 h-1.5 rounded-full ${isConnected ? "bg-emerald-400 animate-pulse" : "bg-red-400"}`} />
            {isConnected ? "Live" : "Disconnected"}
          </div>
        </div>
      </div>

      {/* KPI Cards */}
      <KPICards
        runningWorkflows={runningCount}
        activeAgents={busyAgents}
        totalAgents={agentCount}
        atRiskCount={atRiskWorkflows.length}
      />

      {/* SLA Health Dashboard */}
      <SLAHealthDashboard
        workflows={workflows?.workflows ?? []}
        adherenceSeries={analytics?.series ?? []}
      />

      {/* Active Workflows Panel */}
      <ActiveWorkflowsPanel workflows={workflows?.workflows ?? []} />
    </div>
  );
}
