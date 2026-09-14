"use client";
import React from "react";
import { DashboardShell } from "@/components/dashboard/shell";
import { DataTable, StatusBadge, Column } from "@/components/dashboard/data-table";
import { StatCard } from "@/components/dashboard/stat-card";
import { ADMIN_NAV } from "@/lib/constants";
import { mockEHROperations } from "@/lib/mock-data";
import { EHROperation } from "@/types";
import { formatDateTime } from "@/lib/utils";

const columns: Column<EHROperation>[] = [
  { key: "hospital_name", label: "Hospital", sortable: true, render: (o) => <span className="font-medium">{o.hospital_name}</span> },
  { key: "operation_type", label: "Operation", render: (o) => <span className="capitalize text-xs">{o.operation_type.replace(/_/g, " ")}</span> },
  { key: "connector", label: "Connector", render: (o) => <span className="text-xs font-mono bg-[hsl(var(--muted))] px-1.5 py-0.5 rounded">{o.connector}</span> },
  { key: "external_id", label: "External ID", render: (o) => o.external_id ? <span className="text-xs font-mono">{o.external_id}</span> : "—" },
  { key: "status", label: "Status", render: (o) => <StatusBadge status={o.status} /> },
  { key: "verification_status", label: "Verification", render: (o) => o.verification_status ? <StatusBadge status={o.verification_status} /> : "—" },
  { key: "duration_ms", label: "Duration", render: (o) => `${o.duration_ms}ms` },
  { key: "retries", label: "Retries" },
  { key: "created_at", label: "Time", sortable: true, render: (o) => formatDateTime(o.created_at) },
];

export default function IntegrationsPage() {
  const success = mockEHROperations.filter(o => o.status === "success").length;
  const failed = mockEHROperations.filter(o => o.status === "failure").length;
  const avgDuration = Math.round(mockEHROperations.reduce((s, o) => s + o.duration_ms, 0) / mockEHROperations.length);

  return (
    <DashboardShell navItems={ADMIN_NAV} sidebarTitle="AI.Prof" sidebarSubtitle="Platform Admin" pageTitle="EHR / Integration Activity" pageSubtitle="Healthcare system integration operations">
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 mb-6">
        <StatCard title="Total Operations" value={mockEHROperations.length} icon="Link2" color="blue" />
        <StatCard title="Successful" value={success} icon="CheckCircle" color="emerald" />
        <StatCard title="Failed" value={failed} icon="XCircle" color="rose" />
        <StatCard title="Avg Duration" value={`${avgDuration}ms`} icon="Zap" color="teal" />
      </div>
      <DataTable columns={columns} data={mockEHROperations} searchPlaceholder="Search operations..." />
    </DashboardShell>
  );
}
