"use client";

export const dynamic = "force-dynamic";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import {
  Settings, Users, Key, Bell, Shield, Copy, Eye, EyeOff,
  Plus, Trash2, CheckCircle, ChevronRight, Building2, Zap,
  Lock, Globe, Database
} from "lucide-react";
import { toast } from "sonner";
import { formatDistanceToNow } from "date-fns";

const ROLE_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  SUPERADMIN: { label: "Super Admin", color: "text-red-400", bg: "bg-red-500/10 border-red-500/20" },
  TENANT_ADMIN: { label: "Tenant Admin", color: "text-violet-400", bg: "bg-violet-500/10 border-violet-500/20" },
  WORKFLOW_MANAGER: { label: "Workflow Manager", color: "text-blue-400", bg: "bg-blue-500/10 border-blue-500/20" },
  AGENT_OPERATOR: { label: "Agent Operator", color: "text-emerald-400", bg: "bg-emerald-500/10 border-emerald-500/20" },
  AUDITOR: { label: "Auditor", color: "text-amber-400", bg: "bg-amber-500/10 border-amber-500/20" },
};

const MOCK_TEAM = [
  { id: "u1", email: "admin@corp.com", name: "Admin User", role: "TENANT_ADMIN", last_active: new Date(Date.now() - 5 * 60 * 1000).toISOString() },
  { id: "u2", email: "priya.sharma@corp.com", name: "Priya Sharma", role: "WORKFLOW_MANAGER", last_active: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString() },
  { id: "u3", email: "arjun.verma@corp.com", name: "Arjun Verma", role: "AGENT_OPERATOR", last_active: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString() },
  { id: "u4", email: "ananya.nair@corp.com", name: "Ananya Nair", role: "AUDITOR", last_active: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString() },
  { id: "u5", email: "rohan.kapoor@corp.com", name: "Rohan Kapoor", role: "WORKFLOW_MANAGER", last_active: new Date(Date.now() - 1 * 60 * 60 * 1000).toISOString() },
];

const MOCK_API_KEYS = [
  { id: "key-001", name: "Production Integration", prefix: "ag_live_", last_used: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(), created_at: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString() },
  { id: "key-002", name: "CI/CD Pipeline", prefix: "ag_live_", last_used: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(), created_at: new Date(Date.now() - 14 * 24 * 60 * 60 * 1000).toISOString() },
  { id: "key-003", name: "Dev Testing", prefix: "ag_test_", last_used: null, created_at: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString() },
];

const TABS = [
  { id: "general", label: "General", icon: Building2 },
  { id: "team", label: "Team & Access", icon: Users },
  { id: "apikeys", label: "API Keys", icon: Key },
  { id: "notifications", label: "Notifications", icon: Bell },
  { id: "security", label: "Security", icon: Shield },
];

function GeneralTab() {
  const [saving, setSaving] = useState(false);
  const [tenantName, setTenantName] = useState("ACME Corporation");
  const [plan, _setPlan] = useState("Enterprise");
  const [timezone, setTimezone] = useState("Asia/Kolkata");
  const [language, setLanguage] = useState("en");

  const handleSave = async () => {
    setSaving(true);
    await new Promise(r => setTimeout(r, 1000));
    setSaving(false);
    toast.success("Settings saved!");
  };

  return (
    <div className="space-y-6">
      <div className="bg-slate-900/50 border border-slate-800/50 rounded-2xl p-6">
        <h3 className="text-white font-semibold mb-5 flex items-center gap-2">
          <Building2 size={16} className="text-violet-400" /> Tenant Information
        </h3>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-xs text-slate-400 block mb-1.5">Organization Name</label>
            <input
              type="text"
              value={tenantName}
              onChange={(e) => setTenantName(e.target.value)}
              className="w-full px-3 py-2.5 bg-slate-800 border border-slate-700/50 rounded-xl text-sm text-white focus:outline-none focus:border-violet-500/50"
            />
          </div>
          <div>
            <label className="text-xs text-slate-400 block mb-1.5">Plan</label>
            <div className="px-3 py-2.5 bg-slate-800/50 border border-slate-700/30 rounded-xl">
              <span className="text-sm text-white">{plan}</span>
              <span className="ml-2 px-2 py-0.5 rounded-md text-[10px] bg-violet-500/20 border border-violet-500/30 text-violet-400">Active</span>
            </div>
          </div>
          <div>
            <label className="text-xs text-slate-400 block mb-1.5">Timezone</label>
            <select
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
              className="w-full px-3 py-2.5 bg-slate-800 border border-slate-700/50 rounded-xl text-sm text-white focus:outline-none focus:border-violet-500/50"
            >
              <option value="Asia/Kolkata">Asia/Kolkata (IST)</option>
              <option value="UTC">UTC</option>
              <option value="America/New_York">America/New_York (EST)</option>
              <option value="America/Los_Angeles">America/Los_Angeles (PST)</option>
              <option value="Europe/London">Europe/London (GMT)</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-slate-400 block mb-1.5">Language</label>
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="w-full px-3 py-2.5 bg-slate-800 border border-slate-700/50 rounded-xl text-sm text-white focus:outline-none focus:border-violet-500/50"
            >
              <option value="en">English</option>
              <option value="hi">Hindi</option>
              <option value="fr">French</option>
              <option value="de">German</option>
            </select>
          </div>
        </div>
      </div>

      {/* Usage Stats */}
      <div className="bg-slate-900/50 border border-slate-800/50 rounded-2xl p-6">
        <h3 className="text-white font-semibold mb-5 flex items-center gap-2">
          <Zap size={16} className="text-violet-400" /> Plan Usage
        </h3>
        <div className="grid grid-cols-3 gap-4">
          {[
            { label: "Workflow Runs / Month", used: 127, limit: 500, unit: "runs" },
            { label: "Agent Compute Hours", used: 48, limit: 200, unit: "hours" },
            { label: "Storage Used", used: 2.4, limit: 50, unit: "GB" },
          ].map(({ label, used, limit, unit }) => (
            <div key={label} className="bg-slate-800/30 rounded-xl p-4">
              <div className="text-[11px] text-slate-400 mb-2">{label}</div>
              <div className="flex justify-between items-center mb-2">
                <span className="text-white font-semibold">{used} {unit}</span>
                <span className="text-slate-500 text-xs">/ {limit} {unit}</span>
              </div>
              <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-violet-600 to-indigo-600 transition-all"
                  style={{ width: `${Math.min((used / limit) * 100, 100)}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      <button
        onClick={handleSave}
        disabled={saving}
        className="px-6 py-2.5 bg-gradient-to-r from-violet-600 to-indigo-600 rounded-xl text-white text-sm font-medium disabled:opacity-50 transition-all"
      >
        {saving ? "Saving..." : "Save Changes"}
      </button>
    </div>
  );
}

function TeamTab() {
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("AGENT_OPERATOR");

  return (
    <div className="space-y-4">
      {/* Invite Bar */}
      <div className="bg-slate-900/50 border border-slate-800/50 rounded-2xl p-5">
        <h3 className="text-white font-semibold mb-4">Invite Team Member</h3>
        <div className="flex gap-3">
          <input
            type="email"
            value={inviteEmail}
            onChange={(e) => setInviteEmail(e.target.value)}
            placeholder="colleague@company.com"
            className="flex-1 px-3 py-2.5 bg-slate-800 border border-slate-700/50 rounded-xl text-sm text-white placeholder-slate-600 focus:outline-none focus:border-violet-500/50"
          />
          <select
            value={inviteRole}
            onChange={(e) => setInviteRole(e.target.value)}
            className="px-3 py-2.5 bg-slate-800 border border-slate-700/50 rounded-xl text-sm text-white focus:outline-none focus:border-violet-500/50"
          >
            {Object.entries(ROLE_CONFIG).filter(([k]) => k !== "SUPERADMIN").map(([key, val]) => (
              <option key={key} value={key}>{val.label}</option>
            ))}
          </select>
          <button
            onClick={() => { toast.success("Invitation sent!"); setInviteEmail(""); }}
            disabled={!inviteEmail.trim()}
            className="px-4 py-2.5 bg-violet-600 rounded-xl text-white text-sm font-medium disabled:opacity-50"
          >
            Invite
          </button>
        </div>
      </div>

      {/* Team Members */}
      <div className="bg-slate-900/50 border border-slate-800/50 rounded-2xl overflow-hidden">
        <div className="px-6 py-3 border-b border-slate-800/50 grid grid-cols-12 text-xs text-slate-500 font-medium">
          <div className="col-span-4">Member</div>
          <div className="col-span-3">Role</div>
          <div className="col-span-3">Last Active</div>
          <div className="col-span-2 text-right">Actions</div>
        </div>
        <div className="divide-y divide-slate-800/50">
          {MOCK_TEAM.map((member) => {
            const roleConfig = ROLE_CONFIG[member.role] || ROLE_CONFIG.AUDITOR;
            return (
              <div key={member.id} className="px-6 py-4 grid grid-cols-12 items-center hover:bg-slate-800/20 transition-all">
                <div className="col-span-4 flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center text-white text-xs font-bold">
                    {member.name.split(" ").map(n => n[0]).join("").slice(0, 2)}
                  </div>
                  <div>
                    <div className="text-sm text-white font-medium">{member.name}</div>
                    <div className="text-[10px] text-slate-500">{member.email}</div>
                  </div>
                </div>
                <div className="col-span-3">
                  <span className={`px-2 py-0.5 rounded-md text-[10px] font-medium border ${roleConfig.bg} ${roleConfig.color}`}>
                    {roleConfig.label}
                  </span>
                </div>
                <div className="col-span-3 text-xs text-slate-500">
                  {formatDistanceToNow(new Date(member.last_active), { addSuffix: true })}
                </div>
                <div className="col-span-2 text-right">
                  <button
                    onClick={() => toast("Role management coming soon")}
                    className="text-[11px] text-violet-400 hover:underline"
                  >
                    Edit role
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function ApiKeysTab() {
  const [showNew, setShowNew] = useState(false);
  const [newKeyName, setNewKeyName] = useState("");
  const [generatedKey, setGeneratedKey] = useState<string | null>(null);
  const [showKeyIds, setShowKeyIds] = useState<Set<string>>(new Set());

  const handleGenerate = () => {
    const key = `ag_live_${Math.random().toString(36).slice(2)}${Math.random().toString(36).slice(2)}`;
    setGeneratedKey(key);
    toast.success("API key generated — copy it now, it won't be shown again!");
  };

  const copyKey = (key: string) => {
    navigator.clipboard.writeText(key);
    toast.success("Copied to clipboard!");
  };

  return (
    <div className="space-y-4">
      {/* Generated Key Banner */}
      {generatedKey && (
        <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-2xl p-5">
          <div className="flex items-center gap-2 mb-3 text-emerald-400">
            <Key size={14} />
            <span className="text-sm font-semibold">New API Key Generated</span>
          </div>
          <div className="flex items-center gap-3">
            <code className="flex-1 px-3 py-2 bg-slate-900 rounded-lg text-xs font-mono text-emerald-300 break-all">
              {generatedKey}
            </code>
            <button
              onClick={() => copyKey(generatedKey)}
              className="p-2 bg-emerald-500/20 rounded-lg text-emerald-400 hover:bg-emerald-500/30 transition-all flex-shrink-0"
            >
              <Copy size={14} />
            </button>
          </div>
          <p className="text-emerald-600 text-xs mt-2">⚠ Copy this key now — it will not be shown again.</p>
        </div>
      )}

      {/* Create New Key */}
      <div className="bg-slate-900/50 border border-slate-800/50 rounded-2xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-white font-semibold">API Keys</h3>
          <button
            onClick={() => setShowNew(!showNew)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-violet-500/10 border border-violet-500/20 rounded-lg text-violet-400 text-xs hover:bg-violet-500/20 transition-all"
          >
            <Plus size={12} /> New Key
          </button>
        </div>

        {showNew && (
          <div className="mb-4 p-4 bg-slate-800/30 rounded-xl">
            <label className="text-xs text-slate-400 block mb-2">Key Name</label>
            <div className="flex gap-3">
              <input
                type="text"
                value={newKeyName}
                onChange={(e) => setNewKeyName(e.target.value)}
                placeholder="e.g., Production Integration"
                className="flex-1 px-3 py-2 bg-slate-800 border border-slate-700/50 rounded-lg text-sm text-white placeholder-slate-600 focus:outline-none focus:border-violet-500/50"
              />
              <button
                onClick={handleGenerate}
                disabled={!newKeyName.trim()}
                className="px-4 py-2 bg-violet-600 rounded-lg text-white text-sm font-medium disabled:opacity-50"
              >
                Generate
              </button>
            </div>
          </div>
        )}

        {/* Existing Keys List */}
        <div className="divide-y divide-slate-800/50">
          {MOCK_API_KEYS.map((key) => (
            <div key={key.id} className="py-4 flex items-center gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-sm text-white font-medium">{key.name}</span>
                </div>
                <div className="flex items-center gap-3 text-[10px] text-slate-500">
                  <code className="font-mono">{key.prefix}••••••••••••</code>
                  <span>Created {formatDistanceToNow(new Date(key.created_at), { addSuffix: true })}</span>
                  {key.last_used && <span>Last used {formatDistanceToNow(new Date(key.last_used), { addSuffix: true })}</span>}
                  {!key.last_used && <span className="text-slate-600">Never used</span>}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => toast.error("Are you sure you want to revoke this key?")}
                  className="p-1.5 rounded-lg text-red-500/50 hover:text-red-400 hover:bg-red-500/10 transition-all"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function NotificationsTab() {
  const [settings, setSettings] = useState({
    email_sla_breach: true,
    email_agent_failure: true,
    slack_sla_breach: false,
    slack_task_created: true,
    push_escalations: true,
    digest_daily: true,
    digest_weekly: false,
  });

  const toggle = (key: keyof typeof settings) => {
    setSettings(prev => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <div className="space-y-4">
      <div className="bg-slate-900/50 border border-slate-800/50 rounded-2xl p-6">
        <h3 className="text-white font-semibold mb-5 flex items-center gap-2">
          <Bell size={16} className="text-violet-400" /> Notification Preferences
        </h3>
        <div className="space-y-4">
          {[
            { key: "email_sla_breach", label: "Email: SLA Breach Alert", desc: "Get emailed when a workflow is predicted to breach SLA" },
            { key: "email_agent_failure", label: "Email: Agent Failure Alert", desc: "Get emailed when an agent fails repeatedly" },
            { key: "slack_sla_breach", label: "Slack: SLA Breach", desc: "Slack message for SLA breach predictions" },
            { key: "slack_task_created", label: "Slack: Task Assigned", desc: "Slack message when a human task is assigned to you" },
            { key: "push_escalations", label: "Push: Escalations", desc: "Browser push notification for critical escalations" },
            { key: "digest_daily", label: "Daily Digest Email", desc: "Daily summary of workflow activity and SLA status" },
            { key: "digest_weekly", label: "Weekly Report", desc: "Weekly analytics report via email" },
          ].map(({ key, label, desc }) => (
            <div key={key} className="flex items-center justify-between py-3 border-b border-slate-800/30 last:border-0">
              <div>
                <div className="text-sm text-white">{label}</div>
                <div className="text-[11px] text-slate-500 mt-0.5">{desc}</div>
              </div>
              <button
                onClick={() => toggle(key as keyof typeof settings)}
                className={`relative w-11 h-6 rounded-full transition-all ${
                  settings[key as keyof typeof settings] ? "bg-violet-600" : "bg-slate-700"
                }`}
              >
                <div className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white transition-all ${
                  settings[key as keyof typeof settings] ? "translate-x-5" : "translate-x-0"
                }`} />
              </button>
            </div>
          ))}
        </div>
        <button
          onClick={() => toast.success("Notification preferences saved!")}
          className="mt-4 px-6 py-2.5 bg-gradient-to-r from-violet-600 to-indigo-600 rounded-xl text-white text-sm font-medium"
        >
          Save Preferences
        </button>
      </div>
    </div>
  );
}

function SecurityTab() {
  return (
    <div className="space-y-4">
      <div className="bg-slate-900/50 border border-slate-800/50 rounded-2xl p-6">
        <h3 className="text-white font-semibold mb-5 flex items-center gap-2">
          <Shield size={16} className="text-violet-400" /> Security Settings
        </h3>
        <div className="space-y-4">
          {[
            { label: "Two-Factor Authentication", desc: "Require 2FA for all team members", enabled: false, icon: Lock },
            { label: "SSO / SAML 2.0", desc: "Enterprise single sign-on via Okta, Azure AD, Google Workspace", enabled: false, icon: Globe },
            { label: "Audit Log Retention", desc: "Keep audit records for 365 days (hash-chained)", enabled: true, icon: Database },
            { label: "IP Allowlist", desc: "Restrict API access to specific IP ranges", enabled: false, icon: Shield },
          ].map(({ label, desc, enabled, icon: Icon }) => (
            <div key={label} className="flex items-center justify-between p-4 bg-slate-800/30 rounded-xl">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-slate-800 flex items-center justify-center">
                  <Icon size={15} className={enabled ? "text-violet-400" : "text-slate-500"} />
                </div>
                <div>
                  <div className="text-sm text-white">{label}</div>
                  <div className="text-[11px] text-slate-500 mt-0.5">{desc}</div>
                </div>
              </div>
              <div className="flex items-center gap-3">
                {enabled ? (
                  <span className="px-2 py-0.5 rounded-md text-[10px] bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">Enabled</span>
                ) : (
                  <span className="px-2 py-0.5 rounded-md text-[10px] bg-slate-700/50 border border-slate-600/30 text-slate-500">Disabled</span>
                )}
                <button className="text-violet-400 text-xs hover:underline" onClick={() => toast("Configuration coming soon")}>
                  Configure
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState("general");

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Settings</h1>
        <p className="text-slate-400 text-sm mt-1">Configure your AntiGravity tenant, team, and security preferences</p>
      </div>

      {/* Tabs + Content */}
      <div className="flex gap-6">
        {/* Side Nav */}
        <div className="w-52 flex-shrink-0 space-y-1">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all text-left ${
                activeTab === id
                  ? "bg-violet-600/20 text-violet-300 border border-violet-500/30"
                  : "text-slate-400 hover:text-white hover:bg-slate-800/50"
              }`}
            >
              <Icon size={15} className={activeTab === id ? "text-violet-400" : "text-slate-500"} />
              {label}
              {activeTab === id && <ChevronRight size={13} className="ml-auto text-violet-400" />}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          {activeTab === "general" && <GeneralTab />}
          {activeTab === "team" && <TeamTab />}
          {activeTab === "apikeys" && <ApiKeysTab />}
          {activeTab === "notifications" && <NotificationsTab />}
          {activeTab === "security" && <SecurityTab />}
        </div>
      </div>
    </div>
  );
}
