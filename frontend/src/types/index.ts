// ===== User & Auth =====
export type UserRole = "platform_admin" | "hospital_admin" | "doctor" | "patient";

export interface User {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  avatar_url?: string;
  tenant_id?: string;
  hospital_id?: string;
  created_at: string;
}

// ===== Hospital =====
export type HospitalStatus = "draft" | "submitted" | "under_review" | "approved" | "rejected" | "suspended";

export interface Hospital {
  id: string;
  name: string;
  address: string;
  city: string;
  state: string;
  phone: string;
  email: string;
  website?: string;
  status: HospitalStatus;
  departments: string[];
  specialties: string[];
  operating_hours?: string;
  tenant_id: string;
  created_at: string;
  updated_at: string;
}

// ===== Doctor =====
export type DoctorStatus = "invited" | "active" | "inactive" | "suspended";

export interface Doctor {
  id: string;
  name: string;
  email: string;
  photo_url?: string;
  specialty: string;
  department: string;
  qualifications: string[];
  experience_years: number;
  languages: string[];
  consultation_types: string[];
  consultation_duration: number; // minutes
  hospital_id: string;
  hospital_name?: string;
  status: DoctorStatus;
  created_at: string;
}

// ===== Patient =====
export interface Patient {
  id: string;
  name: string;
  email: string;
  phone: string;
  date_of_birth: string;
  preferred_communication: string;
  created_at: string;
}

// ===== Appointment =====
export type AppointmentStatus =
  | "requested"
  | "pending"
  | "confirmed"
  | "rescheduled"
  | "cancelled"
  | "completed"
  | "no_show"
  | "failed";

export interface Appointment {
  id: string;
  patient_id: string;
  patient_name: string;
  doctor_id: string;
  doctor_name: string;
  hospital_id: string;
  hospital_name: string;
  specialty: string;
  appointment_type: string;
  date: string;
  time: string;
  duration: number;
  status: AppointmentStatus;
  external_appointment_id?: string;
  ehr_sync_status?: string;
  questionnaire_status?: string;
  notes?: string;
  created_at: string;
}

// ===== Calendar & Availability =====
export interface TimeSlot {
  id: string;
  doctor_id: string;
  date: string;
  start_time: string;
  end_time: string;
  is_available: boolean;
  is_blocked: boolean;
  block_reason?: string;
  appointment_id?: string;
}

export interface WorkingHours {
  day_of_week: number; // 0=Sunday
  start_time: string;
  end_time: string;
  is_active: boolean;
}

// ===== Questionnaire =====
export type QuestionType = "yes_no" | "multiple_choice" | "single_choice" | "numeric" | "date" | "short_text" | "long_text";

export interface Question {
  id: string;
  text: string;
  type: QuestionType;
  options?: string[];
  required: boolean;
  order: number;
}

export interface Questionnaire {
  id: string;
  title: string;
  specialty: string;
  doctor_id: string;
  status: "draft" | "active" | "archived";
  questions: Question[];
  created_at: string;
}

export interface QuestionnaireResponse {
  id: string;
  questionnaire_id: string;
  appointment_id: string;
  patient_id: string;
  patient_name: string;
  responses: Record<string, string | number | boolean>;
  status: "pending" | "in_progress" | "completed";
  completed_at?: string;
}

// ===== Workflow =====
export type WorkflowStatus = "running" | "completed" | "failed" | "retrying" | "cancelled";

export interface Workflow {
  id: string;
  type: string;
  status: WorkflowStatus;
  trigger: string;
  related_id?: string;
  started_at: string;
  completed_at?: string;
  error?: string;
  retries: number;
}

// ===== AI Activity =====
export interface AIConversation {
  id: string;
  patient_id: string;
  patient_name: string;
  channel: "web_voice" | "phone";
  started_at: string;
  ended_at?: string;
  duration_seconds?: number;
  intents_detected: string[];
  capabilities_used: string[];
  outcome: string;
  escalated: boolean;
}

export interface CapabilityExecution {
  id: string;
  conversation_id: string;
  capability_name: string;
  input: Record<string, unknown>;
  output?: Record<string, unknown>;
  status: "success" | "failure" | "timeout";
  duration_ms: number;
  executed_at: string;
}

// ===== EHR Integration =====
export interface EHROperation {
  id: string;
  hospital_id: string;
  hospital_name: string;
  operation_type: string;
  connector: string;
  external_id?: string;
  status: "success" | "failure" | "pending" | "retrying" | "reconciliation_required";
  verification_status?: "verified" | "unverified" | "failed";
  duration_ms: number;
  error?: string;
  retries: number;
  created_at: string;
}

// ===== Audit =====
export interface AuditEvent {
  id: string;
  event_type: string;
  actor_id: string;
  actor_name: string;
  actor_role: UserRole;
  resource_type: string;
  resource_id: string;
  correlation_id?: string;
  details?: Record<string, unknown>;
  timestamp: string;
}

// ===== Notification =====
export interface Notification {
  id: string;
  user_id: string;
  type: string;
  title: string;
  message: string;
  read: boolean;
  created_at: string;
}

// ===== Analytics / KPIs =====
export interface PlatformKPIs {
  total_hospitals: number;
  active_hospitals: number;
  total_doctors: number;
  total_patients: number;
  appointments_today: number;
  ai_calls_today: number;
  booking_success_rate: number;
  questionnaire_completion_rate: number;
  human_escalation_rate: number;
  avg_ai_latency: number;
  ehr_integration_success_rate: number;
}

export interface HospitalKPIs {
  appointments_today: number;
  upcoming_appointments: number;
  active_doctors: number;
  available_slots: number;
  cancelled_appointments: number;
  rescheduled_appointments: number;
  ai_bookings: number;
  human_escalations: number;
  questionnaire_completion: number;
  workflow_failures: number;
  ehr_success_rate: number;
  ehr_failure_count: number;
}
