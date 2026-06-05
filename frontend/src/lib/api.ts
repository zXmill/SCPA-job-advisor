/**
 * SCPA API Client — connects frontend to the real API Gateway.
 *
 * The gateway (services/gateway/main.py) listens on port 8000 by
 * convention. Override at build time via NEXT_PUBLIC_API_URL — for
 * example, point at a staging gateway by setting that env var in
 * frontend/.env.local.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

function formatApiDetail(detail: unknown, fallback: string): string {
  if (typeof detail === 'string' && detail.trim()) return detail;

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (!item || typeof item !== 'object') return '';
        const record = item as Record<string, unknown>;
        const loc = Array.isArray(record.loc) ? record.loc.join('.') : '';
        const msg = typeof record.msg === 'string' ? record.msg : '';
        return [loc, msg].filter(Boolean).join(': ');
      })
      .filter(Boolean);
    if (messages.length > 0) return messages.join('; ');
  }

  if (detail && typeof detail === 'object') {
    const record = detail as Record<string, unknown>;
    const message = typeof record.message === 'string' ? record.message : '';
    const invalidSkill = typeof record.invalid_skill === 'string' ? record.invalid_skill : '';
    const suggestion = typeof record.suggestion === 'string' ? record.suggestion : '';

    if (message === 'Skill is not in the controlled taxonomy' && invalidSkill) {
      return suggestion
        ? `Skill "${invalidSkill}" belum ada di database skill. Pilih "${suggestion}" atau gunakan saran yang tersedia.`
        : `Skill "${invalidSkill}" belum ada di database skill. Pilih skill dari saran yang tersedia.`;
    }
    if (message) return message;
  }

  return fallback;
}

class ApiClient {
  private token: string | null = null;

  constructor() {
    if (typeof window !== 'undefined') {
      this.token = localStorage.getItem('scpa_token');
    }
  }

  setToken(token: string | null) {
    this.token = token;
    if (typeof window !== 'undefined') {
      if (token) localStorage.setItem('scpa_token', token);
      else localStorage.removeItem('scpa_token');
    }
  }

  getToken(): string | null {
    if (typeof window !== 'undefined' && !this.token) {
      this.token = localStorage.getItem('scpa_token');
    }
    return this.token;
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData;
    const headers: Record<string, string> = {
      ...(options.headers as Record<string, string> || {}),
    };
    if (!isFormData) headers['Content-Type'] = 'application/json';
    const tok = this.getToken();
    if (tok) headers['Authorization'] = `Bearer ${tok}`;

    let res: Response;
    try {
      res = await fetch(`${API_BASE}${path}`, { ...options, headers });
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        throw new ApiCancellationError();
      }
      // Network failure — gateway down, wrong port, DNS, CORS preflight, etc.
      // Surface a user-friendly Indonesian message instead of a generic
      // browser fetch error.
      throw new ApiError(
        0,
        `Tidak dapat terhubung ke server (${API_BASE}). Pastikan API gateway berjalan.`,
      );
    }
    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: '' }));
      // Prefer the gateway's own ``detail`` (e.g. "Email tidak ditemukan").
      // Fall back to a status-aware default so the user never sees the
      // raw "Not Found" / "Internal Server Error" string.
      const fallback =
        res.status === 404
          ? 'Endpoint tidak ditemukan di server.'
          : res.status >= 500
          ? 'Terjadi kesalahan di server. Coba lagi sesaat lagi.'
          : 'Permintaan gagal. Silakan coba lagi.';
      throw new ApiError(res.status, formatApiDetail(body.detail, fallback));
    }
    return res.json();
  }

  // ── Auth ──
  async login(email: string, password: string) {
    const data = await this.request<{ access_token: string; user: UserData }>('/api/auth/login', {
      method: 'POST', body: JSON.stringify({ email, password }),
    });
    this.setToken(data.access_token);
    return data;
  }

  async register(name: string, email: string, password: string) {
    const data = await this.request<{ access_token: string; user: UserData }>('/api/auth/register', {
      method: 'POST', body: JSON.stringify({ name, email, password }),
    });
    this.setToken(data.access_token);
    return data;
  }

  async getMe() {
    return this.request<UserData & { skills: SkillData[] }>('/api/auth/me');
  }

  logout() {
    this.setToken(null);
    if (typeof window !== 'undefined') localStorage.removeItem('scpa_user');
  }

  // ── Jobs ──
  async getJobs(filters?: {
    location?: string;
    experience?: string;
    page?: number;
    limit?: number;
  }, signal?: AbortSignal) {
    const params = new URLSearchParams();
    if (filters?.location) params.set('location', filters.location);
    if (filters?.experience) params.set('experience', filters.experience);
    if (filters?.page) params.set('page', String(filters.page));
    if (filters?.limit) params.set('limit', String(filters.limit));
    const qs = params.toString();
    return this.request<JobsPage>(`/api/jobs${qs ? `?${qs}` : ''}`, { signal });
  }

  async getJob(id: string) {
    return this.request<JobData>(`/api/jobs/${id}`);
  }

  async getJobSkillGap(id: string, signal?: AbortSignal) {
    return this.request<JobSkillGapResponse>(
      `/api/jobs/${encodeURIComponent(id)}/skill-gap`,
      { signal },
    );
  }

  async getSavedJobs(signal?: AbortSignal) {
    return this.request<SavedJobsResponse>('/api/jobs/saved', { signal });
  }

  async saveJob(id: string) {
    return this.request<JobActionResponse>(`/api/jobs/${encodeURIComponent(id)}/save`, {
      method: 'POST',
    });
  }

  async unsaveJob(id: string) {
    return this.request<JobActionResponse>(`/api/jobs/${encodeURIComponent(id)}/save`, {
      method: 'DELETE',
    });
  }

  async skipJob(id: string) {
    return this.request<JobActionResponse>(`/api/jobs/${encodeURIComponent(id)}/skip`, {
      method: 'POST',
    });
  }

  async getJobAlerts(signal?: AbortSignal) {
    return this.request<JobAlertsResponse>('/api/job-alerts', { signal });
  }

  async createJobAlert(data: JobAlertCreateInput) {
    return this.request<JobAlertData>('/api/job-alerts', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateJobAlert(id: number, data: JobAlertUpdateInput) {
    return this.request<JobAlertData>(`/api/job-alerts/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async disableJobAlert(id: number) {
    return this.request<{ status: string; alert_id: number }>(`/api/job-alerts/${id}`, {
      method: 'DELETE',
    });
  }

  // ── Recommendations (calls real ML Hybrid service) ──
  async getRecommendations(signal?: AbortSignal) {
    return this.request<RecommendationResponse>(
      '/api/recommendations',
      { method: 'POST', signal },
    );
  }

  async searchSkills(
    query: string,
    options: { limit?: number; exclude?: string[] } = {},
    signal?: AbortSignal,
  ) {
    const params = new URLSearchParams();
    params.set('q', query);
    if (options.limit) params.set('limit', String(options.limit));
    for (const skill of options.exclude || []) {
      if (skill.trim()) params.append('exclude', skill.trim());
    }
    return this.request<SkillSearchResponse>(`/api/skills/search?${params.toString()}`, { signal });
  }

  async trackRecommendationEvent(payload: {
    job_id: string;
    recommendation_id?: string;
    run_id?: string;
    served_slate_id?: string;
    event: 'impression' | 'view' | 'click' | 'source_click' | 'save' | 'apply' | 'skip' | 'dwell';
    rank: number;
    dwell_ms?: number;
    slate_job_ids?: string[];
  }) {
    return this.request<{ status: string }>('/api/recommendations/feedback', {
      method: 'POST',
      body: JSON.stringify({ dwell_ms: 0, slate_job_ids: [], ...payload }),
    });
  }

  // ── Applications ──
  async getApplications() {
    return this.request<{ applications: ApplicationData[] }>('/api/applications');
  }

  async submitApplications(jobIds: string[]) {
    return this.request<{ created: number; application_ids: string[] }>('/api/applications', {
      method: 'POST', body: JSON.stringify({ job_ids: jobIds }),
    });
  }

  // ── Profile ──
  async updateProfile(data: Partial<ProfileUpdate>) {
    return this.request<{ status: string }>('/api/profile', {
      method: 'PUT', body: JSON.stringify(data),
    });
  }

  async getProfileCompleteness(signal?: AbortSignal) {
    return this.request<ProfileCompletenessResponse>('/api/profile/completeness', { signal });
  }

  async uploadCv(file: File) {
    const form = new FormData();
    form.append('file', file);
    return this.request<CvUploadResponse>('/api/profile/cv', {
      method: 'POST',
      body: form,
    });
  }

  async getAdminModelHealth(signal?: AbortSignal) {
    return this.request<AdminModelHealthResponse>('/api/admin/model-health', { signal });
  }

  async saveOnboarding(step: number, data: Record<string, unknown>) {
    return this.request<{ status: string; step: number }>('/api/profile/onboarding', {
      method: 'PUT', body: JSON.stringify({ step, data }),
    });
  }
}

// ── Error class ──
export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

export class ApiCancellationError extends Error {
  constructor() {
    super('Permintaan dibatalkan.');
    this.name = 'ApiCancellationError';
  }
}

// ── Types ──
export interface UserData {
  id: string;
  name: string;
  email: string;
  role: string;
  program_studi: string | null;
  university: string | null;
  completion_percent: number;
  cv_uploaded_at?: string | null;
  skills?: SkillData[];
}

export interface SkillData {
  skill: string;
  category: string;
  proficiency_level: string;
}

export interface SkillSearchItem {
  id: string;
  name: string;
  category: string;
  aliases: string[];
  source?: string;
  confidence?: number;
}

export interface SkillSearchResponse {
  skills: SkillSearchItem[];
}

export interface ProfileCompletenessItem {
  id: string;
  label: string;
  completed: boolean;
}

export interface ProfileCompletenessResponse {
  percent: number;
  completed_item_ids: string[];
  missing_item_ids: string[];
  items: ProfileCompletenessItem[];
  skill_count: number;
  stored_percent: number;
  cv_uploaded_at?: string | null;
}

export interface CvUploadResponse {
  status: string;
  extracted_skills: string[];
  skills_added: number;
  skills_ignored: number;
  filename: string;
  stored_name: string;
  uploaded_at: string;
}

export interface AdminModelHealthStage {
  count?: number;
  last_ms?: number;
  p50_ms?: number;
  p95_ms?: number;
}

export interface AdminModelHealthService {
  status: string;
  url?: string | null;
  stage: AdminModelHealthStage;
}

export interface AdminModelHealthPipeline {
  status: string;
  mode?: string | null;
  p95_target_ms?: number | null;
}

export interface AdminModelHealthTelemetry {
  window_size?: number;
  p95_target_ms?: number;
  stages: Record<string, AdminModelHealthStage>;
}

export interface AdminModelHealthContinualTraining {
  enabled?: boolean;
  interval_seconds?: number;
  cycles?: number;
  last_error?: string | null;
  scrape_target?: number;
  candidate_pool_limit?: number;
}

export interface AdminModelHealthResponse {
  status: string;
  pipeline: AdminModelHealthPipeline;
  models: Record<string, AdminModelHealthService>;
  telemetry: AdminModelHealthTelemetry;
  continual_training: AdminModelHealthContinualTraining;
}

export interface JobData {
  id: string;
  title: string;
  company: string;
  company_logo?: string | null;
  location: string | null;
  type: string | null;
  min_salary: number | null;
  max_salary: number | null;
  salary_currency?: string;
  salary_text?: string | null;
  employment_mode?: string | null;
  description: string | null;
  raw_description_html?: string | null;
  description_text?: string | null;
  description_sections?: Record<string, string>;
  responsibilities?: string[];
  requirements?: string[];
  nice_to_have?: string[];
  benefits?: string[];
  seniority_level?: string | null;
  employment_type?: string | null;
  job_function?: string | null;
  industry?: string | null;
  education_level?: string | null;
  years_experience_min?: number | null;
  years_experience_max?: number | null;
  required_skill_names?: string[];
  preferred_skill_names?: string[];
  extracted_skill_names?: string[];
  required_skills?: string[];
  preferred_skills?: string[];
  extracted_skills?: string[];
  experience_level: string | null;
  posted_at: string | null;
  source: string | null;
  source_url?: string | null;
  skills?: string[];
  is_active?: boolean;
}

export interface JobsPage {
  jobs: JobData[];
  total: number;
  page: number;
  limit: number;
  total_pages: number;
}

export interface SavedJobsResponse {
  jobs: JobData[];
  total: number;
}

export interface JobActionResponse {
  status: string;
  job_id: string;
}

export interface JobSkillGapExplanation {
  matched_count: number;
  missing_count: number;
  required_count: number;
  summary: string;
}

export interface JobSkillGapResponse {
  job_id: string;
  job_title: string | null;
  company: string | null;
  required_skills: string[];
  preferred_skills?: string[];
  extracted_skills?: string[];
  matched_skills: string[];
  missing_skills: string[];
  skill_match_percent: number;
  explanation: JobSkillGapExplanation;
}

export interface JobAlertCriteria {
  query: string | null;
  location: string | null;
  min_match_percent: number;
}

export interface JobAlertData {
  id: number;
  name: string;
  query: string | null;
  location: string | null;
  min_match_percent: number;
  frequency: 'daily' | 'weekly';
  active: boolean;
  criteria: JobAlertCriteria;
  created_at?: string;
  updated_at?: string;
}

export interface JobAlertsResponse {
  alerts: JobAlertData[];
  total: number;
}

export interface JobAlertCreateInput {
  name: string;
  query?: string | null;
  location?: string | null;
  min_match_percent?: number;
  frequency?: 'daily' | 'weekly';
}

export interface JobAlertUpdateInput {
  name?: string | null;
  query?: string | null;
  location?: string | null;
  min_match_percent?: number;
  frequency?: 'daily' | 'weekly';
  active?: boolean;
}

export interface RecommendationData {
  job: JobData;
  hybrid_score: number;
  sbert_score: number;
  ncf_score: number;
  dqn_score?: number;
  weights?: { sbert?: number; ncf?: number; dqn?: number };
  segment?: string | null;
  strategy?: string | null;
  recommendation_id?: string;
  run_id?: string;
  match_percent: number;
  explanation?: string;
  explanation_provenance?: {
    semantic_match?: number;
    behavior_match?: number;
    session_rerank_signal?: number;
    skill_gap?: string[];
  };
  reason_filter_scores?: Record<string, number>;
  reason_filter_labels?: Record<string, string>;
}

export interface RecommendationResponse {
  recommendations: RecommendationData[];
  fairness_tpr_gap: number;
  recommendation_id?: string;
  run_id?: string;
  degraded?: boolean;
  source_status?: string;
}

export interface ApplicationData {
  id: string;
  status: string;
  applied_at: string | null;
  job_title: string;
  company: string;
  location: string | null;
}

export interface ProfileUpdate {
  name?: string;
  program_studi?: string;
  university?: string;
  skills?: string[];
  interests?: string[];
}

// Singleton instance
export const api = new ApiClient();
