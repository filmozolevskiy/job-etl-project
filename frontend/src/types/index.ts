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
  [key: string]: unknown;
}

export interface DashboardStats {
  active_campaigns_count: number;
  total_campaigns_count: number;
  jobs_processed_count: number;
  success_rate: number;
  recent_jobs: Job[];
  activity_data: Array<{ date: string; found: number; applied: number }>;
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
