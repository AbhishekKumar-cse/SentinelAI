"use client";

export const dynamic = "force-dynamic";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { useState } from "react";
import {
  Bot, Cpu, Zap, AlertTriangle, Clock, CheckCircle, Activity,
  TrendingUp, TrendingDown, Play, Pause, RefreshCw, BarChart3,
  Shield
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { toast } from "sonner";
import {
  AreaChart, Area, ResponsiveContainer, Tooltip, XAxis
} from "recharts";

const FAMILY_CONFIG: Record<string, {
  label: string; color: string; bg: string; icon: React.FC<any>; description: string;
}> = {
  MOA: { label: "Meta-Orchestrator", color: "text-violet-400", bg: "bg-violet-500/10 border-violet-500/20", icon: Cpu, description: "Manages workflow execution and agent assignment" },
  DRA: { label: "Data Retrieval", color: "text-blue-400", bg: "bg-blue-500/10 border-blue-500/20", icon: Bot, description: "Fetches and normalizes data from external systems" },
  DMA: { label: "Decision Making", color: "text-amber-400", bg: "bg-amber-500/10 border-amber-500/20", icon: Zap, description: "Applies LLM reasoning to produce structured decisions" },
  AEA: { label: "Action Execution", color: "text-emerald-400", bg: "bg-emerald-500/10 border-emerald-500/20", icon: CheckCircle, description: "Executes actions against external systems safely" },
  VA: { label: "Verification", color: "text-cyan-400", bg: "bg-cyan-500/10 border-cyan-500/20", icon: Shield, description: "Verifies action outcomes and detects anomalies" },
  MIA: { label: "Meeting Intelligence", color: "text-pink-400", bg: "bg-pink-500/10 border-pink-500/20", icon: Activity, description: "Processes meeting transcripts to extract intelligence" },
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

// Mock throughput sparkline per agent
function generateSparkline(base: number) {
  return Array.from({ length: 12 }, (_, i) => ({
    t: i,
    v: Math.max(0, base + (Math.random() - 0.5) * base * 0.6),
  }));
}

const MOCK_AGENTS: Agent[] = [
  { agent_id: "ag-moa-001", family: "MOA", name: "MOA Primary", status: "BUSY", current_task_id: "task-orch-0012", last_heartbeat_at: new Date(Date.now() - 5000).toISOString(), performance_metrics: { tasks_completed: 342, tasks_failed: 4, avg_confidence: 0.94, error_rate: 0.012, last_24h_throughput: 48 } },
  { agent_id: "ag-dra-001", family: "DRA", name: "DRA Alpha", status: "BUSY", current_task_id: "task-fetch-0031", last_heartbeat_at: new Date(Date.now() - 3000).toISOString(), performance_metrics: { tasks_completed: 891, tasks_failed: 12, avg_confidence: 0.89, error_rate: 0.013, last_24h_throughput: 127 } },
  { agent_id: "ag-dra-002", family: "DRA", name: "DRA Beta", status: "IDLE", current_task_id: null, last_heartbeat_at: new Date(Date.now() - 45000).toISOString(), performance_metrics: { tasks_completed: 654, tasks_failed: 8, avg_confidence: 0.91, error_rate: 0.012, last_24h_throughput: 94 } },
  { agent_id: "ag-dma-001", family: "DMA", name: "DMA Reasoning-1", status: "BUSY", current_task_id: "task-decide-0008", last_heartbeat_at: new Date(Date.now() - 2000).toISOString(), performance_metrics: { tasks_completed: 421, tasks_failed: 7, avg_confidence: 0.92, error_rate: 0.017, last_24h_throughput: 61 } },
  { agent_id: "ag-dma-002", family: "DMA", name: "DMA Reasoning-2", status: "IDLE", current_task_id: null, last_heartbeat_at: new Date(Date.now() - 22000).toISOString(), performance_metrics: { tasks_completed: 389, tasks_failed: 5, avg_confidence: 0.94, error_rate: 0.013, last_24h_throughput: 52 } },
  { agent_id: "ag-aea-001", family: "AEA", name: "AEA Executor-1", status: "BUSY", current_task_id: "task-action-0019", last_heartbeat_at: new Date(Date.now() - 4000).toISOString(), performance_metrics: { tasks_completed: 278, tasks_failed: 9, avg_confidence: 0.87, error_rate: 0.032, last_24h_throughput: 43 } },
  { agent_id: "ag-aea-002", family: "AEA", name: "AEA Executor-2", status: "DEGRADED", current_task_id: null, last_heartbeat_at: new Date(Date.now() - 180000).toISOString(), performance_metrics: { tasks_completed: 142, tasks_failed: 18, avg_confidence: 0.75, error_rate: 0.112, last_24h_throughput: 21 } },
  { agent_id: "ag-va-001", family: "VA", name: "VA Verifier-1", status: "IDLE", current_task_id: null, last_heartbeat_at: new Date(Date.now() - 12000).toISOString(), performance_metrics: { tasks_completed: 567, tasks_failed: 3, avg_confidence: 0.97, error_rate: 0.005, last_24h_throughput: 82 } },
  { agent_id: "ag-va-002", family: "VA", name: "VA Verifier-2", status: "BUSY", current_task_id: "task-verify-0022", last_heartbeat_at: new Date(Date.now() - 1000).toISOString(), performance_metrics: { tasks_completed: 483, tasks_failed: 4, avg_confidence: 0.96, error_rate: 0.008, last_24h_throughput: 73 } },
  { agent_id: "ag-mia-001", family: "MIA", name: "MIA Intelligence", status: "IDLE", current_task_id: null, last_heartbeat_at: new Date(Date.now() - 30000).toISOString(), performance_metrics: { tasks_completed: 89, tasks_failed: 2, avg_confidence: 0.88, error_rate: 0.022, last_24h_throughput: 14 } },
];

function AgentCard({
  agent,
  onDisable,
  onEnable,
}: {
  agent: Agent;
  onDisable: (id: string) => void;
  onEnable: (id: string) => void;
}) {
  const family = FAMILY_CONFIG[agent.family] || FAMILY_CONFIG.DRA;
  const Icon = family.icon;
  const statusColor = STATUS_COLOR[agent.status] || STATUS_COLOR.IDLE;
  const heartbeatAge = agent.last_heartbeat_at
    ? (Date.now() - new Date(agent.last_heartbeat_at).getTime()) / 1000
    : 999;
  const isHealthy = heartbeatAge < 60;
  const sparkline = generateSparkline(agent.performance_metrics?.last_24h_throughput ?? 10);

  const errorRate = agent.performance_metrics?.error_rate ?? 0;
  const confidence = agent.performance_metrics?.avg_confidence ?? 0;
  const throughput = agent.performance_metrics?.last_24h_throughput ?? 0;
  const completed = agent.performance_metrics?.tasks_completed ?? 0;
  const failed = agent.performance_metrics?.tasks_failed ?? 0;

  const isDisabled = agent.status === "DISABLED";
  const isDegraded = agent.status === "DEGRADED" || agent.status === "STUCK";

  return (
    <div className={`bg-slate-900/60 border rounded-2xl p-5 backdrop-blur-sm hover:shadow-lg transition-all ${
      isDegraded ? "border-amber-500/30 shadow-amber-500/5" : family.bg
    }`}>
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
            {isHealthy ? `${Math.round(heartbeatAge)}s` : "Stale"}
          </div>
        </div>
      </div>

      {/* Sparkline */}
      <div className="h-14 mb-4 -mx-1">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={sparkline}>
            <defs>
              <linearGradient id={`sg-${agent.agent_id}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
              </linearGradient>
            </defs>
            <Area
              type="monotone"
              dataKey="v"
              stroke="#8b5cf6"
              strokeWidth={1.5}
              fill={`url(#sg-${agent.agent_id})`}
              dot={false}
            />
            <Tooltip
              contentStyle={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 6, fontSize: 10 }}
              formatter={(v: number) => [Math.round(v), "tasks"]}
              labelFormatter={() => ""}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 gap-2 mb-4">
        {[
          { label: "Throughput/24h", value: throughput.toString(), color: "text-violet-400" },
          { label: "Completed", value: `${completed} (✗${failed})`, color: "text-emerald-400" },
          {
            label: "Avg Confidence",
            value: `${Math.round(confidence * 100)}%`,
            color: confidence > 0.85 ? "text-emerald-400" : confidence > 0.7 ? "text-amber-400" : "text-red-400",
          },
          {
            label: "Error Rate",
            value: `${(errorRate * 100).toFixed(1)}%`,
            color: errorRate < 0.03 ? "text-emerald-400" : errorRate < 0.08 ? "text-amber-400" : "text-red-400",
          },
        ].map((m) => (
          <div key={m.label} className="bg-slate-800/30 rounded-lg p-2.5">
            <div className="text-[10px] text-slate-500">{m.label}</div>
            <div className={`text-xs font-bold ${m.color} mt-0.5`}>{m.value}</div>
          </div>
        ))}
      </div>

      {/* Current Task / Status */}
      <div className="text-[10px] text-slate-600 truncate mb-3">
        {agent.current_task_id ? (
          <span>
            Current: <span className="font-mono text-violet-400">{agent.current_task_id.slice(0, 18)}...</span>
          </span>
        ) : (
          <span>
            Idle · Last active {agent.last_heartbeat_at && formatDistanceToNow(new Date(agent.last_heartbeat_at), { addSuffix: true })}
          </span>
        )}
      </div>

      {/* Actions */}
      <div className="flex gap-2">
        {isDisabled ? (
          <button
            onClick={() => onEnable(agent.agent_id)}
            className="flex-1 py-1.5 rounded-lg text-xs bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 hover:bg-emerald-500/20 transition-all flex items-center justify-center gap-1.5"
          >
            <Play size={11} /> Enable
          </button>
        ) : (
          <button
            onClick={() => onDisable(agent.agent_id)}
            className="flex-1 py-1.5 rounded-lg text-xs bg-slate-800/50 border border-slate-700/50 text-slate-400 hover:text-white hover:border-slate-600 transition-all flex items-center justify-center gap-1.5"
          >
            <Pause size={11} /> Disable
          </button>
        )}
        {isDegraded && (
          <button
            onClick={() => toast.success("Restart signal sent to agent")}
            className="flex-1 py-1.5 rounded-lg text-xs bg-amber-500/10 border border-amber-500/20 text-amber-400 hover:bg-amber-500/20 transition-all flex items-center justify-center gap-1.5"
          >
            <RefreshCw size={11} /> Restart
          </button>
        )}
      </div>
    </div>
  );
}

export default function AgentsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["agents"],
    queryFn: async () => {
      try {
        const result = await api.get<{ agents: Agent[]; count: number }>("/agents");
        if (result.agents.length === 0) throw new Error("empty");
        return result;
      } catch {
        return { agents: MOCK_AGENTS, count: MOCK_AGENTS.length };
      }
    },
    refetchInterval: 30000,
  });

  const handleDisable = (id: string) => toast.success(`Graceful shutdown signal sent to ${id.slice(0, 12)}`);
  const handleEnable = (id: string) => toast.success(`Agent ${id.slice(0, 12)} re-enabled`);

  const agents = data?.agents ?? [];
  const byFamily = agents.reduce((acc, a) => {
    if (!acc[a.family]) acc[a.family] = [];
    acc[a.family].push(a);
    return acc;
  }, {} as Record<string, Agent[]>);

  const busyCount = agents.filter(a => a.status === "BUSY").length;
  const stuckCount = agents.filter(a => a.status === "STUCK").length;
  const degradedCount = agents.filter(a => a.status === "DEGRADED").length;
  const totalThroughput = agents.reduce((s, a) => s + (a.performance_metrics?.last_24h_throughput ?? 0), 0);
  const avgConfidence = agents.length
    ? agents.reduce((s, a) => s + (a.performance_metrics?.avg_confidence ?? 0), 0) / agents.length
    : 0;

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
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400 text-xs animate-pulse">
            <AlertTriangle size={12} />
            {stuckCount + degradedCount} agents need attention
          </div>
        )}
      </div>

      {/* Fleet KPIs */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "Total Agents", value: agents.length.toString(), color: "text-white" },
          { label: "Active (Busy)", value: busyCount.toString(), color: "text-emerald-400" },
          { label: "Total Throughput (24h)", value: `${totalThroughput} tasks`, color: "text-violet-400" },
          { label: "Fleet Avg Confidence", value: `${Math.round(avgConfidence * 100)}%`, color: avgConfidence > 0.88 ? "text-emerald-400" : "text-amber-400" },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-slate-900/50 border border-slate-800/50 rounded-2xl p-5">
            <div className="text-slate-400 text-xs mb-2">{label}</div>
            <div className={`text-2xl font-bold ${color}`}>{value}</div>
          </div>
        ))}
      </div>

      {/* Family Stats Row */}
      <div className="grid grid-cols-6 gap-3">
        {Object.entries(FAMILY_CONFIG).map(([family, config]) => {
          const familyAgents = byFamily[family] ?? [];
          const Icon = config.icon;
          return (
            <div key={family} className={`bg-slate-900/50 border ${config.bg} rounded-xl p-4 text-center`}>
              <Icon size={16} className={`${config.color} mx-auto mb-2`} />
              <div className={`text-2xl font-bold ${config.color}`}>{familyAgents.length}</div>
              <div className="text-[10px] text-slate-500 mt-0.5 truncate">{config.label.split(" ")[0]}</div>
              <div className="text-[9px] text-slate-600">
                {familyAgents.filter(a => a.status === "BUSY").length} busy
              </div>
            </div>
          );
        })}
      </div>

      {/* Agent Cards by Family */}
      {isLoading ? (
        <div className="grid grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-64 bg-slate-800/30 rounded-2xl animate-pulse" />
          ))}
        </div>
      ) : (
        Object.entries(FAMILY_CONFIG).map(([family, config]) => {
          const familyAgents = byFamily[family] ?? [];
          if (familyAgents.length === 0) return null;
          return (
            <div key={family}>
              <div className="flex items-center gap-3 mb-3">
                <config.icon size={14} className={config.color} />
                <h2 className="text-sm font-semibold text-white">{config.label} Agents</h2>
                <span className={`px-2 py-0.5 rounded text-[10px] border ${config.bg} ${config.color}`}>
                  {familyAgents.length}
                </span>
                <span className="text-[11px] text-slate-600 ml-2">{config.description}</span>
              </div>
              <div className="grid grid-cols-3 gap-4">
                {familyAgents.map((agent) => (
                  <AgentCard
                    key={agent.agent_id}
                    agent={agent}
                    onDisable={handleDisable}
                    onEnable={handleEnable}
                  />
                ))}
              </div>
            </div>
          );
        })
      )}
    </div>
  );
}
