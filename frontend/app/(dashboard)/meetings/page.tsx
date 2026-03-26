"use client";

export const dynamic = "force-dynamic";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { useState } from "react";
import { Video, Upload, CheckSquare, Mic, Users, TrendingUp, Clock } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { toast } from "sonner";

interface Meeting {
  meeting_id: string;
  source: string;
  participants: Array<{ name: string; email?: string }>;
  status: string;
  summary_doc: {
    summary?: string;
    decisions?: Array<{ text: string; maker: string; confidence: number }>;
    action_items?: Array<{ description: string; assignee_name: string; due_in_days: number }>;
  } | null;
  meeting_at: string | null;
  created_at: string;
}

const SOURCE_CONFIG: Record<string, { color: string; label: string }> = {
  ZOOM: { color: "text-blue-400", label: "Zoom" },
  TEAMS: { color: "text-indigo-400", label: "MS Teams" },
  GOOGLE_MEET: { color: "text-emerald-400", label: "Google Meet" },
  MANUAL: { color: "text-slate-400", label: "Manual Upload" },
};

function MeetingCard({ meeting }: { meeting: Meeting }) {
  const source = SOURCE_CONFIG[meeting.source] || SOURCE_CONFIG.MANUAL;
  const decisions = meeting.summary_doc?.decisions ?? [];
  const actionItems = meeting.summary_doc?.action_items ?? [];
  const summary = meeting.summary_doc?.summary ?? "";
  const isAnalyzed = meeting.status === "ANALYZED";

  return (
    <div className="bg-slate-900/50 border border-slate-800/50 rounded-2xl p-5 hover:bg-slate-900/70 transition-all">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center">
            <Video size={16} className="text-violet-400" />
          </div>
          <div>
            <div className="text-sm font-medium text-white">
              {meeting.participants.slice(0, 2).map((p) => p.name).join(", ")}
              {meeting.participants.length > 2 && ` +${meeting.participants.length - 2}`}
            </div>
            <div className="flex items-center gap-2 text-[10px] text-slate-500 mt-0.5">
              <span className={source.color}>{source.label}</span>
              <span>·</span>
              <Users size={9} />
              <span>{meeting.participants.length} people</span>
              {meeting.meeting_at && (
                <>
                  <span>·</span>
                  <Clock size={9} />
                  <span>{formatDistanceToNow(new Date(meeting.meeting_at), { addSuffix: true })}</span>
                </>
              )}
            </div>
          </div>
        </div>
        <span className={`px-2 py-0.5 rounded-md text-[10px] font-medium border ${
          isAnalyzed ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" :
          meeting.status === "PROCESSING" ? "bg-amber-500/10 text-amber-400 border-amber-500/20" :
          "bg-slate-500/10 text-slate-400 border-slate-500/20"
        }`}>
          {meeting.status}
        </span>
      </div>

      {/* Summary */}
      {summary && (
        <p className="text-xs text-slate-400 mb-4 line-clamp-2">{summary}</p>
      )}

      {/* Stats */}
      {isAnalyzed && (
        <div className="grid grid-cols-3 gap-2">
          {[
            { label: "Decisions", value: decisions.length, color: "text-violet-400", icon: TrendingUp },
            { label: "Action Items", value: actionItems.length, color: "text-emerald-400", icon: CheckSquare },
            { label: "Participants", value: meeting.participants.length, color: "text-blue-400", icon: Users },
          ].map((stat) => (
            <div key={stat.label} className="bg-slate-800/30 rounded-lg p-2.5 text-center">
              <div className={`text-lg font-bold ${stat.color}`}>{stat.value}</div>
              <div className="text-[10px] text-slate-500">{stat.label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Top Decision */}
      {decisions.length > 0 && (
        <div className="mt-3 p-3 bg-violet-500/5 border border-violet-500/10 rounded-xl">
          <div className="text-[10px] text-violet-400 mb-1">Key Decision</div>
          <div className="text-xs text-slate-300 line-clamp-2">{decisions[0].text}</div>
          <div className="text-[10px] text-slate-500 mt-1">— {decisions[0].maker} · {Math.round(decisions[0].confidence * 100)}% confidence</div>
        </div>
      )}
    </div>
  );
}

export default function MeetingsPage() {
  const queryClient = useQueryClient();
  const [showUploader, setShowUploader] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [participants, setParticipants] = useState("");
  const [source, setSource] = useState("MANUAL");

  const { data, isLoading } = useQuery({
    queryKey: ["meetings"],
    queryFn: () => api.get<{ meetings: Meeting[]; count: number }>("/meetings?limit=20"),
    refetchInterval: 30000,
  });

  const ingestMutation = useMutation({
    mutationFn: (payload: { transcript_text: string; participants: string[]; source: string }) =>
      api.post("/meetings/ingest", payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["meetings"] });
      toast.success("Meeting ingested — MIA analysis started!");
      setShowUploader(false);
      setTranscript("");
    },
    onError: () => toast.error("Failed to ingest meeting"),
  });

  const meetings = data?.meetings ?? [];
  const analyzedCount = meetings.filter((m) => m.status === "ANALYZED").length;
  const totalActionItems = meetings.reduce((sum, m) => sum + (m.summary_doc?.action_items?.length ?? 0), 0);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Meeting Intelligence</h1>
          <p className="text-slate-400 text-sm mt-1">
            {meetings.length} meetings · {analyzedCount} analyzed · {totalActionItems} action items extracted
          </p>
        </div>
        <button
          onClick={() => setShowUploader(true)}
          className="flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 rounded-xl text-white text-sm font-medium transition-all"
        >
          <Upload size={14} />
          Analyze Meeting
        </button>
      </div>

      {/* Transcript Upload Panel */}
      {showUploader && (
        <div className="bg-slate-900/50 border border-violet-500/20 rounded-2xl p-6">
          <h2 className="text-white font-semibold mb-4 flex items-center gap-2">
            <Mic size={16} className="text-violet-400" />
            Submit Meeting for MIA Analysis
          </h2>
          <div className="space-y-4">
            <div>
              <label className="text-xs text-slate-400 block mb-1.5">Transcript Text</label>
              <textarea
                value={transcript}
                onChange={(e) => setTranscript(e.target.value)}
                placeholder="Paste meeting transcript or auto-captured text..."
                rows={8}
                className="w-full px-4 py-3 bg-slate-800 border border-slate-700/50 rounded-xl text-sm text-white placeholder-slate-600 focus:outline-none focus:border-violet-500/50 resize-none"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-slate-400 block mb-1.5">Participant Emails (comma-separated)</label>
                <input
                  type="text"
                  value={participants}
                  onChange={(e) => setParticipants(e.target.value)}
                  placeholder="priya@corp.com, arjun@corp.com"
                  className="w-full px-4 py-3 bg-slate-800 border border-slate-700/50 rounded-xl text-sm text-white placeholder-slate-600 focus:outline-none focus:border-violet-500/50"
                />
              </div>
              <div>
                <label className="text-xs text-slate-400 block mb-1.5">Source Platform</label>
                <select
                  value={source}
                  onChange={(e) => setSource(e.target.value)}
                  className="w-full px-4 py-3 bg-slate-800 border border-slate-700/50 rounded-xl text-sm text-white focus:outline-none focus:border-violet-500/50"
                >
                  {Object.entries(SOURCE_CONFIG).map(([k, v]) => (
                    <option key={k} value={k}>{v.label}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => ingestMutation.mutate({
                  transcript_text: transcript,
                  participants: participants.split(",").map((e) => e.trim()).filter(Boolean),
                  source,
                })}
                disabled={!transcript.trim() || ingestMutation.isPending}
                className="flex-1 py-3 bg-gradient-to-r from-violet-600 to-indigo-600 rounded-xl text-white text-sm font-medium disabled:opacity-50 transition-all"
              >
                {ingestMutation.isPending ? "Analyzing..." : "Start MIA Analysis"}
              </button>
              <button
                onClick={() => setShowUploader(false)}
                className="px-6 py-3 bg-slate-800 rounded-xl text-slate-400 text-sm border border-slate-700/50 hover:text-white transition-all"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Meeting Cards */}
      {isLoading ? (
        <div className="grid grid-cols-2 gap-4">
          {[...Array(4)].map((_, i) => <div key={i} className="h-52 bg-slate-800/30 rounded-2xl animate-pulse" />)}
        </div>
      ) : meetings.length === 0 ? (
        <div className="py-16 text-center">
          <Video size={40} className="text-slate-700 mx-auto mb-4" />
          <div className="text-slate-500 text-sm">No meetings yet. Analyze your first meeting.</div>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4">
          {meetings.map((meeting) => (
            <MeetingCard key={meeting.meeting_id} meeting={meeting} />
          ))}
        </div>
      )}
    </div>
  );
}
