"use client";
import React from "react";
import { DashboardShell } from "@/components/dashboard/shell";
import { DataTable, StatusBadge, Column } from "@/components/dashboard/data-table";
import { ADMIN_NAV } from "@/lib/constants";
import { Appointment } from "@/types";
import { formatDate } from "@/lib/utils";
import { useAppointments } from "@/lib/queries";
import { LiveBadge } from "@/components/dashboard/live-badge";

const columns: Column<Appointment>[] = [
  { key: "patient_name", label: "Patient", sortable: true, render: (a) => <span className="font-medium">{a.patient_name}</span> },
  { key: "doctor_name", label: "Doctor", sortable: true },
  { key: "hospital_name", label: "Hospital", sortable: true },
  { key: "specialty", label: "Specialty" },
  { key: "date", label: "Date", sortable: true, render: (a) => formatDate(a.date) },
  { key: "time", label: "Time" },
  { key: "status", label: "Status", render: (a) => <StatusBadge status={a.status} /> },
  { key: "ehr_sync_status", label: "EHR", render: (a) => a.ehr_sync_status ? <StatusBadge status={a.ehr_sync_status} /> : <span className="text-xs text-[hsl(var(--muted-foreground))]">—</span> },
];

export default function AppointmentsPage() {
  const { data: appointments, isLive, isLoading } = useAppointments();
  return (
    <DashboardShell navItems={ADMIN_NAV} sidebarTitle="AI.Prof" sidebarSubtitle="Platform Admin" pageTitle="Appointments" pageSubtitle="All appointments across hospitals">
      <div className="mb-4"><LiveBadge live={isLive} loading={isLoading} /></div>
      <DataTable columns={columns} data={appointments} searchPlaceholder="Search appointments..." />
    </DashboardShell>
  );
}
