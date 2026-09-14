"use client";
import React from "react";

/** Small indicator showing whether a page's data is coming from the live backend
 * or the bundled mock fallback. */
export function LiveBadge({ live, loading }: { live: boolean; loading?: boolean }) {
  if (loading) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-[hsl(var(--muted))] px-2.5 py-1 text-xs font-medium text-[hsl(var(--muted-foreground))]">
        <span className="h-2 w-2 rounded-full bg-gray-400 animate-pulse" /> Loading…
      </span>
    );
  }
  return live ? (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-medium text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400">
      <span className="h-2 w-2 rounded-full bg-emerald-500" /> Live API
    </span>
  ) : (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-100 px-2.5 py-1 text-xs font-medium text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
      <span className="h-2 w-2 rounded-full bg-amber-500" /> Mock data
    </span>
  );
}
