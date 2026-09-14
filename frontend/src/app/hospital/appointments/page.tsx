"use client";
import React from "react";
import { DashboardShell } from "@/components/dashboard/shell";
import { DataTable, StatusBadge, Column } from "@/components/dashboard/data-table";
import { HOSPITAL_NAV } from "@/lib/constants";
import { mockAppointments } from "@/lib/mock-data";
import { Appointment } from "@/types";
import { formatDate } from "@/lib/utils";

const columns: Column<Appointment>[] = [
  { key: "patient_name", label: "Patient", sortable: true, render: (a) => <span className="font-medium">{a.patient_name}</span> },
  { key: "doctor_name", label: "Doctor", sortable: true },
  { key: "specialty", label: "Specialty" },
  { key: "date", label: "Date", sortable: true, render: (a) => formatDate(a.date) },
  { key: "time", label: "Time" },
  { key: "appointment_type", label: "Type", render: (a) => <span className="text-xs">{a.appointment_type}</span> },
  { key: "status", label: "Status", render: (a) => <StatusBadge status={a.status} /> },
  { key: "questionnaire_status", label: "Questionnaire", render: (a) => a.questionnaire_status ? <StatusBadge status={a.questionnaire_status} /> : "—" },
];

export default function HospitalAppointmentsPage() {
  const data = mockAppointments.filter(a => a.hospital_id === "h1");
  return (
    <DashboardShell navItems={HOSPITAL_NAV} sidebarTitle="City General Hospital" sidebarSubtitle="Hospital Admin" pageTitle="Appointments" pageSubtitle={`${data.length} appointments`}>
      <DataTable columns={columns} data={data} searchPlaceholder="Search appointments..." />
    </DashboardShell>
  );
}
