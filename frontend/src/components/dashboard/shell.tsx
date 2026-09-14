"use client";

import React from "react";
import { Sidebar } from "./sidebar";
import { Topbar } from "./topbar";
import { NavItem } from "@/lib/constants";

interface DashboardShellProps {
  navItems: NavItem[];
  sidebarTitle: string;
  sidebarSubtitle?: string;
  pageTitle: string;
  pageSubtitle?: string;
  children: React.ReactNode;
  actions?: React.ReactNode;
}

export function DashboardShell({
  navItems,
  sidebarTitle,
  sidebarSubtitle,
  pageTitle,
  pageSubtitle,
  children,
  actions,
}: DashboardShellProps) {
  return (
    <div className="min-h-screen bg-[hsl(var(--background))]">
      <Sidebar navItems={navItems} title={sidebarTitle} subtitle={sidebarSubtitle} />
      <div className="ml-64 transition-all duration-300">
        <Topbar title={pageTitle} subtitle={pageSubtitle}>
          {actions}
        </Topbar>
        <main className="p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
