import { UserRole } from "@/types";

export const APP_NAME = "AI.Prof";
export const APP_DESCRIPTION = "AI-Native Healthcare Operations Platform";

// Route maps per role
export const ROLE_ROUTES: Record<UserRole, string> = {
  platform_admin: "/admin",
  hospital_admin: "/hospital",
  doctor: "/doctor",
  patient: "/patient",
};

// Sidebar navigation per role
export interface NavItem {
  label: string;
  href: string;
  icon: string; // lucide icon name
  badge?: string;
}

export const ADMIN_NAV: NavItem[] = [
  { label: "Overview", href: "/admin", icon: "LayoutDashboard" },
  { label: "Hospital Applications", href: "/admin/applications", icon: "FileCheck" },
  { label: "Hospitals", href: "/admin/hospitals", icon: "Building2" },
  { label: "Doctors", href: "/admin/doctors", icon: "Stethoscope" },
  { label: "Patients", href: "/admin/patients", icon: "Users" },
  { label: "Appointments", href: "/admin/appointments", icon: "CalendarCheck" },
  { label: "AI Activity", href: "/admin/ai-activity", icon: "Bot" },
  { label: "EHR Integration", href: "/admin/integrations", icon: "Link2" },
  { label: "Workflows", href: "/admin/workflows", icon: "GitBranch" },
  { label: "Notifications", href: "/admin/notifications", icon: "Bell" },
  { label: "Analytics", href: "/admin/analytics", icon: "BarChart3" },
  { label: "AI Evaluation", href: "/admin/evaluation", icon: "Target" },
  { label: "Operational Health", href: "/admin/health", icon: "Activity" },
  { label: "Audit Logs", href: "/admin/audit", icon: "ScrollText" },
  { label: "Users & Access", href: "/admin/users", icon: "Shield" },
  { label: "Settings", href: "/admin/settings", icon: "Settings" },
];

export const HOSPITAL_NAV: NavItem[] = [
  { label: "Overview", href: "/hospital", icon: "LayoutDashboard" },
  { label: "Appointments", href: "/hospital/appointments", icon: "CalendarCheck" },
  { label: "Doctors", href: "/hospital/doctors", icon: "Stethoscope" },
  { label: "Calendars", href: "/hospital/calendars", icon: "Calendar" },
  { label: "Availability", href: "/hospital/availability", icon: "Clock" },
  { label: "Questionnaires", href: "/hospital/questionnaires", icon: "ClipboardList" },
  { label: "Patients", href: "/hospital/patients", icon: "Users" },
  { label: "AI Activity", href: "/hospital/ai-activity", icon: "Bot" },
  { label: "EHR Integration", href: "/hospital/integrations", icon: "Link2" },
  { label: "Workflows", href: "/hospital/workflows", icon: "GitBranch" },
  { label: "Notifications", href: "/hospital/notifications", icon: "Bell" },
  { label: "Analytics", href: "/hospital/analytics", icon: "BarChart3" },
  { label: "Hospital Settings", href: "/hospital/settings", icon: "Settings" },
  { label: "EHR Config", href: "/hospital/ehr", icon: "Plug" },
  { label: "Staff & Access", href: "/hospital/staff", icon: "Shield" },
];

export const DOCTOR_NAV: NavItem[] = [
  { label: "Overview", href: "/doctor", icon: "LayoutDashboard" },
  { label: "My Calendar", href: "/doctor/calendar", icon: "Calendar" },
  { label: "Appointments", href: "/doctor/appointments", icon: "CalendarCheck" },
  { label: "Availability", href: "/doctor/availability", icon: "Clock" },
  { label: "Blocked Time", href: "/doctor/blocked", icon: "CalendarOff" },
  { label: "Questionnaires", href: "/doctor/questionnaires", icon: "ClipboardList" },
  { label: "Pre-Visit Responses", href: "/doctor/responses", icon: "FileText" },
  { label: "Profile", href: "/doctor/profile", icon: "UserCircle" },
  { label: "Settings", href: "/doctor/settings", icon: "Settings" },
];

export const PATIENT_NAV: NavItem[] = [
  { label: "Home", href: "/patient", icon: "Home" },
  { label: "AI Assistant", href: "/patient/assistant", icon: "Mic" },
  { label: "My Appointments", href: "/patient/appointments", icon: "CalendarCheck" },
  { label: "History", href: "/patient/history", icon: "History" },
  { label: "Preferences", href: "/patient/preferences", icon: "Heart" },
  { label: "Profile", href: "/patient/profile", icon: "UserCircle" },
  { label: "Settings", href: "/patient/settings", icon: "Settings" },
];

export const APPOINTMENT_STATUSES = [
  "requested",
  "pending",
  "confirmed",
  "rescheduled",
  "cancelled",
  "completed",
  "no_show",
  "failed",
] as const;

export const SPECIALTIES = [
  "Cardiology",
  "Dermatology",
  "Endocrinology",
  "Gastroenterology",
  "General Medicine",
  "Neurology",
  "Oncology",
  "Ophthalmology",
  "Orthopedics",
  "Pediatrics",
  "Psychiatry",
  "Pulmonology",
  "Radiology",
  "Urology",
];
