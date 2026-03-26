"use client";

import { Bell, Search, Plus } from "lucide-react";
import { useWebSocketStore } from "@/lib/websocket-store";
import Link from "next/link";

export default function Header() {
  const { isConnected } = useWebSocketStore();

  return (
    <header className="h-16 border-b border-slate-800/50 bg-slate-900/30 backdrop-blur-xl flex items-center px-6 gap-4 flex-shrink-0">
      {/* Search */}
      <div className="flex-1 max-w-md">
        <div className="relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            placeholder="Search workflows, agents, tasks..."
            className="w-full pl-9 pr-4 py-2 bg-slate-800/50 border border-slate-700/50 rounded-lg text-sm text-slate-300 placeholder-slate-500 focus:outline-none focus:border-violet-500/50 focus:bg-slate-800 transition-all"
          />
        </div>
      </div>

      <div className="flex items-center gap-3">
        {/* Launch Workflow Button */}
        <Link
          href="/workflows/new"
          className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 rounded-lg text-white text-sm font-medium transition-all shadow-lg shadow-violet-500/20"
        >
          <Plus size={14} />
          Launch Workflow
        </Link>

        {/* Notifications */}
        <button className="relative w-9 h-9 flex items-center justify-center rounded-lg bg-slate-800/50 border border-slate-700/50 text-slate-400 hover:text-white hover:border-slate-600 transition-all">
          <Bell size={16} />
          <span className="absolute -top-1 -right-1 w-4 h-4 bg-violet-500 rounded-full text-[9px] text-white flex items-center justify-center font-bold">
            3
          </span>
        </button>

        {/* Connection status */}
        <div className={`w-2 h-2 rounded-full ${isConnected ? "bg-emerald-400 animate-pulse" : "bg-red-400"}`} title={isConnected ? "Live" : "Disconnected"} />
      </div>
    </header>
  );
}
