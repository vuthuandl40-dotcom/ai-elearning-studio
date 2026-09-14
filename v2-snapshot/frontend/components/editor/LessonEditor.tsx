"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { CopilotProposal, ExportFormat, LmsCatalog, LmsProfile, MediaAsset, Project, Section, Slide, SlideBlueprint, VisualCatalog } from "@/lib/types";
import TopBar from "./TopBar";
import SectionSidebar from "./SectionSidebar";
import SlideStage from "./SlideStage";
import Inspector from "./Inspector";
import LmsSettingsDialog from "./LmsSettingsDialog";

function editablePatch(slide: Slide): Partial<Slide> {
  return {
    title: slide.title,
    slide_type: slide.slide_type,
    onscreen_text: slide.onscreen_text,
    teacher_script: slide.teacher_script,
    student_instruction: slide.student_instruction,
    visual_type: slide.visual_type,
    visual_description: slide.visual_description,
    image_prompt: slide.image_prompt,
    video_prompt: slide.video_prompt,
    duration_seconds: slide.duration_seconds,
    layout_hint: slide.layout_hint,
    media: slide.media,
    design_json: slide.design_json,
    ai_metadata: slide.ai_metadata,
    teacher_approved: slide.teacher_approved,
  };
}

export default function LessonEditor({ projectId }: { projectId: string }) {
  const [project, setProject] = useState<Project | null>(null);
  const [sections, setSections] = useState<Section[]>([]);
  const [slides, setSlides] = useState<Slide[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [draft, setDraft] = useState<Slide | null>(null);
  const [blueprint, setBlueprint] = useState<SlideBlueprint | null>(null);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [catalog, setCatalog] = useState<VisualCatalog | null>(null);
  const [mediaAssets, setMediaAssets] = useState<MediaAsset[]>([]);
  const [selectedElementId, setSelectedElementId] = useState<string | null>(null);
  const [lmsProfile, setLmsProfile] = useState<LmsProfile | null>(null);
  const [lmsCatalog, setLmsCatalog] = useState<LmsCatalog | null>(null);
  const [lmsOpen, setLmsOpen] = useState(false);

  const loadCore = useCallback(async (preferredId?: string) => {
    const [p, secs, sls, cat, media, lms, lmsCat] = await Promise.all([api.getProject(projectId), api.getSections(projectId), api.getSlides(projectId), api.visualCatalog(), api.listMedia(projectId), api.getLmsProfile(projectId), api.lmsCatalog()]);
    setCatalog(cat); setMediaAssets(media); setLmsProfile(lms); setLmsCatalog(lmsCat);
    setProject(p);
    setSections([...secs].sort((a, b) => a.section_order - b.section_order));
    const ordered = [...sls].sort((a, b) => a.slide_order - b.slide_order);
    setSlides(ordered);
    const nextId = preferredId && ordered.some((s) => s.id === preferredId) ? preferredId : (ordered[0]?.id || "");
    setSelectedId(nextId);
    if (!nextId) { setDraft(null); setBlueprint(null); }
  }, [projectId]);

  useEffect(() => {
    setBusy("Đang tải bài giảng…");
    loadCore().catch((e) => setError(e.message)).finally(() => setBusy(""));
  }, [loadCore]);

  useEffect(() => {
    if (!selectedId) return;
    setBlueprint(null);
    api.getBlueprint(selectedId).then((bp) => {
      const full = { ...bp.slide, guiding_question: undefined } as Slide;
      setBlueprint(bp);
      setDraft(full);
      setDirty(false); setSelectedElementId(null);
    }).catch((e) => setError(e.message));
  }, [selectedId]);

  const selectedSlide = slides.find((s) => s.id === selectedId);
  const currentSection = sections.find((s) => s.id === (draft?.section_id || selectedSlide?.section_id));

  const selectSlide = (slide: Slide) => {
    if (dirty && !confirm("Slide hiện tại có thay đổi chưa lưu. Chuyển slide và bỏ thay đổi?")) return;
    setSelectedId(slide.id);
  };

  const changeDraft = (patch: Partial<Slide>) => {
    setDraft((prev) => prev ? ({ ...prev, ...patch } as Slide) : prev);
    setDirty(true);
  };

  const save = async () => {
    if (!draft) return;
    setBusy("Đang lưu slide…"); setError("");
    try {
      const saved = await api.updateSlide(draft.id, editablePatch(draft));
      setSlides((prev) => prev.map((s) => s.id === saved.id ? saved : s));
      const bp = await api.getBlueprint(saved.id);
      setBlueprint(bp); setDraft(bp.slide as Slide); setDirty(false); setNotice("Đã lưu slide.");
    } catch (e) { setError(e instanceof Error ? e.message : "Không lưu được slide"); }
    finally { setBusy(""); }
  };

  const navigate = (delta: number) => {
    if (!draft || !slides.length) return;
    const index = slides.findIndex((s) => s.id === draft.id);
    const next = slides[Math.min(slides.length - 1, Math.max(0, index + delta))];
    if (next && next.id !== draft.id) selectSlide(next);
  };

  const generateLesson = async () => {
    if (dirty && !confirm("Có thay đổi chưa lưu. Tiếp tục sinh bài có thể làm mất bản nháp hiện tại. Tiếp tục?")) return;
    setBusy("AI đang sinh lesson blueprints…"); setError("");
    try { await api.generateLesson(projectId); await loadCore(selectedId); setNotice("Đã sinh/cập nhật bài giảng."); }
    catch (e) { setError(e instanceof Error ? e.message : "Sinh bài thất bại"); }
    finally { setBusy(""); }
  };

  const regenerateSection = async (instruction?: string) => {
    if (!currentSection) return;
    const suffix = instruction?.trim() ? " theo yêu cầu riêng đang nhập" : " theo kế hoạch hiện tại";
    if (!confirm(`Tạo lại toàn bộ phần “${currentSection.title}”${suffix}? Tất cả slide trong section này, kể cả slide đã duyệt, sẽ được thay bằng bản mới.`)) return;
    setBusy(`Đang tạo lại ${currentSection.title}…`); setError("");
    try {
      await api.regenerateSection(projectId, currentSection.section_key, true, instruction?.trim() || undefined);
      await loadCore();
      setNotice("Đã tạo lại toàn bộ section theo yêu cầu.");
    }
    catch (e) { setError(e instanceof Error ? e.message : "Tạo lại section thất bại"); }
    finally { setBusy(""); }
  };

  const approve = async () => {
    setBusy("Đang duyệt generation…"); setError("");
    try {
      if (dirty) await save();
      const run = await api.latestGeneration(projectId);
      if (!run.teacher_approved) await api.approveGeneration(projectId, run.id);
      await loadCore(selectedId);
      setNotice("Đã duyệt generation và khóa các slide thuộc lần sinh này.");
    } catch (e) { setError(e instanceof Error ? e.message : "Không duyệt được bài"); }
    finally { setBusy(""); }
  };


  const exportLesson = async (format: ExportFormat) => {
    setError("");
    try {
      if (dirty && draft) {
        if (!confirm("Slide hiện tại có thay đổi chưa lưu. Cần lưu trước khi xuất. Tiếp tục?")) return;
        setBusy("Đang lưu slide trước khi xuất…");
        const saved = await api.updateSlide(draft.id, editablePatch(draft));
        setSlides((prev) => prev.map((s) => s.id === saved.id ? saved : s));
        setDraft(saved); setDirty(false);
      }
      const isScorm = format === "scorm12" || format === "scorm2004";
      setBusy(format === "pptx" ? "Đang tạo PowerPoint…" : format === "pdf" ? "Đang tạo PDF…" : format === "html5" ? "Đang đóng gói HTML5…" : format === "scorm12" ? "Đang đóng gói SCORM 1.2…" : "Đang đóng gói SCORM 2004…");
      const options = isScorm ? {
        include_notes: false, include_sources: false, include_quiz: true,
        passing_score: lmsProfile?.passing_score ?? 80,
        completion_threshold: Number(lmsProfile?.completion_threshold ?? 1),
        track_interactions: lmsProfile?.track_interactions ?? true,
        resume_enabled: lmsProfile?.resume_enabled ?? true,
        report_session_time: lmsProfile?.report_session_time ?? true,
      } : {};
      const run = await api.createExport(projectId, format, options);
      const url = api.exportDownloadUrl(run);
      if (!url) throw new Error("Backend chưa trả đường dẫn tải file.");
      window.location.href = url;
      setNotice(`Đã tạo ${run.file_name || format.toUpperCase()}.`);
    } catch (e) { setError(e instanceof Error ? e.message : "Xuất bài thất bại"); }
    finally { setBusy(""); }
  };

  const applyProposal = (proposal: CopilotProposal) => {
    if (!draft) return;
    const patch = { ...proposal.patch } as Partial<Slide>;
    if (patch.ai_metadata) patch.ai_metadata = { ...(draft.ai_metadata || {}), ...(patch.ai_metadata || {}) };
    changeDraft(patch);
    setNotice("Đã áp dụng đề xuất vào bản nháp. Bấm “Lưu slide” để ghi vào database.");
  };

  const refreshMedia = async () => { setMediaAssets(await api.listMedia(projectId)); };

  const updateProjectTheme = async (themeKey: string) => {
    if (!project) return;
    const settings = { ...(project.settings || {}), theme_key: themeKey };
    const saved = await api.updateProject(project.id, { settings });
    setProject((prev) => prev ? ({ ...prev, ...saved }) : saved);
    setNotice("Đã đặt theme mặc định cho toàn dự án.");
  };

  const acceptPersistedSlide = (slide: Slide) => {
    setSlides((prev) => prev.map((s) => s.id === slide.id ? slide : s));
    setDraft(slide);
    setDirty(false);
    api.getBlueprint(slide.id).then(setBlueprint).catch(() => undefined);
    setNotice("Đã cập nhật media của slide.");
  };

  useEffect(() => {
    if (!notice) return;
    const t = setTimeout(() => setNotice(""), 3500);
    return () => clearTimeout(t);
  }, [notice]);

  const sectionTitle = currentSection?.title;
  const mobileSections = useMemo(() => sections.map((s) => ({ ...s, count: slides.filter((x) => x.section_id === s.id).length })), [sections, slides]);

  if (!project && busy) return <Centered text={busy} />;
  if (!project) return <Centered text={error || "Không tìm thấy project."} error />;

  return (
    <main className="flex h-screen min-h-0 flex-col overflow-hidden bg-white">
      <TopBar project={project} dirty={dirty} busy={busy} onSave={save} onApprove={approve} onGenerate={generateLesson} onExport={exportLesson} onOpenLmsSettings={() => setLmsOpen(true)} />
      <LmsSettingsDialog open={lmsOpen} profile={lmsProfile} catalog={lmsCatalog} onClose={() => setLmsOpen(false)} onSave={async (value) => {
        const saved = await api.saveLmsProfile(projectId, value);
        setLmsProfile(saved); setNotice("Đã lưu cài đặt LMS.");
      }} />
      {(error || notice || busy) && <div className={`absolute left-1/2 top-20 z-50 max-w-[90vw] -translate-x-1/2 rounded-xl border px-4 py-2.5 text-xs font-semibold shadow-xl ${error ? "border-rose-200 bg-rose-50 text-rose-700" : busy ? "border-violet-200 bg-violet-50 text-violet-700" : "border-emerald-200 bg-emerald-50 text-emerald-700"}`}>{error || busy || notice}</div>}

      <div className="flex h-10 shrink-0 items-center gap-2 overflow-x-auto border-b border-slate-200 bg-slate-50 px-3 lg:hidden">
        {mobileSections.map((s) => <span key={s.id} className={`shrink-0 rounded-full px-2.5 py-1 text-[10px] font-bold ${s.id === currentSection?.id ? "bg-violet-600 text-white" : "bg-white text-slate-500"}`}>{s.section_order}. {s.title} ({s.count})</span>)}
      </div>

      <div className="flex min-h-0 flex-1">
        <SectionSidebar sections={sections} slides={slides} selectedSlideId={selectedId} currentSectionId={currentSection?.id} onSelectSlide={selectSlide} />
        {draft ? (
          <>
            <SlideStage slide={draft} sectionTitle={sectionTitle} totalSlides={slides.length} catalog={catalog} projectTheme={String((project.settings || {}).theme_key || "studio_light")} mediaAssets={mediaAssets} selectedElementId={selectedElementId} onSelectElement={setSelectedElementId} onDesignChange={(design_json) => changeDraft({ design_json })} onPrev={() => navigate(-1)} onNext={() => navigate(1)} />
            <Inspector draft={draft} blueprint={blueprint} project={project} catalog={catalog} mediaAssets={mediaAssets} selectedElementId={selectedElementId} onSelectElement={setSelectedElementId} onChange={changeDraft} onApplyProposal={applyProposal} onRegenerateSection={regenerateSection} onProjectThemeChanged={updateProjectTheme} onMediaRefresh={refreshMedia} onPersistedSlide={acceptPersistedSlide} busy={busy} />
          </>
        ) : (
          <div className="flex flex-1 items-center justify-center bg-slate-50 p-8">
            <div className="max-w-md rounded-3xl border border-slate-200 bg-white p-8 text-center surface-shadow">
              <div className="text-4xl">🪄</div>
              <h2 className="mt-4 text-xl font-black">Chưa có slide</h2>
              <p className="mt-2 text-sm leading-6 text-slate-500">Project đã có cấu trúc 15 phần nhưng chưa có slide blueprint. Sinh bài từ Pedagogy Plan đã duyệt để bắt đầu biên tập.</p>
              <button disabled={!!busy} onClick={generateLesson} className="mt-5 rounded-xl bg-violet-600 px-5 py-3 text-sm font-bold text-white">Sinh bài giảng</button>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}

function Centered({ text, error = false }: { text: string; error?: boolean }) {
  return <main className="flex min-h-screen items-center justify-center bg-slate-50 p-6"><div className={`rounded-2xl border bg-white p-7 text-sm shadow-lg ${error ? "border-rose-200 text-rose-700" : "border-slate-200 text-slate-500"}`}>{text}</div></main>;
}
