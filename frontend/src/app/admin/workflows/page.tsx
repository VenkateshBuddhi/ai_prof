"use client";
import React from "react";
import { DashboardShell } from "@/components/dashboard/shell";
import { DataTable, StatusBadge, Column } from "@/components/dashboard/data-table";
import { ADMIN_NAV } from "@/lib/constants";
import { mockWorkflows } from "@/lib/mock-data";
import { Workflow } from "@/types";
import { formatDateTime } from "@/lib/utils";

const columns: Column<Workflow>[] = [
  { key: "type", label: "Workflow", sortable: true, render: (w) => <span className="font-medium capitalize">{w.type.replace(/_/g, " ")}</span> },
  { key: "status", label: "Status", render: (w) => <StatusBadge status={w.status} /> },
  { key: "trigger", label: "Trigger", render: (w) => <span className="capitalize text-xs">{w.trigger.replace(/_/g, " ")}</span> },
  { key: "retries", label: "Retries" },
  { key: "error", label: "Error", render: (w) => w.error ? <span className="text-xs text-red-500">{w.error}</span> : "—" },
  { key: "started_at", label: "Started", sortable: true, render: (w) => formatDateTime(w.started_at) },
  { key: "completed_at", label: "Completed", render: (w) => w.completed_at ? formatDateTime(w.completed_at) : "—" },
];

export default function WorkflowsPage() {
  return (
    <DashboardShell navItems={ADMIN_NAV} sidebarTitle="AI.Prof" sidebarSubtitle="Platform Admin" pageTitle="Workflows" pageSubtitle="Background workflow executions">
      <DataTable columns={columns} data={mockWorkflows} searchPlaceholder="Search workflows..." />
    </DashboardShell>
  );
}
