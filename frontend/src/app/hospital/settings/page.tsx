"use client";
import React from "react";
import { DashboardShell } from "@/components/dashboard/shell";
import { HOSPITAL_NAV } from "@/lib/constants";
import { Globe, Database, Shield, Bell, Building2 } from "lucide-react";

export default function HospitalSettingsPage() {
  return (
    <DashboardShell navItems={HOSPITAL_NAV} sidebarTitle="City General Hospital" sidebarSubtitle="Hospital Admin" pageTitle="Hospital Settings" pageSubtitle="Manage hospital configuration">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5">
          <div className="flex items-center gap-3 mb-4"><Building2 className="h-5 w-5 text-[hsl(var(--muted-foreground))]" /><h3 className="text-sm font-semibold">Hospital Profile</h3></div>
          <div className="space-y-3">
            <div><label className="text-xs font-medium text-[hsl(var(--muted-foreground))]">Hospital Name</label><input className="mt-1 h-9 w-full rounded-lg border border-[hsl(var(--border))] px-3 text-sm" defaultValue="City General Hospital" /></div>
            <div><label className="text-xs font-medium text-[hsl(var(--muted-foreground))]">Address</label><input className="mt-1 h-9 w-full rounded-lg border border-[hsl(var(--border))] px-3 text-sm" defaultValue="123 Medical Drive, Hyderabad" /></div>
            <div className="grid grid-cols-2 gap-3">
              <div><label className="text-xs font-medium text-[hsl(var(--muted-foreground))]">Phone</label><input className="mt-1 h-9 w-full rounded-lg border border-[hsl(var(--border))] px-3 text-sm" defaultValue="+91-40-12345678" /></div>
              <div><label className="text-xs font-medium text-[hsl(var(--muted-foreground))]">Email</label><input className="mt-1 h-9 w-full rounded-lg border border-[hsl(var(--border))] px-3 text-sm" defaultValue="admin@citygeneral.com" /></div>
            </div>
          </div>
        </div>
        <div className="rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5">
          <div className="flex items-center gap-3 mb-4"><Shield className="h-5 w-5 text-[hsl(var(--muted-foreground))]" /><h3 className="text-sm font-semibold">Departments & Specialties</h3></div>
          <div className="flex flex-wrap gap-2">
            {["Cardiology", "Orthopedics", "Neurology", "Pediatrics", "General Medicine"].map(s => (
              <span key={s} className="inline-flex items-center rounded-full bg-blue-100 px-3 py-1 text-xs font-medium text-blue-700">{s} ×</span>
            ))}
            <button className="rounded-full border border-dashed border-[hsl(var(--border))] px-3 py-1 text-xs text-[hsl(var(--muted-foreground))] hover:border-blue-500 hover:text-blue-500 transition-colors">+ Add</button>
          </div>
        </div>
        <div className="rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5">
          <div className="flex items-center gap-3 mb-4"><Bell className="h-5 w-5 text-[hsl(var(--muted-foreground))]" /><h3 className="text-sm font-semibold">Communication Preferences</h3></div>
          <div className="space-y-2">
            {["Email notifications", "SMS reminders", "Appointment confirmations", "Workflow alerts"].map(pref => (
              <div key={pref} className="flex items-center justify-between rounded-lg bg-[hsl(var(--muted))] px-3 py-2">
                <span className="text-sm">{pref}</span>
                <div className="relative inline-flex h-5 w-9 items-center rounded-full bg-blue-600 cursor-pointer"><span className="inline-block h-3.5 w-3.5 rounded-full bg-white translate-x-4" /></div>
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5">
          <div className="flex items-center gap-3 mb-4"><Database className="h-5 w-5 text-[hsl(var(--muted-foreground))]" /><h3 className="text-sm font-semibold">Operating Hours</h3></div>
          <div className="space-y-2">
            <div className="flex items-center gap-3"><span className="text-sm w-24">Weekdays</span><span className="text-sm font-medium">9:00 AM - 6:00 PM</span></div>
            <div className="flex items-center gap-3"><span className="text-sm w-24">Saturday</span><span className="text-sm font-medium">9:00 AM - 1:00 PM</span></div>
            <div className="flex items-center gap-3"><span className="text-sm w-24">Sunday</span><span className="text-sm text-[hsl(var(--muted-foreground))]">Closed</span></div>
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}
