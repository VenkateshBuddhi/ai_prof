"use client";
import React from "react";
import { DashboardShell } from "@/components/dashboard/shell";
import { DataTable, Column } from "@/components/dashboard/data-table";
import { ADMIN_NAV } from "@/lib/constants";
import { AuditEvent } from "@/types";
import { formatDateTime } from "@/lib/utils";
import { useAudit } from "@/lib/queries";
import { LiveBadge } from "@/components/dashboard/live-badge";

const columns: Column<AuditEvent>[] = [
  { key: "timestamp", label: "Time", sortable: true, render: (e) => <span className="text-xs font-mono">{formatDateTime(e.timestamp)}</span> },
  { key: "event_type", label: "Event", sortable: true, render: (e) => (
    <span className="inline-flex items-center gap-1.5 text-xs font-mono font-medium bg-[hsl(var(--muted))] px-2 py-0.5 rounded">
      {e.event_type}
    </span>
  )},
  { key: "actor_name", label: "Actor", render: (e) => <span className="font-medium text-sm">{e.actor_name}</span> },
  { key: "actor_role", label: "Role", render: (e) => <span className="capitalize text-xs">{e.actor_role.replace(/_/g, " ")}</span> },
  { key: "resource_type", label: "Resource", render: (e) => <span className="capitalize text-xs">{e.resource_type.replace(/_/g, " ")}</span> },
  { key: "resource_id", label: "Resource ID", render: (e) => <span className="text-xs font-mono">{e.resource_id}</span> },
  { key: "correlation_id", label: "Correlation ID", render: (e) => e.correlation_id ? <span className="text-xs font-mono text-blue-600">{e.correlation_id}</span> : "—" },
];

export default function AuditPage() {
  const { data: events, isLive, isLoading } = useAudit();
  return (
    <DashboardShell navItems={ADMIN_NAV} sidebarTitle="AI.Prof" sidebarSubtitle="Platform Admin" pageTitle="Audit Logs" pageSubtitle="Complete audit trail of platform operations">
      <div className="mb-4"><LiveBadge live={isLive} loading={isLoading} /></div>
      <DataTable columns={columns} data={events} searchPlaceholder="Search audit events..." />
    </DashboardShell>
  );
}
