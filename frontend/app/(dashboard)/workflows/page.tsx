"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api-client";
import { Plus, Search, Filter, GitBranch, Clock } from "lucide-react";
import { useState } from "react";
import { formatDistanceToNow } from "date-fns";

interface WorkflowRun {
  workflow_id: string;
  name: string;
  template_id: string;
  status: string;
  health_score: number;
  sla_status: string;
  breach_probability: number;
  started_at: string;
  completed_at: string | null;
}

const STATUS_COLORS: Record<string, string> = {
  RUNNING: "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20",
  COMPLETED: "bg-blue-500/10 text-blue-400 border border-blue-500/20",
  PAUSED: "bg-amber-500/10 text-amber-400 border border-amber-500/20",
  FAILED: "bg-red-500/10 text-red-400 border border-red-500/20",
  CANCELLED: "bg-slate-500/10 text-slate-400 border border-slate-500/20",
  INITIALIZING: "bg-violet-500/10 text-violet-400 border border-violet-500/20",
};

export default function WorkflowsPage() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["workflows", statusFilter],
    queryFn: () =>
      api.get<{ workflows: WorkflowRun[]; count: number }>(
        `/workflows?limit=50${statusFilter ? `&status=${statusFilter}` : ""}`
      ),
    refetchInterval: 30000,
  });

  const filtered = (data?.workflows ?? []).filter(
    (w) =>
      !search ||
      (w.name || w.workflow_id).toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Workflows</h1>
          <p className="text-slate-400 text-sm mt-1">
            {data?.count ?? 0} total runs across all templates
          </p>
        </div>
        <Link
          href="/workflows/new"
          className="flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 rounded-xl text-white text-sm font-medium transition-all shadow-lg shadow-violet-500/25"
        >
          <Plus size={15} />
          Launch Workflow
        </Link>
      </div>

      {/* Filters */}
      <div className="flex gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            placeholder="Search workflows..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2.5 bg-slate-800/50 border border-slate-700/50 rounded-xl text-sm text-white placeholder-slate-500 focus:outline-none focus:border-violet-500/50 transition-all"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-4 py-2.5 bg-slate-800/50 border border-slate-700/50 rounded-xl text-sm text-white focus:outline-none focus:border-violet-500/50 transition-all"
        >
          <option value="">All Status</option>
          {["RUNNING", "COMPLETED", "PAUSED", "FAILED", "CANCELLED"].map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>

      {/* Workflow Table */}
      <div className="bg-slate-900/50 border border-slate-800/50 rounded-2xl overflow-hidden backdrop-blur-sm">
        {/* Table Header */}
        <div className="grid grid-cols-12 px-6 py-3 border-b border-slate-800/50 text-xs text-slate-500 font-medium">
          <div className="col-span-4">Workflow</div>
          <div className="col-span-2">Template</div>
          <div className="col-span-2">Status</div>
          <div className="col-span-1 text-center">Health</div>
          <div className="col-span-2">Started</div>
          <div className="col-span-1" />
        </div>

        {isLoading ? (
          <div className="py-12 text-center text-slate-600">Loading...</div>
        ) : filtered.length === 0 ? (
          <div className="py-12 text-center">
            <GitBranch size={32} className="text-slate-700 mx-auto mb-3" />
            <div className="text-slate-500 text-sm">No workflows found</div>
            <Link href="/workflows/new" className="mt-3 inline-block text-violet-400 text-xs hover:underline">
              Launch your first workflow →
            </Link>
          </div>
        ) : (
          <div className="divide-y divide-slate-800/50">
            {filtered.map((workflow) => {
              const healthColor =
                workflow.health_score >= 80
                  ? "text-emerald-400"
                  : workflow.health_score >= 60
                  ? "text-amber-400"
                  : "text-red-400";

              return (
                <Link
                  key={workflow.workflow_id}
                  href={`/workflows/${workflow.workflow_id}`}
                  className="grid grid-cols-12 px-6 py-4 hover:bg-slate-800/30 transition-all group items-center"
                >
                  <div className="col-span-4">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-violet-500/10 border border-violet-500/20 flex items-center justify-center flex-shrink-0">
                        <GitBranch size={13} className="text-violet-400" />
                      </div>
                      <div>
                        <div className="text-sm text-white font-medium truncate group-hover:text-violet-300 transition-colors">
                          {workflow.name || workflow.workflow_id.slice(0, 20) + "..."}
                        </div>
                        <div className="text-[10px] text-slate-600 font-mono">
                          {workflow.workflow_id.slice(0, 12)}...
                        </div>
                      </div>
                    </div>
                  </div>
                  <div className="col-span-2 text-xs text-slate-400 truncate">
                    {workflow.template_id?.slice(0, 16) || "—"}
                  </div>
                  <div className="col-span-2">
                    <span className={`px-2 py-1 rounded-lg text-[10px] font-medium ${STATUS_COLORS[workflow.status] || STATUS_COLORS.RUNNING}`}>
                      {workflow.status}
                    </span>
                  </div>
                  <div className={`col-span-1 text-center text-sm font-bold font-mono ${healthColor}`}>
                    {Math.round(workflow.health_score)}
                  </div>
                  <div className="col-span-2 text-xs text-slate-500 flex items-center gap-1.5">
                    <Clock size={10} />
                    {workflow.started_at
                      ? formatDistanceToNow(new Date(workflow.started_at), { addSuffix: true })
                      : "—"}
                  </div>
                  <div className="col-span-1 text-right">
                    <span className="text-slate-600 group-hover:text-violet-400 transition-colors text-xs">→</span>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
