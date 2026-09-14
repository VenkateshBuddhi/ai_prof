"use client";
import React from "react";
import { DashboardShell } from "@/components/dashboard/shell";
import { StatCard } from "@/components/dashboard/stat-card";
import { HOSPITAL_NAV } from "@/lib/constants";
import { useKpis, useAppointments, useDoctors } from "@/lib/queries";
import { LiveBadge } from "@/components/dashboard/live-badge";
import { StatusBadge } from "@/components/dashboard/data-table";

export default function HospitalOverviewPage() {
  const { data: kpis, isLive: kpisLive, isLoading: kpisLoading } = useKpis();
  const { data: appointments, isLive: apptLive, isLoading: apptLoading } = useAppointments();
  const { data: doctors, isLive: docLive, isLoading: docLoading } = useDoctors();

  const hospitalAppointments = appointments.filter((a: any) => a.hospital_id === "h1");
  const hospitalDoctors = doctors.filter((d: any) => d.hospital_id === "h1");

  const isLive = kpisLive && apptLive && docLive;
  const isLoading = kpisLoading || apptLoading || docLoading;

  return (
    <DashboardShell navItems={HOSPITAL_NAV} sidebarTitle="City General Hospital" sidebarSubtitle="Hospital Admin" pageTitle="Hospital Overview" pageSubtitle="Your hospital at a glance">
      <div className="mb-6"><LiveBadge live={isLive} loading={isLoading} /></div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 mb-8">
        <StatCard title="Appointments Today" value={kpis.total_appointments_today || 0} icon="CalendarCheck" color="blue" trend={{ value: 12, label: "vs yesterday" }} />
        <StatCard title="Total Appointments" value={kpis.total_appointments || 0} icon="Stethoscope" color="teal" />
        <StatCard title="Completed" value={kpis.completed || 0} icon="Clock" color="emerald" />
        <StatCard title="AI Conversations" value={kpis.active_ai_conversations || 0} icon="Bot" color="purple" trend={{ value: 18, label: "this week" }} />
        <StatCard title="Cancelled" value={kpis.cancelled || 0} icon="XCircle" color="rose" />
        <StatCard title="Booked" value={kpis.booked || 0} icon="RefreshCw" color="amber" />
        <StatCard title="Total Users" value={kpis.total_users || 0} icon="User" color="purple" />
        <StatCard title="Total Hospitals" value={kpis.total_hospitals || 0} icon="Link2" color="emerald" />
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
