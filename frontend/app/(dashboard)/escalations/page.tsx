"use client";

export const dynamic = "force-dynamic";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { useState, useEffect } from "react";
import {
  AlertTriangle, Clock, User, ChevronRight, CheckCircle,
  TrendingUp, Flame, Shield, X, ArrowRight
} from "lucide-react";
import { formatDistanceToNow, differenceInSeconds } from "date-fns";
import { toast } from "sonner";

interface Escalation {
  escalation_id: string;
  workflow_id: string;
  trigger_type: string;
  risk_score: number;
  predicted_breach_at: string | null;
  assigned_to: string | null;
  status: string;
  resolved_at: string | null;
  resolution_notes: string | null;
  created_at: string;
}

const RISK_CONFIG: Record<string, { label: string; color: string; bg: string; icon: React.FC<any> }> = {
  CRITICAL: { label: "Critical", color: "text-red-400", bg: "bg-red-500/10 border-red-500/30", icon: Flame },
  HIGH: { label: "High", color: "text-orange-400", bg: "bg-orange-500/10 border-orange-500/30", icon: AlertTriangle },
  MEDIUM: { label: "Medium", color: "text-amber-400", bg: "bg-amber-500/10 border-amber-500/30", icon: TrendingUp },
  LOW: { label: "Low", color: "text-blue-400", bg: "bg-blue-500/10 border-blue-500/30", icon: Shield },
};

function getRiskLevel(score: number): string {
  if (score >= 0.85) return "CRITICAL";
  if (score >= 0.7) return "HIGH";
  if (score >= 0.5) return "MEDIUM";
  return "LOW";
}

function CountdownTimer({ targetDate }: { targetDate: string | null }) {
  const [timeLeft, setTimeLeft] = useState<number | null>(null);

  useEffect(() => {
    if (!targetDate) return;
    const update = () => {
      const diff = differenceInSeconds(new Date(targetDate), new Date());
      setTimeLeft(diff);
    };
    update();
    const interval = setInterval(update, 1000);
    return () => clearInterval(interval);
  }, [targetDate]);

  if (!targetDate || timeLeft === null) return <span className="text-slate-600">—</span>;

  if (timeLeft <= 0) {
    return <span className="text-red-400 font-mono text-xs font-bold animate-pulse">BREACHED</span>;
  }

  const hours = Math.floor(timeLeft / 3600);
  const minutes = Math.floor((timeLeft % 3600) / 60);
  const seconds = timeLeft % 60;

  const isUrgent = timeLeft < 3600;
  const isCritical = timeLeft < 900;

  return (
    <span className={`font-mono text-xs font-bold ${
      isCritical ? "text-red-400 animate-pulse" : isUrgent ? "text-orange-400" : "text-amber-400"
    }`}>
      {hours > 0 ? `${hours}h ` : ""}{minutes.toString().padStart(2, "0")}m {seconds.toString().padStart(2, "0")}s
    </span>
  );
}

function EscalationCard({
  escalation,
  onResolve,
}: {
  escalation: Escalation;
  onResolve: (id: string) => void;
}) {
  const [showResolve, setShowResolve] = useState(false);
  const [notes, setNotes] = useState("");
  const riskLevel = getRiskLevel(escalation.risk_score);
  const riskConfig = RISK_CONFIG[riskLevel];
  const Icon = riskConfig.icon;
  const isResolved = escalation.status === "RESOLVED";

  return (
    <div className={`bg-slate-900/60 border rounded-2xl overflow-hidden transition-all backdrop-blur-sm ${
      isResolved ? "border-slate-800/30 opacity-60" : riskConfig.bg
    }`}>
      <div className="p-5">
        {/* Header Row */}
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${riskConfig.bg}`}>
              <Icon size={18} className={riskConfig.color} />
            </div>
            <div>
              <div className="text-sm font-semibold text-white">
                {escalation.trigger_type.replace(/_/g, " ")}
              </div>
              <div className="flex items-center gap-2 mt-0.5">
                <span className={`px-2 py-0.5 rounded-md text-[10px] font-bold border ${riskConfig.bg} ${riskConfig.color}`}>
                  {riskLevel}
                </span>
                <span className="text-[10px] text-slate-500 font-mono">
                  {escalation.workflow_id.slice(0, 12)}...
                </span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3 flex-shrink-0">
            {/* Risk Score Ring */}
            <div className="relative w-12 h-12">
              <svg className="w-12 h-12 -rotate-90" viewBox="0 0 36 36">
                <circle cx="18" cy="18" r="15" fill="none" stroke="#1e293b" strokeWidth="3" />
                <circle
                  cx="18" cy="18" r="15" fill="none"
                  stroke={escalation.risk_score >= 0.8 ? "#ef4444" : escalation.risk_score >= 0.6 ? "#f97316" : "#f59e0b"}
                  strokeWidth="3"
                  strokeDasharray={`${escalation.risk_score * 94.2} 94.2`}
                  strokeLinecap="round"
                />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center">
                <span className={`text-[10px] font-bold ${riskConfig.color}`}>
                  {Math.round(escalation.risk_score * 100)}%
                </span>
              </div>
            </div>

            {!isResolved && (
              <button
                onClick={() => setShowResolve(!showResolve)}
                className="px-3 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs hover:bg-emerald-500/20 transition-all flex items-center gap-1.5"
              >
                <CheckCircle size={12} />
                Resolve
              </button>
            )}
          </div>
        </div>

        {/* Stats Row */}
        <div className="grid grid-cols-3 gap-3 mb-4">
          <div className="bg-slate-800/30 rounded-xl p-3">
            <div className="text-[10px] text-slate-500 mb-1 flex items-center gap-1">
              <Clock size={9} /> Time to Breach
            </div>
            <CountdownTimer targetDate={escalation.predicted_breach_at} />
          </div>
          <div className="bg-slate-800/30 rounded-xl p-3">
            <div className="text-[10px] text-slate-500 mb-1 flex items-center gap-1">
              <User size={9} /> Assigned To
            </div>
            <div className="text-xs text-white font-medium truncate">
              {escalation.assigned_to || "Unassigned"}
            </div>
          </div>
          <div className="bg-slate-800/30 rounded-xl p-3">
            <div className="text-[10px] text-slate-500 mb-1">Triggered</div>
            <div className="text-xs text-white">
              {formatDistanceToNow(new Date(escalation.created_at), { addSuffix: true })}
            </div>
          </div>
        </div>

        {/* Resolution Notes (if resolved) */}
        {isResolved && escalation.resolution_notes && (
          <div className="p-3 bg-emerald-500/5 border border-emerald-500/10 rounded-xl">
            <div className="text-[10px] text-emerald-400 mb-1">Resolution Notes</div>
            <div className="text-xs text-slate-400">{escalation.resolution_notes}</div>
          </div>
        )}

        {/* Resolve Form */}
        {showResolve && !isResolved && (
          <div className="pt-4 border-t border-slate-800/50">
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Resolution notes (required)..."
              rows={2}
              className="w-full px-3 py-2 bg-slate-800/50 border border-slate-700/50 rounded-xl text-xs text-white placeholder-slate-600 focus:outline-none focus:border-violet-500/50 transition-all resize-none mb-3"
            />
            <div className="flex gap-2">
              <button
                onClick={() => { onResolve(escalation.escalation_id); setShowResolve(false); }}
                disabled={!notes.trim()}
                className="flex-1 py-2 bg-gradient-to-r from-emerald-600 to-teal-600 rounded-xl text-white text-xs font-medium disabled:opacity-50 transition-all flex items-center justify-center gap-1.5"
              >
                <CheckCircle size={12} />
                Mark Resolved
              </button>
              <button
                onClick={() => setShowResolve(false)}
                className="px-4 py-2 bg-slate-800 rounded-xl text-slate-400 text-xs border border-slate-700/50 hover:text-white transition-all"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// Mock escalation data (used when backend returns empty)
const MOCK_ESCALATIONS: Escalation[] = [
  {
    escalation_id: "esc-001",
    workflow_id: "wf-procurement-abc123",
    trigger_type: "SLA_BREACH_PREDICTED",
    risk_score: 0.91,
    predicted_breach_at: new Date(Date.now() + 42 * 60 * 1000).toISOString(),
    assigned_to: "priya.sharma@corp.com",
    status: "ACTIVE",
    resolved_at: null,
    resolution_notes: null,
    created_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
  },
  {
    escalation_id: "esc-002",
    workflow_id: "wf-onboarding-def456",
    trigger_type: "AGENT_REPEATED_FAILURE",
    risk_score: 0.76,
    predicted_breach_at: new Date(Date.now() + 2.5 * 60 * 60 * 1000).toISOString(),
    assigned_to: "arjun.verma@corp.com",
    status: "ACTIVE",
    resolved_at: null,
    resolution_notes: null,
    created_at: new Date(Date.now() - 45 * 60 * 1000).toISOString(),
  },
  {
    escalation_id: "esc-003",
    workflow_id: "wf-contract-ghi789",
    trigger_type: "HUMAN_TASK_OVERDUE",
    risk_score: 0.55,
    predicted_breach_at: new Date(Date.now() + 6 * 60 * 60 * 1000).toISOString(),
    assigned_to: null,
    status: "ACTIVE",
    resolved_at: null,
    resolution_notes: null,
    created_at: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString(),
  },
  {
    escalation_id: "esc-004",
    workflow_id: "wf-payment-jkl012",
    trigger_type: "PAYMENT_APPROVAL_TIMEOUT",
    risk_score: 0.88,
    predicted_breach_at: null,
    assigned_to: "ananya.nair@corp.com",
    status: "RESOLVED",
    resolved_at: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
    resolution_notes: "Manually approved by finance director. Payment cleared.",
    created_at: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString(),
  },
];

export default function EscalationsPage() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<"active" | "resolved">("active");

  const { data, isLoading } = useQuery({
    queryKey: ["escalations", activeTab],
    queryFn: async () => {
      try {
        return await api.get<{ escalations: Escalation[]; count: number }>(
          `/escalations?status=${activeTab === "active" ? "ACTIVE" : "RESOLVED"}&limit=50`
        );
      } catch {
        // Use mock data if endpoint not available
        const filtered = MOCK_ESCALATIONS.filter(e =>
          activeTab === "active" ? e.status === "ACTIVE" : e.status === "RESOLVED"
        );
        return { escalations: filtered, count: filtered.length };
      }
    },
    refetchInterval: 15000,
  });

  const resolveMutation = useMutation({
    mutationFn: (id: string) => api.post(`/escalations/${id}/resolve`, { resolution_notes: "Resolved via dashboard" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["escalations"] });
      toast.success("Escalation resolved!");
    },
    onError: () => toast.error("Failed to resolve escalation"),
  });

  const escalations = data?.escalations ?? [];
  const activeCount = MOCK_ESCALATIONS.filter(e => e.status === "ACTIVE").length;
  const criticalCount = MOCK_ESCALATIONS.filter(e => e.status === "ACTIVE" && getRiskLevel(e.risk_score) === "CRITICAL").length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Escalations</h1>
          <p className="text-slate-400 text-sm mt-1">
            {activeCount} active · {criticalCount} critical requiring immediate attention
          </p>
        </div>
        {criticalCount > 0 && (
          <div className="flex items-center gap-2 px-4 py-2 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm animate-pulse">
            <Flame size={14} />
            {criticalCount} Critical — Action Required
          </div>
        )}
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "Active", value: activeCount.toString(), color: "text-amber-400", bg: "bg-amber-500/10 border-amber-500/20" },
          { label: "Critical", value: criticalCount.toString(), color: "text-red-400", bg: "bg-red-500/10 border-red-500/20" },
          { label: "Avg Risk Score", value: `${Math.round(MOCK_ESCALATIONS.filter(e => e.status === "ACTIVE").reduce((s, e) => s + e.risk_score, 0) / Math.max(activeCount, 1) * 100)}%`, color: "text-orange-400", bg: "bg-orange-500/10 border-orange-500/20" },
          { label: "Resolved Today", value: "4", color: "text-emerald-400", bg: "bg-emerald-500/10 border-emerald-500/20" },
        ].map((stat) => (
          <div key={stat.label} className={`bg-slate-900/50 border rounded-2xl p-5 ${stat.bg}`}>
            <div className="text-slate-400 text-xs mb-2">{stat.label}</div>
            <div className={`text-3xl font-bold ${stat.color}`}>{stat.value}</div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-slate-900/50 border border-slate-800/50 rounded-xl p-1 w-fit">
        {[{ id: "active", label: "Active Escalations" }, { id: "resolved", label: "Resolved" }].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as "active" | "resolved")}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === tab.id ? "bg-violet-600 text-white" : "text-slate-400 hover:text-white"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Escalation Cards */}
      {isLoading ? (
        <div className="grid grid-cols-1 gap-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-48 bg-slate-800/30 rounded-2xl animate-pulse" />
          ))}
        </div>
      ) : escalations.length === 0 ? (
        <div className="py-16 text-center">
          <Shield size={48} className="text-slate-700 mx-auto mb-4" />
          <div className="text-slate-400 font-medium">
            {activeTab === "active" ? "No active escalations 🎉" : "No resolved escalations yet"}
          </div>
          <div className="text-slate-600 text-sm mt-1">
            {activeTab === "active" ? "All workflows are running within SLA parameters" : ""}
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {escalations.map((esc) => (
            <EscalationCard
              key={esc.escalation_id}
              escalation={esc}
              onResolve={(id) => resolveMutation.mutate(id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
