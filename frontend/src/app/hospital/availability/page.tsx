"use client";
import React from "react";
import { DashboardShell } from "@/components/dashboard/shell";
import { HOSPITAL_NAV } from "@/lib/constants";

export default function HospitalAvailabilityPage() {
  const days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
  const schedule = [
    { day: "Monday", start: "09:00", end: "17:00", active: true },
    { day: "Tuesday", start: "09:00", end: "17:00", active: true },
    { day: "Wednesday", start: "09:00", end: "13:00", active: true },
    { day: "Thursday", start: "09:00", end: "17:00", active: true },
    { day: "Friday", start: "09:00", end: "15:00", active: true },
    { day: "Saturday", start: "10:00", end: "14:00", active: false },
  ];

  return (
    <DashboardShell navItems={HOSPITAL_NAV} sidebarTitle="City General Hospital" sidebarSubtitle="Hospital Admin" pageTitle="Availability" pageSubtitle="Configure doctor working hours">
      <div className="rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5">
        <h3 className="text-sm font-semibold mb-4">Dr. Arun Sharma — Working Hours</h3>
        <div className="space-y-3">
          {schedule.map(s => (
            <div key={s.day} className="flex items-center gap-4 rounded-lg bg-[hsl(var(--muted))] px-4 py-3">
              <div className="w-2 h-2 rounded-full" style={{ backgroundColor: s.active ? "#10b981" : "#9ca3af" }} />
              <span className="w-28 text-sm font-medium">{s.day}</span>
              <input className="h-8 w-24 rounded border border-[hsl(var(--border))] px-2 text-sm text-center" defaultValue={s.start} />
              <span className="text-sm text-[hsl(var(--muted-foreground))]">to</span>
              <input className="h-8 w-24 rounded border border-[hsl(var(--border))] px-2 text-sm text-center" defaultValue={s.end} />
              <label className="ml-auto flex items-center gap-2 cursor-pointer">
                <div className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${s.active ? "bg-blue-600" : "bg-gray-300"}`}>
                  <span className={`inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform ${s.active ? "translate-x-4" : "translate-x-0.5"}`} />
                </div>
              </label>
            </div>
          ))}
        </div>
        <button className="mt-4 rounded-lg bg-gradient-to-r from-blue-600 to-cyan-500 px-4 py-2 text-sm font-medium text-white hover:from-blue-700 hover:to-cyan-600 transition-all">Save Changes</button>
      </div>
    </DashboardShell>
  );
}
