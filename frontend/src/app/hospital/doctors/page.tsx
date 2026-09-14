"use client";
import React from "react";
import { DashboardShell } from "@/components/dashboard/shell";
import { DataTable, StatusBadge, Column } from "@/components/dashboard/data-table";
import { HOSPITAL_NAV } from "@/lib/constants";
import { mockDoctors } from "@/lib/mock-data";
import { Doctor } from "@/types";
import { Plus } from "lucide-react";

const columns: Column<Doctor>[] = [
  { key: "name", label: "Doctor", sortable: true, render: (d) => (
    <div className="flex items-center gap-3">
      <div className="h-8 w-8 rounded-full bg-gradient-to-br from-purple-400 to-pink-400 flex items-center justify-center text-white text-xs font-bold">{d.name.split(" ").map(n=>n[0]).join("").slice(0,2)}</div>
      <div><p className="font-medium text-sm">{d.name}</p><p className="text-xs text-[hsl(var(--muted-foreground))]">{d.email}</p></div>
    </div>
  )},
  { key: "specialty", label: "Specialty", sortable: true },
  { key: "experience_years", label: "Experience", render: (d) => `${d.experience_years} yrs` },
  { key: "consultation_types", label: "Types", render: (d) => <span className="text-xs">{d.consultation_types.join(", ")}</span> },
  { key: "consultation_duration", label: "Duration", render: (d) => `${d.consultation_duration} min` },
  { key: "status", label: "Status", render: (d) => <StatusBadge status={d.status} /> },
];

export default function HospitalDoctorsPage() {
  const data = mockDoctors.filter(d => d.hospital_id === "h1");
  return (
    <DashboardShell navItems={HOSPITAL_NAV} sidebarTitle="City General Hospital" sidebarSubtitle="Hospital Admin" pageTitle="Doctors" pageSubtitle={`${data.length} doctors`}
      actions={<button className="flex items-center gap-2 rounded-lg bg-gradient-to-r from-blue-600 to-cyan-500 px-4 py-2 text-sm font-medium text-white hover:from-blue-700 hover:to-cyan-600 transition-all"><Plus className="h-4 w-4" />Add Doctor</button>}>
      <DataTable columns={columns} data={data} searchPlaceholder="Search doctors..." />
    </DashboardShell>
  );
}
