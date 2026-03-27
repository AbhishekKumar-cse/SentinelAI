"use client";

export const dynamic = "force-dynamic";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { useState, useRef } from "react";
import {
  CheckSquare, Clock, AlertTriangle, User, ChevronDown, ChevronUp,
  Filter, Inbox, PlayCircle, PauseCircle, CheckCircle2, Plus,
  ArrowRight, Flag, Calendar, Search
} from "lucide-react";
import { formatDistanceToNow, isPast, isToday, isTomorrow } from "date-fns";
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

const PRIORITY_CONFIG: Record<string, { label: string; color: string; dot: string; border: string }> = {
  CRITICAL: { label: "Critical", color: "text-red-400 bg-red-500/10 border-red-500/20", dot: "bg-red-400", border: "border-l-red-500" },
  HIGH: { label: "High", color: "text-amber-400 bg-amber-500/10 border-amber-500/20", dot: "bg-amber-400", border: "border-l-amber-500" },
  MEDIUM: { label: "Medium", color: "text-blue-400 bg-blue-500/10 border-blue-500/20", dot: "bg-blue-400", border: "border-l-blue-500" },
  LOW: { label: "Low", color: "text-slate-400 bg-slate-500/10 border-slate-500/20", dot: "bg-slate-500", border: "border-l-slate-600" },
};

const STATUS_COLUMNS = [
  { id: "PENDING", label: "To Do", icon: Inbox, color: "text-slate-400" },
  { id: "IN_PROGRESS", label: "In Progress", icon: PlayCircle, color: "text-blue-400" },
  { id: "BLOCKED", label: "Blocked", icon: PauseCircle, color: "text-red-400" },
  { id: "COMPLETED", label: "Done", icon: CheckCircle2, color: "text-emerald-400" },
];

// Mock tasks with diverse statuses
const MOCK_TASKS: HumanTask[] = [
  { human_task_id: "t1", workflow_id: "wf-001", title: "Approve Vendor Payment — INR 2.4L to TechCorp", description: "Three-way match completed. Payment requires CFO sign-off before execution.", status: "PENDING", priority: "CRITICAL", due_at: new Date(Date.now() + 2 * 60 * 60 * 1000).toISOString(), assignee_id: "priya.sharma@corp.com", context_snapshot: { vendor: "TechCorp Ltd", amount: "₹2,40,000", po_number: "PO-2024-0891" } },
  { human_task_id: "t2", workflow_id: "wf-002", title: "Review Employee Onboarding Package — Arjun Kumar", description: "Equipment and system access configured. Review and approve 90-day milestone plan.", status: "IN_PROGRESS", priority: "HIGH", due_at: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(), assignee_id: "hr.lead@corp.com", context_snapshot: { employee: "Arjun Kumar", department: "Engineering", start_date: "2024-02-01" } },
  { human_task_id: "t3", workflow_id: "wf-003", title: "Legal Review — Vendor NDA with Softworks", description: "AI analysis complete. Low-risk but 2 clauses flagged for human review.", status: "PENDING", priority: "MEDIUM", due_at: new Date(Date.now() + 3 * 24 * 60 * 60 * 1000).toISOString(), assignee_id: "legal@corp.com", context_snapshot: { contract_type: "NDA", vendor: "Softworks India" } },
  { human_task_id: "t4", workflow_id: "wf-004", title: "Resolve Escalation — Unmatched Invoice from Vendors", description: "Invoice amount (₹1.8L) does not match PO (₹1.6L). Investigate discrepancy.", status: "BLOCKED", priority: "HIGH", due_at: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(), assignee_id: "finance@corp.com", context_snapshot: { discrepancy: "₹20,000", po_number: "PO-2024-0876" } },
  { human_task_id: "t5", workflow_id: "wf-005", title: "Sign Off on Q4 Settlement Statement", description: "Quarterly reconciliation complete. Final signoff required from Finance Director.", status: "COMPLETED", priority: "HIGH", due_at: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(), assignee_id: "admin@corp.com", context_snapshot: { quarter: "Q4 2024", amount: "₹18.4L" } },
  { human_task_id: "t6", workflow_id: "wf-001", title: "Verify Goods Receipt — SAP GR Document", description: "Automated match score: 97%. QC inspection report attached.", status: "PENDING", priority: "LOW", due_at: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(), assignee_id: "ops@corp.com", context_snapshot: { gr_number: "GR-2024-4521", items: 12 } },
  { human_task_id: "t7", workflow_id: "wf-006", title: "Approve Access Grant — AWS Production", description: "New hire Priya Sharma requires read access to production AWS environment.", status: "IN_PROGRESS", priority: "CRITICAL", due_at: new Date(Date.now() + 1 * 60 * 60 * 1000).toISOString(), assignee_id: "it.security@corp.com", context_snapshot: { user: "priya.sharma@corp.com", environment: "AWS Production", access_level: "ReadOnly" } },
  { human_task_id: "t8", workflow_id: "wf-007", title: "Meeting Follow-up — Budget Planning Actions", description: "7 action items extracted from budget planning meeting. Please review assignment.", status: "COMPLETED", priority: "MEDIUM", due_at: null, assignee_id: "admin@corp.com", context_snapshot: { action_items: 7, meeting: "Q4 Budget Review" } },
];

function TaskCard({
  task,
  onComplete,
  onStatusChange,
}: {
  task: HumanTask;
  onComplete: (id: string, outcome: string, notes: string) => void;
  onStatusChange: (id: string, status: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [outcome, setOutcome] = useState("COMPLETED");
  const [notes, setNotes] = useState("");

  const priority = PRIORITY_CONFIG[task.priority] || PRIORITY_CONFIG.MEDIUM;
  const isOverdue = task.due_at && isPast(new Date(task.due_at));
  const isDone = task.status === "COMPLETED";
  const isBlocked = task.status === "BLOCKED";

  const dueBadge = () => {
    if (!task.due_at) return null;
    const date = new Date(task.due_at);
    if (isPast(date) && !isDone) return { text: "Overdue", cls: "text-red-400" };
    if (isToday(date)) return { text: "Due today", cls: "text-amber-400" };
    if (isTomorrow(date)) return { text: "Due tomorrow", cls: "text-yellow-400" };
    return { text: formatDistanceToNow(date, { addSuffix: true }), cls: "text-slate-500" };
  };

  const due = dueBadge();

  return (
    <div className={`bg-slate-900/50 border border-l-2 rounded-xl overflow-hidden transition-all ${
      isDone ? "border-slate-800/30 opacity-60 border-l-emerald-600" :
      isBlocked ? "border-slate-800/50 border-l-red-500" :
      priority.border
    } ${!isDone && "hover:bg-slate-900/70"}`}>
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-start gap-3 p-4 text-left"
      >
        <div className={`mt-1 w-2 h-2 rounded-full flex-shrink-0 ${priority.dot} ${isOverdue && !isDone ? "animate-pulse" : ""}`} />
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className={`text-sm font-medium leading-tight ${isDone ? "line-through text-slate-500" : "text-white"}`}>
              {task.title}
            </div>
            <div className="flex items-center gap-1.5 flex-shrink-0">
              <span className={`px-2 py-0.5 rounded-md text-[10px] font-medium border ${priority.color}`}>
                {priority.label}
              </span>
              {isDone ? <CheckCircle2 size={13} className="text-emerald-400" /> :
               expanded ? <ChevronUp size={13} className="text-slate-500" /> :
               <ChevronDown size={13} className="text-slate-500" />}
            </div>
          </div>
          <div className="flex items-center gap-3 mt-1.5 text-[10px] text-slate-500">
            <span className="flex items-center gap-1">
              <User size={9} />{task.assignee_id.split("@")[0]}
            </span>
            {due && (
              <span className={`flex items-center gap-1 ${due.cls}`}>
                <Clock size={9} />{due.text}
              </span>
            )}
          </div>
        </div>
      </button>

      {expanded && !isDone && (
        <div className="px-4 pb-4 border-t border-slate-800/50 pt-3">
          <p className="text-xs text-slate-400 mb-3">{task.description}</p>

          {Object.keys(task.context_snapshot).length > 0 && (
            <div className="bg-slate-800/30 rounded-lg p-3 mb-3">
              <div className="text-[10px] text-slate-500 mb-1.5 uppercase tracking-wider">Context</div>
              <div className="grid grid-cols-2 gap-1">
                {Object.entries(task.context_snapshot).slice(0, 6).map(([k, v]) => (
                  <div key={k} className="text-[10px]">
                    <span className="text-slate-600">{k.replace(/_/g, " ")}: </span>
                    <span className="text-slate-300">{String(v)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="space-y-2">
            <div className="flex gap-1.5">
              {["APPROVED", "REJECTED", "COMPLETED"].map((opt) => (
                <button
                  key={opt}
                  onClick={() => setOutcome(opt)}
                  className={`flex-1 py-1.5 rounded-lg text-[11px] font-medium border transition-all ${
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
              placeholder="Notes (optional)..."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              className="w-full px-3 py-2 bg-slate-800/50 border border-slate-700/50 rounded-lg text-[11px] text-white placeholder-slate-600 focus:outline-none focus:border-violet-500/50 resize-none"
            />
            <button
              onClick={() => { onComplete(task.human_task_id, outcome, notes); setExpanded(false); }}
              className="w-full py-2 bg-gradient-to-r from-violet-600 to-indigo-600 rounded-lg text-white text-xs font-medium transition-all flex items-center justify-center gap-1.5"
            >
              <CheckSquare size={12} /> Complete — {outcome}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function TasksPage() {
  const queryClient = useQueryClient();
  const [viewMode, setViewMode] = useState<"kanban" | "list">("kanban");
  const [search, setSearch] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["tasks"],
    queryFn: async () => {
      try {
        const result = await api.get<{ tasks: HumanTask[]; count: number }>("/tasks?limit=100");
        if (result.tasks.length === 0) throw new Error("empty");
        return result;
      } catch {
        return { tasks: MOCK_TASKS, count: MOCK_TASKS.length };
      }
    },
    refetchInterval: 30000,
  });

  const completeMutation = useMutation({
    mutationFn: ({ taskId, outcome, notes }: { taskId: string; outcome: string; notes: string }) =>
      api.post(`/tasks/${taskId}/complete`, { outcome, completion_notes: notes }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      toast.success("Task completed!");
    },
    onError: () => toast.error("Failed to complete task"),
  });

  const allTasks = data?.tasks ?? [];
  const filtered = allTasks.filter(t => {
    const matchSearch = !search || t.title.toLowerCase().includes(search.toLowerCase());
    const matchPriority = !priorityFilter || t.priority === priorityFilter;
    return matchSearch && matchPriority;
  });

  const byStatus = STATUS_COLUMNS.reduce((acc, col) => {
    acc[col.id] = filtered.filter(t => {
      if (col.id === "PENDING") return t.status === "PENDING";
      if (col.id === "IN_PROGRESS") return t.status === "IN_PROGRESS" || t.status === "ASSIGNED";
      if (col.id === "BLOCKED") return t.status === "BLOCKED";
      if (col.id === "COMPLETED") return t.status === "COMPLETED";
      return false;
    });
    return acc;
  }, {} as Record<string, HumanTask[]>);

  const totalCount = allTasks.length;
  const criticalCount = allTasks.filter(t => t.priority === "CRITICAL" && t.status !== "COMPLETED").length;
  const overdueCount = allTasks.filter(t => t.due_at && isPast(new Date(t.due_at)) && t.status !== "COMPLETED").length;
  const dueTodayCount = allTasks.filter(t => t.due_at && isToday(new Date(t.due_at)) && t.status !== "COMPLETED").length;

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Task Inbox</h1>
          <p className="text-slate-400 text-sm mt-1">
            {totalCount} total · {dueTodayCount} due today · {overdueCount} overdue
          </p>
        </div>
        <div className="flex items-center gap-2">
          {criticalCount > 0 && (
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-xs animate-pulse">
              <Flag size={11} /> {criticalCount} critical
            </div>
          )}
          <div className="flex gap-1 bg-slate-900/50 border border-slate-800/50 rounded-xl p-1">
            {["kanban", "list"].map(mode => (
              <button
                key={mode}
                onClick={() => setViewMode(mode as "kanban" | "list")}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize transition-all ${
                  viewMode === mode ? "bg-violet-600 text-white" : "text-slate-400 hover:text-white"
                }`}
              >
                {mode}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Stats Bar */}
      <div className="grid grid-cols-4 gap-3">
        {STATUS_COLUMNS.map((col) => {
          const count = byStatus[col.id]?.length ?? 0;
          const Icon = col.icon;
          return (
            <div key={col.id} className="bg-slate-900/50 border border-slate-800/50 rounded-xl px-4 py-3 flex items-center gap-3">
              <Icon size={16} className={col.color} />
              <div>
                <div className={`text-xl font-bold ${col.color}`}>{count}</div>
                <div className="text-[11px] text-slate-500">{col.label}</div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Filter Bar */}
      <div className="flex gap-3">
        <div className="relative flex-1 max-w-xs">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search tasks..."
            className="w-full pl-9 pr-4 py-2 bg-slate-800/50 border border-slate-700/50 rounded-xl text-sm text-white placeholder-slate-500 focus:outline-none focus:border-violet-500/50"
          />
        </div>
        <select
          value={priorityFilter}
          onChange={(e) => setPriorityFilter(e.target.value)}
          className="px-3 py-2 bg-slate-800/50 border border-slate-700/50 rounded-xl text-sm text-white focus:outline-none focus:border-violet-500/50"
        >
          <option value="">All Priorities</option>
          {Object.entries(PRIORITY_CONFIG).map(([k, v]) => (
            <option key={k} value={k}>{v.label}</option>
          ))}
        </select>
      </div>

      {/* Kanban View */}
      {viewMode === "kanban" ? (
        <div className="grid grid-cols-4 gap-4 min-h-[600px]">
          {STATUS_COLUMNS.map((col) => {
            const Icon = col.icon;
            const tasks = byStatus[col.id] ?? [];
            return (
              <div key={col.id} className="bg-slate-900/30 border border-slate-800/30 rounded-2xl p-3">
                <div className="flex items-center gap-2 mb-3 px-1">
                  <Icon size={14} className={col.color} />
                  <span className="text-xs font-semibold text-slate-300">{col.label}</span>
                  <span className={`ml-auto text-xs font-bold ${col.color}`}>{tasks.length}</span>
                </div>
                <div className="space-y-2">
                  {tasks.map((task) => (
                    <TaskCard
                      key={task.human_task_id}
                      task={task}
                      onComplete={(id, outcome, notes) => completeMutation.mutate({ taskId: id, outcome, notes })}
                      onStatusChange={(id, status) => toast(`Status change to ${status} — coming soon`)}
                    />
                  ))}
                  {tasks.length === 0 && (
                    <div className="py-8 text-center text-slate-700 text-xs">
                      No tasks
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        // List View
        <div className="space-y-2">
          {filtered.length === 0 ? (
            <div className="py-16 text-center">
              <CheckSquare size={40} className="text-slate-700 mx-auto mb-4" />
              <div className="text-slate-500 text-sm">All tasks completed! 🎉</div>
            </div>
          ) : (
            filtered.map((task) => (
              <TaskCard
                key={task.human_task_id}
                task={task}
                onComplete={(id, outcome, notes) => completeMutation.mutate({ taskId: id, outcome, notes })}
                onStatusChange={(id, status) => toast(`Status change to ${status} — coming soon`)}
              />
            ))
          )}
        </div>
      )}
    </div>
  );
}
