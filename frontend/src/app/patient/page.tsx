"use client";
import React from "react";
import { DashboardShell } from "@/components/dashboard/shell";
import { PATIENT_NAV } from "@/lib/constants";
import { mockAppointments, mockDoctors } from "@/lib/mock-data";
import { CalendarCheck, Clock, User, Heart, Sparkles, ArrowRight, ShieldCheck, Video, MapPin, Activity } from "lucide-react";
import Link from "next/link";

export default function PatientOverviewPage() {
  const patientAppointments = mockAppointments.filter(
    (a) => a.status === "confirmed" || a.status === "pending"
  );
  const nextAppt = patientAppointments[0];

  return (
    <DashboardShell
      navItems={PATIENT_NAV}
      role="patient"
      sidebarTitle="Patient Portal"
      sidebarSubtitle="Health & Appointments"
    >
      <div className="space-y-8">
        {/* Welcome Hero Banner */}
        <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-emerald-600 via-teal-600 to-cyan-600 p-8 text-white shadow-xl">
          <div className="relative z-10 max-w-2xl">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/15 backdrop-blur text-xs font-semibold mb-4 border border-white/20">
              <Sparkles className="h-3.5 w-3.5" />
              AI-Powered Healthcare Experience
            </div>
            <h1 className="text-3xl font-bold tracking-tight sm:text-4xl text-white">
              Welcome back, Michael
            </h1>
            <p className="mt-2 text-emerald-100 text-base leading-relaxed">
              Book appointments instantly using our conversational voice AI assistant, view your upcoming visits, and complete your pre-consultation questionnaires.
            </p>
            <div className="mt-6 flex flex-wrap items-center gap-4">
              <Link
                href="/patient/assistant"
                className="inline-flex items-center gap-2 rounded-xl bg-white px-5 py-3 text-sm font-bold text-emerald-800 shadow-lg transition-transform hover:scale-105 active:scale-95"
              >
                <Sparkles className="h-4 w-4 text-emerald-600" />
                Start AI Voice Booking
              </Link>
              <Link
                href="/patient/appointments"
                className="inline-flex items-center gap-2 rounded-xl bg-white/20 backdrop-blur px-5 py-3 text-sm font-semibold text-white border border-white/30 hover:bg-white/30 transition-colors"
              >
                View My Schedule
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </div>
          <div className="absolute -right-12 -bottom-12 w-80 h-80 rounded-full bg-white/10 blur-3xl pointer-events-none" />
        </div>

        {/* Next Appointment Card */}
        {nextAppt && (
          <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <div className="h-3 w-3 rounded-full bg-emerald-500 animate-pulse" />
                <h3 className="font-semibold text-foreground text-lg">Upcoming Appointment</h3>
              </div>
              <span className="px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-600 border border-emerald-500/20 capitalize">
                {nextAppt.status}
              </span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6 items-center">
              <div className="flex items-center gap-4 md:col-span-2">
                <div className="h-14 w-14 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-600">
                  <User className="h-7 w-7" />
                </div>
                <div>
                  <h4 className="font-bold text-foreground text-base">{nextAppt.doctor_name}</h4>
                  <p className="text-sm text-muted-foreground">{nextAppt.hospital_name}</p>
                  <p className="text-xs text-primary font-medium mt-0.5">{nextAppt.reason}</p>
                </div>
              </div>
              <div className="space-y-1.5 text-sm text-muted-foreground">
                <div className="flex items-center gap-2">
                  <CalendarCheck className="h-4 w-4 text-emerald-600" />
                  <span>{new Date(nextAppt.start_time).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })}</span>
                </div>
                <div className="flex items-center gap-2">
                  <Clock className="h-4 w-4 text-emerald-600" />
                  <span>{new Date(nextAppt.start_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} ({nextAppt.duration_minutes} min)</span>
                </div>
              </div>
              <div className="flex flex-col gap-2">
                <button className="w-full inline-flex items-center justify-center gap-2 rounded-xl bg-primary text-primary-foreground px-4 py-2.5 text-sm font-semibold shadow hover:opacity-90 transition-opacity">
                  <Video className="h-4 w-4" />
                  Join Consultation
                </button>
                <button className="w-full rounded-xl border border-border px-4 py-2 text-xs font-semibold text-muted-foreground hover:bg-muted transition-colors">
                  Reschedule / Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Quick Actions & Recommended Doctors */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left 2 Cols: Featured Doctors */}
          <div className="lg:col-span-2 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-foreground text-lg">Recommended Specialists</h3>
              <span className="text-xs text-muted-foreground">Top Rated in Network</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {mockDoctors.slice(0, 4).map((doc) => (
                <div
                  key={doc.id}
                  className="rounded-2xl border border-border bg-card p-5 hover:border-primary/50 transition-all hover:shadow-md flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-3">
                        <div className="h-12 w-12 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center font-bold text-primary">
                          {doc.name.split(" ")[1]?.[0] || doc.name[0]}
                        </div>
                        <div>
                          <h4 className="font-bold text-foreground text-sm">{doc.name}</h4>
                          <span className="inline-block px-2 py-0.5 rounded text-[11px] font-medium bg-secondary text-secondary-foreground mt-0.5">
                            {doc.specialty}
                          </span>
                        </div>
                      </div>
                    </div>
                    <p className="text-xs text-muted-foreground mt-3 line-clamp-2">
                      {doc.bio || `Specialist in ${doc.specialty} with over 10+ years clinical experience.`}
                    </p>
                  </div>
                  <div className="mt-4 pt-3 border-t border-border flex items-center justify-between">
                    <span className="text-xs font-semibold text-foreground">${doc.consultation_fee} / visit</span>
                    <Link
                      href="/patient/assistant"
                      className="inline-flex items-center gap-1.5 text-xs font-bold text-primary hover:underline"
                    >
                      Book with AI
                      <ArrowRight className="h-3 w-3" />
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Right Col: Health Profile & Quick Tips */}
          <div className="space-y-6">
            <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
              <h3 className="font-semibold text-foreground text-base mb-4 flex items-center gap-2">
                <Heart className="h-4 w-4 text-rose-500" />
                Health Profile Summary
              </h3>
              <div className="space-y-3 text-sm">
                <div className="flex justify-between py-2 border-b border-border/50">
                  <span className="text-muted-foreground">Blood Type</span>
                  <span className="font-semibold text-foreground">O+ Positive</span>
                </div>
                <div className="flex justify-between py-2 border-b border-border/50">
                  <span className="text-muted-foreground">Known Allergies</span>
                  <span className="font-semibold text-foreground">Penicillin</span>
                </div>
                <div className="flex justify-between py-2 border-b border-border/50">
                  <span className="text-muted-foreground">Active Medication</span>
                  <span className="font-semibold text-foreground">Lisinopril 10mg</span>
                </div>
                <div className="flex justify-between py-2">
                  <span className="text-muted-foreground">Insurance</span>
                  <span className="font-semibold text-emerald-600">Active (BlueCross)</span>
                </div>
              </div>
              <Link
                href="/patient/profile"
                className="mt-4 block text-center rounded-xl bg-secondary py-2 text-xs font-semibold text-foreground hover:bg-muted transition-colors"
              >
                Update Health Records
              </Link>
            </div>

            <div className="rounded-2xl border border-border bg-gradient-to-br from-primary/5 via-card to-card p-6">
              <div className="flex items-center gap-2 text-primary font-semibold text-sm mb-2">
                <ShieldCheck className="h-4 w-4" />
                HIPAA Compliant & Secure
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                All voice transcripts, pre-visit notes, and appointment records are encrypted with 256-bit AES at rest and in transit.
              </p>
            </div>
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}
