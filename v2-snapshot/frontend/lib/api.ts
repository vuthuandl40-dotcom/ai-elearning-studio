import type { AnalysisRun, BackgroundJob, PlanningRun, SourceFile, AnalyticsSummary, Assignment, AttemptDetail, AuthUser, Classroom, ClassroomAnalyticsSummary, ClassroomAssignmentAnalytics, ClassroomLearnerAnalytics, ClassroomMember, CopilotAction, CopilotProposal, ExportFormat, ExportRun, LearnerAnswerResult, LearnerAssignmentStatus, LearnerAttempt, LearnerFinishResult, LearnerLesson, LearnerSummary, LmsCatalog, LmsProfile, LrsConnection, LrsDelivery, MediaAsset, ObjectiveAnalytics, Organization, OrganizationMember, Project, Section, Slide, SlideBlueprint, SourceChunk, TokenResponse, UserRole, VisualCatalog } from "./types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export class ApiError extends Error {
  status: number;
  detail?: unknown;
  constructor(message: string, status: number, detail?: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

export function getAccessToken(): string | null {
  // Step 12: browser auth uses HttpOnly cookies. Bearer tokens remain available
  // in API responses for non-browser clients, but are never persisted here.
  return null;
}
export function setSession(_token: string | null, user?: AuthUser | null) {
  if (typeof window === "undefined") return;
  if (user) window.sessionStorage.setItem("ai-elearning-user", JSON.stringify(user));
  else {
    window.sessionStorage.removeItem("ai-elearning-user");
    if (!_token) fetch(`${API_URL}/auth/logout`, { method: "POST", credentials: "include", keepalive: true }).catch(() => undefined);
  }
}
export function getStoredUser(): AuthUser | null {
  if (typeof window === "undefined") return null;
  try { const raw=window.sessionStorage.getItem("ai-elearning-user"); return raw ? JSON.parse(raw) as AuthUser : null; } catch { return null; }
}

async function refreshBrowserSession(): Promise<boolean> {
  const res = await fetch(`${API_URL}/auth/refresh`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
  });
  if (!res.ok) return false;
  try {
    const data = await res.json() as TokenResponse;
    setSession(null, data.user);
  } catch { /* cookie renewal is sufficient */ }
  return true;
}

async function request<T>(path: string, init?: RequestInit, retried = false): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });
  const noAutoRefresh = ["/auth/login", "/auth/register", "/auth/refresh", "/auth/request-password-reset", "/auth/reset-password", "/auth/verify-email"];
  if (res.status === 401 && !retried && !noAutoRefresh.some(p => path.startsWith(p))) {
    if (await refreshBrowserSession()) return request<T>(path, init, true);
  }
  if (!res.ok) {
    const raw = await res.text();
    let detail: unknown = raw;
    if (raw) { try { detail = JSON.parse(raw) as unknown; } catch { /* keep raw text */ } }
    const message = typeof detail === "object" && detail && "detail" in detail ? String((detail as { detail: unknown }).detail) : (typeof detail === "string" && detail ? detail : `API error ${res.status}`);
    throw new ApiError(message, res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

async function uploadRequest<T>(path: string, form: FormData, retried = false): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { method: "POST", body: form, credentials: "include", cache: "no-store" });
  if (res.status === 401 && !retried && await refreshBrowserSession()) return uploadRequest<T>(path, form, true);
  if (!res.ok) {
    const raw = await res.text();
    let detail: unknown = raw;
    if (raw) { try { detail = JSON.parse(raw) as unknown; } catch { /* keep raw text */ } }
    const message = typeof detail === "object" && detail && "detail" in detail ? String((detail as { detail: unknown }).detail) : (typeof detail === "string" && detail ? detail : `API error ${res.status}`);
    throw new ApiError(message, res.status, detail);
  }
  return res.json() as Promise<T>;
}

async function waitForJob(jobId: string, onProgress?: (job: BackgroundJob) => void): Promise<BackgroundJob> {
  const deadline = Date.now() + 20 * 60 * 1000;
  while (Date.now() < deadline) {
    const job = await request<BackgroundJob>(`/jobs/${jobId}`);
    onProgress?.(job);
    if (job.status === "completed") return job;
    if (job.status === "failed" || job.status === "cancelled") throw new ApiError(job.error_message || `Job ${job.status}`, 409, job);
    await new Promise((resolve) => setTimeout(resolve, 1500));
  }
  throw new ApiError("Tác vụ vượt quá thời gian chờ trên trình duyệt. Có thể kiểm tra lại trạng thái sau.", 408);
}

export const api = {
  url: API_URL,
  createProject: (value: { title: string; subject?: string; grade?: string; education_level?: string; book_series?: string; duration_minutes?: number; lesson_periods?: number; organization_id?: string | null; visual_style?: string; narration_style?: string; interaction_level?: "low"|"medium"|"high"; source_policy?: "strict"|"source_plus_verified"|"open"; extra_instructions?: string }) => request<Project>("/projects", { method: "POST", body: JSON.stringify(value) }),
  uploadSourceFile: (projectId: string, file: File) => { const form = new FormData(); form.append("file", file); return uploadRequest<SourceFile>(`/projects/${projectId}/files`, form); },
  createJob: (projectId: string, kind: BackgroundJob["kind"], payload: Record<string, unknown> = {}) => request<BackgroundJob>(`/projects/${projectId}/jobs`, { method: "POST", body: JSON.stringify({ kind, payload, max_attempts: 3 }) }),
  getJob: (jobId: string) => request<BackgroundJob>(`/jobs/${jobId}`),
  waitForJob,
  latestAnalysis: (projectId: string) => request<AnalysisRun>(`/projects/${projectId}/analysis/latest`),
  latestPlan: (projectId: string) => request<PlanningRun>(`/projects/${projectId}/plan/latest`),
  listObjectives: (projectId: string) => request<Array<{ id: string; objective_order: number; objective_text: string; is_teacher_approved: boolean }>>(`/projects/${projectId}/objectives`),
  updateObjective: (objectiveId: string, value: { objective_text: string; is_teacher_approved?: boolean }) => request<{ id: string; objective_order: number; objective_text: string; is_teacher_approved: boolean }>(`/objectives/${objectiveId}`, { method: "PATCH", body: JSON.stringify(value) }),
  approvePlan: (projectId: string, runId: string) => request<PlanningRun>(`/projects/${projectId}/plan/${runId}/approve`, { method: "POST" }),
  login: (email: string, password: string) => request<TokenResponse>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  register: (email: string, password: string, display_name: string, role: "teacher" | "student") => request<TokenResponse>("/auth/register", { method: "POST", body: JSON.stringify({ email, password, display_name, role }) }),
  me: () => request<AuthUser>("/auth/me"),
  logout: () => request<{message:string}>("/auth/logout", { method: "POST" }),
  requestPasswordReset: (email: string) => request<{message:string;debug_token?:string|null}>("/auth/request-password-reset", { method: "POST", body: JSON.stringify({ email }) }),
  resetPassword: (token: string, new_password: string) => request<{message:string}>("/auth/reset-password", { method: "POST", body: JSON.stringify({ token, new_password }) }),
  verifyEmail: (token: string) => request<{message:string}>("/auth/verify-email", { method: "POST", body: JSON.stringify({ token }) }),
  requestEmailVerification: () => request<{message:string;debug_token?:string|null}>("/auth/request-email-verification", { method: "POST" }),
  listOrganizations: () => request<Organization[]>("/organizations"),
  createOrganization: (name: string, slug?: string) => request<Organization>("/organizations", { method: "POST", body: JSON.stringify({ name, slug }) }),
  organizationMembers: (id: string) => request<OrganizationMember[]>(`/organizations/${id}/members`),
  addOrganizationMember: (id: string, email: string, role: "admin"|"teacher"|"student") => request<OrganizationMember>(`/organizations/${id}/members`, { method: "POST", body: JSON.stringify({ email, role }) }),
  listClassrooms: () => request<Classroom[]>("/classrooms"),
  createClassroom: (value: Partial<Classroom> & { name: string }) => request<Classroom>("/classrooms", { method: "POST", body: JSON.stringify(value) }),
  joinClassroom: (join_code: string) => request<Classroom>("/classroom-join", { method: "POST", body: JSON.stringify({ join_code }) }),
  getClassroom: (id: string) => request<Classroom>(`/classrooms/${id}`),
  updateClassroom: (id: string, patch: Partial<Classroom> & { regenerate_join_code?: boolean }) => request<Classroom>(`/classrooms/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  classroomMembers: (id: string) => request<ClassroomMember[]>(`/classrooms/${id}/members`),
  addClassroomMember: (id: string, email: string, member_role: "teacher" | "student" = "student") => request<ClassroomMember>(`/classrooms/${id}/members`, { method: "POST", body: JSON.stringify({ email, member_role }) }),
  classroomAssignments: (id: string) => request<Assignment[]>(`/classrooms/${id}/assignments`),
  createAssignment: (id: string, value: { project_id: string; title?: string; instructions?: string; status?: string; due_at?: string | null; max_attempts?: number | null; passing_score?: number | null }) => request<Assignment>(`/classrooms/${id}/assignments`, { method: "POST", body: JSON.stringify(value) }),
  updateAssignment: (id: string, patch: Partial<Assignment>) => request<Assignment>(`/assignments/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  classroomAnalyticsSummary: (id: string) => request<ClassroomAnalyticsSummary>(`/classrooms/${id}/analytics/summary`),
  classroomAnalyticsLearners: (id: string) => request<ClassroomLearnerAnalytics[]>(`/classrooms/${id}/analytics/learners`),
  classroomAnalyticsAssignments: (id: string) => request<ClassroomAssignmentAnalytics[]>(`/classrooms/${id}/analytics/assignments`),
  myAssignments: () => request<LearnerAssignmentStatus[]>("/me/assignments"),
  startAssignmentAttempt: (id: string) => request<LearnerAttempt>(`/assignments/${id}/attempts`, { method: "POST" }),
  learnerLesson: (id: string) => request<LearnerLesson>(`/assignments/${id}/lesson`),
  answerAssignment: (id: string, attempt_id: string, interaction_id: string, response: unknown, duration_seconds?: number) => request<LearnerAnswerResult>(`/assignments/${id}/answer`, { method: "POST", body: JSON.stringify({ attempt_id, interaction_id, response, duration_seconds }) }),
  progressAssignment: (id: string, attempt_id: string, progress: number, slide_id?: string) => request<void>(`/assignments/${id}/progress`, { method: "POST", body: JSON.stringify({ attempt_id, progress, slide_id }) }),
  finishAssignment: (id: string, attempt_id: string) => request<LearnerFinishResult>(`/assignments/${id}/finish`, { method: "POST", body: JSON.stringify({ attempt_id }) }),
  adminUsers: () => request<Array<{id:string;email?:string|null;display_name?:string|null;role:UserRole;is_active:boolean}>>("/admin/users"),
  adminUpdateUser: (id: string, patch: { role?: UserRole; is_active?: boolean }) => request(`/admin/users/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  listProjects: (userId?: string) => request<Project[]>(`/projects${userId ? `?user_id=${userId}` : ""}`),
  getProject: (id: string) => request<Project>(`/projects/${id}`),
  updateProject: (id: string, patch: Partial<Project>) => request<Project>(`/projects/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  getSections: (id: string) => request<Section[]>(`/projects/${id}/sections`),
  getSlides: (id: string) => request<Slide[]>(`/projects/${id}/slides`),
  getBlueprint: (slideId: string) => request<SlideBlueprint>(`/slides/${slideId}/blueprint`),
  updateSlide: (slideId: string, patch: Partial<Slide>) => request<Slide>(`/slides/${slideId}`, { method: "PATCH", body: JSON.stringify(patch) }),
  updateSection: (sectionId: string, patch: Partial<Section>) => request<Section>(`/sections/${sectionId}`, { method: "PATCH", body: JSON.stringify(patch) }),
  generateLesson: (projectId: string) => request(`/projects/${projectId}/generate`, { method: "POST", body: JSON.stringify({ use_ai: true, preserve_teacher_edits: true, fallback_to_local: true }) }),
  regenerateSection: (projectId: string, sectionKey: string, force = true, instruction?: string) => request(`/projects/${projectId}/sections/${sectionKey}/regenerate`, { method: "POST", body: JSON.stringify({ use_ai: true, force, fallback_to_local: true, instruction: instruction || null }) }),
  latestGeneration: (projectId: string) => request<{ id: string; teacher_approved: boolean }>(`/projects/${projectId}/generation/latest`),
  approveGeneration: (projectId: string, runId: string) => request(`/projects/${projectId}/generation/${runId}/approve`, { method: "POST" }),
  getChunk: (chunkId: string) => request<SourceChunk>(`/chunks/${chunkId}`),
  copilot: (slideId: string, action: CopilotAction, instruction?: string) => request<CopilotProposal>(`/slides/${slideId}/copilot`, { method: "POST", body: JSON.stringify({ action, instruction, use_ai: true }) }),
  visualCatalog: () => request<VisualCatalog>("/visual/catalog"),
  listMedia: (projectId: string) => request<MediaAsset[]>(`/projects/${projectId}/media`),
  attachMedia: (slideId: string, assetId: string, role = "visual") => request<Slide>(`/slides/${slideId}/media/attach`, { method: "POST", body: JSON.stringify({ media_asset_id: assetId, role }) }),
  promptMedia: (slideId: string, assetType: "image" | "video", prompt: string) => request<MediaAsset>(`/slides/${slideId}/media/from-prompt`, { method: "POST", body: JSON.stringify({ asset_type: assetType, prompt, use_ai: true, attach_to_slide: true }) }),
  deleteMedia: (assetId: string) => fetch(`${API_URL}/media-assets/${assetId}`, { method: "DELETE", credentials: "include" }),
  mediaUrl: (assetId: string) => `${API_URL}/media-assets/${assetId}/content`,
  createExport: (projectId: string, format: ExportFormat, options: Record<string, unknown> = {}) => request<ExportRun>(`/projects/${projectId}/exports`, { method: "POST", body: JSON.stringify({ format, include_notes: true, include_sources: true, include_quiz: true, only_approved: false, ...options }) }),
  listExports: (projectId: string) => request<ExportRun[]>(`/projects/${projectId}/exports`),
  lmsCatalog: () => request<LmsCatalog>("/lms/catalog"),
  getLmsProfile: (projectId: string) => request<LmsProfile>(`/projects/${projectId}/lms/profile`),
  saveLmsProfile: (projectId: string, profile: Omit<LmsProfile, "id" | "project_id" | "created_at" | "updated_at">) => request<LmsProfile>(`/projects/${projectId}/lms/profile`, { method: "PUT", body: JSON.stringify(profile) }),
  xapiTemplate: (projectId: string) => request(`/projects/${projectId}/xapi/template`),
  analyticsSummary: (projectId: string) => request<AnalyticsSummary>(`/projects/${projectId}/analytics/summary`),
  analyticsLearners: (projectId: string) => request<LearnerSummary[]>(`/projects/${projectId}/analytics/learners`),
  analyticsObjectives: (projectId: string) => request<ObjectiveAnalytics[]>(`/projects/${projectId}/analytics/objectives`),
  analyticsAttempts: (projectId: string) => request<LearnerAttempt[]>(`/projects/${projectId}/analytics/attempts`),
  analyticsAttempt: (attemptId: string) => request<AttemptDetail>(`/analytics/attempts/${attemptId}`),
  getLrsConnection: (projectId: string) => request<LrsConnection>(`/projects/${projectId}/lrs/connection`),
  saveLrsConnection: (projectId: string, value: Omit<LrsConnection, "id" | "project_id" | "created_at" | "updated_at">) => request<LrsConnection>(`/projects/${projectId}/lrs/connection`, { method: "PUT", body: JSON.stringify(value) }),
  testLrsConnection: (projectId: string) => request<{ ok: boolean; http_status?: number | null; message: string; version_header?: string | null }>(`/projects/${projectId}/lrs/test`, { method: "POST" }),
  syncFromLrs: (projectId: string, maxPages = 5) => request<{ statements_received: number; events_created: number; attempts_touched: number; pages: number; warnings: string[] }>(`/projects/${projectId}/lrs/sync?max_pages=${maxPages}`, { method: "POST" }),
  pushAttemptToLrs: (attemptId: string) => request<LrsDelivery>(`/analytics/attempts/${attemptId}/lrs/push`, { method: "POST" }),
  listLrsDeliveries: (projectId: string) => request<LrsDelivery[]>(`/projects/${projectId}/lrs/deliveries`),
  exportDownloadUrl: (run: ExportRun) => run.download_url ? `${API_URL.replace(/\/api\/v1\/?$/, "")}${run.download_url}` : "",
  uploadMedia: async (projectId: string, file: File, slideId?: string) => {
    const form = new FormData(); form.append("file", file); if (slideId) form.append("slide_id", slideId);
    const res = await fetch(`${API_URL}/projects/${projectId}/media`, { method: "POST", body: form, credentials: "include" });
    if (!res.ok) { let detail: unknown; try { detail = await res.json(); } catch { detail = await res.text(); } throw new ApiError(typeof detail === "object" && detail && "detail" in detail ? String((detail as { detail: unknown }).detail) : `API error ${res.status}`, res.status, detail); }
    return res.json() as Promise<MediaAsset>;
  },
};
