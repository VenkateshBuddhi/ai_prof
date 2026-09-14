"use client";
import React from "react";
import { DashboardShell } from "@/components/dashboard/shell";
import { ADMIN_NAV } from "@/lib/constants";
import { useEvaluation } from "@/lib/queries";
import { LiveBadge } from "@/components/dashboard/live-badge";

const DEFAULT_METRICS = [
  { label: "Intent Accuracy", value: 94.2, color: "blue" },
  { label: "Context Resolution", value: 91.8, color: "teal" },
  { label: "Capability Selection", value: 96.1, color: "purple" },
  { label: "Booking Verification", value: 98.4, color: "emerald" },
  { label: "EHR Integration Success", value: 97.8, color: "blue" },
  { label: "Safety Compliance", value: 99.1, color: "emerald" },
];

function metricsFromScorecard(sc: any) {
  if (!sc) return DEFAULT_METRICS;
  const v = (x: number | null | undefined) => (typeof x === "number" ? x : 0);
  return [
    { label: "Intent Accuracy", value: v(sc.intent_accuracy_pct), color: "blue" },
    { label: "Capability Selection", value: v(sc.capability_selection_pct), color: "purple" },
    { label: "Tool-Arg Correctness", value: v(sc.tool_arg_correctness_pct), color: "teal" },
    { label: "Booking Verification", value: v(sc.booking_verification_pct), color: "emerald" },
    { label: "Capability Success", value: v(sc.capability_success_pct), color: "blue" },
    { label: "Safety Compliance", value: v(sc.safety_compliance_pct), color: "emerald" },
  ];
}

function GaugeChart({ value, label, color }: { value: number; label: string; color: string }) {
  const colorMap: Record<string, string> = { blue: "#3b82f6", teal: "#14b8a6", purple: "#8b5cf6", emerald: "#10b981" };
  const fill = colorMap[color] || colorMap.blue;
  const circumference = 2 * Math.PI * 45;
  const offset = circumference - (value / 100) * circumference;

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative h-28 w-28">
        <svg className="h-28 w-28 -rotate-90" viewBox="0 0 100 100">
          <circle cx="50" cy="50" r="45" fill="none" stroke="hsl(var(--muted))" strokeWidth="8" />
          <circle cx="50" cy="50" r="45" fill="none" stroke={fill} strokeWidth="8" strokeDasharray={circumference} strokeDashoffset={offset} strokeLinecap="round" className="transition-all duration-1000 ease-out" />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-xl font-bold text-[hsl(var(--foreground))]">{value}%</span>
        </div>
      </div>
      <p className="text-sm font-medium text-[hsl(var(--muted-foreground))] text-center">{label}</p>
    </div>
  );
}

export default function EvaluationPage() {
  const { data: report, isLive, isLoading } = useEvaluation();
  const scorecard = report && report.scorecard ? report.scorecard : null;
  const metrics = metricsFromScorecard(scorecard);
  const results: Array<{ scenario: string; passed: boolean }> = (report && report.results) || [];

  return (
    <DashboardShell navItems={ADMIN_NAV} sidebarTitle="AI.Prof" sidebarSubtitle="Platform Admin" pageTitle="AI Evaluation" pageSubtitle="Systematic AI quality metrics">
      <div className="mb-4"><LiveBadge live={isLive && !!scorecard} loading={isLoading} /></div>
      <div className="rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-8 mb-8">
        <h3 className="text-sm font-semibold text-[hsl(var(--foreground))] mb-8 text-center">AI Performance Metrics</h3>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-8">
          {metrics.map((m) => (
            <GaugeChart key={m.label} value={m.value} label={m.label} color={m.color} />
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5">
          <h3 className="text-sm font-semibold mb-4">Recent Evaluation Results</h3>
          <div className="space-y-3">
            {(results.length
              ? results.map((r) => ({ test: r.scenario.replace(/_/g, " "), pass: r.passed }))
              : [
                  { test: "Booking intent detection", pass: true },
                  { test: "Context resolution (same doctor)", pass: true },
                  { test: "Ambiguity handling (multiple slots)", pass: true },
                  { test: "Unsupported request rejection", pass: true },
                  { test: "EHR appointment mapping", pass: true },
                  { test: "Safety boundary (diagnosis prevention)", pass: true },
                ]
            ).map((t, i) => (
              <div key={i} className="flex items-center justify-between rounded-lg px-3 py-2.5 bg-[hsl(var(--muted))]">
                <span className="text-sm capitalize">{t.test}</span>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono">{t.pass ? "PASS" : "FAIL"}</span>
                  <span className={`h-2 w-2 rounded-full ${t.pass ? "bg-emerald-500" : "bg-red-500"}`} />
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5">
          <h3 className="text-sm font-semibold mb-4">Common Failure Categories</h3>
          <div className="space-y-3">
            {[
              { category: "Context leakage", count: 2, severity: "low" },
              { category: "Incorrect capability selection", count: 5, severity: "medium" },
              { category: "Ambiguous slot interpretation", count: 3, severity: "low" },
              { category: "EHR mapping error", count: 1, severity: "high" },
              { category: "Timeout in tool execution", count: 4, severity: "medium" },
            ].map((f, i) => (
              <div key={i} className="flex items-center justify-between rounded-lg px-3 py-2.5 bg-[hsl(var(--muted))]">
                <span className="text-sm">{f.category}</span>
                <div className="flex items-center gap-2">
                  <span className="text-xs">{f.count} occurrences</span>
                  <span className={`h-2 w-2 rounded-full ${f.severity === "high" ? "bg-red-500" : f.severity === "medium" ? "bg-amber-500" : "bg-blue-500"}`} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}
