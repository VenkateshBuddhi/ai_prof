"use client";
import React from "react";
import { DashboardShell } from "@/components/dashboard/shell";
import { HOSPITAL_NAV } from "@/lib/constants";
import { mockQuestionnaires } from "@/lib/mock-data";
import { StatusBadge } from "@/components/dashboard/data-table";
import { Plus, GripVertical } from "lucide-react";

export default function HospitalQuestionnairesPage() {
  return (
    <DashboardShell navItems={HOSPITAL_NAV} sidebarTitle="City General Hospital" sidebarSubtitle="Hospital Admin" pageTitle="Questionnaires" pageSubtitle="Pre-visit questionnaire templates"
      actions={<button className="flex items-center gap-2 rounded-lg bg-gradient-to-r from-blue-600 to-cyan-500 px-4 py-2 text-sm font-medium text-white hover:from-blue-700 hover:to-cyan-600 transition-all"><Plus className="h-4 w-4" />New Questionnaire</button>}>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {mockQuestionnaires.map(q => (
          <div key={q.id} className="rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-semibold">{q.title}</h3>
                <p className="text-xs text-[hsl(var(--muted-foreground))]">{q.specialty} • {q.questions.length} questions</p>
              </div>
              <StatusBadge status={q.status} />
            </div>
            <div className="space-y-2">
              {q.questions.map(question => (
                <div key={question.id} className="flex items-center gap-3 rounded-lg bg-[hsl(var(--muted))] px-3 py-2">
                  <GripVertical className="h-4 w-4 text-[hsl(var(--muted-foreground))] shrink-0" />
                  <span className="text-sm flex-1">{question.text}</span>
                  <span className="text-xs text-[hsl(var(--muted-foreground))] capitalize shrink-0">{question.type.replace(/_/g, " ")}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </DashboardShell>
  );
}
