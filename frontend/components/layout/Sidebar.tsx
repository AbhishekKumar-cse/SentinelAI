"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  GitBranch,
  Bot,
  Video,
  CheckSquare,
  AlertTriangle,
  BarChart3,
  Plug,
  Settings,
  Zap,
} from "lucide-react";

const navItems = [
  { href: "/", icon: LayoutDashboard, label: "Command Center" },
  { href: "/workflows", icon: GitBranch, label: "Workflows" },
  { href: "/agents", icon: Bot, label: "Agent Fleet" },
  { href: "/meetings", icon: Video, label: "Meetings" },
  { href: "/tasks", icon: CheckSquare, label: "Task Inbox" },
  { href: "/escalations", icon: AlertTriangle, label: "Escalations" },
  { href: "/analytics", icon: BarChart3, label: "Analytics" },
  { href: "/connectors", icon: Plug, label: "Connectors" },
  { href: "/settings", icon: Settings, label: "Settings" },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <div className="w-64 flex-shrink-0 bg-slate-900/50 backdrop-blur-xl border-r border-slate-800/50 flex flex-col">
      {/* Brand */}
      <div className="p-6 border-b border-slate-800/50">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-violet-600 to-indigo-600 flex items-center justify-center shadow-lg shadow-violet-500/25">
            <Zap size={18} className="text-white" />
          </div>
          <div>
            <div className="font-bold text-white text-sm tracking-tight">
              Anti<span className="text-violet-400">Gravity</span>
            </div>
            <div className="text-[10px] text-slate-500">Enterprise AI Platform</div>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));

          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 group ${
                isActive
                  ? "bg-violet-600/20 text-violet-300 border border-violet-500/30"
                  : "text-slate-400 hover:text-white hover:bg-slate-800/50"
              }`}
            >
              <Icon
                size={16}
                className={`${isActive ? "text-violet-400" : "text-slate-500 group-hover:text-slate-300"} transition-colors`}
              />
              {item.label}
              {/* Active indicator */}
              {isActive && (
                <div className="ml-auto w-1.5 h-1.5 rounded-full bg-violet-400" />
              )}
            </Link>
          );
        })}
      </nav>

      {/* Bottom section */}
      <div className="p-4 border-t border-slate-800/50">
        <div className="flex items-center gap-3 px-3 py-2.5 rounded-xl bg-slate-800/30">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center text-white text-xs font-bold">
            A
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-xs text-white font-medium truncate">Admin User</div>
            <div className="text-[10px] text-slate-500 truncate">Tenant Admin</div>
          </div>
        </div>
      </div>
    </div>
  );
}
