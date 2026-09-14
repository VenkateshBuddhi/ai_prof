"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Activity, Eye, EyeOff } from "lucide-react";

const DEMO_ACCOUNTS = [
  { label: "Platform Admin", email: "admin@aiprof.com", role: "platform_admin", path: "/admin" },
  { label: "Hospital Admin", email: "hospital@citygeneral.com", role: "hospital_admin", path: "/hospital" },
  { label: "Doctor", email: "dr.sharma@citygeneral.com", role: "doctor", path: "/doctor" },
  { label: "Patient", email: "ravi@email.com", role: "patient", path: "/patient" },
];

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleLogin = (path: string) => {
    setLoading(true);
    setTimeout(() => {
      router.push(path);
    }, 500);
  };

  return (
    <div className="min-h-screen flex">
      {/* Left - Brand Panel */}
      <div className="hidden lg:flex lg:w-1/2 relative bg-gradient-to-br from-blue-600 via-blue-700 to-cyan-600 overflow-hidden">
        {/* Animated background shapes */}
        <div className="absolute inset-0">
          <div className="absolute top-20 left-20 h-72 w-72 rounded-full bg-white/10 blur-3xl animate-pulse" />
          <div className="absolute bottom-32 right-16 h-96 w-96 rounded-full bg-cyan-400/10 blur-3xl animate-pulse" style={{ animationDelay: "1s" }} />
          <div className="absolute top-1/2 left-1/3 h-48 w-48 rounded-full bg-blue-300/10 blur-2xl animate-pulse" style={{ animationDelay: "2s" }} />
        </div>

        <div className="relative z-10 flex flex-col justify-center px-16">
          <div className="flex items-center gap-3 mb-8">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-white/20 backdrop-blur-sm">
              <Activity className="h-7 w-7 text-white" />
            </div>
            <span className="text-2xl font-bold text-white">AI.Prof</span>
          </div>

          <h1 className="text-4xl font-bold text-white leading-tight mb-4">
            AI-Native Healthcare
            <br />
            Operations Platform
          </h1>
          <p className="text-lg text-blue-100/80 max-w-md">
            Multi-hospital scheduling, voice AI, EHR integration, and workflow automation — unified in one intelligent platform.
          </p>

          {/* Feature pills */}
          <div className="flex flex-wrap gap-2 mt-8">
            {["Voice AI", "Multi-Tenant", "EHR Integration", "Real-Time", "HIPAA Ready"].map((f) => (
              <span key={f} className="rounded-full bg-white/10 backdrop-blur-sm px-3 py-1.5 text-sm text-white/90 border border-white/10">
                {f}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Right - Login Form */}
      <div className="flex-1 flex items-center justify-center p-8 bg-[hsl(var(--background))]">
        <div className="w-full max-w-md space-y-8">
          {/* Mobile logo */}
          <div className="lg:hidden flex items-center gap-3 justify-center mb-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-cyan-400">
              <Activity className="h-6 w-6 text-white" />
            </div>
            <span className="text-xl font-bold">AI.Prof</span>
          </div>

          <div>
            <h2 className="text-2xl font-bold text-[hsl(var(--foreground))]">Welcome back</h2>
            <p className="mt-1 text-sm text-[hsl(var(--muted-foreground))]">
              Sign in to your account to continue
            </p>
          </div>

          {/* Demo Quick Login */}
          <div className="space-y-2">
            <p className="text-xs font-medium text-[hsl(var(--muted-foreground))] uppercase tracking-wider">
              Quick Demo Access
            </p>
            <div className="grid grid-cols-2 gap-2">
              {DEMO_ACCOUNTS.map((account) => (
                <button
                  key={account.role}
                  onClick={() => handleLogin(account.path)}
                  className="flex flex-col items-start rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-3 text-left hover:border-blue-500/50 hover:shadow-md hover:shadow-blue-500/5 transition-all duration-200 group"
                >
                  <span className="text-sm font-medium text-[hsl(var(--foreground))] group-hover:text-blue-600 transition-colors">
                    {account.label}
                  </span>
                  <span className="text-xs text-[hsl(var(--muted-foreground))] truncate w-full">
                    {account.email}
                  </span>
                </button>
              ))}
            </div>
          </div>

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-[hsl(var(--border))]" />
            </div>
            <div className="relative flex justify-center text-xs">
              <span className="bg-[hsl(var(--background))] px-3 text-[hsl(var(--muted-foreground))]">
                or sign in with email
              </span>
            </div>
          </div>

          {/* Email/Password Form */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleLogin("/admin");
            }}
            className="space-y-4"
          >
            <div>
              <label className="block text-sm font-medium text-[hsl(var(--foreground))] mb-1.5">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@hospital.com"
                className="h-11 w-full rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--background))] px-4 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500 transition-all"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-[hsl(var(--foreground))] mb-1.5">
                Password
              </label>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="h-11 w-full rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--background))] px-4 pr-10 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500 transition-all"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="h-11 w-full rounded-lg bg-gradient-to-r from-blue-600 to-cyan-500 text-white font-medium text-sm hover:from-blue-700 hover:to-cyan-600 focus:outline-none focus:ring-2 focus:ring-blue-500/50 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Signing in...
                </span>
              ) : (
                "Sign In"
              )}
            </button>
          </form>

          <p className="text-center text-sm text-[hsl(var(--muted-foreground))]">
            New hospital?{" "}
            <Link href="/register/hospital" className="text-blue-600 hover:text-blue-700 font-medium">
              Register here
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
