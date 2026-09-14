"use client";
import React, { useState } from "react";
import { DashboardShell } from "@/components/dashboard/shell";
import { DataTable, StatusBadge, Column } from "@/components/dashboard/data-table";
import { DOCTOR_NAV } from "@/lib/constants";
import { useAppointments } from "@/lib/queries";
import { LiveBadge } from "@/components/dashboard/live-badge";
import { Video, FileText, CheckCircle, Clock } from "lucide-react";

export default function DoctorAppointmentsPage() {
  const { data: appointments, isLive, isLoading } = useAppointments();
  const doctorAppointments = appointments.slice(0, 8);

  const columns: Column<any>[] = [
    {
      header: "Patient",
      accessor: (row) => (
        <div>
          <span className="font-semibold text-foreground block">{row.patient_name}</span>
          <span className="text-xs text-muted-foreground">{row.patient_email}</span>
        </div>
      ),
    },
    {
      header: "Date & Time",
      accessor: (row) => (
        <div className="text-xs">
          <span className="font-medium text-foreground block">
            {new Date(row.start_time).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })}
          </span>
          <span className="text-muted-foreground">
            {new Date(row.start_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} ({row.duration_minutes}m)
          </span>
        </div>
      ),
    },
    {
      header: "Reason / Symptoms",
      accessor: (row) => (
        <span className="text-xs font-medium text-foreground max-w-xs truncate block">
          {row.reason}
        </span>
      ),
    },
    {
      header: "Status",
      accessor: (row) => <StatusBadge status={row.status} />,
    },
    {
      header: "Actions",
      accessor: (row) => (
        <div className="flex items-center gap-2">
          <button
            title="View Pre-Visit Questionnaire"
            className="p-1.5 rounded-lg border border-border hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
          >
            <FileText className="h-4 w-4" />
          </button>
          {row.status === "confirmed" && (
            <button
              title="Start Consultation"
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-primary text-primary-foreground text-xs font-semibold hover:opacity-90 transition-opacity"
            >
              <Video className="h-3.5 w-3.5" />
              Start
            </button>
          )}
        </div>
      ),
    },
  ];

  return (
    <DashboardShell
      navItems={DOCTOR_NAV}
      role="doctor"
      sidebarTitle="Dr. Robert Chen"
      sidebarSubtitle="Cardiology Dept"
    >
      <div className="space-y-6">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-foreground">Doctor Clinical Appointments</h1>
            <LiveBadge live={isLive} loading={isLoading} />
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Manage your scheduled patient consultations, pre-visit AI summaries, and session notes.
          </p>
        </div>

        <DataTable
          title="Scheduled Appointments"
          description="Live patient consultations for Dr. Robert Chen"
          columns={columns}
          data={doctorAppointments}
          searchPlaceholder="Search by patient name or reason..."
        />
      </div>
    </DashboardShell>
  );
}
