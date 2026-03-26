"use client";

import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { AlertTriangle, Clock, Activity } from "lucide-react";
import Link from "next/link";

interface Workflow {
  workflow_id: string;
  name: string;
  status: string;
  health_score: number;
  sla_status: string;
  breach_probability: number;
  started_at: string;
}

interface SLAHealthDashboardProps {
  workflows: Workflow[];
  adherenceSeries: Array<{ timestamp: string; adherence_pct: number }>;
}

function HealthGauge({ score }: { score: number }) {
  const color = score >= 80 ? "#10b981" : score >= 60 ? "#f59e0b" : score >= 40 ? "#f97316" : "#ef4444";
  const circumference = 2 * Math.PI * 45;
  const strokeDashoffset = circumference - (score / 100) * circumference;

  return (
    <div className="relative w-32 h-32 flex items-center justify-center">
      <svg width="128" height="128" className="-rotate-90">
        <circle cx="64" cy="64" r="45" fill="none" stroke="#1e293b" strokeWidth="10" />
        <circle
          cx="64"
          cy="64"
          r="45"
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          strokeLinecap="round"
          style={{ transition: "stroke-dashoffset 1s ease" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-bold text-white">{Math.round(score)}</span>
        <span className="text-[10px] text-slate-500">Health</span>
      </div>
    </div>
  );
}

function BreachCountdown({ probability, workflowName }: { probability: number; workflowName: string }) {
  const pct = Math.round(probability * 100);
  const color = pct > 70 ? "text-red-400" : pct > 40 ? "text-amber-400" : "text-emerald-400";
  const bg = pct > 70 ? "bg-red-500/10 border-red-500/20" : pct > 40 ? "bg-amber-500/10 border-amber-500/20" : "bg-emerald-500/10 border-emerald-500/20";

  return (
    <div className={`p-3 rounded-xl border ${bg} flex items-center justify-between gap-3`}>
      <div className="flex-1 min-w-0">
        <div className="text-xs text-white truncate">{workflowName}</div>
        <div className="text-[10px] text-slate-500 mt-0.5">SLA Breach Risk</div>
      </div>
      <div className={`text-lg font-bold ${color} flex-shrink-0`}>{pct}%</div>
    </div>
  );
}

export default function SLAHealthDashboard({ workflows, adherenceSeries }: SLAHealthDashboardProps) {
  const atRisk = workflows.filter((w) => w.breach_probability > 0.4);
  const avgHealth = workflows.length
    ? workflows.reduce((sum, w) => sum + w.health_score, 0) / workflows.length
    : 100;

  const avgAdherence =
    adherenceSeries.length > 0
      ? adherenceSeries.reduce((sum, d) => sum + d.adherence_pct, 0) / adherenceSeries.length
      : 100;

  return (
    <div className="bg-slate-900/50 border border-slate-800/50 rounded-2xl p-6 backdrop-blur-sm">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-white font-semibold">SLA Health Dashboard</h2>
          <p className="text-slate-500 text-xs mt-0.5">Real-time SLA monitoring & breach prediction</p>
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <Activity size={12} className="text-emerald-400" />
          Live
        </div>
      </div>

      <div className="grid grid-cols-4 gap-6">
        {/* Overall Health Score */}
        <div className="flex flex-col items-center gap-2">
          <HealthGauge score={avgHealth} />
          <div className="text-center">
            <div className="text-xs text-white font-medium">Overall Health</div>
            <div className="text-[10px] text-slate-500">Avg across {workflows.length} workflows</div>
          </div>
        </div>

        {/* 24h Adherence Chart */}
        <div className="col-span-2">
          <div className="text-xs text-slate-400 mb-3 flex items-center gap-2">
            <Clock size={11} />
            24h SLA Adherence
          </div>
          <div className="h-24">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={adherenceSeries.slice(-24)}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="timestamp" tick={false} axisLine={false} tickLine={false} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 9, fill: "#64748b" }} axisLine={false} tickLine={false} width={24} />
                <Tooltip
                  contentStyle={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 8, fontSize: 11 }}
                  formatter={(v: number) => [`${v}%`, "Adherence"]}
                />
                <Line
                  type="monotone"
                  dataKey="adherence_pct"
                  stroke="#8b5cf6"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 3 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-2 text-[10px] text-slate-500 text-center">
            Avg: <span className="text-violet-400">{avgAdherence.toFixed(1)}%</span>
          </div>
        </div>

        {/* At-Risk Workflows */}
        <div>
          <div className="text-xs text-slate-400 mb-3 flex items-center gap-2">
            <AlertTriangle size={11} />
            At-Risk Workflows
          </div>
          <div className="space-y-2">
            {atRisk.length === 0 ? (
              <div className="text-[11px] text-emerald-400 text-center py-4">
                ✓ All workflows on track
              </div>
            ) : (
              atRisk.slice(0, 3).map((w) => (
                <Link key={w.workflow_id} href={`/workflows/${w.workflow_id}`}>
                  <BreachCountdown
                    probability={w.breach_probability}
                    workflowName={w.name || w.workflow_id.slice(0, 12)}
                  />
                </Link>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
