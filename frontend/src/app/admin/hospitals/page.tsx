"use client";
import React from "react";
import { DashboardShell } from "@/components/dashboard/shell";
import { DataTable, StatusBadge, Column } from "@/components/dashboard/data-table";
import { ADMIN_NAV } from "@/lib/constants";
import { Hospital } from "@/types";
import { formatDate } from "@/lib/utils";
import { useHospitals } from "@/lib/queries";
import { LiveBadge } from "@/components/dashboard/live-badge";

const columns: Column<Hospital>[] = [
  { key: "name", label: "Hospital", sortable: true, render: (h) => <span className="font-medium">{h.name}</span> },
  { key: "city", label: "City", sortable: true },
  { key: "state", label: "State", sortable: true },
  { key: "status", label: "Status", render: (h) => <StatusBadge status={h.status} /> },
  { key: "specialties", label: "Specialties", render: (h) => <span className="text-xs">{h.specialties.join(", ")}</span> },
  { key: "created_at", label: "Registered", sortable: true, render: (h) => formatDate(h.created_at) },
];

export default function HospitalsPage() {
  const { data: hospitals, isLive, isLoading } = useHospitals();
  return (
    <DashboardShell navItems={ADMIN_NAV} sidebarTitle="AI.Prof" sidebarSubtitle="Platform Admin" pageTitle="Hospitals" pageSubtitle={`${hospitals.length} hospitals registered`}>
      <div className="mb-4"><LiveBadge live={isLive} loading={isLoading} /></div>
      <DataTable columns={columns} data={hospitals} searchPlaceholder="Search hospitals..." />
    </DashboardShell>
  );
}
