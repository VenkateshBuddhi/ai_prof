"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import { NavItem } from "@/lib/constants";
import { createClient } from "@/lib/supabase";
import {
  LayoutDashboard, FileCheck, Building2, Stethoscope, Users, CalendarCheck,
  Bot, Link2, GitBranch, Bell, BarChart3, Target, Activity, ScrollText,
  Shield, Settings, Calendar, Clock, ClipboardList, Plug, Home, Mic,
  History, Heart, UserCircle, CalendarOff, FileText, ChevronLeft,
  ChevronRight, LogOut, Moon, Sun,
} from "lucide-react";

const iconMap: Record<string, React.ElementType> = {
  LayoutDashboard, FileCheck, Building2, Stethoscope, Users, CalendarCheck,
  Bot, Link2, GitBranch, Bell, BarChart3, Target, Activity, ScrollText,
  Shield, Settings, Calendar, Clock, ClipboardList, Plug, Home, Mic,
  History, Heart, UserCircle, CalendarOff, FileText,
};

interface SidebarProps {
  navItems: NavItem[];
  title: string;
  subtitle?: string;
}

export function Sidebar({ navItems, title, subtitle }: SidebarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const [darkMode, setDarkMode] = useState(false);

  const toggleDarkMode = () => {
    setDarkMode(!darkMode);
    document.documentElement.classList.toggle("dark");
  };

  const handleSignOut = async () => {
    try {
      const supabase = createClient();
      await supabase.auth.signOut();
    } catch {
      // Ignore if Supabase is not configured yet
    }
    if (typeof window !== "undefined") {
      sessionStorage.clear();
      localStorage.removeItem("supabase.auth.token");
    }
    router.push("/login");
  };

  return (
    <aside
      className={cn(
        "fixed left-0 top-0 z-40 h-screen flex flex-col border-r border-[hsl(var(--border))] bg-[hsl(var(--card))] transition-all duration-300 ease-in-out",
        collapsed ? "w-[4.5rem]" : "w-64"
      )}
    >
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-5 border-b border-[hsl(var(--border))]">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500 to-cyan-400 text-white font-bold text-sm">
          AI
        </div>
        {!collapsed && (
          <div className="animate-fade-in overflow-hidden">
            <h1 className="font-bold text-sm text-[hsl(var(--foreground))]">{title}</h1>
            {subtitle && (
              <p className="text-xs text-[hsl(var(--muted-foreground))] truncate">{subtitle}</p>
            )}
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
        {navItems.map((item) => {
          const Icon = iconMap[item.icon] || LayoutDashboard;
          const isActive = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href + "/"));
          const isExactActive = pathname === item.href;

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-200 group",
                isExactActive || isActive
                  ? "bg-blue-50 text-blue-700 dark:bg-blue-900/20 dark:text-blue-400 shadow-sm"
                  : "text-[hsl(var(--muted-foreground))] hover:bg-[hsl(var(--muted))] hover:text-[hsl(var(--foreground))]"
              )}
              title={collapsed ? item.label : undefined}
            >
              <Icon
                className={cn(
                  "h-5 w-5 shrink-0 transition-colors",
                  isExactActive || isActive
                    ? "text-blue-600 dark:text-blue-400"
                    : "text-[hsl(var(--muted-foreground))] group-hover:text-[hsl(var(--foreground))]"
                )}
              />
              {!collapsed && (
                <span className="truncate animate-fade-in">{item.label}</span>
              )}
              {!collapsed && item.badge && (
                <span className="ml-auto shrink-0 rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
                  {item.badge}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="border-t border-[hsl(var(--border))] px-3 py-3 space-y-1">
        <button
          onClick={toggleDarkMode}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-[hsl(var(--muted-foreground))] hover:bg-[hsl(var(--muted))] hover:text-[hsl(var(--foreground))] transition-colors"
        >
          {darkMode ? <Sun className="h-5 w-5 shrink-0" /> : <Moon className="h-5 w-5 shrink-0" />}
          {!collapsed && <span>{darkMode ? "Light Mode" : "Dark Mode"}</span>}
        </button>
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-[hsl(var(--muted-foreground))] hover:bg-[hsl(var(--muted))] hover:text-[hsl(var(--foreground))] transition-colors"
        >
          {collapsed ? <ChevronRight className="h-5 w-5 shrink-0" /> : <ChevronLeft className="h-5 w-5 shrink-0" />}
          {!collapsed && <span>Collapse</span>}
        </button>
        <button
          onClick={handleSignOut}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-red-500 hover:bg-red-50 dark:hover:bg-red-900/10 transition-colors cursor-pointer"
        >
          <LogOut className="h-5 w-5 shrink-0" />
          {!collapsed && <span>Sign Out</span>}
        </button>
      </div>
    </aside>
  );
}
