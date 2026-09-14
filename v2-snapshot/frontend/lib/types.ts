export type Project = {
  id: string;
  user_id: string;
  organization_id?: string | null;
  title: string;
  subject?: string | null;
  grade?: string | null;
  education_level?: string | null;
  book_series?: string | null;
  duration_minutes?: number | null;
  lesson_periods: number;
  language: string;
  visual_style?: string | null;
  narration_style?: string | null;
  interaction_level?: "low" | "medium" | "high" | null;
  source_policy: "strict" | "source_plus_verified" | "open";
  extra_instructions?: string | null;
  settings: Record<string, unknown>;
  status: string;
  created_at: string;
  updated_at: string;
};

export type Section = {
  id: string;
  project_id: string;
  section_key: string;
  section_order: number;
  title: string;
  purpose?: string | null;
  is_required: boolean;
  is_enabled: boolean;
  teacher_approved: boolean;
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type Slide = {
  id: string;
  project_id: string;
  section_id: string;
  generation_run_id?: string | null;
  slide_order: number;
  title?: string | null;
  slide_type: string;
  onscreen_text: unknown[];
  teacher_script?: string | null;
  student_instruction?: string | null;
  visual_type?: string | null;
  visual_description?: string | null;
  image_prompt?: string | null;
  video_prompt?: string | null;
  duration_seconds?: number | null;
  layout_hint?: string | null;
  media: Array<{ asset_id?: string; role?: string; asset_type?: string } | unknown>;
  design_json: DesignState;
  ai_metadata: Record<string, unknown>;
  teacher_approved: boolean;
  version: number;
  created_at: string;
  updated_at: string;
};

export type SlideSourceRef = {
  id: string;
  slide_id: string;
  source_chunk_id: string;
  claim_text?: string | null;
  relevance_score?: number | null;
  created_at: string;
};

export type Interaction = {
  id: string;
  interaction_type: string;
  question: string;
  options: unknown[];
  correct_answer: unknown;
  correct_feedback?: string | null;
  incorrect_feedback?: string | null;
  explanation?: string | null;
  difficulty?: string | null;
  points: number;
  settings: Record<string, unknown>;
};

export type SlideBlueprint = {
  slide: Slide & { guiding_question?: string };
  source_refs: SlideSourceRef[];
  interactions: Interaction[];
};

export type SourceChunk = {
  id: string;
  source_file_id: string;
  project_id: string;
  chunk_index: number;
  page_start?: number | null;
  page_end?: number | null;
  heading?: string | null;
  content: string;
  token_count?: number | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
};

export type CopilotAction = "shorten" | "simplify" | "make_engaging" | "generate_question" | "visual_prompt" | "custom";
export type CopilotProposal = {
  mode: string;
  action: CopilotAction;
  summary: string;
  patch: Partial<Slide>;
  warnings: string[];
};


export type DesignElement = {
  id: string;
  type: string;
  x: number; y: number; w: number; h: number;
  z: number; locked?: boolean; visible?: boolean;
  style?: Record<string, unknown>;
};

export type DesignState = {
  version?: number;
  theme_key?: string | null;
  layout_key?: string | null;
  elements?: DesignElement[];
};

export type ThemeDefinition = {
  key: string; name: string; description: string;
  tokens: { bg: string; surface: string; text: string; muted: string; accent: string; accentSoft: string; radius: number };
};
export type LayoutDefinition = {
  key: string; name: string; description: string;
  elements: Record<string, [number, number, number, number]>;
};
export type VisualCatalog = { themes: ThemeDefinition[]; layouts: LayoutDefinition[] };

export type MediaAsset = {
  id: string; project_id: string; slide_id?: string | null; asset_type: string; status: string;
  original_name?: string | null; storage_uri?: string | null; mime_type?: string | null; size_bytes?: number | null;
  prompt?: string | null; provider?: string | null; provider_asset_id?: string | null; width?: number | null; height?: number | null;
  duration_seconds?: number | null; metadata_json: Record<string, unknown>; error_message?: string | null; created_at: string; updated_at: string;
};

export type ExportFormat = "pptx" | "pdf" | "html5" | "scorm12" | "scorm2004";
export type ExportRun = {
  id: string; project_id: string; format: ExportFormat | string; status: string;
  file_name?: string | null; storage_uri?: string | null; mime_type?: string | null; size_bytes?: number | null;
  options: Record<string, unknown>; warnings: unknown[]; error_message?: string | null; created_at: string; completed_at?: string | null;
  download_url?: string | null;
};


export type LmsStandard = "scorm12" | "scorm2004";
export type LmsProfile = {
  id: string; project_id: string; default_standard: LmsStandard; passing_score: number; completion_threshold: number;
  track_interactions: boolean; resume_enabled: boolean; report_session_time: boolean; settings: Record<string, unknown>;
  created_at: string; updated_at: string;
};
export type LmsCatalog = {
  standards: Array<{ key: LmsStandard; name: string; description: string; api_object: string; initialize: string; terminate: string }>;
  tracking: Array<{ key: string; label: string }>;
  xapi: { status: string; events: string[]; note: string };
};

export type AnalyticsSummary = {
  learner_count: number; attempt_count: number; completed_attempts: number; passed_attempts: number;
  completion_rate: number; pass_rate: number; average_score?: number | null; average_progress: number;
  total_learning_seconds: number; response_count: number; correct_response_rate?: number | null;
};
export type LearnerSummary = {
  learner_key: string; learner_name?: string | null; attempt_count: number; latest_attempt_id: string;
  latest_status: string; latest_score?: number | null; latest_progress: number; latest_success?: boolean | null;
  total_learning_seconds: number; last_event_at: string;
};
export type ObjectiveAnalytics = {
  objective_id: string; objective_order: number; objective_text: string; response_count: number; correct_count: number;
  mastery_percent?: number | null; learner_count: number;
};
export type LearnerAttempt = {
  id: string; project_id: string; learner_key: string; learner_name?: string | null; external_attempt_id?: string | null;
  source: string; status: string; score_raw?: number | null; score_scaled?: number | null; progress: number;
  completed: boolean; success?: boolean | null; duration_seconds: number; session_count: number; metadata_json: Record<string, unknown>;
  started_at: string; last_event_at: string; completed_at?: string | null; created_at: string; updated_at: string;
};
export type LearnerEvent = {
  id: string; attempt_id: string; project_id: string; event_type: string; event_id?: string | null; verb_iri?: string | null;
  slide_id?: string | null; interaction_id?: string | null; objective_ids: string[]; response?: unknown; correct?: boolean | null;
  score_raw?: number | null; score_scaled?: number | null; progress?: number | null; duration_seconds?: number | null;
  payload: Record<string, unknown>; event_time: string; created_at: string;
};
export type AttemptDetail = { attempt: LearnerAttempt; events: LearnerEvent[]; objective_mastery: ObjectiveAnalytics[] };
export type LrsConnection = {
  id: string; project_id: string; enabled: boolean; endpoint?: string | null; xapi_version: string;
  auth_type: "none" | "basic" | "bearer"; username_env?: string | null; password_env?: string | null; token_env?: string | null;
  verify_tls: boolean; timeout_seconds: number; settings: Record<string, unknown>; created_at: string; updated_at: string;
};
export type LrsDelivery = {
  id: string; project_id: string; attempt_id?: string | null; status: string; statement_count: number;
  http_status?: number | null; response_excerpt?: string | null; error_message?: string | null; created_at: string; completed_at?: string | null;
};

// Step 11 — authenticated classroom / assignment layer
export type UserRole = "admin" | "teacher" | "student";
export type AuthUser = { id: string; email?: string | null; display_name?: string | null; role: UserRole; is_active: boolean };
export type TokenResponse = { access_token: string; token_type: string; expires_at: string; refresh_expires_at?: string | null; user: AuthUser };
export type OrganizationRole = "owner" | "admin" | "teacher" | "student";
export type Organization = { id: string; name: string; slug: string; status: string; settings: Record<string, unknown>; member_role?: OrganizationRole | null; created_at: string; updated_at: string };
export type OrganizationMember = { id: string; organization_id: string; user_id: string; role: OrganizationRole; status: string; display_name?: string | null; email?: string | null; joined_at?: string | null };
export type Classroom = {
  id: string; owner_id: string; organization_id?: string | null; name: string; subject?: string | null; grade?: string | null; school_name?: string | null;
  academic_year?: string | null; join_code: string; status: string; settings: Record<string, unknown>;
  member_count: number; student_count: number; assignment_count: number; created_at: string; updated_at: string;
};
export type ClassroomMember = {
  id: string; classroom_id: string; user_id: string; member_role: "teacher" | "student" | string; status: string;
  enrolled_at: string; display_name?: string | null; email?: string | null; account_role?: string | null;
};
export type Assignment = {
  id: string; classroom_id: string; project_id: string; assigned_by: string; title: string; instructions?: string | null; status: string;
  opens_at?: string | null; due_at?: string | null; closes_at?: string | null; max_attempts?: number | null; passing_score?: number | null;
  settings: Record<string, unknown>; created_at: string; updated_at: string; project_title?: string | null; subject?: string | null; grade?: string | null;
};
export type ClassroomAnalyticsSummary = {
  student_count: number; assignment_count: number; published_assignment_count: number; expected_completions: number;
  started_pairs: number; completed_pairs: number; passed_pairs: number; completion_rate: number; pass_rate: number;
  average_score?: number | null; total_learning_seconds: number;
};
export type ClassroomLearnerAnalytics = {
  user_id: string; display_name?: string | null; email?: string | null; assigned_count: number; started_count: number; completed_count: number;
  passed_count: number; completion_rate: number; average_score?: number | null; total_learning_seconds: number; last_activity_at?: string | null;
};
export type ClassroomAssignmentAnalytics = {
  assignment_id: string; title: string; project_id: string; project_title: string; student_count: number; started_count: number;
  completed_count: number; passed_count: number; completion_rate: number; pass_rate: number; average_score?: number | null; due_at?: string | null; status: string;
};
export type LearnerAssignmentStatus = {
  assignment: Assignment; attempt_count: number; latest_attempt_id?: string | null; status: string; progress: number; score?: number | null;
  completed: boolean; success?: boolean | null; can_start: boolean; lock_reason?: string | null;
};
export type LearnerInteraction = { id: string; interaction_type: string; question: string; options: unknown[]; difficulty?: string | null; points: number };
export type LearnerSlide = {
  id: string; slide_order: number; title?: string | null; slide_type: string; onscreen_text: unknown[]; student_instruction?: string | null;
  visual_type?: string | null; visual_description?: string | null; media: unknown[]; design_json: DesignState; duration_seconds?: number | null;
  interactions: LearnerInteraction[];
};
export type LearnerLesson = { assignment: Assignment; project_title: string; subject?: string | null; grade?: string | null; slides: LearnerSlide[] };
export type LearnerAnswerResult = { event_id: string; correct: boolean; feedback?: string | null };
export type LearnerFinishResult = { attempt_id: string; score: number; passed: boolean; answered_count: number; question_count: number };

export type SourceFile = {
  id: string; project_id: string; original_name: string; storage_uri?: string | null;
  mime_type?: string | null; size_bytes?: number | null; parse_status: string; page_count?: number | null;
  created_at: string; updated_at: string;
};

export type BackgroundJob = {
  id: string; organization_id?: string | null; project_id: string; created_by?: string | null;
  kind: "analyze" | "plan" | "generate" | "export"; status: "queued" | "running" | "completed" | "failed" | "cancelled";
  progress: number; attempts: number; max_attempts: number; payload: Record<string, unknown>; result: Record<string, unknown>;
  error_message?: string | null; available_at: string; locked_at?: string | null; started_at?: string | null;
  completed_at?: string | null; created_at: string; updated_at: string;
};

export type AnalysisRun = {
  id: string; project_id: string; status: string; analyzer_version: string; analysis_mode: string;
  file_count: number; chunk_count: number; knowledge_map: Record<string, unknown>; warnings: string[];
  error_message?: string | null; started_at: string; completed_at?: string | null; created_at: string;
};

export type PlanningRun = {
  id: string; project_id: string; analysis_run_id?: string | null; status: string; planner_version: string;
  planning_mode: string; plan_json: Record<string, unknown>; warnings: string[]; error_message?: string | null;
  teacher_approved: boolean; approved_at?: string | null; started_at: string; completed_at?: string | null; created_at: string;
};
