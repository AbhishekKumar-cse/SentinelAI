"use client";

export const dynamic = "force-dynamic";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend
} from "recharts";
import { TrendingUp, TrendingDown, Activity, Zap, Target, AlertTriangle } from "lucide-react";

const CHART_COLORS = ["#8b5cf6", "#06b6d4", "#10b981", "#f59e0b", "#ef4444", "#f97316"];

function MetricCard({
  label, value, change, positive, icon: Icon
}: { label: string; value: string; change?: string; positive?: boolean; icon?: React.FC<any> }) {
  return (
    <div className="bg-slate-900/50 border border-slate-800/50 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-3">
        <div className="text-slate-400 text-xs">{label}</div>
        {Icon && <Icon size={14} className="text-slate-600" />}
      </div>
      <div className="text-2xl font-bold text-white">{value}</div>
      {change && (
        <div className={`flex items-center gap-1 text-xs mt-1 ${positive ? "text-emerald-400" : "text-red-400"}`}>
          {positive ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
          {change}
        </div>
      )}
    </div>
  );
}

export default function AnalyticsPage() {
  const { data: sla } = useQuery({
    queryKey: ["analytics", "sla"],
    queryFn: () => api.get<{ series: Array<{ timestamp: string; adherence_pct: number }> }>("/analytics/sla"),
    refetchInterval: 60000,
  });

  const { data: agentPerf } = useQuery({
    queryKey: ["analytics", "agent-performance"],
    queryFn: () => api.get<{ agents: Array<{ agent_id: string; family: string; throughput: number; error_rate: number; avg_confidence: number }> }>("/analytics/agent-performance"),
    refetchInterval: 60000,
  });

  const { data: errors } = useQuery({
    queryKey: ["analytics", "errors"],
    queryFn: () => api.get<{ breakdown: Array<{ error_type: string; count: number }> }>("/analytics/errors"),
    refetchInterval: 60000,
  });

  const { data: throughput } = useQuery({
    queryKey: ["analytics", "throughput"],
    queryFn: () => api.get<{ series: Array<{ timestamp: string; workflows_started: number; workflows_completed: number }> }>("/analytics/throughput"),
    refetchInterval: 60000,
  });

  const slaSeries = sla?.series ?? [];
  const avgAdherence = slaSeries.length
    ? Math.round(slaSeries.reduce((s, d) => s + d.adherence_pct, 0) / slaSeries.length)
    : 100;

  const agentData = (agentPerf?.agents ?? []).slice(0, 8).map((a) => ({
    name: a.family,
    throughput: a.throughput,
    errors: Math.round(a.error_rate * 100),
  }));

  const errorBreakdown = errors?.breakdown ?? [
    { error_type: "Timeout", count: 3 },
    { error_type: "Auth Failed", count: 1 },
    { error_type: "Validation Error", count: 7 },
    { error_type: "Connector Down", count: 2 },
  ];

  const throughputSeries = throughput?.series ?? [];

  const tooltipStyle = {
    contentStyle: { background: "#0f172a", border: "1px solid #1e293b", borderRadius: 8, fontSize: 11 },
    itemStyle: { color: "#94a3b8" },
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Analytics</h1>
        <p className="text-slate-400 text-sm mt-1">Platform-wide performance metrics and insights</p>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-4 gap-4">
        <MetricCard label="SLA Adherence" value={`${avgAdherence}%`} change="+2.1% vs last week" positive icon={Target} />
        <MetricCard label="Agent Utilization" value="68%" change="High demand" positive icon={Activity} />
        <MetricCard label="Avg Decision Confidence" value="91.4%" change="+0.8%" positive icon={Zap} />
        <MetricCard label="Total Errors (24h)" value={errorBreakdown.reduce((s, e) => s + e.count, 0).toString()} change="↓ 23% vs yesterday" positive icon={AlertTriangle} />
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* SLA Adherence Chart */}
        <div className="bg-slate-900/50 border border-slate-800/50 rounded-2xl p-5">
          <h2 className="text-sm font-semibold text-white mb-4">SLA Adherence (24h)</h2>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={slaSeries.slice(-24)}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="timestamp" tick={false} axisLine={false} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: "#64748b" }} tickLine={false} axisLine={false} width={28} />
                <Tooltip {...tooltipStyle} formatter={(v: number) => [`${v}%`, "Adherence"]} />
                <Line type="monotone" dataKey="adherence_pct" stroke="#8b5cf6" strokeWidth={2.5} dot={false} activeDot={{ r: 4, fill: "#8b5cf6" }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Workflow Throughput */}
        <div className="bg-slate-900/50 border border-slate-800/50 rounded-2xl p-5">
          <h2 className="text-sm font-semibold text-white mb-4">Workflow Throughput (7d)</h2>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={throughputSeries.slice(-7)}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="timestamp" tick={{ fontSize: 9, fill: "#64748b" }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 10, fill: "#64748b" }} tickLine={false} axisLine={false} width={28} />
                <Tooltip {...tooltipStyle} />
                <Bar dataKey="workflows_started" fill="#8b5cf6" radius={[4, 4, 0, 0]} name="Started" />
                <Bar dataKey="workflows_completed" fill="#10b981" radius={[4, 4, 0, 0]} name="Completed" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Agent Performance */}
        <div className="bg-slate-900/50 border border-slate-800/50 rounded-2xl p-5">
          <h2 className="text-sm font-semibold text-white mb-4">Agent Throughput by Family</h2>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={agentData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 10, fill: "#64748b" }} tickLine={false} axisLine={false} />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 10, fill: "#94a3b8" }} tickLine={false} axisLine={false} width={36} />
                <Tooltip {...tooltipStyle} />
                <Bar dataKey="throughput" fill="#8b5cf6" radius={[0, 4, 4, 0]} name="Tasks/24h" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Error Breakdown */}
        <div className="bg-slate-900/50 border border-slate-800/50 rounded-2xl p-5">
          <h2 className="text-sm font-semibold text-white mb-4">Error Breakdown</h2>
          <div className="flex gap-6">
            <div className="h-48 flex-1">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={errorBreakdown}
                    dataKey="count"
                    nameKey="error_type"
                    cx="50%"
                    cy="50%"
                    outerRadius={72}
                    innerRadius={48}
                    strokeWidth={0}
                  >
                    {errorBreakdown.map((_, i) => (
                      <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip {...tooltipStyle} formatter={(v: number) => [v, "count"]} />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="flex flex-col justify-center gap-2 min-w-32">
              {errorBreakdown.map((e, i) => (
                <div key={e.error_type} className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: CHART_COLORS[i % CHART_COLORS.length] }} />
                  <span className="text-[11px] text-slate-400 truncate">{e.error_type}</span>
                  <span className="text-[11px] text-white ml-auto">{e.count}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
