"use client";
import React from "react";
import { DashboardShell } from "@/components/dashboard/shell";
import { HOSPITAL_NAV } from "@/lib/constants";
import { Construction } from "lucide-react";

export default function Page() {
  return (
    <DashboardShell navItems={HOSPITAL_NAV} sidebarTitle="City General Hospital" sidebarSubtitle="Hospital Admin" pageTitle="EHR Configuration" pageSubtitle="Healthcare system integration settings">
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-blue-100 dark:bg-blue-900/20 mb-4">
          <Construction className="h-8 w-8 text-blue-600 dark:text-blue-400" />
        </div>
        <h2 className="text-lg font-semibold text-[hsl(var(--foreground))] mb-1">EHR Configuration</h2>
        <p className="text-sm text-[hsl(var(--muted-foreground))] max-w-sm">Healthcare system integration settings. This page is connected and will display live data when the backend API is integrated.</p>
      </div>
    </DashboardShell>
  );
}
