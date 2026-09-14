"use client";

import React from "react";
import { cn } from "@/lib/utils";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import * as LucideIcons from "lucide-react";

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: string;
  trend?: {
    value: number;
    label: string;
  };
  color?: "blue" | "teal" | "purple" | "amber" | "rose" | "emerald";
  className?: string;
}

const colorMap = {
  blue: {
    bg: "bg-blue-50 dark:bg-blue-900/20",
    icon: "text-blue-600 dark:text-blue-400",
    ring: "ring-blue-500/20",
  },
  teal: {
    bg: "bg-teal-50 dark:bg-teal-900/20",
    icon: "text-teal-600 dark:text-teal-400",
    ring: "ring-teal-500/20",
  },
  purple: {
    bg: "bg-purple-50 dark:bg-purple-900/20",
    icon: "text-purple-600 dark:text-purple-400",
    ring: "ring-purple-500/20",
  },
  amber: {
    bg: "bg-amber-50 dark:bg-amber-900/20",
    icon: "text-amber-600 dark:text-amber-400",
    ring: "ring-amber-500/20",
  },
  rose: {
    bg: "bg-rose-50 dark:bg-rose-900/20",
    icon: "text-rose-600 dark:text-rose-400",
    ring: "ring-rose-500/20",
  },
  emerald: {
    bg: "bg-emerald-50 dark:bg-emerald-900/20",
    icon: "text-emerald-600 dark:text-emerald-400",
    ring: "ring-emerald-500/20",
  },
};

export function StatCard({
  title,
  value,
  subtitle,
  icon,
  trend,
  color = "blue",
  className,
}: StatCardProps) {
  const colors = colorMap[color];
  const IconComponent = (LucideIcons as Record<string, React.ElementType>)[icon] || LucideIcons.Activity;

  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5 transition-all duration-300 hover:shadow-lg hover:shadow-blue-500/5 hover:-translate-y-0.5 group",
        className
      )}
    >
      {/* Background accent */}
      <div className="absolute top-0 right-0 h-24 w-24 rounded-full bg-gradient-to-bl from-blue-500/5 to-transparent -translate-y-8 translate-x-8 group-hover:scale-150 transition-transform duration-500" />

      <div className="flex items-start justify-between">
        <div className="space-y-2">
          <p className="text-sm font-medium text-[hsl(var(--muted-foreground))]">{title}</p>
          <p className="text-2xl font-bold text-[hsl(var(--foreground))] animate-counter">
            {typeof value === "number" ? value.toLocaleString() : value}
          </p>
          {trend && (
            <div className="flex items-center gap-1.5">
              {trend.value > 0 ? (
                <TrendingUp className="h-3.5 w-3.5 text-emerald-500" />
              ) : trend.value < 0 ? (
                <TrendingDown className="h-3.5 w-3.5 text-red-500" />
              ) : (
                <Minus className="h-3.5 w-3.5 text-gray-400" />
              )}
              <span
                className={cn(
                  "text-xs font-medium",
                  trend.value > 0 ? "text-emerald-600 dark:text-emerald-400" : trend.value < 0 ? "text-red-600 dark:text-red-400" : "text-gray-500"
                )}
              >
                {trend.value > 0 ? "+" : ""}
                {trend.value}% {trend.label}
              </span>
            </div>
          )}
          {subtitle && !trend && (
            <p className="text-xs text-[hsl(var(--muted-foreground))]">{subtitle}</p>
          )}
        </div>

        <div className={cn("flex h-11 w-11 shrink-0 items-center justify-center rounded-xl", colors.bg)}>
          <IconComponent className={cn("h-5 w-5", colors.icon)} />
        </div>
      </div>
    </div>
  );
}
