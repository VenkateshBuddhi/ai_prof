"use client";

import React, { useState } from "react";
import Link from "next/link";
import { Building2, ArrowLeft, CheckCircle2, ShieldCheck, Mail, Phone, MapPin, Globe, Stethoscope, Sparkles } from "lucide-react";

export default function RegisterHospitalPage() {
  const [submitted, setSubmitted] = useState(false);
  const [formData, setFormData] = useState({
    hospitalName: "",
    domain: "",
    adminName: "",
    adminEmail: "",
    phone: "",
    address: "",
    ehrSystem: "Medplum",
    npi: "",
    departments: "Cardiology, General Medicine, Orthopedics",
    notes: "",
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitted(true);
  };

  return (
    <div className="min-h-screen bg-[hsl(var(--background))] text-[hsl(var(--foreground))] flex flex-col justify-between p-6 sm:p-12">
      <div className="max-w-3xl mx-auto w-full space-y-8">
        {/* Navigation */}
        <div className="flex items-center justify-between">
          <Link
            href="/login"
            className="inline-flex items-center gap-2 text-sm font-semibold text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Sign In
          </Link>
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500 to-cyan-400 text-white font-bold text-xs">
              AI
            </div>
            <span className="font-bold text-sm tracking-tight">AI.Prof</span>
          </div>
        </div>

        {!submitted ? (
          <div className="rounded-3xl border border-border bg-card p-8 sm:p-10 shadow-xl space-y-8">
            <div>
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/10 text-blue-600 text-xs font-semibold mb-3 border border-blue-500/20">
                <Building2 className="h-3.5 w-3.5" />
                Hospital Onboarding Application
              </div>
              <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-foreground">
                Register Your Healthcare Institution
              </h1>
              <p className="text-sm text-muted-foreground mt-2 leading-relaxed">
                Connect your hospital with the AI.Prof autonomous patient intake platform. Once submitted, our platform admin team will review and provision your dedicated tenant environment.
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-6">
              {/* Institution Details */}
              <div className="space-y-4">
                <h3 className="text-sm font-bold uppercase tracking-wider text-muted-foreground">
                  Institution Details
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold mb-1.5">Hospital / Clinic Name *</label>
                    <input
                      required
                      type="text"
                      placeholder="e.g. City General Hospital"
                      value={formData.hospitalName}
                      onChange={(e) => setFormData({ ...formData, hospitalName: e.target.value })}
                      className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold mb-1.5">Custom Domain / Subdomain</label>
                    <input
                      type="text"
                      placeholder="e.g. citygeneral.aiprof.health"
                      value={formData.domain}
                      onChange={(e) => setFormData({ ...formData, domain: e.target.value })}
                      className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold mb-1.5">Hospital NPI / Tax ID *</label>
                    <input
                      required
                      type="text"
                      placeholder="e.g. 1928374650"
                      value={formData.npi}
                      onChange={(e) => setFormData({ ...formData, npi: e.target.value })}
                      className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold mb-1.5">EHR Integration Engine</label>
                    <select
                      value={formData.ehrSystem}
                      onChange={(e) => setFormData({ ...formData, ehrSystem: e.target.value })}
                      className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                    >
                      <option value="Medplum">Medplum (Open-source FHIR API)</option>
                      <option value="Epic">Epic Systems (FHIR R4)</option>
                      <option value="Cerner">Oracle Cerner (Millennium FHIR)</option>
                      <option value="Custom">Custom Proprietary EHR</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* Administrator Contact */}
              <div className="space-y-4 pt-4 border-t border-border">
                <h3 className="text-sm font-bold uppercase tracking-wider text-muted-foreground">
                  Primary Administrator
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold mb-1.5">Admin Full Name *</label>
                    <input
                      required
                      type="text"
                      placeholder="e.g. Dr. Arthur Pendelton"
                      value={formData.adminName}
                      onChange={(e) => setFormData({ ...formData, adminName: e.target.value })}
                      className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold mb-1.5">Official Work Email *</label>
                    <input
                      required
                      type="email"
                      placeholder="e.g. admin@citygeneral.org"
                      value={formData.adminEmail}
                      onChange={(e) => setFormData({ ...formData, adminEmail: e.target.value })}
                      className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold mb-1.5">Phone Number *</label>
                    <input
                      required
                      type="tel"
                      placeholder="e.g. +1 (555) 392-1092"
                      value={formData.phone}
                      onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                      className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold mb-1.5">Physical Address / City *</label>
                    <input
                      required
                      type="text"
                      placeholder="e.g. 100 Medical Center Dr, Boston, MA"
                      value={formData.address}
                      onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                      className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                  </div>
                </div>
              </div>

              {/* Departments & Notes */}
              <div className="space-y-4 pt-4 border-t border-border">
                <div>
                  <label className="block text-xs font-semibold mb-1.5">Departments to Enable (comma separated)</label>
                  <input
                    type="text"
                    value={formData.departments}
                    onChange={(e) => setFormData({ ...formData, departments: e.target.value })}
                    className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold mb-1.5">Additional Deployment Notes / Integration Requests</label>
                  <textarea
                    rows={3}
                    placeholder="Provide any specific voice workflow requirements or legacy system integration notes..."
                    value={formData.notes}
                    onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                    className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>
              </div>

              <div className="pt-4 flex items-center justify-end gap-3">
                <Link
                  href="/login"
                  className="px-5 py-2.5 rounded-xl border border-border text-sm font-semibold text-muted-foreground hover:bg-muted transition-colors"
                >
                  Cancel
                </Link>
                <button
                  type="submit"
                  className="inline-flex items-center gap-2 px-6 py-2.5 rounded-xl bg-primary text-primary-foreground text-sm font-semibold shadow hover:opacity-90 transition-opacity"
                >
                  <Sparkles className="h-4 w-4" />
                  Submit Application
                </button>
              </div>
            </form>
          </div>
        ) : (
          <div className="rounded-3xl border border-emerald-500/30 bg-card p-10 shadow-xl text-center space-y-6 animate-in fade-in zoom-in-95">
            <div className="h-16 w-16 rounded-full bg-emerald-500/10 text-emerald-600 border border-emerald-500/20 flex items-center justify-center mx-auto">
              <CheckCircle2 className="h-8 w-8" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-foreground">Application Received!</h2>
              <p className="text-sm text-muted-foreground mt-2 max-w-md mx-auto">
                Thank you, <span className="font-semibold text-foreground">{formData.adminName || "Administrator"}</span>. Your application for <span className="font-semibold text-foreground">{formData.hospitalName || "your institution"}</span> has been routed to the Platform Admin dashboard for review.
              </p>
            </div>

            <div className="p-4 rounded-2xl bg-muted/50 border border-border max-w-md mx-auto text-xs text-left space-y-2">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Application Reference:</span>
                <span className="font-mono font-bold text-foreground">HOSP-APP-8921</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">EHR Connector:</span>
                <span className="font-semibold text-foreground">{formData.ehrSystem}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Status:</span>
                <span className="font-semibold text-amber-500">Under Review</span>
              </div>
            </div>

            <div className="pt-4 flex justify-center gap-4">
              <Link
                href="/login"
                className="px-6 py-2.5 rounded-xl bg-primary text-primary-foreground text-sm font-semibold shadow hover:opacity-90 transition-opacity"
              >
                Return to Sign In
              </Link>
            </div>
          </div>
        )}

        {/* Footer info */}
        <div className="flex items-center justify-center gap-2 text-xs text-muted-foreground">
          <ShieldCheck className="h-4 w-4 text-emerald-600" />
          <span>HIPAA & SOC2 Type II Certified Healthcare Cloud</span>
        </div>
      </div>
    </div>
  );
}
