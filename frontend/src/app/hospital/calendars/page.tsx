"use client";
import React from "react";
import { DashboardShell } from "@/components/dashboard/shell";
import { HOSPITAL_NAV } from "@/lib/constants";

export default function HospitalCalendarsPage() {
  const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const hours = Array.from({ length: 10 }, (_, i) => `${i + 8}:00`);
  const slots = [
    { day: 0, hour: 0, type: "booked", label: "Ravi Kumar" },
    { day: 0, hour: 2, type: "booked", label: "Anita Singh" },
    { day: 1, hour: 1, type: "blocked", label: "Lunch Break" },
    { day: 2, hour: 3, type: "booked", label: "Vikram Reddy" },
    { day: 3, hour: 0, type: "available", label: "" },
    { day: 3, hour: 4, type: "booked", label: "Deepa Nair" },
    { day: 4, hour: 2, type: "leave", label: "Leave" },
    { day: 4, hour: 3, type: "leave", label: "Leave" },
  ];

  return (
    <DashboardShell navItems={HOSPITAL_NAV} sidebarTitle="City General Hospital" sidebarSubtitle="Hospital Admin" pageTitle="Calendars" pageSubtitle="Dr. Arun Sharma — Cardiology">
      <div className="rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] overflow-hidden">
        <div className="flex items-center gap-4 px-5 py-3 border-b border-[hsl(var(--border))]">
          <button className="rounded-lg bg-blue-100 px-3 py-1.5 text-xs font-medium text-blue-700">Week</button>
          <button className="rounded-lg px-3 py-1.5 text-xs font-medium text-[hsl(var(--muted-foreground))] hover:bg-[hsl(var(--muted))]">Day</button>
          <button className="rounded-lg px-3 py-1.5 text-xs font-medium text-[hsl(var(--muted-foreground))] hover:bg-[hsl(var(--muted))]">Month</button>
          <div className="ml-auto flex gap-2">
            <span className="flex items-center gap-1.5 text-xs"><span className="h-2.5 w-2.5 rounded bg-blue-500" />Booked</span>
            <span className="flex items-center gap-1.5 text-xs"><span className="h-2.5 w-2.5 rounded bg-emerald-500" />Available</span>
            <span className="flex items-center gap-1.5 text-xs"><span className="h-2.5 w-2.5 rounded bg-red-400" />Blocked</span>
            <span className="flex items-center gap-1.5 text-xs"><span className="h-2.5 w-2.5 rounded bg-gray-400" />Leave</span>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[hsl(var(--border))]">
                <th className="w-20 px-3 py-2 text-left text-xs font-medium text-[hsl(var(--muted-foreground))]">Time</th>
                {days.map(d => <th key={d} className="px-3 py-2 text-center text-xs font-medium text-[hsl(var(--muted-foreground))]">{d}</th>)}
              </tr>
            </thead>
            <tbody>
              {hours.map((h, hi) => (
                <tr key={h} className="border-b border-[hsl(var(--border))] last:border-0">
                  <td className="px-3 py-3 text-xs text-[hsl(var(--muted-foreground))] font-mono">{h}</td>
                  {days.map((_, di) => {
                    const slot = slots.find(s => s.day === di && s.hour === hi);
                    const colors: Record<string, string> = { booked: "bg-blue-100 border-blue-300 text-blue-700", blocked: "bg-red-100 border-red-300 text-red-600", available: "bg-emerald-50 border-emerald-300 text-emerald-700 border-dashed", leave: "bg-gray-100 border-gray-300 text-gray-500" };
                    return (
                      <td key={di} className="px-1 py-1">
                        {slot ? (
                          <div className={`rounded-lg border px-2 py-1.5 text-xs font-medium ${colors[slot.type] || ""}`}>
                            {slot.label || slot.type}
                          </div>
                        ) : (
                          <div className="h-8 rounded-lg hover:bg-[hsl(var(--muted))] transition-colors cursor-pointer" />
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </DashboardShell>
  );
}
