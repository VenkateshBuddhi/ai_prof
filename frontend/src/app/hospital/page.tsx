"use client";
import React from "react";
import { DashboardShell } from "@/components/dashboard/shell";
import { StatCard } from "@/components/dashboard/stat-card";
import { HOSPITAL_NAV } from "@/lib/constants";
import { mockHospitalKPIs, mockAppointments, mockDoctors } from "@/lib/mock-data";
import { StatusBadge } from "@/components/dashboard/data-table";

export default function HospitalOverviewPage() {
  const kpis = mockHospitalKPIs;
  const hospitalAppointments = mockAppointments.filter(a => a.hospital_id === "h1");
  const hospitalDoctors = mockDoctors.filter(d => d.hospital_id === "h1");

  return (
    <DashboardShell navItems={HOSPITAL_NAV} sidebarTitle="City General Hospital" sidebarSubtitle="Hospital Admin" pageTitle="Hospital Overview" pageSubtitle="Your hospital at a glance">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 mb-8">
        <StatCard title="Appointments Today" value={kpis.appointments_today} icon="CalendarCheck" color="blue" trend={{ value: 12, label: "vs yesterday" }} />
        <StatCard title="Active Doctors" value={kpis.active_doctors} icon="Stethoscope" color="teal" />
        <StatCard title="Available Slots" value={kpis.available_slots} icon="Clock" color="emerald" />
        <StatCard title="AI Bookings" value={kpis.ai_bookings} icon="Bot" color="purple" trend={{ value: 18, label: "this week" }} />
        <StatCard title="Cancelled" value={kpis.cancelled_appointments} icon="XCircle" color="rose" />
        <StatCard title="Rescheduled" value={kpis.rescheduled_appointments} icon="RefreshCw" color="amber" />
        <StatCard title="Questionnaire %" value={`${kpis.questionnaire_completion}%`} icon="ClipboardList" color="purple" />
        <StatCard title="EHR Success" value={`${kpis.ehr_success_rate}%`} icon="Link2" color="emerald" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5">
          <h3 className="text-sm font-semibold mb-4">Today&apos;s Appointments</h3>
          <div className="space-y-3">
            {hospitalAppointments.slice(0, 5).map(apt => (
              <div key={apt.id} className="flex items-center justify-between rounded-lg px-3 py-2.5 hover:bg-[hsl(var(--muted))] transition-colors">
                <div className="flex items-center gap-3">
                  <div className="h-8 w-8 rounded-full bg-gradient-to-br from-blue-400 to-cyan-400 flex items-center justify-center text-white text-xs font-bold">{apt.patient_name[0]}</div>
                  <div><p className="text-sm font-medium">{apt.patient_name}</p><p className="text-xs text-[hsl(var(--muted-foreground))]">{apt.time} • {apt.doctor_name}</p></div>
                </div>
                <StatusBadge status={apt.status} />
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5">
          <h3 className="text-sm font-semibold mb-4">Active Doctors</h3>
          <div className="space-y-3">
            {hospitalDoctors.map(doc => (
              <div key={doc.id} className="flex items-center justify-between rounded-lg px-3 py-2.5 hover:bg-[hsl(var(--muted))] transition-colors">
                <div className="flex items-center gap-3">
                  <div className="h-8 w-8 rounded-full bg-gradient-to-br from-purple-400 to-pink-400 flex items-center justify-center text-white text-xs font-bold">{doc.name.split(" ").map(n=>n[0]).join("").slice(0,2)}</div>
                  <div><p className="text-sm font-medium">{doc.name}</p><p className="text-xs text-[hsl(var(--muted-foreground))]">{doc.specialty} • {doc.consultation_duration}min</p></div>
                </div>
                <StatusBadge status={doc.status} />
              </div>
            ))}
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}
