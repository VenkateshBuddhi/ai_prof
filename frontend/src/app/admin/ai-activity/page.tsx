"use client";
import React from "react";
import { DashboardShell } from "@/components/dashboard/shell";
import { DataTable, StatusBadge, Column } from "@/components/dashboard/data-table";
import { StatCard } from "@/components/dashboard/stat-card";
import { ADMIN_NAV } from "@/lib/constants";
import { useAiActivity } from "@/lib/queries";
import { formatDateTime } from "@/lib/utils";
import { LiveBadge } from "@/components/dashboard/live-badge";

const columns: Column<any>[] = [
  { key: "patient_name", label: "Patient", sortable: true, render: (c) => <span className="font-medium">{c.patient_name}</span> },
  { key: "channel", label: "Channel", render: (c) => (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium capitalize rounded-full px-2 py-0.5 bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
      {c.channel === "web_voice" ? "🎤 Web Voice" : "📞 Phone"}
    </span>
  )},
  { key: "duration_seconds", label: "Duration", render: (c) => c.duration_seconds ? `${Math.floor(c.duration_seconds / 60)}m ${c.duration_seconds % 60}s` : "—" },
  { key: "intents_detected", label: "Intents", render: (c) => <span className="text-xs">{c.intents_detected?.join(", ")}</span> },
  { key: "capabilities_used", label: "Capabilities", render: (c) => <span className="text-xs">{(c.capabilities_used || []).length} tools</span> },
  { key: "outcome", label: "Outcome", render: (c) => <span className="text-xs">{c.outcome}</span> },
  { key: "escalated", label: "Escalated", render: (c) => c.escalated ? <StatusBadge status="failed" /> : <StatusBadge status="completed" /> },
  { key: "started_at", label: "Started", sortable: true, render: (c) => formatDateTime(c.started_at) },
];

export default function AIActivityPage() {
  const { data: auditEvents, isLive, isLoading } = useAiActivity();

  // Parse AuditEvent into AIConversation shape
  const conversations = auditEvents.map((a: any) => {
    let details: any = {};
    try {
      if (a.details?.outcome) details = JSON.parse(a.details.outcome);
    } catch (e) {}

    return {
      id: a.id,
      patient_name: a.actor_name,
      channel: "web_voice",
      duration_seconds: details.duration_s || 0,
      intents_detected: details.intents || ["booking"],
      capabilities_used: details.tools ? Object.keys(details.tools) : [],
      outcome: "processed",
      escalated: !!details.tools?.transfer_to_human,
      started_at: a.timestamp
    };
  });

  const totalConversations = conversations.length;
  const escalated = conversations.filter((c: any) => c.escalated).length;
  const avgDuration = totalConversations > 0 ? Math.round(conversations.reduce((s: number, c: any) => s + (c.duration_seconds || 0), 0) / totalConversations) : 0;

  return (
    <DashboardShell navItems={ADMIN_NAV} sidebarTitle="AI.Prof" sidebarSubtitle="Platform Admin" pageTitle="AI Activity" pageSubtitle="Conversational AI interactions">
      <div className="mb-6"><LiveBadge live={isLive} loading={isLoading} /></div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <StatCard title="Total Conversations" value={totalConversations} icon="Bot" color="blue" />
        <StatCard title="Avg Duration" value={`${Math.floor(avgDuration / 60)}m ${avgDuration % 60}s`} icon="Clock" color="teal" />
        <StatCard title="Escalations" value={escalated} icon="AlertCircle" color="rose" />
      </div>
      <DataTable columns={columns} data={conversations} searchPlaceholder="Search conversations..." />
    </DashboardShell>
  );
}
