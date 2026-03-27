"use client";

export const dynamic = "force-dynamic";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { useState } from "react";
import {
  Video, Upload, CheckSquare, Mic, Users, User, TrendingUp, Clock,
  Brain, FileText, AlertCircle, ChevronRight, X, Search, Filter
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { toast } from "sonner";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer
} from "recharts";

interface Meeting {
  meeting_id: string;
  source: string;
  participants: Array<{ name: string; email?: string }>;
  status: string;
  summary_doc: {
    summary?: string;
    decisions?: Array<{ text: string; maker: string; confidence: number }>;
    action_items?: Array<{ description: string; assignee_name: string; due_in_days: number; status?: string }>;
    unresolved_topics?: string[];
    sentiment_timeline?: Array<{ timestamp: number; score: number; speaker: string }>;
  } | null;
  meeting_at: string | null;
  created_at: string;
}

const SOURCE_CONFIG: Record<string, { color: string; label: string; bg: string }> = {
  ZOOM: { color: "text-blue-400", label: "Zoom", bg: "bg-blue-500/10" },
  TEAMS: { color: "text-indigo-400", label: "MS Teams", bg: "bg-indigo-500/10" },
  GOOGLE_MEET: { color: "text-emerald-400", label: "Google Meet", bg: "bg-emerald-500/10" },
  MANUAL: { color: "text-slate-400", label: "Manual Upload", bg: "bg-slate-500/10" },
};

const MOCK_MEETINGS: Meeting[] = [
  {
    meeting_id: "m1",
    source: "ZOOM",
    participants: [
      { name: "Priya Sharma", email: "priya@corp.com" },
      { name: "Arjun Verma", email: "arjun@corp.com" },
      { name: "Ananya Nair", email: "ananya@corp.com" },
      { name: "Rohan Kapoor", email: "rohan@corp.com" },
    ],
    status: "ANALYZED",
    summary_doc: {
      summary: "Q4 budget planning session focused on infrastructure spend, headcount, and AI tooling investments. Key decisions around cloud cost optimization and vendor contract renewals were made.",
      decisions: [
        { text: "Increase cloud infrastructure budget by 15% for Q1 2025", maker: "Priya Sharma", confidence: 0.94 },
        { text: "Renew Salesforce contract with enterprise tier upgrade", maker: "Arjun Verma", confidence: 0.88 },
        { text: "Freeze external hiring until March; focus on internal mobility", maker: "Priya Sharma", confidence: 0.91 },
        { text: "Pilot AntiGravity Procurement automation across 3 business units", maker: "Ananya Nair", confidence: 0.85 },
      ],
      action_items: [
        { description: "Submit revised cloud budget proposal to ExCo", assignee_name: "Arjun Verma", due_in_days: 3, status: "COMPLETED" },
        { description: "Get Salesforce renewal quote from vendor", assignee_name: "Rohan Kapoor", due_in_days: 7, status: "PENDING" },
        { description: "Draft internal mobility announcement for March", assignee_name: "Ananya Nair", due_in_days: 14, status: "PENDING" },
        { description: "Set up AntiGravity pilot in Finance BU", assignee_name: "Priya Sharma", due_in_days: 21, status: "IN_PROGRESS" },
      ],
      unresolved_topics: ["AI tooling vendor shortlist not finalized", "Capex vs Opex classification for new hires"],
      sentiment_timeline: Array.from({ length: 10 }, (_, i) => ({
        timestamp: i * 6,
        score: 0.4 + Math.random() * 0.45,
        speaker: ["Priya Sharma", "Arjun Verma", "Ananya Nair"][i % 3],
      })),
    },
    meeting_at: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
    created_at: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
  },
  {
    meeting_id: "m2",
    source: "TEAMS",
    participants: [
      { name: "Admin User", email: "admin@corp.com" },
      { name: "Priya Sharma", email: "priya@corp.com" },
      { name: "Engineering Lead", email: "eng@corp.com" },
    ],
    status: "ANALYZED",
    summary_doc: {
      summary: "Sprint 23 retrospective and sprint 24 planning. Team velocity reviewed. 3 carry-over stories identified. Risk around API integration timeline flagged.",
      decisions: [
        { text: "Move API integration deadline to January 20th", maker: "Engineering Lead", confidence: 0.83 },
        { text: "Add 2 more QA capacity for sprint 24", maker: "Admin User", confidence: 0.77 },
      ],
      action_items: [
        { description: "Update project timeline in Jira", assignee_name: "Engineering Lead", due_in_days: 1, status: "COMPLETED" },
        { description: "Post retrospective notes in Confluence", assignee_name: "Priya Sharma", due_in_days: 2, status: "PENDING" },
      ],
      unresolved_topics: ["Performance testing strategy not agreed"],
      sentiment_timeline: Array.from({ length: 8 }, (_, i) => ({
        timestamp: i * 7.5,
        score: 0.3 + Math.random() * 0.5,
        speaker: ["Admin User", "Priya Sharma"][i % 2],
      })),
    },
    meeting_at: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000).toISOString(),
    created_at: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000).toISOString(),
  },
  {
    meeting_id: "m3",
    source: "MANUAL",
    participants: [{ name: "Finance Lead" }, { name: "Vendor Manager" }],
    status: "PROCESSING",
    summary_doc: null,
    meeting_at: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
    created_at: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
  },
];

const SENTIMENT_COLORS = ["#8b5cf6", "#06b6d4", "#10b981", "#f59e0b"];

function MeetingList({ meetings, selectedId, onSelect }: {
  meetings: Meeting[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="space-y-2">
      {meetings.map((meeting) => {
        const source = SOURCE_CONFIG[meeting.source] || SOURCE_CONFIG.MANUAL;
        const isAnalyzed = meeting.status === "ANALYZED";
        const isSelected = meeting.meeting_id === selectedId;

        return (
          <button
            key={meeting.meeting_id}
            onClick={() => onSelect(meeting.meeting_id)}
            className={`w-full text-left p-4 rounded-xl border transition-all ${
              isSelected
                ? "bg-violet-500/10 border-violet-500/30"
                : "bg-slate-900/40 border-slate-800/50 hover:bg-slate-900/60"
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Video size={13} className={source.color} />
                <span className="text-xs font-medium text-white">
                  {meeting.participants.slice(0, 2).map(p => p.name.split(" ")[0]).join(", ")}
                  {meeting.participants.length > 2 && ` +${meeting.participants.length - 2}`}
                </span>
              </div>
              <span className={`px-2 py-0.5 rounded-md text-[9px] font-bold border ${
                isAnalyzed ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" :
                meeting.status === "PROCESSING" ? "bg-amber-500/10 text-amber-400 border-amber-500/20" :
                "bg-slate-500/10 text-slate-400 border-slate-500/20"
              }`}>
                {meeting.status}
              </span>
            </div>
            {meeting.summary_doc?.summary ? (
              <p className="text-[11px] text-slate-500 line-clamp-2">{meeting.summary_doc.summary}</p>
            ) : (
              <p className="text-[11px] text-slate-600">Analysis in progress...</p>
            )}
            <div className="flex items-center gap-3 mt-2 text-[10px] text-slate-600">
              {isAnalyzed && (
                <>
                  <span>{meeting.summary_doc?.decisions?.length ?? 0} decisions</span>
                  <span>·</span>
                  <span>{meeting.summary_doc?.action_items?.length ?? 0} actions</span>
                  <span>·</span>
                </>
              )}
              <span>{meeting.meeting_at && formatDistanceToNow(new Date(meeting.meeting_at), { addSuffix: true })}</span>
            </div>
          </button>
        );
      })}
    </div>
  );
}

function MeetingIntelligencePanel({ meeting }: { meeting: Meeting }) {
  const [activeTab, setActiveTab] = useState<"decisions" | "actions" | "sentiment" | "unresolved">("decisions");
  const doc = meeting.summary_doc;
  const source = SOURCE_CONFIG[meeting.source] || SOURCE_CONFIG.MANUAL;

  if (!doc) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-slate-600">
        <Brain size={40} className="mb-4 animate-pulse" />
        <div className="text-sm">MIA analysis in progress...</div>
        <div className="text-xs text-slate-700 mt-1">This usually takes 1-2 minutes</div>
      </div>
    );
  }

  const tabs = [
    { id: "decisions", label: "Decisions", count: doc.decisions?.length ?? 0, icon: Brain },
    { id: "actions", label: "Action Items", count: doc.action_items?.length ?? 0, icon: CheckSquare },
    { id: "sentiment", label: "Sentiment", count: doc.sentiment_timeline?.length ?? 0, icon: TrendingUp },
    { id: "unresolved", label: "Unresolved", count: doc.unresolved_topics?.length ?? 0, icon: AlertCircle },
  ];

  return (
    <div className="bg-slate-900/50 border border-slate-800/50 rounded-2xl overflow-hidden">
      {/* Header */}
      <div className="p-5 border-b border-slate-800/50">
        <div className="flex items-center gap-3 mb-3">
          <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${source.bg} border border-slate-700/30`}>
            <Video size={16} className={source.color} />
          </div>
          <div>
            <div className="text-sm font-semibold text-white">
              {meeting.participants.map(p => p.name.split(" ")[0]).join(", ")}
            </div>
            <div className="text-[10px] text-slate-500">
              {source.label} · {meeting.meeting_at && formatDistanceToNow(new Date(meeting.meeting_at), { addSuffix: true })} · {meeting.participants.length} participants
            </div>
          </div>
        </div>
        {doc.summary && (
          <p className="text-xs text-slate-400 leading-relaxed">{doc.summary}</p>
        )}
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-800/50">
        {tabs.map(({ id, label, count, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id as any)}
            className={`flex-1 flex items-center justify-center gap-1.5 py-3 text-xs font-medium transition-all border-b-2 ${
              activeTab === id
                ? "border-violet-500 text-violet-400"
                : "border-transparent text-slate-500 hover:text-slate-300"
            }`}
          >
            <Icon size={12} />
            {label}
            <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${
              activeTab === id ? "bg-violet-500/20 text-violet-300" : "bg-slate-800 text-slate-500"
            }`}>
              {count}
            </span>
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="p-4">
        {activeTab === "decisions" && (
          <div className="space-y-3">
            {(doc.decisions ?? []).map((d, i) => (
              <div key={i} className="bg-slate-800/30 rounded-xl p-4">
                <div className="flex items-start justify-between gap-3 mb-2">
                  <p className="text-sm text-white leading-relaxed">{d.text}</p>
                  <div className={`flex-shrink-0 px-2 py-0.5 rounded-lg text-[10px] font-bold ${
                    d.confidence >= 0.9 ? "bg-emerald-500/15 text-emerald-400" :
                    d.confidence >= 0.75 ? "bg-amber-500/15 text-amber-400" :
                    "bg-red-500/15 text-red-400"
                  }`}>
                    {Math.round(d.confidence * 100)}%
                  </div>
                </div>
                <div className="flex items-center gap-2 text-[10px] text-slate-500">
                  <User size={9} />
                  <span>{d.maker}</span>
                  <span className="ml-auto text-slate-600">Decision #{i + 1}</span>
                </div>
                {/* Confidence bar */}
                <div className="mt-2 h-1 bg-slate-700 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-violet-500 to-indigo-500"
                    style={{ width: `${d.confidence * 100}%` }}
                  />
                </div>
              </div>
            ))}
            {(!doc.decisions?.length) && (
              <div className="text-center py-8 text-slate-600 text-sm">No decisions extracted</div>
            )}
          </div>
        )}

        {activeTab === "actions" && (
          <div className="space-y-2">
            {(doc.action_items ?? []).map((item, i) => (
              <div key={i} className="flex items-center gap-3 p-3 bg-slate-800/30 rounded-xl">
                <div className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 ${
                  item.status === "COMPLETED" ? "bg-emerald-500/20" : "bg-slate-700"
                }`}>
                  {item.status === "COMPLETED"
                    ? <CheckSquare size={11} className="text-emerald-400" />
                    : <span className="text-[10px] text-slate-500">{i + 1}</span>
                  }
                </div>
                <div className="flex-1 min-w-0">
                  <div className={`text-xs ${item.status === "COMPLETED" ? "line-through text-slate-500" : "text-white"}`}>
                    {item.description}
                  </div>
                  <div className="flex items-center gap-2 mt-0.5 text-[10px] text-slate-500">
                    <span>{item.assignee_name}</span>
                    <span>·</span>
                    <span className={item.due_in_days <= 2 ? "text-amber-400" : ""}>
                      Due in {item.due_in_days}d
                    </span>
                  </div>
                </div>
                <span className={`px-2 py-0.5 rounded-md text-[9px] font-medium border flex-shrink-0 ${
                  item.status === "COMPLETED" ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" :
                  item.status === "IN_PROGRESS" ? "bg-blue-500/10 text-blue-400 border-blue-500/20" :
                  "bg-slate-700/50 text-slate-500 border-slate-600/30"
                }`}>
                  {item.status ?? "PENDING"}
                </span>
              </div>
            ))}
            {(!doc.action_items?.length) && (
              <div className="text-center py-8 text-slate-600 text-sm">No action items extracted</div>
            )}
          </div>
        )}

        {activeTab === "sentiment" && (
          <div>
            <div className="text-xs text-slate-400 mb-3">Sentiment score over meeting duration (by speaker)</div>
            <div className="h-44">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={doc.sentiment_timeline ?? []}>
                  <XAxis dataKey="timestamp" tick={{ fontSize: 9, fill: "#475569" }} tickFormatter={(v) => `${v}m`} axisLine={false} tickLine={false} />
                  <YAxis domain={[0, 1]} tick={{ fontSize: 9, fill: "#475569" }} axisLine={false} tickLine={false} width={24} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
                  <Tooltip
                    contentStyle={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 8, fontSize: 11 }}
                    formatter={(v: number) => [`${(v * 100).toFixed(0)}% positive`, "Sentiment"]}
                    labelFormatter={(l) => `${l}m in`}
                  />
                  <Line type="monotone" dataKey="score" stroke="#8b5cf6" strokeWidth={2.5} dot={false} activeDot={{ r: 4 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2">
              {meeting.participants.slice(0, 4).map((p, i) => (
                <div key={i} className="flex items-center gap-2 text-[11px] text-slate-500">
                  <div className="w-2 h-2 rounded-full" style={{ background: SENTIMENT_COLORS[i % 4] }} />
                  {p.name}
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === "unresolved" && (
          <div className="space-y-2">
            {(doc.unresolved_topics ?? []).map((topic, i) => (
              <div key={i} className="flex items-start gap-3 p-3 bg-amber-500/5 border border-amber-500/15 rounded-xl">
                <AlertCircle size={14} className="text-amber-400 flex-shrink-0 mt-0.5" />
                <p className="text-xs text-slate-300">{topic}</p>
              </div>
            ))}
            {(!doc.unresolved_topics?.length) && (
              <div className="text-center py-8">
                <CheckSquare size={32} className="text-emerald-500/30 mx-auto mb-3" />
                <div className="text-slate-500 text-sm">All topics resolved! 🎉</div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function MeetingsPage() {
  const queryClient = useQueryClient();
  const [showUploader, setShowUploader] = useState(false);
  const [selectedMeetingId, setSelectedMeetingId] = useState<string | null>(MOCK_MEETINGS[0].meeting_id);
  const [transcript, setTranscript] = useState("");
  const [participants, setParticipants] = useState("");
  const [source, setSource] = useState("MANUAL");

  const { data, isLoading } = useQuery({
    queryKey: ["meetings"],
    queryFn: async () => {
      try {
        const result = await api.get<{ meetings: Meeting[]; count: number }>("/meetings?limit=20");
        if (result.meetings.length === 0) throw new Error("empty");
        return result;
      } catch {
        return { meetings: MOCK_MEETINGS, count: MOCK_MEETINGS.length };
      }
    },
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
  const selectedMeeting = meetings.find(m => m.meeting_id === selectedMeetingId) ?? null;
  const analyzedCount = meetings.filter(m => m.status === "ANALYZED").length;
  const totalActionItems = meetings.reduce((sum, m) => sum + (m.summary_doc?.action_items?.length ?? 0), 0);

  return (
    <div className="space-y-5">
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
          className="flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 rounded-xl text-white text-sm font-medium transition-all shadow-lg shadow-violet-500/25"
        >
          <Upload size={14} />
          Analyze Meeting
        </button>
      </div>

      {/* Upload Panel */}
      {showUploader && (
        <div className="bg-slate-900/50 border border-violet-500/20 rounded-2xl p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-white font-semibold flex items-center gap-2">
              <Mic size={16} className="text-violet-400" />
              Submit Meeting for MIA Analysis
            </h2>
            <button onClick={() => setShowUploader(false)} className="text-slate-500 hover:text-white transition-colors">
              <X size={16} />
            </button>
          </div>
          <div className="space-y-4">
            <div>
              <label className="text-xs text-slate-400 block mb-1.5">Transcript Text</label>
              <textarea
                value={transcript}
                onChange={(e) => setTranscript(e.target.value)}
                placeholder="Paste meeting transcript or auto-captured text..."
                rows={6}
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
                  participants: participants.split(",").map(e => e.trim()).filter(Boolean),
                  source,
                })}
                disabled={!transcript.trim() || ingestMutation.isPending}
                className="flex-1 py-3 bg-gradient-to-r from-violet-600 to-indigo-600 rounded-xl text-white text-sm font-medium disabled:opacity-50"
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

      {/* Two-Column Layout */}
      {isLoading ? (
        <div className="grid grid-cols-2 gap-4">
          {[...Array(2)].map((_, i) => <div key={i} className="h-64 bg-slate-800/30 rounded-2xl animate-pulse" />)}
        </div>
      ) : meetings.length === 0 ? (
        <div className="py-16 text-center">
          <Video size={40} className="text-slate-700 mx-auto mb-4" />
          <div className="text-slate-500 text-sm">No meetings yet. Analyze your first meeting.</div>
        </div>
      ) : (
        <div className="grid grid-cols-5 gap-5">
          {/* Meeting List — left 2 cols */}
          <div className="col-span-2">
            <div className="text-xs text-slate-500 font-medium mb-3 uppercase tracking-wider">
              {meetings.length} Meetings
            </div>
            <MeetingList
              meetings={meetings}
              selectedId={selectedMeetingId}
              onSelect={setSelectedMeetingId}
            />
          </div>

          {/* Intelligence Panel — right 3 cols */}
          <div className="col-span-3">
            {selectedMeeting ? (
              <MeetingIntelligencePanel meeting={selectedMeeting} />
            ) : (
              <div className="flex items-center justify-center h-64 text-slate-600 text-sm">
                Select a meeting to view intelligence
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
