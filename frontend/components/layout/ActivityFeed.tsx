"use client";

import { useEffect, useRef, useState } from "react";
import { useWebSocketStore } from "@/lib/websocket-store";
import { GitBranch, Bot, AlertTriangle, CheckCircle, Info, X, ChevronRight } from "lucide-react";
import { formatDistanceToNow } from "date-fns";

interface ActivityEvent {
  id: string;
  event_type: string;
  collection?: string;
  data?: Record<string, unknown>;
  timestamp: string;
  read?: boolean;
}

const eventConfig: Record<string, { icon: React.FC<any>; color: string; bg: string; label: string }> = {
  WorkflowUpdated: { icon: GitBranch, color: "text-blue-400", bg: "bg-blue-500/10 border-blue-500/30", label: "Workflow" },
  TaskStatusChanged: { icon: CheckCircle, color: "text-emerald-400", bg: "bg-emerald-500/10 border-emerald-500/30", label: "Task" },
  NewHumanTask: { icon: CheckCircle, color: "text-amber-400", bg: "bg-amber-500/10 border-amber-500/30", label: "Human Task" },
  EscalationTriggered: { icon: AlertTriangle, color: "text-red-400", bg: "bg-red-500/10 border-red-500/30", label: "Escalation" },
  NewAuditEvent: { icon: Info, color: "text-slate-400", bg: "bg-slate-500/10 border-slate-500/30", label: "Audit" },
  AgentDecisionMade: { icon: Bot, color: "text-violet-400", bg: "bg-violet-500/10 border-violet-500/30", label: "Decision" },
};

export default function ActivityFeed() {
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [isOpen, setIsOpen] = useState(true);
  const { subscribe } = useWebSocketStore();
  const feedRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  useEffect(() => {
    const unsubscribe = subscribe("*" as any, (event: any) => {
      if (event.event_type === "Connected" || event.event_type === "Heartbeat" || event.event_type === "Ping") return;

      setEvents((prev) => {
        const newEvent: ActivityEvent = {
          id: `${Date.now()}-${Math.random()}`,
          ...event,
        };
        const updated = [newEvent, ...prev].slice(0, 200);
        return updated;
      });
    });

    return unsubscribe;
  }, [subscribe]);

  useEffect(() => {
    if (autoScroll && feedRef.current) {
      feedRef.current.scrollTop = 0;
    }
  }, [events, autoScroll]);

  const criticalCount = events.filter(
    (e) => !e.read && (e.event_type === "EscalationTriggered")
  ).length;

  if (!isOpen) {
    return (
      <div className="w-10 border-l border-slate-800/50 flex flex-col items-center py-4 gap-4 bg-slate-900/30">
        <button
          onClick={() => setIsOpen(true)}
          className="w-8 h-8 flex items-center justify-center rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition-all relative"
        >
          <ChevronRight size={14} />
          {criticalCount > 0 && (
            <span className="absolute -top-1 -right-1 w-3.5 h-3.5 bg-red-500 rounded-full text-[8px] flex items-center justify-center text-white font-bold">
              {criticalCount}
            </span>
          )}
        </button>
      </div>
    );
  }

  return (
    <div className="w-80 flex-shrink-0 border-l border-slate-800/50 bg-slate-900/30 backdrop-blur-xl flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800/50">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-white">Activity</span>
          {criticalCount > 0 && (
            <span className="w-5 h-5 bg-red-500 rounded-full text-[10px] flex items-center justify-center text-white font-bold">
              {criticalCount}
            </span>
          )}
        </div>
        <button
          onClick={() => setIsOpen(false)}
          className="w-6 h-6 flex items-center justify-center rounded text-slate-500 hover:text-white hover:bg-slate-700 transition-all"
        >
          <X size={12} />
        </button>
      </div>

      {/* Events Feed */}
      <div
        ref={feedRef}
        className="flex-1 overflow-y-auto p-3 space-y-2"
        onScroll={(e) => {
          const { scrollTop } = e.currentTarget;
          setAutoScroll(scrollTop < 20);
        }}
      >
        {events.length === 0 ? (
          <div className="text-center text-slate-600 text-xs py-8">
            <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center mx-auto mb-2">
              <Info size={14} />
            </div>
            Waiting for live events...
          </div>
        ) : (
          events.map((event) => {
            const config = eventConfig[event.event_type] || {
              icon: Info,
              color: "text-slate-400",
              bg: "bg-slate-800/30 border-slate-700/30",
              label: event.event_type,
            };
            const Icon = config.icon;

            return (
              <div
                key={event.id}
                className={`flex gap-2.5 p-2.5 rounded-lg border ${config.bg} cursor-pointer hover:opacity-80 transition-opacity`}
              >
                <div className={`mt-0.5 flex-shrink-0 ${config.color}`}>
                  <Icon size={13} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-xs text-white font-medium leading-tight">
                    {config.label}
                    {!!event.data?.workflow_id && (
                      <span className="text-slate-500 font-normal ml-1">
                        {String(event.data.workflow_id as string).slice(0, 8)}...
                      </span>
                    )}
                  </div>
                  <div className={`text-[10px] mt-0.5 ${config.color} opacity-70`}>
                    {event.event_type.replace(/([A-Z])/g, ' $1').trim()}
                  </div>
                  <div className="text-[10px] text-slate-600 mt-0.5">
                    {formatDistanceToNow(new Date(event.timestamp), { addSuffix: true })}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Footer */}
      <div className="px-4 py-2 border-t border-slate-800/50">
        <div className="text-[10px] text-slate-600">
          {events.length} events · {autoScroll ? "Live" : "Paused"}
        </div>
      </div>
    </div>
  );
}
