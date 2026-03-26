"use client";

import { GitBranch, Bot, AlertTriangle, TrendingUp } from "lucide-react";

interface KPICardsProps {
  runningWorkflows: number;
  activeAgents: number;
  totalAgents: number;
  atRiskCount: number;
}

export default function KPICards({ runningWorkflows, activeAgents, totalAgents, atRiskCount }: KPICardsProps) {
  const cards = [
    {
      label: "Active Workflows",
      value: runningWorkflows,
      icon: GitBranch,
      color: "from-violet-600/20 to-indigo-600/20",
      iconColor: "text-violet-400",
      border: "border-violet-500/20",
      change: "+12%",
      changePositive: true,
    },
    {
      label: "Agents Running",
      value: `${activeAgents}/${totalAgents}`,
      icon: Bot,
      color: "from-cyan-600/20 to-blue-600/20",
      iconColor: "text-cyan-400",
      border: "border-cyan-500/20",
      change: `${Math.round((activeAgents / Math.max(totalAgents, 1)) * 100)}% util`,
      changePositive: true,
    },
    {
      label: "At Risk",
      value: atRiskCount,
      icon: AlertTriangle,
      color: atRiskCount > 0 ? "from-red-600/20 to-orange-600/20" : "from-emerald-600/20 to-teal-600/20",
      iconColor: atRiskCount > 0 ? "text-red-400" : "text-emerald-400",
      border: atRiskCount > 0 ? "border-red-500/20" : "border-emerald-500/20",
      change: "SLA breach risk",
      changePositive: atRiskCount === 0,
    },
    {
      label: "Avg Health Score",
      value: "94.2",
      icon: TrendingUp,
      color: "from-emerald-600/20 to-teal-600/20",
      iconColor: "text-emerald-400",
      border: "border-emerald-500/20",
      change: "+2.1 pts",
      changePositive: true,
    },
  ];

  return (
    <div className="grid grid-cols-4 gap-4">
      {cards.map((card) => {
        const Icon = card.icon;
        return (
          <div
            key={card.label}
            className={`bg-gradient-to-br ${card.color} border ${card.border} rounded-2xl p-5 backdrop-blur-sm relative overflow-hidden`}
          >
            {/* Background decoration */}
            <div className="absolute -right-4 -top-4 w-16 h-16 rounded-full bg-white/5" />

            <div className="flex items-start justify-between mb-4">
              <div className={`p-2 rounded-xl bg-slate-900/50 ${card.iconColor}`}>
                <Icon size={18} />
              </div>
            </div>

            <div className="text-2xl font-bold text-white mb-1">
              {card.value}
            </div>
            <div className="text-slate-400 text-xs">{card.label}</div>
            <div className={`text-[10px] mt-1 ${card.changePositive ? "text-emerald-400" : "text-red-400"}`}>
              {card.change}
            </div>
          </div>
        );
      })}
    </div>
  );
}
