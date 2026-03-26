"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { api } from "@/lib/api-client";
import { useState } from "react";
import Link from "next/link";
import { ArrowLeft, Pause, Play, XCircle, Shield, Activity, Bot } from "lucide-react";
import { formatDistanceToNow } from "date-fns";

const TASK_STATUS_COLOR: Record<string, string> = {
  PENDING: "bg-slate-500/20 text-slate-400 border-slate-500/30",
  ASSIGNED: "bg-blue-500/20 text-blue-300 border-blue-500/30",
  IN_PROGRESS: "bg-violet-500/20 text-violet-300 border-violet-500/30",
  COMPLETED: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
  FAILED: "bg-red-500/20 text-red-300 border-red-500/30",
  CANCELLED: "bg-slate-500/10 text-slate-500 border-slate-500/20",
};

export default function WorkflowDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [activeTab, setActiveTab] = useState<"tasks" | "decisions" | "audit" | "health">("tasks");

  const { data: workflow, isLoading } = useQuery({
    queryKey: ["workflow", id],
    queryFn: () => api.get<any>(`/workflows/${id}`),
    refetchInterval: 15000,
  });

  const { data: decisions } = useQuery({
    queryKey: ["workflow-decisions", id],
    queryFn: () => api.get<any>(`/workflows/${id}/decisions`),
    enabled: activeTab === "decisions",
  });

  const { data: audit } = useQuery({
    queryKey: ["workflow-audit", id],
    queryFn: () => api.get<any>(`/workflows/${id}/audit`),
    enabled: activeTab === "audit",
  });

  const { data: health } = useQuery({
    queryKey: ["workflow-health", id],
    queryFn: () => api.get<any>(`/workflows/${id}/health`),
    refetchInterval: 30000,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 rounded-full border-2 border-violet-500 border-t-transparent animate-spin" />
      </div>
    );
  }

  if (!workflow) {
    return (
      <div className="text-center py-12">
        <div className="text-slate-500">Workflow not found</div>
        <Link href="/workflows" className="text-violet-400 text-sm mt-2 inline-block">← Back to workflows</Link>
      </div>
    );
  }

  const healthColor =
    (health?.health_score ?? 100) >= 80
      ? "text-emerald-400"
      : (health?.health_score ?? 100) >= 60
      ? "text-amber-400"
      : "text-red-400";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-4">
          <Link href="/workflows" className="w-9 h-9 flex items-center justify-center rounded-xl bg-slate-800 hover:bg-slate-700 transition-colors text-slate-400 hover:text-white">
            <ArrowLeft size={16} />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-white">{workflow.name || "Workflow"}</h1>
            <div className="text-slate-500 text-xs font-mono mt-1">{id}</div>
          </div>
          <span className={`px-3 py-1 rounded-full text-xs font-medium border ${
            workflow.status === "RUNNING" ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" :
            workflow.status === "FAILED" ? "bg-red-500/10 text-red-400 border-red-500/20" :
            "bg-amber-500/10 text-amber-400 border-amber-500/20"
          }`}>
            {workflow.status}
          </span>
        </div>

        {/* Controls */}
        <div className="flex gap-2">
          {workflow.status === "RUNNING" && (
            <button
              onClick={() => api.post(`/workflows/${id}/pause`, { reason: "Manual pause" })}
              className="flex items-center gap-2 px-4 py-2 bg-amber-500/10 border border-amber-500/20 rounded-lg text-amber-400 hover:bg-amber-500/20 transition-all text-sm"
            >
              <Pause size={13} />
              Pause
            </button>
          )}
          {workflow.status === "PAUSED" && (
            <button
              onClick={() => api.post(`/workflows/${id}/resume`, { resume_context: {} })}
              className="flex items-center gap-2 px-4 py-2 bg-emerald-500/10 border border-emerald-500/20 rounded-lg text-emerald-400 hover:bg-emerald-500/20 transition-all text-sm"
            >
              <Play size={13} />
              Resume
            </button>
          )}
          <button
            onClick={() => api.post(`/workflows/${id}/cancel`, { reason: "Manual cancel", execute_rollback: false })}
            className="flex items-center gap-2 px-4 py-2 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 hover:bg-red-500/20 transition-all text-sm"
          >
            <XCircle size={13} />
            Cancel
          </button>
        </div>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "Health Score", value: `${Math.round(health?.health_score ?? 0)}`, color: healthColor },
          { label: "SLA Status", value: health?.sla_status ?? "—", color: health?.sla_status === "ON_TRACK" ? "text-emerald-400" : "text-red-400" },
          { label: "Breach Risk", value: `${Math.round((health?.breach_probability ?? 0) * 100)}%`, color: (health?.breach_probability ?? 0) > 0.5 ? "text-red-400" : "text-emerald-400" },
          { label: "Tasks", value: `${health?.task_stats?.completed ?? 0}/${health?.task_stats?.total ?? 0}`, color: "text-violet-400" },
        ].map((stat) => (
          <div key={stat.label} className="bg-slate-900/50 border border-slate-800/50 rounded-xl p-4">
            <div className="text-slate-500 text-xs">{stat.label}</div>
            <div className={`text-xl font-bold mt-1 ${stat.color}`}>{stat.value}</div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-slate-900/50 border border-slate-800/50 rounded-xl p-1 w-fit">
        {(["tasks", "decisions", "audit", "health"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 rounded-lg text-sm font-medium capitalize transition-all ${
              activeTab === tab
                ? "bg-violet-600 text-white shadow-sm"
                : "text-slate-400 hover:text-white"
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === "tasks" && (
        <div className="bg-slate-900/50 border border-slate-800/50 rounded-2xl overflow-hidden">
          <div className="grid grid-cols-12 px-6 py-3 border-b border-slate-800/50 text-xs text-slate-500 font-medium">
            <div className="col-span-4">Task</div>
            <div className="col-span-2">Type</div>
            <div className="col-span-2">Status</div>
            <div className="col-span-2">Agent</div>
            <div className="col-span-2">Started</div>
          </div>
          <div className="divide-y divide-slate-800/50">
            {(workflow.tasks || []).map((task: any) => (
              <div key={task.task_id} className="grid grid-cols-12 px-6 py-3 items-center hover:bg-slate-800/20 transition-all">
                <div className="col-span-4">
                  <div className="flex items-center gap-2">
                    <Bot size={12} className="text-slate-500" />
                    <span className="text-sm text-white font-mono">{task.task_id.slice(0, 12)}...</span>
                  </div>
                </div>
                <div className="col-span-2 text-xs text-slate-500">{task.task_type}</div>
                <div className="col-span-2">
                  <span className={`px-2 py-0.5 rounded-md text-[10px] font-medium border ${TASK_STATUS_COLOR[task.status] || TASK_STATUS_COLOR.PENDING}`}>
                    {task.status}
                  </span>
                </div>
                <div className="col-span-2 text-xs text-slate-500 truncate font-mono">{task.assigned_agent_id?.slice(0, 12) || "—"}</div>
                <div className="col-span-2 text-xs text-slate-500">
                  {task.started_at ? formatDistanceToNow(new Date(task.started_at), { addSuffix: true }) : "—"}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === "decisions" && (
        <div className="space-y-3">
          {(decisions?.decisions || []).map((d: any) => (
            <div key={d.decision_id} className="bg-slate-900/50 border border-slate-800/50 rounded-xl p-5">
              <div className="flex items-center justify-between mb-3">
                <div className="text-sm text-white font-medium">{d.decision_type}</div>
                <div className={`px-3 py-1 rounded-full text-xs font-medium ${
                  d.confidence >= 0.8 ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" :
                  d.confidence >= 0.6 ? "bg-amber-500/10 text-amber-400 border border-amber-500/20" :
                  "bg-red-500/10 text-red-400 border border-red-500/20"
                }`}>
                  {Math.round(d.confidence * 100)}% confidence
                </div>
              </div>
              <div className="text-xs text-slate-500 space-y-1">
                {d.reasoning_trace?.slice(0, 3).map((trace: string, i: number) => (
                  <div key={i} className="flex gap-2">
                    <span className="text-violet-500">{i + 1}.</span>
                    {trace}
                  </div>
                ))}
              </div>
            </div>
          ))}
          {(!decisions?.decisions?.length) && (
            <div className="text-center py-8 text-slate-600">No decisions yet</div>
          )}
        </div>
      )}

      {activeTab === "audit" && (
        <div className="bg-slate-900/50 border border-slate-800/50 rounded-2xl overflow-hidden">
          <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800/50">
            <div className="flex items-center gap-2 text-sm text-white">
              <Shield size={14} className="text-violet-400" />
              Audit Trail
            </div>
            <Link href={`/workflows/${id}/audit`} className="text-xs text-violet-400 hover:underline">
              Full audit →
            </Link>
          </div>
          <div className="divide-y divide-slate-800/50">
            {(audit?.records || []).slice(0, 10).map((record: any) => (
              <div key={record.audit_id} className="px-6 py-3 flex items-start gap-3 hover:bg-slate-800/20 transition-all">
                <div className={`mt-1 w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                  record.event_type.includes("FAIL") ? "bg-red-400" :
                  record.event_type.includes("COMPLETE") ? "bg-emerald-400" :
                  "bg-violet-400"
                }`} />
                <div className="flex-1 min-w-0">
                  <div className="text-xs text-white font-medium">{record.event_type}</div>
                  <div className="text-[10px] text-slate-500 mt-0.5">
                    {record.actor_id?.slice(0, 20)} · {record.created_at && new Date(record.created_at).toLocaleTimeString()}
                  </div>
                </div>
                <div className="flex-shrink-0">
                  <Shield size={10} className={record.curr_hash ? "text-emerald-500" : "text-red-500"} aria-label="Hash verified" />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
