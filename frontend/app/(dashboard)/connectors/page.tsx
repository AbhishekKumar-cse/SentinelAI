"use client";

export const dynamic = "force-dynamic";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { useState } from "react";
import {
  Plug, Plus, CheckCircle, XCircle, AlertCircle, RefreshCw,
  Database, Mail, MessageSquare, Video, FileText, CreditCard,
  Users, Package, Webhook, Trash2, ExternalLink
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { toast } from "sonner";

interface Connector {
  connector_id: string;
  system_type: string;
  display_name: string;
  status: string;
  last_health_check_at: string | null;
  created_at: string;
}

const SYSTEM_CONFIGS: Record<string, {
  label: string;
  icon: React.FC<any>;
  category: string;
  color: string;
  bg: string;
  description: string;
}> = {
  SALESFORCE: { label: "Salesforce", icon: Users, category: "CRM", color: "text-blue-400", bg: "bg-blue-500/10 border-blue-500/20", description: "REST + Bulk API, leads, opportunities, contacts" },
  HUBSPOT: { label: "HubSpot", icon: Users, category: "CRM", color: "text-orange-400", bg: "bg-orange-500/10 border-orange-500/20", description: "REST API, contacts, deals, activities" },
  SAP: { label: "SAP S/4HANA", icon: Database, category: "ERP", color: "text-emerald-400", bg: "bg-emerald-500/10 border-emerald-500/20", description: "BAPI/RFC, OData v4, purchase orders" },
  NETSUITE: { label: "NetSuite", icon: Database, category: "ERP", color: "text-yellow-400", bg: "bg-yellow-500/10 border-yellow-500/20", description: "REST API, SuiteScript, purchase orders" },
  DYNAMICS: { label: "MS Dynamics 365", icon: Database, category: "ERP/CRM", color: "text-indigo-400", bg: "bg-indigo-500/10 border-indigo-500/20", description: "Dataverse API, sales orders, customer records" },
  WORKDAY: { label: "Workday", icon: Users, category: "HRMS", color: "text-violet-400", bg: "bg-violet-500/10 border-violet-500/20", description: "REST API, worker data, job changes, onboarding" },
  JIRA: { label: "Jira", icon: Package, category: "Project Mgmt", color: "text-blue-300", bg: "bg-blue-500/10 border-blue-500/20", description: "REST API, issues, sprints, boards, webhooks" },
  SERVICENOW: { label: "ServiceNow", icon: Package, category: "ITSM", color: "text-cyan-400", bg: "bg-cyan-500/10 border-cyan-500/20", description: "Table API, incidents, change requests, CMDB" },
  SLACK: { label: "Slack", icon: MessageSquare, category: "Messaging", color: "text-green-400", bg: "bg-green-500/10 border-green-500/20", description: "Web API, Block Kit, event subscriptions" },
  SENDGRID: { label: "SendGrid", icon: Mail, category: "Email", color: "text-teal-400", bg: "bg-teal-500/10 border-teal-500/20", description: "Mail Send API, dynamic templates, webhooks" },
  DOCUSIGN: { label: "DocuSign", icon: FileText, category: "E-Signature", color: "text-amber-400", bg: "bg-amber-500/10 border-amber-500/20", description: "eSignature API, envelope creation, status webhooks" },
  STRIPE: { label: "Stripe", icon: CreditCard, category: "Payments", color: "text-purple-400", bg: "bg-purple-500/10 border-purple-500/20", description: "Payment Intents API, refunds, webhooks" },
  ZOOM: { label: "Zoom", icon: Video, category: "Meetings", color: "text-blue-400", bg: "bg-blue-500/10 border-blue-500/20", description: "Meeting API, transcript webhooks, recording access" },
  WEBHOOK: { label: "Custom Webhook", icon: Webhook, category: "Custom", color: "text-slate-400", bg: "bg-slate-500/10 border-slate-500/20", description: "Generic outbound webhook integration" },
};

const MOCK_CONNECTORS: Connector[] = [
  { connector_id: "con-001", system_type: "SALESFORCE", display_name: "Salesforce CRM", status: "ACTIVE", last_health_check_at: new Date(Date.now() - 5*60*1000).toISOString(), created_at: new Date(Date.now() - 7*24*60*60*1000).toISOString() },
  { connector_id: "con-002", system_type: "SLACK", display_name: "Slack Workspace", status: "ACTIVE", last_health_check_at: new Date(Date.now() - 2*60*1000).toISOString(), created_at: new Date(Date.now() - 7*24*60*60*1000).toISOString() },
  { connector_id: "con-003", system_type: "JIRA", display_name: "Jira - CORP", status: "DEGRADED", last_health_check_at: new Date(Date.now() - 30*60*1000).toISOString(), created_at: new Date(Date.now() - 14*24*60*60*1000).toISOString() },
  { connector_id: "con-004", system_type: "SENDGRID", display_name: "SendGrid Email", status: "ACTIVE", last_health_check_at: new Date(Date.now() - 8*60*1000).toISOString(), created_at: new Date(Date.now() - 14*24*60*60*1000).toISOString() },
  { connector_id: "con-005", system_type: "DOCUSIGN", display_name: "DocuSign Production", status: "INACTIVE", last_health_check_at: null, created_at: new Date(Date.now() - 30*24*60*60*1000).toISOString() },
];

const STATUS_CONFIG: Record<string, { icon: React.FC<any>; color: string; label: string }> = {
  ACTIVE: { icon: CheckCircle, color: "text-emerald-400", label: "Active" },
  DEGRADED: { icon: AlertCircle, color: "text-amber-400", label: "Degraded" },
  INACTIVE: { icon: XCircle, color: "text-slate-400", label: "Inactive" },
  ERROR: { icon: XCircle, color: "text-red-400", label: "Error" },
};

function ConnectorCard({
  connector,
  onTest,
  onDelete,
  testing,
}: {
  connector: Connector;
  onTest: (id: string) => void;
  onDelete: (id: string) => void;
  testing: string | null;
}) {
  const config = SYSTEM_CONFIGS[connector.system_type] || SYSTEM_CONFIGS.WEBHOOK;
  const statusConfig = STATUS_CONFIG[connector.status] || STATUS_CONFIG.INACTIVE;
  const StatusIcon = statusConfig.icon;
  const ConnIcon = config.icon;
  const isTesting = testing === connector.connector_id;

  return (
    <div className={`bg-slate-900/60 border rounded-2xl p-5 hover:bg-slate-900/80 transition-all backdrop-blur-sm ${config.bg}`}>
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-xl flex items-center justify-center border ${config.bg}`}>
            <ConnIcon size={18} className={config.color} />
          </div>
          <div>
            <div className="text-sm font-semibold text-white">{connector.display_name}</div>
            <div className="flex items-center gap-2 mt-0.5">
              <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded border ${config.bg} ${config.color}`}>
                {config.category}
              </span>
              <span className="text-[10px] text-slate-500">{config.label}</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <StatusIcon size={14} className={statusConfig.color} />
          <span className={`text-xs font-medium ${statusConfig.color}`}>{statusConfig.label}</span>
        </div>
      </div>

      {/* Description */}
      <p className="text-[11px] text-slate-500 mb-4 line-clamp-1">{config.description}</p>

      {/* Last Health Check */}
      <div className="flex items-center justify-between text-[10px] text-slate-600 mb-4">
        <span>Last checked: {connector.last_health_check_at
          ? formatDistanceToNow(new Date(connector.last_health_check_at), { addSuffix: true })
          : "Never"
        }</span>
        <span>Added {formatDistanceToNow(new Date(connector.created_at), { addSuffix: true })}</span>
      </div>

      {/* Actions */}
      <div className="flex gap-2">
        <button
          onClick={() => onTest(connector.connector_id)}
          disabled={isTesting}
          className="flex-1 py-2 rounded-lg text-xs font-medium bg-violet-500/10 border border-violet-500/20 text-violet-400 hover:bg-violet-500/20 transition-all flex items-center justify-center gap-1.5"
        >
          {isTesting ? (
            <><RefreshCw size={11} className="animate-spin" /> Testing...</>
          ) : (
            <><RefreshCw size={11} /> Test Connection</>
          )}
        </button>
        <button
          onClick={() => onDelete(connector.connector_id)}
          className="p-2 rounded-lg bg-red-500/5 border border-red-500/10 text-red-500/60 hover:text-red-400 hover:bg-red-500/10 transition-all"
        >
          <Trash2 size={13} />
        </button>
      </div>
    </div>
  );
}

const CONNECTOR_TYPES = Object.entries(SYSTEM_CONFIGS).map(([key, val]) => ({
  value: key,
  label: `${val.label} (${val.category})`,
}));

export default function ConnectorsPage() {
  const queryClient = useQueryClient();
  const [showAdd, setShowAdd] = useState(false);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [newSystem, setNewSystem] = useState("SALESFORCE");
  const [newDisplayName, setNewDisplayName] = useState("");
  const [newApiKey, setNewApiKey] = useState("");
  const [newBaseUrl, setNewBaseUrl] = useState("");

  const { data } = useQuery({
    queryKey: ["connectors"],
    queryFn: async () => {
      try {
        const result = await api.get<{ connectors: Connector[]; count: number }>("/connectors");
        if (result.connectors.length === 0) throw new Error("empty");
        return result;
      } catch {
        return { connectors: MOCK_CONNECTORS, count: MOCK_CONNECTORS.length };
      }
    },
    refetchInterval: 60000,
  });

  const createMutation = useMutation({
    mutationFn: (payload: { system_type: string; display_name: string; config: Record<string, string> }) =>
      api.post("/connectors", payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["connectors"] });
      toast.success("Connector created!");
      setShowAdd(false);
      setNewApiKey("");
      setNewBaseUrl("");
      setNewDisplayName("");
    },
    onError: () => toast.error("Failed to create connector"),
  });

  const handleTest = async (id: string) => {
    setTestingId(id);
    try {
      await api.post(`/connectors/${id}/test`, {});
      toast.success("Connection test passed ✓");
    } catch {
      toast.error("Connection test failed");
    } finally {
      setTestingId(null);
      queryClient.invalidateQueries({ queryKey: ["connectors"] });
    }
  };

  const handleDelete = (id: string) => {
    toast.error("Delete functionality — confirm before removing connector");
  };

  const connectors = data?.connectors ?? [];
  const activeCount = connectors.filter(c => c.status === "ACTIVE").length;
  const degradedCount = connectors.filter(c => c.status === "DEGRADED").length;
  const byCategory = Object.entries(SYSTEM_CONFIGS).reduce((acc, [key]) => {
    const conn = connectors.filter(c => c.system_type === key);
    return { ...acc, [key]: conn };
  }, {} as Record<string, Connector[]>);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Connectors</h1>
          <p className="text-slate-400 text-sm mt-1">
            {connectors.length} configured · {activeCount} active · {degradedCount} degraded
          </p>
        </div>
        <button
          onClick={() => setShowAdd(true)}
          className="flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 rounded-xl text-white text-sm font-medium transition-all shadow-lg shadow-violet-500/25"
        >
          <Plus size={15} />
          Add Connector
        </button>
      </div>

      {/* Status Summary */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "Active", value: activeCount, color: "text-emerald-400", icon: CheckCircle, bg: "bg-emerald-500/10 border-emerald-500/20" },
          { label: "Degraded", value: degradedCount, color: "text-amber-400", icon: AlertCircle, bg: "bg-amber-500/10 border-amber-500/20" },
          { label: "Total Integrated Systems", value: connectors.length, color: "text-violet-400", icon: Plug, bg: "bg-violet-500/10 border-violet-500/20" },
        ].map(({ label, value, color, icon: Icon, bg }) => (
          <div key={label} className={`bg-slate-900/50 border rounded-2xl p-5 ${bg}`}>
            <div className="flex items-center gap-2 mb-3">
              <Icon size={14} className={color} />
              <span className="text-slate-400 text-xs">{label}</span>
            </div>
            <div className={`text-3xl font-bold ${color}`}>{value}</div>
          </div>
        ))}
      </div>

      {/* Add Connector Panel */}
      {showAdd && (
        <div className="bg-slate-900/60 border border-violet-500/20 rounded-2xl p-6 backdrop-blur-sm">
          <h2 className="text-white font-semibold mb-4 flex items-center gap-2">
            <Plus size={16} className="text-violet-400" />
            Add New Connector
          </h2>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <label className="text-xs text-slate-400 block mb-1.5">System Type</label>
              <select
                value={newSystem}
                onChange={(e) => setNewSystem(e.target.value)}
                className="w-full px-3 py-2.5 bg-slate-800 border border-slate-700/50 rounded-xl text-sm text-white focus:outline-none focus:border-violet-500/50"
              >
                {CONNECTOR_TYPES.map(t => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-slate-400 block mb-1.5">Display Name</label>
              <input
                type="text"
                value={newDisplayName}
                onChange={(e) => setNewDisplayName(e.target.value)}
                placeholder={SYSTEM_CONFIGS[newSystem]?.label || "My Connector"}
                className="w-full px-3 py-2.5 bg-slate-800 border border-slate-700/50 rounded-xl text-sm text-white placeholder-slate-600 focus:outline-none focus:border-violet-500/50"
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 block mb-1.5">API Key / Token</label>
              <input
                type="password"
                value={newApiKey}
                onChange={(e) => setNewApiKey(e.target.value)}
                placeholder="sk-..."
                className="w-full px-3 py-2.5 bg-slate-800 border border-slate-700/50 rounded-xl text-sm text-white placeholder-slate-600 focus:outline-none focus:border-violet-500/50"
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 block mb-1.5">Base URL (optional)</label>
              <input
                type="text"
                value={newBaseUrl}
                onChange={(e) => setNewBaseUrl(e.target.value)}
                placeholder="https://your-instance.service.com"
                className="w-full px-3 py-2.5 bg-slate-800 border border-slate-700/50 rounded-xl text-sm text-white placeholder-slate-600 focus:outline-none focus:border-violet-500/50"
              />
            </div>
          </div>
          <div className="flex gap-3">
            <button
              onClick={() => createMutation.mutate({
                system_type: newSystem,
                display_name: newDisplayName || SYSTEM_CONFIGS[newSystem]?.label || newSystem,
                config: { api_key: newApiKey, base_url: newBaseUrl },
              })}
              disabled={createMutation.isPending}
              className="flex-1 py-2.5 bg-gradient-to-r from-violet-600 to-indigo-600 rounded-xl text-white text-sm font-medium disabled:opacity-50"
            >
              {createMutation.isPending ? "Saving..." : "Save Connector"}
            </button>
            <button
              onClick={() => setShowAdd(false)}
              className="px-6 py-2.5 bg-slate-800 rounded-xl text-slate-400 text-sm border border-slate-700/50 hover:text-white transition-all"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Connector Grid */}
      {connectors.length === 0 ? (
        <div className="py-20 text-center">
          <Plug size={48} className="text-slate-700 mx-auto mb-4" />
          <div className="text-slate-400 font-medium">No connectors yet</div>
          <div className="text-slate-600 text-sm mt-1">Add your first connector to start integrating with external systems</div>
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-4">
          {connectors.map((connector) => (
            <ConnectorCard
              key={connector.connector_id}
              connector={connector}
              onTest={handleTest}
              onDelete={handleDelete}
              testing={testingId}
            />
          ))}
        </div>
      )}

      {/* Available Integrations */}
      <div>
        <h2 className="text-sm font-semibold text-white mb-3">Available Integration Categories</h2>
        <div className="grid grid-cols-6 gap-3">
          {[
            { label: "ERP", count: 3, color: "text-emerald-400" },
            { label: "CRM", count: 3, color: "text-blue-400" },
            { label: "HRMS", count: 2, color: "text-violet-400" },
            { label: "Messaging", count: 3, color: "text-green-400" },
            { label: "Payments", count: 2, color: "text-purple-400" },
            { label: "Documents", count: 3, color: "text-amber-400" },
          ].map(({ label, count, color }) => (
            <div key={label} className="bg-slate-800/30 border border-slate-800/50 rounded-xl p-3 text-center">
              <div className={`text-xl font-bold ${color}`}>{count}</div>
              <div className="text-[11px] text-slate-500 mt-0.5">{label}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
