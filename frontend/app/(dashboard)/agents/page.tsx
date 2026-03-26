"use client";

export const dynamic = "force-dynamic";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { Bot, Cpu, Zap, AlertTriangle, Clock, CheckCircle } from "lucide-react";
import { formatDistanceToNow } from "date-fns";

const FAMILY_CONFIG: Record<string, { label: string; color: string; bg: string; icon: React.FC<any> }> = {
  MOA: { label: "Meta-Orchestrator", color: "text-violet-400", bg: "bg-violet-500/10 border-violet-500/20", icon: Cpu },
  DRA: { label: "Data Retrieval", color: "text-blue-400", bg: "bg-blue-500/10 border-blue-500/20", icon: Bot },
  DMA: { label: "Decision Making", color: "text-amber-400", bg: "bg-amber-500/10 border-amber-500/20", icon: Zap },
  AEA: { label: "Action Execution", color: "text-emerald-400", bg: "bg-emerald-500/10 border-emerald-500/20", icon: CheckCircle },
  VA: { label: "Verification", color: "text-cyan-400", bg: "bg-cyan-500/10 border-cyan-500/20", icon: CheckCircle },
  MIA: { label: "Meeting Intelligence", color: "text-pink-400", bg: "bg-pink-500/10 border-pink-500/20", icon: Bot },
};

const STATUS_COLOR: Record<string, string> = {
  IDLE: "text-slate-400 bg-slate-500/10 border-slate-500/20",
  BUSY: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
  DEGRADED: "text-amber-400 bg-amber-500/10 border-amber-500/20",
  RESTARTING: "text-blue-400 bg-blue-500/10 border-blue-500/20",
  DISABLED: "text-slate-600 bg-slate-800/50 border-slate-700/30",
  STUCK: "text-red-400 bg-red-500/10 border-red-500/20",
};

interface Agent {
  agent_id: string;
  family: string;
  name: string;
  status: string;
  current_task_id: string | null;
  last_heartbeat_at: string;
  performance_metrics: {
    tasks_completed: number;
    tasks_failed: number;
    avg_confidence: number;
    error_rate: number;
    last_24h_throughput: number;
  };
}

function AgentCard({ agent }: { agent: Agent }) {
  const family = FAMILY_CONFIG[agent.family] || FAMILY_CONFIG.DRA;
  const Icon = family.icon;
  const statusColor = STATUS_COLOR[agent.status] || STATUS_COLOR.IDLE;
  const heartbeatAge = agent.last_heartbeat_at
    ? (Date.now() - new Date(agent.last_heartbeat_at).getTime()) / 1000
    : 999;
  const isHealthy = heartbeatAge < 60;

  const errorRate = agent.performance_metrics?.error_rate ?? 0;
  const confidence = agent.performance_metrics?.avg_confidence ?? 0;
  const throughput = agent.performance_metrics?.last_24h_throughput ?? 0;
  const completed = agent.performance_metrics?.tasks_completed ?? 0;

  return (
    <div className={`bg-slate-900/50 border ${family.bg} rounded-2xl p-5 backdrop-blur-sm hover:bg-slate-900/70 transition-all`}>
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-xl border flex items-center justify-center ${family.bg}`}>
            <Icon size={18} className={family.color} />
          </div>
          <div>
            <div className="text-sm font-semibold text-white">{agent.name}</div>
            <div className={`text-[10px] font-medium ${family.color}`}>{family.label}</div>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1.5">
          <span className={`px-2 py-0.5 rounded-md text-[10px] font-medium border ${statusColor}`}>
            {agent.status}
          </span>
          <div className={`flex items-center gap-1 text-[10px] ${isHealthy ? "text-emerald-400" : "text-red-400"}`}>
            <div className={`w-1.5 h-1.5 rounded-full ${isHealthy ? "bg-emerald-400 animate-pulse" : "bg-red-400"}`} />
            {isHealthy ? "Heartbeat OK" : "Stale"}
          </div>
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        {[
          { label: "Throughput/24h", value: throughput.toString(), color: "text-violet-400" },
          { label: "Completed", value: completed.toString(), color: "text-emerald-400" },
          { label: "Avg Confidence", value: `${Math.round(confidence * 100)}%`, color: confidence > 0.8 ? "text-emerald-400" : "text-amber-400" },
          { label: "Error Rate", value: `${(errorRate * 100).toFixed(1)}%`, color: errorRate < 0.05 ? "text-emerald-400" : "text-red-400" },
        ].map((m) => (
          <div key={m.label} className="bg-slate-800/30 rounded-lg p-2.5">
            <div className="text-[10px] text-slate-500">{m.label}</div>
            <div className={`text-sm font-bold ${m.color} mt-0.5`}>{m.value}</div>
          </div>
        ))}
      </div>

      {/* Current Task */}
      <div className="text-[10px] text-slate-600 truncate">
        {agent.current_task_id ? (
          <span>Task: <span className="font-mono text-violet-400">{agent.current_task_id.slice(0, 16)}...</span></span>
        ) : (
          <span>Idle · {agent.last_heartbeat_at && formatDistanceToNow(new Date(agent.last_heartbeat_at), { addSuffix: true })}</span>
        )}
      </div>
    </div>
  );
}

export default function AgentsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["agents"],
    queryFn: () => api.get<{ agents: Agent[]; count: number }>("/agents"),
    refetchInterval: 30000,
  });

  const agents = data?.agents ?? [];
  const byFamily = agents.reduce((acc, a) => {
    if (!acc[a.family]) acc[a.family] = [];
    acc[a.family].push(a);
    return acc;
  }, {} as Record<string, Agent[]>);

  const busyCount = agents.filter((a) => a.status === "BUSY").length;
  const stuckCount = agents.filter((a) => a.status === "STUCK").length;
  const degradedCount = agents.filter((a) => a.status === "DEGRADED").length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Agent Fleet</h1>
          <p className="text-slate-400 text-sm mt-1">
            {agents.length} agents · {busyCount} active · {stuckCount + degradedCount} need attention
          </p>
        </div>
        {(stuckCount + degradedCount) > 0 && (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-xs">
            <AlertTriangle size={12} />
            {stuckCount + degradedCount} agents need attention
          </div>
        )}
      </div>

      {/* Fleet Stats */}
      <div className="grid grid-cols-5 gap-3">
        {["MOA", "DRA", "DMA", "AEA", "VA", "MIA"].slice(0, 5).map((family) => {
          const familyAgents = byFamily[family] ?? [];
          const config = FAMILY_CONFIG[family];
          const Icon = config.icon;
          return (
            <div key={family} className={`bg-slate-900/50 border ${config.bg} rounded-xl p-4`}>
              <div className="flex items-center gap-2 mb-2">
                <Icon size={14} className={config.color} />
                <span className="text-[11px] text-slate-400">{config.label}</span>
              </div>
              <div className={`text-2xl font-bold ${config.color}`}>{familyAgents.length}</div>
              <div className="text-[10px] text-slate-600 mt-0.5">
                {familyAgents.filter((a) => a.status === "BUSY").length} busy
              </div>
            </div>
          );
        })}
        <div className="bg-slate-900/50 border border-pink-500/20 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <Bot size={14} className="text-pink-400" />
            <span className="text-[11px] text-slate-400">MIA</span>
          </div>
          <div className="text-2xl font-bold text-pink-400">{(byFamily["MIA"] ?? []).length}</div>
          <div className="text-[10px] text-slate-600 mt-0.5">
            {(byFamily["MIA"] ?? []).filter((a) => a.status === "BUSY").length} busy
          </div>
        </div>
      </div>

      {/* Agent Cards by Family */}
      {isLoading ? (
        <div className="grid grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-52 bg-slate-800/30 rounded-2xl animate-pulse" />
          ))}
        </div>
      ) : (
        Object.entries(FAMILY_CONFIG).map(([family, config]) => {
          const familyAgents = byFamily[family] ?? [];
          if (familyAgents.length === 0) return null;
          return (
            <div key={family}>
              <div className="flex items-center gap-2 mb-3">
                <config.icon size={14} className={config.color} />
                <h2 className="text-sm font-medium text-white">{config.label} Agents</h2>
                <span className={`px-1.5 py-0.5 rounded text-[10px] border ${config.bg} ${config.color}`}>
                  {familyAgents.length}
                </span>
              </div>
              <div className="grid grid-cols-3 gap-4">
                {familyAgents.map((agent) => (
                  <AgentCard key={agent.agent_id} agent={agent} />
                ))}
              </div>
            </div>
          );
        })
      )}
    </div>
  );
}
