"use client";
import { useQuery } from "@tanstack/react-query";

import { apiGet } from "./api";
import { PlatformKPIs } from "./mock-data";

export interface LiveResult<T> {
  data: T;
  isLive: boolean;      // true = came from the backend, false = empty fallback
  isLoading: boolean;
}

/** Fetch from the backend; on any error fall back to empty data so the
 * UI always renders without using static mock data. */
function useLive<T>(key: string, url: string, fallback: T): LiveResult<T> {
  const q = useQuery({ queryKey: [key], queryFn: () => apiGet<T>(url) });
  const isLive = q.isSuccess && q.data != null;
  return { data: isLive ? (q.data as T) : fallback, isLive, isLoading: q.isLoading };
}

const emptyKpis: PlatformKPIs = {
  total_users: 0, total_hospitals: 0, total_appointments_today: 0,
  active_ai_conversations: 0, total_appointments: 0, booked: 0,
  cancelled: 0, completed: 0, no_show: 0
};

export const useKpis = () => useLive("kpis", "/api/kpis", emptyKpis as any);
export const useDoctors = () => useLive("doctors", "/api/doctors", [] as any[]);
export const useAppointments = () => useLive("appointments", "/api/appointments", [] as any[]);
export const usePatients = () => useLive("patients", "/api/patients", [] as any[]);
export const useHospitals = () => useLive("hospitals", "/api/hospitals", [] as any[]);
export const useWorkflows = () => useLive("workflows", "/api/workflows", [] as any[]);
export const useAudit = () => useLive("audit", "/api/audit", [] as any[]);
export const useAiActivity = () => useLive("ai-activity", "/api/ai-activity", [] as any[]);
export const useEvaluation = () => useLive<any>("evaluation", "/api/evaluation", null);
