"use client";
import React from "react";
import { DashboardShell } from "@/components/dashboard/shell";
import { ADMIN_NAV } from "@/lib/constants";
import { Globe, Database, Shield, Bell, Palette } from "lucide-react";

function SettingSection({ icon: Icon, title, description, children }: { icon: React.ElementType; title: string; description: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5">
      <div className="flex items-center gap-3 mb-4">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[hsl(var(--muted))]"><Icon className="h-4 w-4 text-[hsl(var(--muted-foreground))]" /></div>
        <div><h3 className="text-sm font-semibold">{title}</h3><p className="text-xs text-[hsl(var(--muted-foreground))]">{description}</p></div>
      </div>
      {children}
    </div>
  );
}

export default function SettingsPage() {
  return (
    <DashboardShell navItems={ADMIN_NAV} sidebarTitle="AI.Prof" sidebarSubtitle="Platform Admin" pageTitle="Settings" pageSubtitle="Platform configuration">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <SettingSection icon={Globe} title="General" description="Platform-wide settings">
          <div className="space-y-3">
            <div className="flex items-center justify-between"><span className="text-sm">Platform Name</span><input className="h-9 w-48 rounded-lg border border-[hsl(var(--border))] px-3 text-sm" defaultValue="AI.Prof" /></div>
            <div className="flex items-center justify-between"><span className="text-sm">Support Email</span><input className="h-9 w-48 rounded-lg border border-[hsl(var(--border))] px-3 text-sm" defaultValue="support@aiprof.com" /></div>
          </div>
        </SettingSection>
        <SettingSection icon={Shield} title="Security" description="Authentication and authorization">
          <div className="space-y-3">
            <div className="flex items-center justify-between"><span className="text-sm">Session Timeout</span><span className="text-sm text-[hsl(var(--muted-foreground))]">30 minutes</span></div>
            <div className="flex items-center justify-between"><span className="text-sm">2FA Required</span><span className="text-xs bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-full">Enabled</span></div>
          </div>
        </SettingSection>
        <SettingSection icon={Database} title="Database" description="Data management settings">
          <div className="space-y-3">
            <div className="flex items-center justify-between"><span className="text-sm">Audit Log Retention</span><span className="text-sm text-[hsl(var(--muted-foreground))]">90 days</span></div>
            <div className="flex items-center justify-between"><span className="text-sm">Backup Frequency</span><span className="text-sm text-[hsl(var(--muted-foreground))]">Daily</span></div>
          </div>
        </SettingSection>
        <SettingSection icon={Bell} title="Notifications" description="Default notification preferences">
          <div className="space-y-3">
            <div className="flex items-center justify-between"><span className="text-sm">Email Notifications</span><span className="text-xs bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-full">Enabled</span></div>
            <div className="flex items-center justify-between"><span className="text-sm">SMS Notifications</span><span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full">Optional</span></div>
          </div>
        </SettingSection>
      </div>
    </DashboardShell>
  );
}
