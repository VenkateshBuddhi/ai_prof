"use client";
import React from "react";
import { DashboardShell } from "@/components/dashboard/shell";
import { ADMIN_NAV } from "@/lib/constants";
import { Activity, Bot, GitBranch, Link2, Server, Database, AlertTriangle, CheckCircle } from "lucide-react";
import { cn } from "@/lib/utils";

interface HealthPanelProps { title: string; icon: React.ElementType; status: "healthy" | "degraded" | "down"; metrics: { label: string; value: string; status: "ok" | "warn" | "error" }[] }

function HealthPanel({ title, icon: Icon, status, metrics }: HealthPanelProps) {
  const statusColors = { healthy: "bg-emerald-500", degraded: "bg-amber-500", down: "bg-red-500" };
  return (
    <div className="rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Icon className="h-5 w-5 text-[hsl(var(--muted-foreground))]" />
          <h3 className="text-sm font-semibold">{title}</h3>
        </div>
        <div className="flex items-center gap-2">
          <span className={cn("h-2.5 w-2.5 rounded-full", statusColors[status])} />
          <span className="text-xs capitalize font-medium">{status}</span>
        </div>
      </div>
      <div className="space-y-2.5">
        {metrics.map((m, i) => (
          <div key={i} className="flex items-center justify-between">
            <span className="text-sm text-[hsl(var(--muted-foreground))]">{m.label}</span>
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium">{m.value}</span>
              {m.status === "ok" ? <CheckCircle className="h-3.5 w-3.5 text-emerald-500" /> : m.status === "warn" ? <AlertTriangle className="h-3.5 w-3.5 text-amber-500" /> : <AlertTriangle className="h-3.5 w-3.5 text-red-500" />}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function HealthPage() {
  return (
    <DashboardShell navItems={ADMIN_NAV} sidebarTitle="AI.Prof" sidebarSubtitle="Platform Admin" pageTitle="Operational Health" pageSubtitle="System health and performance monitoring">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <HealthPanel title="AI Health" icon={Bot} status="healthy" metrics={[
          { label: "Active Conversations", value: "12", status: "ok" },
          { label: "Avg Response Latency", value: "1.4s", status: "ok" },
          { label: "Failed Capability Calls", value: "2", status: "warn" },
          { label: "Escalation Rate", value: "4.1%", status: "ok" },
          { label: "AI Error Rate", value: "0.3%", status: "ok" },
        ]} />
        <HealthPanel title="Workflow Health" icon={GitBranch} status="healthy" metrics={[
          { label: "Running Workflows", value: "4", status: "ok" },
          { label: "Completed (24h)", value: "127", status: "ok" },
          { label: "Failed (24h)", value: "1", status: "warn" },
          { label: "Avg Duration", value: "2.3s", status: "ok" },
          { label: "Stuck Executions", value: "0", status: "ok" },
        ]} />
        <HealthPanel title="EHR / Integration Health" icon={Link2} status="degraded" metrics={[
          { label: "Integration Requests (24h)", value: "89", status: "ok" },
          { label: "Success Rate", value: "97.8%", status: "ok" },
          { label: "Avg Duration", value: "1.1s", status: "ok" },
          { label: "Verification Rate", value: "100%", status: "ok" },
          { label: "Reconciliation Needed", value: "1", status: "warn" },
          { label: "Unknown-Outcome Ops", value: "0", status: "ok" },
        ]} />
        <HealthPanel title="Platform Health" icon={Server} status="healthy" metrics={[
          { label: "API Errors (24h)", value: "3", status: "ok" },
          { label: "Background Task Failures", value: "0", status: "ok" },
          { label: "Notification Failures", value: "0", status: "ok" },
          { label: "Database Errors", value: "0", status: "ok" },
          { label: "Service Availability", value: "99.97%", status: "ok" },
        ]} />
      </div>
    </DashboardShell>
  );
}
