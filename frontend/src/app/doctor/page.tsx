"use client";
import React from "react";
import { DashboardShell } from "@/components/dashboard/shell";
import { StatCard } from "@/components/dashboard/stat-card";
import { DOCTOR_NAV } from "@/lib/constants";
import { mockAppointments, mockQuestionnaireResponses } from "@/lib/mock-data";
import { StatusBadge } from "@/components/dashboard/data-table";
import { Clock, Calendar } from "lucide-react";

export default function DoctorOverviewPage() {
  const myAppointments = mockAppointments.filter(a => a.doctor_id === "d1");
  const todayAppointments = myAppointments.filter(a => a.status === "confirmed" || a.status === "completed");
  const pending = mockQuestionnaireResponses.filter(r => r.status === "completed");

  return (
    <DashboardShell navItems={DOCTOR_NAV} sidebarTitle="Dr. Arun Sharma" sidebarSubtitle="Cardiology" pageTitle="Dashboard" pageSubtitle="Welcome back, Dr. Sharma">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard title="Today's Appointments" value={todayAppointments.length} icon="CalendarCheck" color="blue" />
        <StatCard title="Upcoming This Week" value={myAppointments.length} icon="Calendar" color="teal" />
        <StatCard title="Pending Questionnaires" value={1} icon="ClipboardList" color="amber" />
        <StatCard title="Completed Responses" value={pending.length} icon="FileText" color="emerald" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Today's Schedule */}
        <div className="rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold">Today&apos;s Schedule</h3>
            <Calendar className="h-4 w-4 text-[hsl(var(--muted-foreground))]" />
          </div>
          <div className="space-y-3">
            {myAppointments.map(apt => (
              <div key={apt.id} className="flex items-center gap-4 rounded-lg border border-[hsl(var(--border))] px-4 py-3 hover:shadow-md transition-all">
                <div className="flex flex-col items-center shrink-0">
                  <span className="text-lg font-bold text-blue-600">{apt.time}</span>
                  <span className="text-xs text-[hsl(var(--muted-foreground))]">{apt.duration}min</span>
                </div>
                <div className="h-10 w-px bg-[hsl(var(--border))]" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium">{apt.patient_name}</p>
                  <p className="text-xs text-[hsl(var(--muted-foreground))]">{apt.appointment_type} • {apt.specialty}</p>
                </div>
                <div className="flex flex-col items-end gap-1">
                  <StatusBadge status={apt.status} />
                  {apt.questionnaire_status && (
                    <span className="text-xs text-[hsl(var(--muted-foreground))]">
                      Q: {apt.questionnaire_status}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Recent Pre-Visit Responses */}
        <div className="rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5">
          <h3 className="text-sm font-semibold mb-4">Recent Pre-Visit Responses</h3>
          {mockQuestionnaireResponses.map(resp => (
            <div key={resp.id} className="rounded-lg border border-[hsl(var(--border))] p-4">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <p className="text-sm font-medium">{resp.patient_name}</p>
                  <p className="text-xs text-[hsl(var(--muted-foreground))]">Cardiology Pre-Visit Assessment</p>
                </div>
                <StatusBadge status={resp.status} />
              </div>
              <div className="space-y-2">
                {Object.entries(resp.responses).map(([key, val]) => (
                  <div key={key} className="flex items-start gap-2 text-xs">
                    <span className="shrink-0 text-[hsl(var(--muted-foreground))]">Q:</span>
                    <span className="text-[hsl(var(--foreground))]">{String(val)}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </DashboardShell>
  );
}
