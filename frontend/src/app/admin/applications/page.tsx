"use client";

import React from "react";
import { DashboardShell } from "@/components/dashboard/shell";
import { DataTable, StatusBadge, Column } from "@/components/dashboard/data-table";
import { ADMIN_NAV } from "@/lib/constants";
import { mockHospitals } from "@/lib/mock-data";
import { Hospital } from "@/types";
import { formatDate } from "@/lib/utils";

const columns: Column<Hospital>[] = [
  { key: "name", label: "Hospital Name", sortable: true, render: (h) => <span className="font-medium">{h.name}</span> },
  { key: "city", label: "City", sortable: true },
  { key: "status", label: "Status", render: (h) => <StatusBadge status={h.status} /> },
  { key: "departments", label: "Departments", render: (h) => <span className="text-xs">{h.departments.length} depts</span> },
  { key: "created_at", label: "Registered", sortable: true, render: (h) => formatDate(h.created_at) },
  {
    key: "actions", label: "Actions",
    render: (h) => (
      <div className="flex gap-2">
        {h.status === "submitted" && (
          <>
            <button className="rounded-lg bg-emerald-100 px-3 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-200 transition-colors">Approve</button>
            <button className="rounded-lg bg-red-100 px-3 py-1 text-xs font-medium text-red-700 hover:bg-red-200 transition-colors">Reject</button>
          </>
        )}
        {h.status === "under_review" && (
          <button className="rounded-lg bg-blue-100 px-3 py-1 text-xs font-medium text-blue-700 hover:bg-blue-200 transition-colors">Review</button>
        )}
      </div>
    ),
  },
];

export default function ApplicationsPage() {
  const pendingHospitals = mockHospitals.filter(h => ["submitted", "under_review"].includes(h.status));
  return (
    <DashboardShell navItems={ADMIN_NAV} sidebarTitle="AI.Prof" sidebarSubtitle="Platform Admin" pageTitle="Hospital Applications" pageSubtitle={`${pendingHospitals.length} pending review`}>
      <DataTable columns={columns} data={mockHospitals} searchPlaceholder="Search hospitals..." emptyMessage="No hospital applications" />
    </DashboardShell>
  );
}
