"use client";

import React from "react";
import { DashboardShell } from "@/components/dashboard/shell";
import { StatCard } from "@/components/dashboard/stat-card";
import { ADMIN_NAV } from "@/lib/constants";
import { useKpis, useAppointments, useAudit } from "@/lib/queries";
import { LiveBadge } from "@/components/dashboard/live-badge";
import { StatusBadge } from "@/components/dashboard/data-table";
import { formatDateTime } from "@/lib/utils";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line, PieChart, Pie, Cell
} from "recharts";
import { mockAppointmentsTrend, mockAILatencyTrend, mockSpecialtyDistribution } from "@/lib/mock-data";

const CHART_COLORS = ["#3b82f6", "#06b6d4", "#8b5cf6", "#f59e0b", "#ef4444", "#10b981"];

export default function AdminOverviewPage() {
  const { data: kpis, isLive: kpisLive, isLoading: kpisLoading } = useKpis();
  const { data: appointments, isLive: apptLive, isLoading: apptLoading } = useAppointments();
  const { data: auditEvents, isLive: auditLive, isLoading: auditLoading } = useAudit();
  
  const isLive = kpisLive && apptLive && auditLive;
  const isLoading = kpisLoading || apptLoading || auditLoading;

  return (
    <DashboardShell
      navItems={ADMIN_NAV}
      sidebarTitle="AI.Prof"
      sidebarSubtitle="Platform Admin"
      pageTitle="Platform Overview"
      pageSubtitle="Global healthcare operations dashboard"
    >
      <div className="mb-4"><LiveBadge live={isLive} loading={isLoading} /></div>
      {/* KPI Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 mb-8">
        <StatCard title="Total Hospitals" value={kpis.total_hospitals || 0} icon="Building2" color="blue" trend={{ value: 12, label: "this month" }} />
        <StatCard title="Active Doctors" value={kpis.total_doctors || 0} icon="Stethoscope" color="teal" trend={{ value: 8, label: "this month" }} />
        <StatCard title="Total Patients" value={kpis.total_patients || 0} icon="Users" color="purple" trend={{ value: 15, label: "this month" }} />
        <StatCard title="Appointments Today" value={kpis.total_appointments_today || 0} icon="CalendarCheck" color="emerald" trend={{ value: 5, label: "vs yesterday" }} />
        <StatCard title="AI Calls Active" value={kpis.active_ai_conversations || 0} icon="Bot" color="blue" trend={{ value: 22, label: "vs yesterday" }} />
        <StatCard title="Total Appts" value={kpis.total_appointments || 0} icon="Target" color="emerald" trend={{ value: 1.3, label: "vs last week" }} />
        <StatCard title="Completed" value={kpis.completed || 0} icon="ClipboardList" color="purple" />
        <StatCard title="No Show" value={kpis.no_show || 0} icon="AlertCircle" color="amber" trend={{ value: -0.5, label: "vs last week" }} />
        <StatCard title="Cancelled" value={kpis.cancelled || 0} icon="Zap" color="teal" />
        <StatCard title="Booked" value={kpis.booked || 0} icon="Link2" color="emerald" trend={{ value: 0.4, label: "vs last week" }} />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* Appointments Trend */}
        <div className="rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5">
          <div className="flex items-center gap-2 mb-4">
            <h3 className="text-sm font-semibold text-[hsl(var(--foreground))]">Appointment Trend</h3>
            <LiveBadge live={false} />
          </div>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={mockAppointmentsTrend}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="date" tick={{ fontSize: 12, fill: "hsl(var(--muted-foreground))" }} />
              <YAxis tick={{ fontSize: 12, fill: "hsl(var(--muted-foreground))" }} />
              <Tooltip contentStyle={{ borderRadius: "8px", border: "1px solid hsl(var(--border))", background: "hsl(var(--card))" }} />
              <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} name="Total" />
              <Bar dataKey="ai_booked" fill="#06b6d4" radius={[4, 4, 0, 0]} name="AI Booked" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* AI Latency Trend */}
        <div className="rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5">
          <div className="flex items-center gap-2 mb-4">
            <h3 className="text-sm font-semibold text-[hsl(var(--foreground))]">AI Response Latency</h3>
            <LiveBadge live={false} />
          </div>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={mockAILatencyTrend}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="date" tick={{ fontSize: 12, fill: "hsl(var(--muted-foreground))" }} />
              <YAxis tick={{ fontSize: 12, fill: "hsl(var(--muted-foreground))" }} unit="s" />
              <Tooltip contentStyle={{ borderRadius: "8px", border: "1px solid hsl(var(--border))", background: "hsl(var(--card))" }} />
              <Line type="monotone" dataKey="avg" stroke="#3b82f6" strokeWidth={2} dot={{ r: 4 }} name="Avg Latency" />
              <Line type="monotone" dataKey="p95" stroke="#f59e0b" strokeWidth={2} dot={{ r: 4 }} name="P95 Latency" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Bottom Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Specialty Distribution */}
        <div className="rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5">
          <div className="flex items-center gap-2 mb-4">
            <h3 className="text-sm font-semibold text-[hsl(var(--foreground))]">Bookings by Specialty</h3>
            <LiveBadge live={false} />
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={mockSpecialtyDistribution} cx="50%" cy="50%" innerRadius={55} outerRadius={85} paddingAngle={3} dataKey="value">
                {mockSpecialtyDistribution.map((_, i) => (
                  <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ borderRadius: "8px", border: "1px solid hsl(var(--border))", background: "hsl(var(--card))" }} />
            </PieChart>
          </ResponsiveContainer>
          <div className="flex flex-wrap gap-2 mt-2">
            {mockSpecialtyDistribution.map((s, i) => (
              <span key={s.name} className="flex items-center gap-1.5 text-xs text-[hsl(var(--muted-foreground))]">
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: CHART_COLORS[i] }} />
                {s.name}
              </span>
            ))}
          </div>
        </div>

        {/* Recent Appointments */}
        <div className="rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5">
          <h3 className="text-sm font-semibold text-[hsl(var(--foreground))] mb-4">Recent Appointments</h3>
          <div className="space-y-3">
            {appointments.slice(0, 5).map((apt: any) => (
              <div key={apt.id} className="flex items-center justify-between rounded-lg px-3 py-2.5 hover:bg-[hsl(var(--muted))] transition-colors">
                <div>
                  <p className="text-sm font-medium text-[hsl(var(--foreground))]">{apt.patient_name}</p>
                  <p className="text-xs text-[hsl(var(--muted-foreground))]">{apt.doctor_name} • {apt.specialty}</p>
                </div>
                <StatusBadge status={apt.status} />
              </div>
            ))}
          </div>
        </div>

        {/* Recent Audit Events */}
        <div className="rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5">
          <h3 className="text-sm font-semibold text-[hsl(var(--foreground))] mb-4">Recent Activity</h3>
          <div className="space-y-3">
            {auditEvents.slice(0, 5).map((evt: any) => (
              <div key={evt.id} className="flex items-start gap-3 rounded-lg px-3 py-2.5 hover:bg-[hsl(var(--muted))] transition-colors">
                <div className="mt-0.5 h-2 w-2 rounded-full bg-blue-500 shrink-0" />
                <div>
                  <p className="text-sm font-medium text-[hsl(var(--foreground))]">
                    {evt.event_type.replace(/_/g, " ")}
                  </p>
                  <p className="text-xs text-[hsl(var(--muted-foreground))]">
                    {evt.actor_name} • {formatDateTime(evt.timestamp)}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}
