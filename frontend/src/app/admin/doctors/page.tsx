"use client";
import React from "react";
import { DashboardShell } from "@/components/dashboard/shell";
import { DataTable, StatusBadge, Column } from "@/components/dashboard/data-table";
import { ADMIN_NAV } from "@/lib/constants";
import { mockDoctors } from "@/lib/mock-data";
import { Doctor } from "@/types";

const columns: Column<Doctor>[] = [
  { key: "name", label: "Doctor", sortable: true, render: (d) => (
    <div className="flex items-center gap-3">
      <div className="h-8 w-8 rounded-full bg-gradient-to-br from-blue-400 to-cyan-400 flex items-center justify-center text-white text-xs font-bold">{d.name.split(" ").map(n=>n[0]).join("").slice(0,2)}</div>
      <div><p className="font-medium text-sm">{d.name}</p><p className="text-xs text-[hsl(var(--muted-foreground))]">{d.email}</p></div>
    </div>
  )},
  { key: "specialty", label: "Specialty", sortable: true },
  { key: "hospital_name", label: "Hospital", sortable: true },
  { key: "experience_years", label: "Experience", render: (d) => `${d.experience_years} yrs` },
  { key: "consultation_duration", label: "Duration", render: (d) => `${d.consultation_duration} min` },
  { key: "status", label: "Status", render: (d) => <StatusBadge status={d.status} /> },
];

export default function DoctorsPage() {
  return (
    <DashboardShell navItems={ADMIN_NAV} sidebarTitle="AI.Prof" sidebarSubtitle="Platform Admin" pageTitle="Doctors" pageSubtitle={`${mockDoctors.length} doctors across all hospitals`}>
      <DataTable columns={columns} data={mockDoctors} searchPlaceholder="Search doctors..." />
    </DashboardShell>
  );
}
