import axios, { type AxiosInstance, type InternalAxiosRequestConfig } from 'axios';
import type { AuthResponse, LoginRequest, RegisterRequest } from '../types';

// In development, use localhost:5000. In production/staging, use relative URL (nginx proxies to backend)
const API_BASE_URL = import.meta.env.VITE_API_URL || (import.meta.env.DEV ? 'http://localhost:5000' : '');

/** In-memory token so the first request after login has the token before localStorage is committed (e.g. on some mobile browsers). */
let memoryToken: string | null = null;

export function setAccessToken(token: string | null): void {
  memoryToken = token;
}

class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.setupInterceptors();
  }

  private setupInterceptors(): void {
    this.client.interceptors.request.use(
      (config: InternalAxiosRequestConfig) => {
        const token = memoryToken ?? localStorage.getItem('access_token');
        if (token && config.headers) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        if (config.data instanceof FormData && config.headers) {
          if (typeof config.headers.delete === 'function') {
            config.headers.delete('Content-Type');
          } else {
            delete (config.headers as Record<string, string>)['Content-Type'];
          }
        }
        return config;
      },
      (error) => {
        return Promise.reject(error);
      }
    );

    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        // Handle 401 (unauthorized). Don't redirect for failed login — let the Login page show the error.
        // For other requests (e.g. expired token), redirect to login.
        if (error.response?.status === 401) {
          const isLoginRequest = error.config?.url?.includes('/api/auth/login');
          if (!isLoginRequest) {
            memoryToken = null;
            localStorage.removeItem('access_token');
            localStorage.removeItem('user');
            window.location.href = '/login';
          }
        }
        // Handle 422 (unprocessable entity) - often means old token format
        if (error.response?.status === 422) {
          const errorMessage = error.response?.data?.msg || error.response?.data?.error || '';
          if (errorMessage.includes('Subject must be a string') || errorMessage.includes('Invalid token')) {
            console.warn('Detected old token format, clearing and redirecting to login');
            memoryToken = null;
            localStorage.removeItem('access_token');
            localStorage.removeItem('user');
            window.location.href = '/login';
          }
        }
        return Promise.reject(error);
      }
    );
  }

  async login(credentials: LoginRequest): Promise<AuthResponse> {
    const response = await this.client.post<AuthResponse>('/api/auth/login', credentials);
    return response.data;
  }

  async register(data: RegisterRequest): Promise<AuthResponse> {
    const response = await this.client.post<AuthResponse>('/api/auth/register', data);
    return response.data;
  }

  async getDashboard(): Promise<unknown> {
    try {
      const response = await this.client.get('/api/dashboard');
      return response.data;
    } catch (error) {
      // Log error for debugging
      console.error('Dashboard API error:', error);
      throw error;
    }
  }

  async getCampaigns(): Promise<{ campaigns: unknown[] }> {
    const response = await this.client.get('/api/campaigns');
    return response.data;
  }

  async getCampaign(id: number): Promise<{ campaign: unknown }> {
    const response = await this.client.get(`/api/campaigns/${id}`);
    return response.data;
  }

  async createCampaign(data: unknown): Promise<{ campaign_id: number }> {
    const response = await this.client.post('/api/campaigns', data);
    return response.data;
  }

  async updateCampaign(id: number, data: unknown): Promise<void> {
    await this.client.put(`/api/campaigns/${id}`, data);
  }

  async deleteCampaign(id: number): Promise<void> {
    await this.client.delete(`/api/campaigns/${id}`);
  }

  async getJobs(campaignId?: number): Promise<{ jobs: unknown[] }> {
    const params = campaignId ? { campaign_id: campaignId } : {};
    const response = await this.client.get('/api/jobs', { params });
    return response.data;
  }

  async getJob(jobId: string): Promise<{ job: unknown; same_company_jobs?: unknown[] }> {
    const response = await this.client.get(`/api/jobs/${jobId}`);
    return response.data;
  }

  async updateJobStatus(jobId: string, status: string): Promise<void> {
    await this.client.post(`/api/jobs/${jobId}/status`, { status });
  }

  async triggerCampaignDag(
    campaignId: number,
    force = false
  ): Promise<{ success?: boolean; message?: string; error?: string; dag_run_id?: string | null; forced?: boolean }> {
    const response = await this.client.post(`/api/campaigns/${campaignId}/trigger-dag`, { force });
    return response.data;
  }

  async getCampaignStatus(
    campaignId: number,
    dagRunId?: string | null
  ): Promise<{
    status: string;
    message?: string;
    completed_tasks?: string[];
    failed_tasks?: string[];
    is_complete?: boolean;
    jobs_available?: boolean;
    dag_run_id?: string | null;
  }> {
    const params = dagRunId ? { dag_run_id: dagRunId } : {};
    const response = await this.client.get(`/api/campaigns/${campaignId}/status`, { params });
    return response.data;
  }

  async getJobApplicationDocuments(jobId: string): Promise<{
    application_doc: unknown;
    user_resumes: unknown[];
    user_cover_letters: unknown[];
  }> {
    const response = await this.client.get(`/api/jobs/${jobId}/application-documents`);
    return response.data;
  }

  async updateJobApplicationDocuments(jobId: string, data: {
    resume_id?: number | null;
    cover_letter_id?: number | null;
    cover_letter_text?: string | null;
    user_notes?: string | null;
  }): Promise<{ message: string }> {
    const response = await this.client.put(`/api/jobs/${jobId}/application-documents`, data);
    return response.data;
  }

  async uploadJobResume(jobId: string, formData: FormData): Promise<{ resume_id: number }> {
    const response = await this.client.post(`/api/jobs/${jobId}/resume/upload`, formData);
    return response.data;
  }

  async createJobCoverLetter(jobId: string, formData: FormData): Promise<{
    cover_letter_id: number;
    cover_letter_text?: string;
    cover_letter_name?: string;
  }> {
    const response = await this.client.post(`/api/jobs/${jobId}/cover-letter/create`, formData);
    return response.data;
  }

  async getJobNotes(jobId: string): Promise<{ notes: unknown[] }> {
    const response = await this.client.get(`/api/jobs/${jobId}/notes`);
    return response.data;
  }

  async addJobNote(jobId: string, noteText: string): Promise<{ note: unknown }> {
    const response = await this.client.post(`/api/jobs/${jobId}/notes`, { note_text: noteText });
    return response.data;
  }

  async updateJobNote(jobId: string, noteId: number, noteText: string): Promise<{ note: unknown }> {
    const response = await this.client.put(`/api/jobs/${jobId}/notes/${noteId}`, {
      note_text: noteText,
    });
    return response.data;
  }

  async deleteJobNote(jobId: string, noteId: number): Promise<void> {
    await this.client.delete(`/api/jobs/${jobId}/notes/${noteId}`);
  }

  async getJobStatusHistory(jobId: string): Promise<{ history: unknown[] }> {
    const response = await this.client.get(`/api/jobs/${jobId}/status/history`);
    return response.data;
  }

  async generateCoverLetter(jobId: string, data: {
    resume_id: number;
    user_comments?: string;
  }): Promise<{ cover_letter_id: number; cover_letter_text: string; cover_letter_name: string }> {
    const response = await this.client.post(`/api/jobs/${jobId}/cover-letter/generate`, data);
    return response.data;
  }

  async getCoverLetterGenerationHistory(jobId: string): Promise<{ history: unknown[] }> {
    const response = await this.client.get(`/api/jobs/${jobId}/cover-letter/generation-history`);
    return response.data;
  }

  async getDocuments(): Promise<{ resumes: unknown[]; cover_letters: unknown[] }> {
    const response = await this.client.get('/api/documents');
    return response.data;
  }

  async uploadResume(formData: FormData): Promise<{ message: string }> {
    const response = await this.client.post('/api/documents/resume/upload', formData);
    return response.data;
  }

  async createCoverLetter(formData: FormData): Promise<{ message: string }> {
    const response = await this.client.post('/api/documents/cover-letter/create', formData);
    return response.data;
  }

  async getCoverLetter(coverLetterId: number): Promise<{ cover_letter_text?: string; file_path?: string }> {
    const response = await this.client.get(`/api/documents/cover-letter/${coverLetterId}`);
    return response.data;
  }

  async downloadResume(resumeId: number): Promise<Blob> {
    const response = await this.client.get(`/api/documents/resume/${resumeId}/download`, {
      responseType: 'blob',
    });
    return response.data as Blob;
  }

  async downloadCoverLetter(coverLetterId: number): Promise<Blob> {
    const response = await this.client.get(`/api/documents/cover-letter/${coverLetterId}/download`, {
      responseType: 'blob',
    });
    return response.data as Blob;
  }

  async getAccount(): Promise<{ user: unknown }> {
    const response = await this.client.get('/api/account');
    return response.data;
  }

  async changePassword(data: {
    current_password: string;
    new_password: string;
    confirm_password: string;
  }): Promise<void> {
    const response = await this.client.post('/api/account/change-password', data);
    return response.data;
  }

  async getUserResumes(): Promise<{ resumes: unknown[] }> {
    const response = await this.client.get('/api/user/resumes');
    return response.data;
  }

  async getUserCoverLetters(jobId?: string): Promise<{ cover_letters: unknown[] }> {
    const params = jobId ? { job_id: jobId } : {};
    const response = await this.client.get('/api/user/cover-letters', { params });
    return response.data;
  }

  async deleteResume(resumeId: number): Promise<void> {
    await this.client.delete(`/api/documents/resume/${resumeId}`);
  }

  async deleteCoverLetter(coverLetterId: number): Promise<void> {
    await this.client.delete(`/api/documents/cover-letter/${coverLetterId}`);
  }

  async toggleCampaignActive(id: number): Promise<{ success: boolean; is_active: boolean; message: string }> {
    const response = await this.client.post(`/api/campaigns/${id}/toggle-active`);
    return response.data;
  }

  // --- Staging Management ---

  async getStagingSlots(): Promise<unknown[]> {
    const response = await this.client.get('/api/staging/slots');
    return response.data;
  }

  async getStagingSlot(id: number): Promise<unknown> {
    const response = await this.client.get(`/api/staging/slots/${id}`);
    return response.data;
  }

  async updateStagingSlot(id: number, data: unknown): Promise<void> {
    await this.client.put(`/api/staging/slots/${id}`, data);
  }

  async releaseStagingSlot(id: number): Promise<void> {
    await this.client.post(`/api/staging/slots/${id}/release`);
  }

  async checkStagingSlotHealth(id: number): Promise<unknown> {
    const response = await this.client.post(`/api/staging/slots/${id}/check-health`);
    return response.data;
  }

  async checkAllStagingSlotsHealth(): Promise<Record<number, unknown>> {
    const response = await this.client.post('/api/staging/slots/check-health');
    return response.data;
  }
}

export const apiClient = new ApiClient();
