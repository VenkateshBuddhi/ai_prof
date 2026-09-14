"use client";
import React from "react";
import { DashboardShell } from "@/components/dashboard/shell";
import { StatCard } from "@/components/dashboard/stat-card";
import { ADMIN_NAV } from "@/lib/constants";
import { mockPlatformKPIs, mockAppointmentsTrend, mockAILatencyTrend, mockSpecialtyDistribution } from "@/lib/mock-data";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line, PieChart, Pie, Cell, AreaChart, Area } from "recharts";

const COLORS = ["#3b82f6", "#06b6d4", "#8b5cf6", "#f59e0b", "#ef4444", "#10b981"];

export default function AnalyticsPage() {
  const kpis = mockPlatformKPIs;
  return (
    <DashboardShell navItems={ADMIN_NAV} sidebarTitle="AI.Prof" sidebarSubtitle="Platform Admin" pageTitle="Analytics" pageSubtitle="Platform-wide metrics and insights">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard title="Booking Success Rate" value={`${kpis.booking_success_rate}%`} icon="Target" color="emerald" />
        <StatCard title="AI Call Volume" value={kpis.ai_calls_today} icon="Bot" color="blue" />
        <StatCard title="Escalation Rate" value={`${kpis.human_escalation_rate}%`} icon="AlertCircle" color="amber" />
        <StatCard title="EHR Integration" value={`${kpis.ehr_integration_success_rate}%`} icon="Link2" color="teal" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <div className="rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5">
          <h3 className="text-sm font-semibold mb-4">Appointments Over Time</h3>
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={mockAppointmentsTrend}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="date" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Area type="monotone" dataKey="count" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.1} name="Total" />
              <Area type="monotone" dataKey="ai_booked" stroke="#06b6d4" fill="#06b6d4" fillOpacity={0.1} name="AI Booked" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div className="rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5">
          <h3 className="text-sm font-semibold mb-4">AI Response Latency Trend</h3>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={mockAILatencyTrend}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="date" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} unit="s" />
              <Tooltip />
              <Line type="monotone" dataKey="avg" stroke="#3b82f6" strokeWidth={2} name="Average" />
              <Line type="monotone" dataKey="p95" stroke="#f59e0b" strokeWidth={2} name="P95" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5">
          <h3 className="text-sm font-semibold mb-4">Appointments by Specialty</h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={mockSpecialtyDistribution} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis type="number" tick={{ fontSize: 12 }} />
              <YAxis dataKey="name" type="category" width={100} tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                {mockSpecialtyDistribution.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5">
          <h3 className="text-sm font-semibold mb-4">Booking Distribution</h3>
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie data={mockSpecialtyDistribution} cx="50%" cy="50%" innerRadius={60} outerRadius={100} paddingAngle={3} dataKey="value" label={({name, percent}) => `${name} ${(percent*100).toFixed(0)}%`}>
                {mockSpecialtyDistribution.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
    </DashboardShell>
  );
}
