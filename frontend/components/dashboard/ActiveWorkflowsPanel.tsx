"use client";

import Link from "next/link";
import { formatDistanceToNow } from "date-fns";
import { GitBranch, CheckCircle2, XCircle, Clock, Pause, AlertCircle } from "lucide-react";

interface Workflow {
  workflow_id: string;
  name: string;
  status: string;
  health_score: number;
  sla_status: string;
  breach_probability: number;
  started_at: string;
}

const statusConfig: Record<string, { label: string; color: string; icon: React.FC<any> }> = {
  RUNNING: { label: "Running", color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20", icon: Clock },
  COMPLETED: { label: "Completed", color: "text-blue-400 bg-blue-500/10 border-blue-500/20", icon: CheckCircle2 },
  PAUSED: { label: "Paused", color: "text-amber-400 bg-amber-500/10 border-amber-500/20", icon: Pause },
  FAILED: { label: "Failed", color: "text-red-400 bg-red-500/10 border-red-500/20", icon: XCircle },
  CANCELLED: { label: "Cancelled", color: "text-slate-400 bg-slate-500/10 border-slate-500/20", icon: XCircle },
};

export default function ActiveWorkflowsPanel({ workflows }: { workflows: Workflow[] }) {
  return (
    <div className="bg-slate-900/50 border border-slate-800/50 rounded-2xl overflow-hidden backdrop-blur-sm">
      <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800/50">
        <div className="flex items-center gap-2">
          <GitBranch size={15} className="text-violet-400" />
          <h2 className="text-white font-semibold text-sm">Active Workflows</h2>
          <span className="px-2 py-0.5 rounded-full bg-violet-500/10 text-violet-400 text-xs border border-violet-500/20">
            {workflows.length}
          </span>
        </div>
        <Link href="/workflows" className="text-xs text-violet-400 hover:text-violet-300 transition-colors">
          View all →
        </Link>
      </div>

      {workflows.length === 0 ? (
        <div className="py-12 text-center text-slate-600 text-sm">
          No active workflows
        </div>
      ) : (
        <div className="divide-y divide-slate-800/50">
          {workflows.map((workflow) => {
            const config = statusConfig[workflow.status] || statusConfig.RUNNING;
            const Icon = config.icon;
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
                className="flex items-center gap-4 px-6 py-4 hover:bg-slate-800/30 transition-all group"
              >
                {/* Status Icon */}
                <div className="flex-shrink-0">
                  <Icon size={14} className={config.color.split(" ")[0]} />
                </div>

                {/* Name */}
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-white font-medium truncate group-hover:text-violet-300 transition-colors">
                    {workflow.name || workflow.workflow_id.slice(0, 16) + "..."}
                  </div>
                  <div className="text-xs text-slate-500 mt-0.5">
                    {workflow.started_at && formatDistanceToNow(new Date(workflow.started_at), { addSuffix: true })}
                  </div>
                </div>

                {/* Status Badge */}
                <div className={`px-2 py-1 rounded-lg border text-[10px] font-medium flex-shrink-0 ${config.color}`}>
                  {config.label}
                </div>

                {/* Health Score */}
                <div className={`text-sm font-bold font-mono flex-shrink-0 ${healthColor}`}>
                  {Math.round(workflow.health_score)}
                </div>

                {/* Breach Probability */}
                {workflow.breach_probability > 0.3 && (
                  <div className="flex items-center gap-1 text-xs text-red-400 flex-shrink-0">
                    <AlertCircle size={11} />
                    {Math.round(workflow.breach_probability * 100)}%
                  </div>
                )}
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
