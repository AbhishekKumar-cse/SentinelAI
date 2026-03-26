"use client";

export const dynamic = "force-dynamic";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { useState } from "react";
import { CheckSquare, Clock, AlertTriangle, User, ChevronDown, ChevronUp } from "lucide-react";
import { formatDistanceToNow, isPast } from "date-fns";
import { toast } from "sonner";

interface HumanTask {
  human_task_id: string;
  workflow_id: string;
  title: string;
  description: string;
  status: string;
  priority: string;
  due_at: string | null;
  assignee_id: string;
  context_snapshot: Record<string, unknown>;
}

const PRIORITY_CONFIG: Record<string, { label: string; color: string; dot: string }> = {
  CRITICAL: { label: "Critical", color: "text-red-400 bg-red-500/10 border-red-500/20", dot: "bg-red-400" },
  HIGH: { label: "High", color: "text-amber-400 bg-amber-500/10 border-amber-500/20", dot: "bg-amber-400" },
  MEDIUM: { label: "Medium", color: "text-blue-400 bg-blue-500/10 border-blue-500/20", dot: "bg-blue-400" },
  LOW: { label: "Low", color: "text-slate-400 bg-slate-500/10 border-slate-500/20", dot: "bg-slate-400" },
};

function TaskCard({ task, onComplete }: { task: HumanTask; onComplete: (id: string, outcome: string) => void }) {
  const [expanded, setExpanded] = useState(false);
  const [outcome, setOutcome] = useState("COMPLETED");
  const [notes, setNotes] = useState("");

  const priority = PRIORITY_CONFIG[task.priority] || PRIORITY_CONFIG.MEDIUM;
  const isOverdue = task.due_at && isPast(new Date(task.due_at));
  const isDone = task.status === "COMPLETED";

  return (
    <div className={`bg-slate-900/50 border rounded-2xl overflow-hidden transition-all ${
      isDone ? "border-slate-800/30 opacity-60" :
      isOverdue ? "border-red-500/30" :
      "border-slate-800/50"
    }`}>
      {/* Task Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-start gap-4 p-5 hover:bg-slate-800/20 transition-all text-left"
      >
        <div className={`mt-0.5 w-2 h-2 rounded-full flex-shrink-0 ${priority.dot} ${isOverdue && !isDone ? "animate-pulse" : ""}`} />

        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <div className={`text-sm font-medium truncate ${isDone ? "line-through text-slate-500" : "text-white"}`}>
                {task.title}
              </div>
              <div className="text-xs text-slate-500 mt-0.5 flex items-center gap-2">
                <span className="font-mono">{task.workflow_id.slice(0, 12)}...</span>
                {task.due_at && (
                  <span className={isOverdue && !isDone ? "text-red-400" : ""}>
                    <Clock size={10} className="inline mr-0.5" />
                    {isPast(new Date(task.due_at))
                      ? `Overdue ${formatDistanceToNow(new Date(task.due_at), { addSuffix: true })}`
                      : `Due ${formatDistanceToNow(new Date(task.due_at), { addSuffix: true })}`}
                  </span>
                )}
              </div>
            </div>

            <div className="flex items-center gap-2 flex-shrink-0">
              <span className={`px-2 py-0.5 rounded-md text-[10px] font-medium border ${priority.color}`}>
                {priority.label}
              </span>
              {isDone ? (
                <CheckSquare size={14} className="text-emerald-400" />
              ) : expanded ? (
                <ChevronUp size={14} className="text-slate-500" />
              ) : (
                <ChevronDown size={14} className="text-slate-500" />
              )}
            </div>
          </div>
        </div>
      </button>

      {/* Expanded Details */}
      {expanded && !isDone && (
        <div className="px-5 pb-5 border-t border-slate-800/50">
          <p className="text-sm text-slate-400 mb-4 mt-4">{task.description}</p>

          {/* Context snapshot */}
          {Object.keys(task.context_snapshot).length > 0 && (
            <div className="bg-slate-800/30 rounded-xl p-3 mb-4">
              <div className="text-xs text-slate-500 mb-2">Context</div>
              <pre className="text-[10px] text-slate-400 overflow-auto max-h-24 font-mono">
                {JSON.stringify(task.context_snapshot, null, 2)}
              </pre>
            </div>
          )}

          {/* Decision Form */}
          <div className="space-y-3">
            <div className="flex gap-2">
              {["APPROVED", "REJECTED", "COMPLETED"].map((opt) => (
                <button
                  key={opt}
                  onClick={() => setOutcome(opt)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                    outcome === opt
                      ? opt === "REJECTED"
                        ? "bg-red-500/20 border-red-500/40 text-red-400"
                        : "bg-emerald-500/20 border-emerald-500/40 text-emerald-400"
                      : "bg-slate-800/50 border-slate-700/50 text-slate-400 hover:border-slate-600"
                  }`}
                >
                  {opt}
                </button>
              ))}
            </div>
            <textarea
              placeholder="Completion notes (optional)..."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              className="w-full px-3 py-2 bg-slate-800/50 border border-slate-700/50 rounded-xl text-xs text-white placeholder-slate-600 focus:outline-none focus:border-violet-500/50 transition-all resize-none"
            />
            <button
              onClick={() => onComplete(task.human_task_id, outcome)}
              className="w-full py-2.5 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 rounded-xl text-white text-xs font-medium transition-all"
            >
              Complete Task — {outcome}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function TasksPage() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<"pending" | "completed">("pending");

  const { data, isLoading } = useQuery({
    queryKey: ["tasks", activeTab],
    queryFn: () =>
      api.get<{ tasks: HumanTask[]; count: number }>(
        `/tasks?status=${activeTab === "pending" ? "PENDING" : "COMPLETED"}&limit=50`
      ),
    refetchInterval: 30000,
  });

  const completeMutation = useMutation({
    mutationFn: ({ taskId, outcome }: { taskId: string; outcome: string }) =>
      api.post(`/tasks/${taskId}/complete`, { outcome, completion_notes: "" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      toast.success("Task completed!");
    },
    onError: () => toast.error("Failed to complete task"),
  });

  const tasks = data?.tasks ?? [];
  const criticalCount = tasks.filter((t) => t.priority === "CRITICAL" && t.status === "PENDING").length;
  const overdueCount = tasks.filter((t) => t.due_at && isPast(new Date(t.due_at)) && t.status !== "COMPLETED").length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Task Inbox</h1>
          <p className="text-slate-400 text-sm mt-1">
            {data?.count ?? 0} tasks · {criticalCount} critical · {overdueCount} overdue
          </p>
        </div>
        <div className="flex gap-2">
          {criticalCount > 0 && (
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-xs">
              <AlertTriangle size={12} />
              {criticalCount} critical
            </div>
          )}
        </div>
      </div>

      {/* Tab Switcher */}
      <div className="flex gap-1 bg-slate-900/50 border border-slate-800/50 rounded-xl p-1 w-fit">
        {[{ id: "pending", label: "Pending" }, { id: "completed", label: "Completed" }].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as "pending" | "completed")}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === tab.id
                ? "bg-violet-600 text-white"
                : "text-slate-400 hover:text-white"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Task List */}
      {isLoading ? (
        <div className="space-y-3">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-20 bg-slate-800/30 rounded-2xl animate-pulse" />
          ))}
        </div>
      ) : tasks.length === 0 ? (
        <div className="py-16 text-center">
          <CheckSquare size={40} className="text-slate-700 mx-auto mb-4" />
          <div className="text-slate-500 text-sm">
            {activeTab === "pending" ? "All tasks completed! 🎉" : "No completed tasks yet"}
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          {tasks.map((task) => (
            <TaskCard
              key={task.human_task_id}
              task={task}
              onComplete={(taskId, outcome) =>
                completeMutation.mutate({ taskId, outcome })
              }
            />
          ))}
        </div>
      )}
    </div>
  );
}
