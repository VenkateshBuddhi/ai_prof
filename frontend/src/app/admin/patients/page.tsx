"use client";
import React from "react";
import { DashboardShell } from "@/components/dashboard/shell";
import { DataTable, Column } from "@/components/dashboard/data-table";
import { ADMIN_NAV } from "@/lib/constants";
import { mockPatients } from "@/lib/mock-data";
import { Patient } from "@/types";
import { formatDate } from "@/lib/utils";

const columns: Column<Patient>[] = [
  { key: "name", label: "Patient", sortable: true, render: (p) => <span className="font-medium">{p.name}</span> },
  { key: "email", label: "Email", sortable: true },
  { key: "phone", label: "Phone" },
  { key: "date_of_birth", label: "DOB", render: (p) => formatDate(p.date_of_birth) },
  { key: "preferred_communication", label: "Preferred Channel", render: (p) => <span className="capitalize">{p.preferred_communication}</span> },
  { key: "created_at", label: "Registered", sortable: true, render: (p) => formatDate(p.created_at) },
];

export default function PatientsPage() {
  return (
    <DashboardShell navItems={ADMIN_NAV} sidebarTitle="AI.Prof" sidebarSubtitle="Platform Admin" pageTitle="Patients" pageSubtitle={`${mockPatients.length} registered patients`}>
      <DataTable columns={columns} data={mockPatients} searchPlaceholder="Search patients..." />
    </DashboardShell>
  );
}
