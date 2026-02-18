export interface User {
  user_id: number;
  username: string;
  email: string;
  role: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
  password_confirm: string;
}

export interface AuthResponse {
  access_token: string;
  user: User;
}

export interface Campaign {
  campaign_id: number;
  campaign_name: string;
  user_id: number;
  is_active: boolean;
  total_jobs?: number;
  [key: string]: unknown;
}

export interface Job {
  jsearch_job_id: string;
  job_title: string;
  company_name: string;
  job_status: string;
  campaign_id?: number;
  job_publisher?: string | null;
  [key: string]: unknown;
}

export interface DashboardStats {
  active_campaigns_count: number;
  total_campaigns_count: number;
  jobs_processed_count: number;
  success_rate: number;
  recent_jobs: Job[];
  activity_data: Array<{ date: string; found: number; applied: number }>;
  /** Public URL to Airflow UI (staging/production only). */
  airflow_ui_url?: string | null;
}

export interface Resume {
  resume_id: number;
  resume_name: string;
  file_type: string;
  file_size?: number;
  created_at: string;
}

export interface CoverLetter {
  cover_letter_id: number;
  cover_letter_name: string;
  file_path?: string;
  created_at: string;
}

export interface StagingSlot {
  slot_id: number;
  slot_name: string;
  status: string;
  health_status: string;
  owner: string | null;
  branch: string | null;
  issue_id: string | null;
  deployed_at: string | null;
  purpose: string | null;
  campaign_ui_url: string | null;
  airflow_url: string | null;
  api_url: string | null;
  last_health_check_at: string | null;
  metadata: any;
}
