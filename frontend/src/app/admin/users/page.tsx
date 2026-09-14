"use client";
import React from "react";
import { DashboardShell } from "@/components/dashboard/shell";
import { ADMIN_NAV } from "@/lib/constants";
import { Shield, Plus, MoreHorizontal } from "lucide-react";

const users = [
  { id: "1", name: "Platform Admin", email: "admin@aiprof.com", role: "Platform Admin", status: "active", lastLogin: "2 hours ago" },
  { id: "2", name: "Hospital Admin", email: "admin@citygeneral.com", role: "Hospital Admin", status: "active", lastLogin: "1 day ago" },
  { id: "3", name: "Support Agent", email: "support@aiprof.com", role: "Support", status: "active", lastLogin: "5 hours ago" },
];

export default function UsersPage() {
  return (
    <DashboardShell navItems={ADMIN_NAV} sidebarTitle="AI.Prof" sidebarSubtitle="Platform Admin" pageTitle="Users & Access" pageSubtitle="Manage platform users and roles"
      actions={<button className="flex items-center gap-2 rounded-lg bg-gradient-to-r from-blue-600 to-cyan-500 px-4 py-2 text-sm font-medium text-white hover:from-blue-700 hover:to-cyan-600 transition-all"><Plus className="h-4 w-4" />Add User</button>}>
      <div className="rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] overflow-hidden">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-[hsl(var(--border))] bg-[hsl(var(--muted))]">
            <th className="px-4 py-3 text-left font-medium text-[hsl(var(--muted-foreground))]">User</th>
            <th className="px-4 py-3 text-left font-medium text-[hsl(var(--muted-foreground))]">Role</th>
            <th className="px-4 py-3 text-left font-medium text-[hsl(var(--muted-foreground))]">Status</th>
            <th className="px-4 py-3 text-left font-medium text-[hsl(var(--muted-foreground))]">Last Login</th>
            <th className="px-4 py-3 text-left font-medium text-[hsl(var(--muted-foreground))]"></th>
          </tr></thead>
          <tbody>
            {users.map(u => (
              <tr key={u.id} className="border-b border-[hsl(var(--border))] last:border-0 hover:bg-[hsl(var(--muted))] transition-colors">
                <td className="px-4 py-3"><div><p className="font-medium">{u.name}</p><p className="text-xs text-[hsl(var(--muted-foreground))]">{u.email}</p></div></td>
                <td className="px-4 py-3"><span className="inline-flex items-center gap-1.5 text-xs"><Shield className="h-3 w-3" />{u.role}</span></td>
                <td className="px-4 py-3"><span className="inline-flex items-center rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700 capitalize">{u.status}</span></td>
                <td className="px-4 py-3 text-[hsl(var(--muted-foreground))]">{u.lastLogin}</td>
                <td className="px-4 py-3"><button className="rounded-lg p-1.5 hover:bg-[hsl(var(--muted))]"><MoreHorizontal className="h-4 w-4" /></button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </DashboardShell>
  );
}
