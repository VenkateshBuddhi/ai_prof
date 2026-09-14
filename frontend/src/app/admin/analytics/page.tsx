"use client";
import React from "react";
import { DashboardShell } from "@/components/dashboard/shell";
import { StatCard } from "@/components/dashboard/stat-card";
import { ADMIN_NAV } from "@/lib/constants";
import { mockAppointmentsTrend, mockAILatencyTrend, mockSpecialtyDistribution } from "@/lib/mock-data";
import { useKpis } from "@/lib/queries";
import { LiveBadge } from "@/components/dashboard/live-badge";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line, PieChart, Pie, Cell, AreaChart, Area } from "recharts";

const COLORS = ["#3b82f6", "#06b6d4", "#8b5cf6", "#f59e0b", "#ef4444", "#10b981"];

export default function AnalyticsPage() {
  const { data: kpis, isLive, isLoading } = useKpis();
  return (
    <DashboardShell navItems={ADMIN_NAV} sidebarTitle="AI.Prof" sidebarSubtitle="Platform Admin" pageTitle="Analytics" pageSubtitle="Platform-wide metrics and insights">
      <div className="mb-6"><LiveBadge live={isLive} loading={isLoading} /></div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard title="Total Appointments" value={kpis.total_appointments || 0} icon="Target" color="emerald" />
        <StatCard title="AI Call Volume" value={kpis.active_ai_conversations || 0} icon="Bot" color="blue" />
        <StatCard title="Completed" value={kpis.completed || 0} icon="AlertCircle" color="amber" />
        <StatCard title="Booked" value={kpis.booked || 0} icon="Link2" color="teal" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <div className="rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5">
          <div className="flex items-center gap-2 mb-4">
            <h3 className="text-sm font-semibold">Appointments Over Time</h3>
            <LiveBadge live={false} />
          </div>
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
          <div className="flex items-center gap-2 mb-4">
            <h3 className="text-sm font-semibold">AI Response Latency Trend</h3>
            <LiveBadge live={false} />
          </div>
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
          <div className="flex items-center gap-2 mb-4">
            <h3 className="text-sm font-semibold">Appointments by Specialty</h3>
            <LiveBadge live={false} />
          </div>
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
          <div className="flex items-center gap-2 mb-4">
            <h3 className="text-sm font-semibold">Booking Distribution</h3>
            <LiveBadge live={false} />
          </div>
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
