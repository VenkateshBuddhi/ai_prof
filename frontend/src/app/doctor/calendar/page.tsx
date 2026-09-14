"use client";
import React, { useState } from "react";
import { DashboardShell } from "@/components/dashboard/shell";
import { DOCTOR_NAV } from "@/lib/constants";
import { ChevronLeft, ChevronRight, Plus, Clock, User, Video, MapPin, Calendar as CalendarIcon } from "lucide-react";

export default function DoctorCalendarPage() {
  const days = ["Mon, Oct 23", "Tue, Oct 24", "Wed, Oct 25", "Thu, Oct 26", "Fri, Oct 27", "Sat, Oct 28"];
  const timeSlots = [
    "09:00 AM",
    "10:00 AM",
    "11:00 AM",
    "12:00 PM",
    "01:00 PM",
    "02:00 PM",
    "03:00 PM",
    "04:00 PM",
    "05:00 PM",
  ];

  const events = [
    { day: "Tue, Oct 24", time: "09:00 AM", title: "Sarah Connor", reason: "Follow-up ECG Review", type: "consultation" },
    { day: "Tue, Oct 24", time: "11:00 AM", title: "Michael Brown", reason: "Hypertension Assessment", type: "consultation" },
    { day: "Wed, Oct 25", time: "01:00 PM", title: "Blocked (Hospital Rounds)", reason: "Inpatient Ward", type: "blocked" },
    { day: "Thu, Oct 26", time: "10:00 AM", title: "David Kim", reason: "Pre-Op Clearance", type: "consultation" },
    { day: "Fri, Oct 27", time: "03:00 PM", title: "Emily Davis", reason: "Chest Pain Evaluation", type: "consultation" },
  ];

  return (
    <DashboardShell
      navItems={DOCTOR_NAV}
      role="doctor"
      sidebarTitle="Dr. Robert Chen"
      sidebarSubtitle="Cardiology Dept"
    >
      <div className="space-y-6">
        {/* Top Controls */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground">Doctor Schedule & Calendar</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Manage your weekly appointment commitments, blocked time, and clinical sessions.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center rounded-xl border border-border bg-card p-1">
              <button className="p-1.5 hover:bg-muted rounded-lg text-muted-foreground">
                <ChevronLeft className="h-4 w-4" />
              </button>
              <span className="px-3 text-xs font-semibold text-foreground">Oct 23 - Oct 28, 2026</span>
              <button className="p-1.5 hover:bg-muted rounded-lg text-muted-foreground">
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
            <button className="inline-flex items-center gap-2 rounded-xl bg-primary text-primary-foreground px-4 py-2 text-xs font-semibold shadow hover:opacity-90 transition-opacity">
              <Plus className="h-3.5 w-3.5" />
              Block Time
            </button>
          </div>
        </div>

        {/* Calendar Grid */}
        <div className="rounded-2xl border border-border bg-card overflow-hidden shadow-sm">
          <div className="grid grid-cols-7 border-b border-border bg-muted/40 text-center text-xs font-semibold text-muted-foreground">
            <div className="p-3 border-r border-border text-left pl-4">Time</div>
            {days.map((day) => (
              <div key={day} className="p-3 border-r border-border last:border-r-0">
                {day}
              </div>
            ))}
          </div>

          <div className="divide-y divide-border">
            {timeSlots.map((slot) => (
              <div key={slot} className="grid grid-cols-7 min-h-[72px]">
                <div className="p-3 text-xs font-mono text-muted-foreground border-r border-border bg-muted/10 flex items-start">
                  {slot}
                </div>
                {days.map((day) => {
                  const event = events.find((e) => e.day === day && e.time === slot);
                  return (
                    <div
                      key={day + slot}
                      className="p-1.5 border-r border-border last:border-r-0 relative group hover:bg-muted/30 transition-colors"
                    >
                      {event ? (
                        <div
                          className={`h-full rounded-xl p-2.5 text-xs flex flex-col justify-between border ${
                            event.type === "blocked"
                              ? "bg-muted/80 text-muted-foreground border-border dashed"
                              : "bg-primary/10 text-primary border-primary/20 shadow-xs"
                          }`}
                        >
                          <div>
                            <span className="font-bold block truncate text-foreground">{event.title}</span>
                            <span className="text-[10px] text-muted-foreground truncate block">{event.reason}</span>
                          </div>
                          <div className="flex items-center gap-1 text-[10px] font-medium text-primary mt-1">
                            <Video className="h-3 w-3" />
                            <span>Video Room</span>
                          </div>
                        </div>
                      ) : (
                        <button className="opacity-0 group-hover:opacity-100 w-full h-full flex items-center justify-center text-[11px] font-medium text-muted-foreground hover:text-primary transition-opacity">
                          + Add
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}
