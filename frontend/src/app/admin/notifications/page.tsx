"use client";
import React from "react";
import { DashboardShell } from "@/components/dashboard/shell";
import { DataTable, Column } from "@/components/dashboard/data-table";
import { ADMIN_NAV } from "@/lib/constants";
import { mockNotifications } from "@/lib/mock-data";
import { Notification } from "@/types";
import { formatDateTime } from "@/lib/utils";
import { cn } from "@/lib/utils";

const columns: Column<Notification>[] = [
  { key: "title", label: "Title", sortable: true, render: (n) => (
    <div className="flex items-center gap-2">
      {!n.read && <span className="h-2 w-2 rounded-full bg-blue-500 shrink-0" />}
      <span className={cn("font-medium", !n.read && "text-[hsl(var(--foreground))]", n.read && "text-[hsl(var(--muted-foreground))]")}>{n.title}</span>
    </div>
  )},
  { key: "message", label: "Message", render: (n) => <span className="text-xs">{n.message}</span> },
  { key: "type", label: "Type", render: (n) => <span className="capitalize text-xs">{n.type.replace(/_/g, " ")}</span> },
  { key: "created_at", label: "Time", sortable: true, render: (n) => formatDateTime(n.created_at) },
];

export default function NotificationsPage() {
  return (
    <DashboardShell navItems={ADMIN_NAV} sidebarTitle="AI.Prof" sidebarSubtitle="Platform Admin" pageTitle="Notifications" pageSubtitle="System notifications and alerts">
      <DataTable columns={columns} data={mockNotifications} searchPlaceholder="Search notifications..." />
    </DashboardShell>
  );
}
