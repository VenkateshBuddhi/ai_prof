"use client";

import React, { useState, useRef, useEffect } from "react";
import { Bell, Search, LogOut, User, Settings, ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase";
import { cn } from "@/lib/utils";

interface TopbarProps {
  title: string;
  subtitle?: string;
  children?: React.ReactNode;
}

export function Topbar({ title, subtitle, children }: TopbarProps) {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const router = useRouter();

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

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
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-[hsl(var(--border))] bg-[hsl(var(--background))/0.8] backdrop-blur-md px-6">
      <div>
        <h1 className="text-lg font-semibold text-[hsl(var(--foreground))]">{title}</h1>
        {subtitle && (
          <p className="text-sm text-[hsl(var(--muted-foreground))]">{subtitle}</p>
        )}
      </div>

      <div className="flex items-center gap-3">
        {/* Search */}
        <div className="relative hidden md:block">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[hsl(var(--muted-foreground))]" />
          <input
            type="text"
            placeholder="Search... (⌘K)"
            className="h-9 w-64 rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--muted))] pl-9 pr-4 text-sm text-[hsl(var(--foreground))] placeholder:text-[hsl(var(--muted-foreground))] focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500 transition-all"
          />
        </div>

        {/* Extra actions */}
        {children}

        {/* Notifications */}
        <button className="relative rounded-lg p-2 text-[hsl(var(--muted-foreground))] hover:bg-[hsl(var(--muted))] hover:text-[hsl(var(--foreground))] transition-colors">
          <Bell className="h-5 w-5" />
          <span className="absolute right-1.5 top-1.5 flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-75"></span>
            <span className="relative inline-flex h-2 w-2 rounded-full bg-blue-500"></span>
          </span>
        </button>

        {/* Avatar with Dropdown */}
        <div className="relative" ref={dropdownRef}>
          <button
            onClick={() => setDropdownOpen(!dropdownOpen)}
            className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-blue-500 to-cyan-400 text-white text-sm font-bold cursor-pointer hover:ring-2 hover:ring-blue-500/30 transition-all focus:outline-none"
          >
            AI
          </button>

          {dropdownOpen && (
            <div className="absolute right-0 mt-2 w-56 rounded-2xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] shadow-xl py-2 z-50 animate-in fade-in zoom-in-95">
              <div className="px-4 py-2 border-b border-[hsl(var(--border))]">
                <p className="text-xs font-semibold text-[hsl(var(--foreground))]">Active Session</p>
                <p className="text-[11px] text-[hsl(var(--muted-foreground))] truncate">admin@aiprof.health</p>
              </div>

              <div className="py-1">
                <button
                  onClick={() => {
                    setDropdownOpen(false);
                    handleSignOut();
                  }}
                  className="w-full flex items-center gap-2.5 px-4 py-2 text-xs font-semibold text-red-500 hover:bg-red-500/10 transition-colors text-left cursor-pointer"
                >
                  <LogOut className="h-4 w-4 shrink-0" />
                  Sign Out
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
