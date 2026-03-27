"use client";

export const dynamic = "force-dynamic";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { useState } from "react";
import {
  LineChart, Line, BarChart, Bar, AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, PieChart, Pie, Cell, RadarChart, Radar,
  PolarGrid, PolarAngleAxis, Legend
} from "recharts";
import {
  TrendingUp, TrendingDown, Activity, Zap, Target, AlertTriangle,
  Download, Clock, Brain, Users, ChevronDown
} from "lucide-react";

const CHART_COLORS = ["#8b5cf6", "#06b6d4", "#10b981", "#f59e0b", "#ef4444", "#f97316"];

// Comprehensive mock data generator
function generateMockData() {
  const now = Date.now();
  const slaSeries = Array.from({ length: 24 }, (_, i) => ({
    timestamp: new Date(now - (23 - i) * 60 * 60 * 1000).toISOString(),
    adherence_pct: 85 + Math.random() * 15,
    label: `${23 - i}h ago`,
  }));

  const throughputSeries = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(now - (6 - i) * 24 * 60 * 60 * 1000);
    return {
      date: d.toLocaleDateString("en-US", { weekday: "short" }),
      "P2P": Math.floor(Math.random() * 8) + 2,
      "Onboarding": Math.floor(Math.random() * 5) + 1,
      "Contract": Math.floor(Math.random() * 4) + 1,
      total: 0,
    };
  }).map(d => ({ ...d, total: (d as any)["P2P"] + (d as any)["Onboarding"] + (d as any)["Contract"] }));

  const agentData = [
    { family: "MOA", throughput: 42, errors: 1, confidence: 94, utilization: 67 },
    { family: "DRA", throughput: 128, errors: 3, confidence: 89, utilization: 78 },
    { family: "DMA", throughput: 89, errors: 2, confidence: 91, utilization: 65 },
    { family: "AEA", throughput: 67, errors: 4, confidence: 87, utilization: 72 },
    { family: "VA", throughput: 95, errors: 1, confidence: 96, utilization: 58 },
    { family: "MIA", throughput: 23, errors: 0, confidence: 88, utilization: 42 },
  ];

  const errorBreakdown = [
    { error_type: "Timeout", count: 3 },
    { error_type: "Auth Failed", count: 1 },
    { error_type: "Validation Error", count: 7 },
    { error_type: "Connector Down", count: 2 },
    { error_type: "Rate Limit", count: 4 },
  ];

  const confidenceHistory = Array.from({ length: 14 }, (_, i) => ({
    day: `Day ${i + 1}`,
    DMA: 82 + Math.random() * 15,
    DRA: 75 + Math.random() * 20,
    VA: 88 + Math.random() * 10,
  }));

  const escalationRate = Array.from({ length: 14 }, (_, i) => ({
    day: new Date(now - (13 - i) * 24 * 60 * 60 * 1000).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
    rate: Math.random() * 8 + 1,
    escalations: Math.floor(Math.random() * 4),
  }));

  return { slaSeries, throughputSeries, agentData, errorBreakdown, confidenceHistory, escalationRate };
}

const MOCK = generateMockData();

const TIME_RANGES = [
  { label: "1H", hours: 1 },
  { label: "24H", hours: 24 },
  { label: "7D", hours: 168 },
  { label: "30D", hours: 720 },
];

function MetricCard({
  label, value, change, positive, icon: Icon, subtext
}: {
  label: string;
  value: string;
  change?: string;
  positive?: boolean;
  icon?: React.FC<any>;
  subtext?: string;
}) {
  return (
    <div className="bg-slate-900/60 border border-slate-800/50 rounded-2xl p-5 backdrop-blur-sm hover:border-slate-700/50 transition-all">
      <div className="flex items-center justify-between mb-3">
        <div className="text-slate-400 text-xs font-medium">{label}</div>
        {Icon && (
          <div className="w-7 h-7 rounded-lg bg-slate-800 flex items-center justify-center">
            <Icon size={14} className="text-slate-500" />
          </div>
        )}
      </div>
      <div className="text-2xl font-bold text-white mb-1">{value}</div>
      {subtext && <div className="text-[10px] text-slate-600">{subtext}</div>}
      {change && (
        <div className={`flex items-center gap-1 text-xs mt-1 ${positive ? "text-emerald-400" : "text-red-400"}`}>
          {positive ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
          {change}
        </div>
      )}
    </div>
  );
}

const tooltipStyle = {
  contentStyle: { background: "#0f172a", border: "1px solid #1e293b", borderRadius: 8, fontSize: 11 },
  itemStyle: { color: "#94a3b8" },
};

function ChartPanel({ title, children, onExport }: { title: string; children: React.ReactNode; onExport?: () => void }) {
  return (
    <div className="bg-slate-900/60 border border-slate-800/50 rounded-2xl p-5 backdrop-blur-sm">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-white">{title}</h2>
        {onExport && (
          <button
            onClick={onExport}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-800 text-slate-400 text-xs hover:text-white transition-all"
          >
            <Download size={11} /> CSV
          </button>
        )}
      </div>
      {children}
    </div>
  );
}

export default function AnalyticsPage() {
  const [timeRange, setTimeRange] = useState(24);

  const { data: sla } = useQuery({
    queryKey: ["analytics", "sla", timeRange],
    queryFn: async () => {
      try {
        return await api.get<{ series: Array<{ timestamp: string; adherence_pct: number }> }>(`/analytics/sla?time_range_hours=${timeRange}`);
      } catch { return null; }
    },
    refetchInterval: 60000,
  });

  const { data: throughput } = useQuery({
    queryKey: ["analytics", "throughput"],
    queryFn: async () => {
      try {
        return await api.get<{ series: any[] }>("/analytics/throughput");
      } catch { return null; }
    },
    refetchInterval: 60000,
  });

  const { data: errors } = useQuery({
    queryKey: ["analytics", "errors"],
    queryFn: async () => {
      try {
        return await api.get<{ breakdown: any[] }>("/analytics/errors");
      } catch { return null; }
    },
    refetchInterval: 60000,
  });

  const slaSeries = (sla?.series ?? MOCK.slaSeries).map((d: any, i: number) => ({
    ...d,
    label: MOCK.slaSeries[i]?.label ?? d.timestamp,
  }));

  const avgAdherence = slaSeries.length
    ? Math.round(slaSeries.reduce((s: number, d: any) => s + d.adherence_pct, 0) / slaSeries.length)
    : 100;

  const errorBreakdown = errors?.breakdown?.map((b: any) => ({
    error_type: String(b[0] ?? b.error_type ?? "Unknown").slice(0, 20),
    count: b[1] ?? b.count ?? 0,
  })) ?? MOCK.errorBreakdown;

  const totalErrors = errorBreakdown.reduce((s, e) => s + e.count, 0);
  const throughputSeries = throughput?.series ?? MOCK.throughputSeries;

  const exportCSV = (filename: string, data: any[]) => {
    const keys = Object.keys(data[0] || {});
    const csv = [keys.join(","), ...data.map(row => keys.map(k => row[k]).join(","))].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = filename; a.click();
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Analytics</h1>
          <p className="text-slate-400 text-sm mt-1">Platform-wide performance metrics and insights</p>
        </div>
        {/* Time Range Selector */}
        <div className="flex gap-1 bg-slate-900/50 border border-slate-800/50 rounded-xl p-1">
          {TIME_RANGES.map((tr) => (
            <button
              key={tr.label}
              onClick={() => setTimeRange(tr.hours)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                timeRange === tr.hours ? "bg-violet-600 text-white" : "text-slate-400 hover:text-white"
              }`}
            >
              {tr.label}
            </button>
          ))}
        </div>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-4 gap-4">
        <MetricCard label="SLA Adherence" value={`${avgAdherence}%`} change="+2.1% vs last week" positive icon={Target} subtext="Across all active workflows" />
        <MetricCard label="Agent Utilization" value="68%" change="High demand — consider scaling" positive={false} icon={Activity} subtext="Fleet-wide average" />
        <MetricCard label="Avg Decision Confidence" value="91.4%" change="+0.8% vs yesterday" positive icon={Brain} subtext="DMA agent family avg" />
        <MetricCard label="Total Errors (24h)" value={totalErrors.toString()} change="↓ 23% vs yesterday" positive icon={AlertTriangle} subtext={`${errorBreakdown.length} distinct types`} />
      </div>

      {/* Row 1: SLA + Throughput */}
      <div className="grid grid-cols-2 gap-6">
        <ChartPanel title={`SLA Adherence (${TIME_RANGES.find(t => t.hours === timeRange)?.label ?? "24H"})`} onExport={() => exportCSV("sla_adherence.csv", slaSeries)}>
          <div className="h-52">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={slaSeries}>
                <defs>
                  <linearGradient id="slaGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="label" tick={false} axisLine={false} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: "#64748b" }} tickLine={false} axisLine={false} width={28} />
                <Tooltip {...tooltipStyle} formatter={(v: number) => [`${v.toFixed(1)}%`, "Adherence"]} />
                <Area type="monotone" dataKey="adherence_pct" stroke="#8b5cf6" strokeWidth={2.5} fill="url(#slaGrad)" dot={false} activeDot={{ r: 4, fill: "#8b5cf6" }} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </ChartPanel>

        <ChartPanel title="Workflow Throughput (7d)" onExport={() => exportCSV("throughput.csv", MOCK.throughputSeries)}>
          <div className="h-52">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={MOCK.throughputSeries}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#64748b" }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 10, fill: "#64748b" }} tickLine={false} axisLine={false} width={28} />
                <Tooltip {...tooltipStyle} />
                <Legend wrapperStyle={{ fontSize: 11, color: "#94a3b8" }} />
                <Bar dataKey="P2P" fill="#8b5cf6" radius={[4, 4, 0, 0]} name="Procurement-to-Pay" stackId="a" />
                <Bar dataKey="Onboarding" fill="#06b6d4" radius={[0, 0, 0, 0]} name="Onboarding" stackId="a" />
                <Bar dataKey="Contract" fill="#10b981" radius={[4, 4, 0, 0]} name="Contract" stackId="a" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </ChartPanel>
      </div>

      {/* Row 2: Agent Throughput + Error Breakdown */}
      <div className="grid grid-cols-2 gap-6">
        <ChartPanel title="Agent Throughput by Family (24h)" onExport={() => exportCSV("agent_throughput.csv", MOCK.agentData)}>
          <div className="h-52">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={MOCK.agentData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 10, fill: "#64748b" }} tickLine={false} axisLine={false} />
                <YAxis type="category" dataKey="family" tick={{ fontSize: 11, fill: "#94a3b8" }} tickLine={false} axisLine={false} width={36} />
                <Tooltip {...tooltipStyle} />
                <Bar dataKey="throughput" fill="#8b5cf6" radius={[0, 4, 4, 0]} name="Tasks/24h" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </ChartPanel>

        <ChartPanel title="Error Breakdown" onExport={() => exportCSV("errors.csv", errorBreakdown)}>
          <div className="flex gap-4">
            <div className="h-52 flex-1">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={errorBreakdown}
                    dataKey="count"
                    nameKey="error_type"
                    cx="50%"
                    cy="50%"
                    outerRadius={76}
                    innerRadius={52}
                    strokeWidth={0}
                  >
                    {errorBreakdown.map((_, i) => (
                      <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip {...tooltipStyle} formatter={(v: number) => [v, "occurrences"]} />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="flex flex-col justify-center gap-2 min-w-[140px]">
              {errorBreakdown.map((e, i) => (
                <div key={e.error_type} className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: CHART_COLORS[i % CHART_COLORS.length] }} />
                  <span className="text-[11px] text-slate-400 flex-1 truncate">{e.error_type}</span>
                  <span className="text-[11px] text-white font-medium">{e.count}</span>
                </div>
              ))}
              <div className="border-t border-slate-800/50 mt-1 pt-1 flex items-center gap-2">
                <AlertTriangle size={10} className="text-slate-500" />
                <span className="text-[10px] text-slate-500">Total: {totalErrors}</span>
              </div>
            </div>
          </div>
        </ChartPanel>
      </div>

      {/* Row 3: Decision Confidence + Human Escalation Rate */}
      <div className="grid grid-cols-2 gap-6">
        <ChartPanel title="Decision Confidence Over Time" onExport={() => exportCSV("confidence.csv", MOCK.confidenceHistory)}>
          <div className="h-52">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={MOCK.confidenceHistory}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="day" tick={false} axisLine={false} />
                <YAxis domain={[60, 100]} tick={{ fontSize: 10, fill: "#64748b" }} tickLine={false} axisLine={false} width={28} tickFormatter={(v) => `${v}%`} />
                <Tooltip {...tooltipStyle} formatter={(v: number) => [`${v.toFixed(1)}%`, ""]} />
                <Legend wrapperStyle={{ fontSize: 11, color: "#94a3b8" }} />
                <Line type="monotone" dataKey="DMA" stroke="#8b5cf6" strokeWidth={2} dot={false} activeDot={{ r: 3 }} />
                <Line type="monotone" dataKey="DRA" stroke="#06b6d4" strokeWidth={2} dot={false} activeDot={{ r: 3 }} />
                <Line type="monotone" dataKey="VA" stroke="#10b981" strokeWidth={2} dot={false} activeDot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </ChartPanel>

        <ChartPanel title="Human Escalation Rate (14d)" onExport={() => exportCSV("escalations.csv", MOCK.escalationRate)}>
          <div className="h-52">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={MOCK.escalationRate}>
                <defs>
                  <linearGradient id="escGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="day" tick={{ fontSize: 9, fill: "#64748b" }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 10, fill: "#64748b" }} tickLine={false} axisLine={false} width={28} tickFormatter={(v) => `${v}%`} />
                <Tooltip {...tooltipStyle} formatter={(v: number) => [`${v.toFixed(1)}%`, "Escalation Rate"]} />
                <Area type="monotone" dataKey="rate" stroke="#ef4444" strokeWidth={2.5} fill="url(#escGrad)" dot={false} activeDot={{ r: 4, fill: "#ef4444" }} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </ChartPanel>
      </div>

      {/* Row 4: Agent Radar Chart */}
      <ChartPanel title="Agent Family Performance Radar">
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart data={MOCK.agentData}>
              <PolarGrid stroke="#1e293b" />
              <PolarAngleAxis dataKey="family" tick={{ fontSize: 11, fill: "#94a3b8" }} />
              <Radar name="Throughput" dataKey="throughput" stroke="#8b5cf6" fill="#8b5cf6" fillOpacity={0.15} />
              <Radar name="Confidence %" dataKey="confidence" stroke="#10b981" fill="#10b981" fillOpacity={0.15} />
              <Radar name="Utilization %" dataKey="utilization" stroke="#06b6d4" fill="#06b6d4" fillOpacity={0.15} />
              <Legend wrapperStyle={{ fontSize: 11, color: "#94a3b8" }} />
              <Tooltip {...tooltipStyle} />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </ChartPanel>
    </div>
  );
}
