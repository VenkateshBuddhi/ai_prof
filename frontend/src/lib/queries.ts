"use client";
import { useQuery } from "@tanstack/react-query";

import { apiGet } from "./api";
import {
  mockPlatformKPIs,
  mockDoctors,
  mockAppointments,
  mockPatients,
  mockHospitals,
  mockWorkflows,
  mockAuditEvents,
} from "./mock-data";

export interface LiveResult<T> {
  data: T;
  isLive: boolean;      // true = came from the backend, false = mock fallback
  isLoading: boolean;
}

/** Fetch from the backend; on any error fall back to bundled mock data so the
 * UI always renders. `isLive` tells the page which source it's showing. */
function useLive<T>(key: string, url: string, fallback: T): LiveResult<T> {
  const q = useQuery({ queryKey: [key], queryFn: () => apiGet<T>(url) });
  const isLive = q.isSuccess && q.data != null;
  return { data: isLive ? (q.data as T) : fallback, isLive, isLoading: q.isLoading };
}

export const useKpis = () => useLive("kpis", "/api/kpis", mockPlatformKPIs as any);
export const useDoctors = () => useLive("doctors", "/api/doctors", mockDoctors);
export const useAppointments = () => useLive("appointments", "/api/appointments", mockAppointments);
export const usePatients = () => useLive("patients", "/api/patients", mockPatients);
export const useHospitals = () => useLive("hospitals", "/api/hospitals", mockHospitals);
export const useWorkflows = () => useLive("workflows", "/api/workflows", mockWorkflows);
export const useAudit = () => useLive("audit", "/api/audit", mockAuditEvents);
export const useEvaluation = () => useLive<any>("evaluation", "/api/evaluation", null);
