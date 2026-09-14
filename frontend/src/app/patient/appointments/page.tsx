"use client";
import React, { useState } from "react";
import { DashboardShell } from "@/components/dashboard/shell";
import { PATIENT_NAV } from "@/lib/constants";
import { mockAppointments } from "@/lib/mock-data";
import { Calendar, Clock, Video, MapPin, Search, Filter, AlertCircle, FileText } from "lucide-react";

export default function PatientAppointmentsPage() {
  const [filter, setFilter] = useState<string>("all");

  const filtered = mockAppointments.filter((a) => {
    if (filter === "all") return true;
    return a.status === filter;
  });

  return (
    <DashboardShell
      navItems={PATIENT_NAV}
      role="patient"
      sidebarTitle="Patient Portal"
      sidebarSubtitle="My Appointments"
    >
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground">My Appointments</h1>
            <p className="text-sm text-muted-foreground mt-1">
              View your upcoming, past, and pending clinical appointments with your healthcare providers.
            </p>
          </div>

          {/* Filter Pills */}
          <div className="flex items-center gap-2 bg-muted p-1 rounded-xl border border-border">
            {["all", "confirmed", "pending", "completed", "cancelled"].map((st) => (
              <button
                key={st}
                onClick={() => setFilter(st)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold capitalize transition-all ${
                  filter === st
                    ? "bg-background text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {st}
              </button>
            ))}
          </div>
        </div>

        {/* Appointments Cards List */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filtered.map((appt) => (
            <div
              key={appt.id}
              className="rounded-2xl border border-border bg-card p-6 hover:border-primary/50 transition-all hover:shadow-md flex flex-col justify-between gap-5"
            >
              <div className="space-y-3">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-bold text-foreground text-base">{appt.doctor_name}</h3>
                    <p className="text-xs text-muted-foreground">{appt.hospital_name}</p>
                  </div>
                  <span
                    className={`px-2.5 py-1 rounded-full text-xs font-semibold capitalize border ${
                      appt.status === "confirmed"
                        ? "bg-emerald-500/10 text-emerald-600 border-emerald-500/20"
                        : appt.status === "pending"
                        ? "bg-amber-500/10 text-amber-600 border-amber-500/20"
                        : appt.status === "completed"
                        ? "bg-blue-500/10 text-blue-600 border-blue-500/20"
                        : "bg-rose-500/10 text-rose-600 border-rose-500/20"
                    }`}
                  >
                    {appt.status}
                  </span>
                </div>

                <div className="p-3 rounded-xl bg-muted/50 border border-border/50 text-xs space-y-1.5">
                  <div className="flex items-center gap-2 text-foreground font-medium">
                    <Calendar className="h-3.5 w-3.5 text-primary" />
                    <span>{new Date(appt.start_time).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric", year: "numeric" })}</span>
                  </div>
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <Clock className="h-3.5 w-3.5 text-primary" />
                    <span>{new Date(appt.start_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} ({appt.duration_minutes} mins)</span>
                  </div>
                  <div className="text-muted-foreground pt-1 border-t border-border/40">
                    Reason: <span className="text-foreground font-medium">{appt.reason}</span>
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between gap-3 pt-2 border-t border-border">
                <button className="inline-flex items-center gap-1.5 text-xs font-semibold text-primary hover:underline">
                  <FileText className="h-3.5 w-3.5" />
                  Pre-Visit Form
                </button>
                <div className="flex items-center gap-2">
                  <button className="px-3 py-1.5 rounded-lg border border-border text-xs font-medium hover:bg-muted text-muted-foreground">
                    Reschedule
                  </button>
                  {appt.status === "confirmed" && (
                    <button className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-xs font-semibold hover:opacity-90 transition-opacity shadow-sm">
                      <Video className="h-3.5 w-3.5" />
                      Join
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </DashboardShell>
  );
}
