import fs from "node:fs";
import path from "node:path";

const root = process.argv[2];
if (!root) throw new Error("source root required");

const dashboard = String.raw`"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { Project } from "@/lib/types";

const nav = [
  { icon: "⌂", label: "Trang chủ", href: "/" },
  { icon: "✦", label: "Tạo bài giảng", href: "/projects/new" },
  { icon: "▣", label: "Thư viện", href: "#recent" },
  { icon: "♙", label: "Lớp học", href: "/classrooms" },
  { icon: "♟", label: "Học sinh", href: "/learn" },
  { icon: "▥", label: "Báo cáo", href: "#analytics" },
  { icon: "✧", label: "AI trợ lý", href: "/projects/new" },
];

function statusLabel(status?: string | null) {
  const s = (status || "").toLowerCase();
  if (s.includes("complete") || s.includes("ready") || s.includes("publish")) return "Sẵn sàng";
  if (s.includes("draft") || s.includes("plan") || s.includes("generat")) return "Đang soạn";
  return status || "Đang xử lý";
}

function cover(i: number) {
  return [
    "from-sky-500 via-cyan-400 to-emerald-300",
    "from-slate-900 via-indigo-900 to-violet-700",
    "from-emerald-400 via-lime-300 to-cyan-300",
    "from-violet-600 via-indigo-500 to-sky-400",
    "from-amber-400 via-orange-400 to-rose-400",
  ][i % 5];
}

export default function HomePage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api.listProjects().then(setProjects).catch((e) => setError(e.message)).finally(() => setLoading(false));
  }, []);

  const stats = useMemo(() => {
    const ready = projects.filter((p) => ["completed", "ready", "published"].some((x) => String(p.status || "").toLowerCase().includes(x))).length;
    const drafting = Math.max(0, projects.length - ready);
    const minutes = projects.reduce((sum, p) => sum + Number(p.duration_minutes || 0), 0);
    return { ready, drafting, minutes };
  }, [projects]);

  return <main className="min-h-screen bg-[#f6f8fe] text-slate-900">
    <header className="sticky top-0 z-40 border-b border-indigo-100 bg-white/95 backdrop-blur">
      <div className="flex h-[68px] items-center gap-5 px-4 md:px-7">
        <button onClick={() => location.href="/"} className="flex items-center gap-2.5">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-indigo-600 to-violet-500 text-lg text-white shadow-lg shadow-indigo-200">▰</span>
          <span className="hidden text-xl font-black tracking-tight text-indigo-800 sm:block">AI E-Learning Studio</span>
        </button>
        <div className="hidden h-7 w-px bg-slate-200 lg:block"/>
        <div className="hidden text-sm font-medium text-slate-500 lg:block">Tạo bài giảng thông minh · Dạy học dễ dàng · Học tập hiệu quả</div>
        <div className="ml-auto flex items-center gap-2">
          <span className="hidden rounded-xl border border-violet-100 bg-violet-50 px-3 py-2 text-[11px] font-black text-violet-700 sm:block">V2 STAGING</span>
          <span className="hidden rounded-xl border border-emerald-100 bg-emerald-50 px-3 py-2 text-[11px] font-black text-emerald-700 md:block">● Sẵn sàng triển khai</span>
          <button onClick={() => location.href="/login"} className="flex items-center gap-2 rounded-xl px-2 py-1.5 hover:bg-slate-50">
            <span className="grid h-9 w-9 place-items-center rounded-full bg-gradient-to-br from-slate-700 to-slate-900 text-sm font-black text-white">GV</span>
            <span className="hidden text-left md:block"><span className="block text-xs font-black">Giáo viên</span><span className="block text-[10px] text-slate-400">Workspace cá nhân</span></span>
          </button>
        </div>
      </div>
    </header>

    <div className="flex">
      <aside className="sticky top-[68px] hidden h-[calc(100vh-68px)] w-[214px] shrink-0 border-r border-indigo-100 bg-white p-3 lg:block">
        <div className="px-3 pb-3 pt-2 text-[10px] font-black uppercase tracking-[.18em] text-slate-400">Không gian làm việc</div>
        <nav className="space-y-1">
          {nav.map((item, i) => <button key={item.label} onClick={() => location.href=item.href} className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm font-semibold transition ${i===0?"bg-indigo-50 text-indigo-700":"text-slate-600 hover:bg-slate-50 hover:text-indigo-700"}`}><span className="w-5 text-center text-base">{item.icon}</span>{item.label}</button>)}
        </nav>
        <div className="absolute bottom-4 left-3 right-3 rounded-2xl bg-gradient-to-br from-indigo-600 to-violet-600 p-4 text-white shadow-lg shadow-indigo-100">
          <div className="text-xs font-black">AI E-Learning Studio V2</div>
          <div className="mt-1 text-[10px] leading-4 text-indigo-100">Sinh bài · Biên tập · Giao bài · Theo dõi học tập</div>
        </div>
      </aside>

      <section className="min-w-0 flex-1 p-4 md:p-7">
        <div className="mx-auto max-w-[1420px]">
          <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            <div><h1 className="text-2xl font-black tracking-tight md:text-3xl">Xin chào, Giáo viên 👋</h1><p className="mt-1 text-sm text-slate-500">Hãy bắt đầu tạo những bài giảng trực quan và tương tác cùng AI.</p></div>
            <button onClick={() => location.href="/projects/new"} className="rounded-xl bg-indigo-600 px-5 py-3 text-sm font-black text-white shadow-lg shadow-indigo-200 transition hover:-translate-y-0.5 hover:bg-indigo-700">＋ Tạo bài giảng mới</button>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {[
              ["▣", projects.length, "Bài giảng", "bg-emerald-50 text-emerald-600"],
              ["✦", stats.drafting, "Đang soạn", "bg-violet-50 text-violet-600"],
              ["✓", stats.ready, "Sẵn sàng", "bg-blue-50 text-blue-600"],
              ["◷", stats.minutes || "—", "Tổng phút học", "bg-amber-50 text-amber-600"],
            ].map(([icon,value,label,tone]) => <div key={String(label)} className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-sm"><div className="flex items-center gap-3"><span className={`grid h-10 w-10 place-items-center rounded-xl text-lg font-black ${tone}`}>{icon}</span><div><div className="text-xl font-black">{value}</div><div className="text-xs text-slate-500">{label}</div></div></div></div>)}
          </div>

          <section className="relative mt-5 overflow-hidden rounded-[26px] bg-gradient-to-r from-indigo-700 via-violet-600 to-indigo-500 px-6 py-7 text-white shadow-xl shadow-indigo-100 md:px-9 md:py-8">
            <div className="absolute -right-16 -top-24 h-64 w-64 rounded-full bg-white/10 blur-2xl"/><div className="absolute right-24 top-5 h-28 w-28 rounded-full bg-cyan-300/20 blur-xl"/>
            <div className="relative max-w-2xl"><div className="mb-2 inline-flex rounded-full bg-white/15 px-3 py-1 text-[10px] font-black uppercase tracking-wider">AI Lesson Builder V2</div><h2 className="text-2xl font-black md:text-3xl">Tạo bài giảng với AI</h2><p className="mt-2 max-w-xl text-sm leading-6 text-indigo-100">Tải tài liệu, AI phân tích nguồn, lập kế hoạch sư phạm và sinh bài giảng hoàn chỉnh với tương tác trong vài bước.</p><div className="mt-5 flex flex-wrap gap-2"><button onClick={() => location.href="/projects/new"} className="rounded-xl bg-white px-5 py-3 text-xs font-black text-indigo-700">Bắt đầu ngay</button><button onClick={() => document.getElementById("recent")?.scrollIntoView({behavior:"smooth"})} className="rounded-xl border border-white/30 bg-white/10 px-5 py-3 text-xs font-black">Xem bài gần đây</button></div></div>
            <div className="absolute bottom-5 right-6 hidden h-36 w-44 place-items-center rounded-[32px] border border-white/20 bg-white/10 backdrop-blur md:grid"><div className="text-center"><div className="text-6xl">🤖</div><div className="mt-1 text-[10px] font-black uppercase tracking-widest text-indigo-100">AI Copilot</div></div></div>
          </section>

          <div id="recent" className="mt-7 flex items-center justify-between"><div><h2 className="text-lg font-black">Bài giảng gần đây</h2><p className="text-xs text-slate-400">Các dự án bạn đang xây dựng và chỉnh sửa</p></div><button onClick={() => location.reload()} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-600">Làm mới</button></div>

          {loading && <div className="mt-4 rounded-2xl border bg-white p-10 text-center text-sm text-slate-400">Đang tải bài giảng…</div>}
          {error && <div className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700">Không kết nối được backend: {error}</div>}
          {!loading && !error && projects.length===0 && <button onClick={() => location.href="/projects/new"} className="mt-4 w-full rounded-3xl border-2 border-dashed border-indigo-200 bg-white p-12 text-center"><div className="text-4xl">✦</div><div className="mt-3 text-base font-black">Tạo bài giảng đầu tiên</div><div className="mt-1 text-sm text-slate-400">Bắt đầu từ tài liệu Word, PDF, PowerPoint hoặc nội dung bạn nhập.</div></button>}

          <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {projects.slice(0,8).map((p,i) => <button key={p.id} onClick={() => location.href=`/projects/${p.id}/editor`} className="group overflow-hidden rounded-2xl border border-slate-200 bg-white text-left shadow-sm transition hover:-translate-y-1 hover:shadow-xl">
              <div className={`relative h-32 bg-gradient-to-br ${cover(i)} p-4 text-white`}><div className="absolute inset-0 bg-black/5"/><div className="relative flex h-full flex-col justify-between"><span className="w-fit rounded-lg bg-black/20 px-2 py-1 text-[9px] font-black uppercase backdrop-blur">{p.subject || "Bài học"}</span><div className="text-3xl opacity-90">{["🌍","💻","🌱","📊","🔬"][i%5]}</div></div></div>
              <div className="p-4"><div className="line-clamp-2 min-h-10 text-sm font-black leading-5 group-hover:text-indigo-700">{p.title}</div><div className="mt-2 flex items-center justify-between text-[10px] text-slate-400"><span>{[p.subject,p.grade? `Lớp ${p.grade}`:null].filter(Boolean).join(" · ") || "Chưa có metadata"}</span><span>{p.duration_minutes ? `${p.duration_minutes} phút` : "—"}</span></div><div className="mt-3 flex items-center justify-between"><span className="rounded-full bg-indigo-50 px-2 py-1 text-[9px] font-black text-indigo-700">{statusLabel(p.status)}</span><span className="text-[10px] font-black text-indigo-600">Mở Editor →</span></div></div>
            </button>)}
          </div>

          <section id="analytics" className="mt-7 grid gap-4 lg:grid-cols-[1.25fr_.75fr]">
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><div className="flex items-center justify-between"><div><h3 className="text-sm font-black">Tiến độ hệ thống</h3><p className="text-xs text-slate-400">Tổng quan workspace hiện tại</p></div><span className="rounded-lg bg-emerald-50 px-2 py-1 text-[10px] font-black text-emerald-700">V2 hoạt động</span></div><div className="mt-6 grid grid-cols-3 gap-3">{[["Bài đã tạo",projects.length],["Đang soạn",stats.drafting],["Sẵn sàng",stats.ready]].map(([l,v])=><div key={String(l)} className="rounded-xl bg-slate-50 p-4"><div className="text-2xl font-black text-indigo-700">{v}</div><div className="mt-1 text-[10px] font-bold text-slate-500">{l}</div></div>)}</div></div>
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><h3 className="text-sm font-black">Truy cập nhanh</h3><div className="mt-4 space-y-2">{[["Tạo bài giảng với AI","/projects/new"],["Quản lý lớp học","/classrooms"],["Giao diện học sinh","/learn"]].map(([l,h])=><button key={l} onClick={()=>location.href=h} className="flex w-full items-center justify-between rounded-xl border border-slate-100 px-3 py-3 text-left text-xs font-bold hover:border-indigo-200 hover:bg-indigo-50"><span>{l}</span><span className="text-indigo-500">→</span></button>)}</div></div>
          </section>
        </div>
      </section>
    </div>
  </main>;
}
`;

fs.writeFileSync(path.join(root, "frontend/app/page.tsx"), dashboard);


const newProject = String.raw\`"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { BackgroundJob, Organization, PlanningRun, Project } from "@/lib/types";

type Stage = "info" | "files" | "analyze" | "plan" | "approve" | "generate" | "done";

export default function NewProjectPage() {
  const [stage, setStage] = useState<Stage>("info");
  const [project, setProject] = useState<Project | null>(null);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [files, setFiles] = useState<File[]>([]);
  const [uploaded, setUploaded] = useState<string[]>([]);
  const [plan, setPlan] = useState<PlanningRun | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [progress, setProgress] = useState<BackgroundJob | null>(null);
  const [form, setForm] = useState({ title:"", subject:"", grade:"", education_level:"THCS", book_series:"", duration_minutes:45, organization_id:"", visual_style:"Hiện đại, trực quan", narration_style:"Tự nhiên, dễ hiểu", interaction_level:"medium" as "low"|"medium"|"high", source_policy:"strict" as "strict"|"source_plus_verified"|"open", extra_instructions:"Chỉ sử dụng kiến thức trong tài liệu tôi cung cấp; không tự thêm số liệu chưa được kiểm chứng." });

  useEffect(() => { api.listOrganizations().then(setOrganizations).catch(() => undefined); }, []);
  const sections = useMemo(() => Array.isArray(plan?.plan_json?.sections) ? plan?.plan_json?.sections as Array<Record<string,unknown>> : [], [plan]);
  const objectives = useMemo(() => Array.isArray(plan?.plan_json?.objectives) ? plan?.plan_json?.objectives as Array<Record<string,unknown>> : [], [plan]);

  const fail = (e: unknown) => { setError(e instanceof Error ? e.message : "Có lỗi xảy ra"); setBusy(""); };
  const watch = (label:string) => (job:BackgroundJob) => { setProgress(job); setBusy(label + " · " + job.status + " · " + job.progress + "%"); };

  async function create() {
    setError(""); setBusy("Đang tạo bài giảng…");
    try {
      const p = await api.createProject({ ...form, organization_id: form.organization_id || null, lesson_periods: 1 });
      setProject(p); setStage("files"); setBusy("");
    } catch(e) { fail(e); }
  }

  async function uploadAndAnalyze() {
    if (!project || files.length === 0) return;
    setError(""); setBusy("Đang tải tài liệu…");
    try {
      for (const file of files) {
        if (uploaded.includes(file.name)) continue;
        await api.uploadSourceFile(project.id, file);
        setUploaded((x) => [...x, file.name]);
      }
      setStage("analyze");
      const job = await api.createJob(project.id, "analyze", { use_ai:true, create_embeddings:true, vision_fallback:true });
      await api.waitForJob(job.id, watch("AI đang đọc và phân tích tài liệu"));
      setStage("plan"); setProgress(null); setBusy("AI đang xây cấu trúc bài học…");
      const pjob = await api.createJob(project.id, "plan", { use_ai:true, preserve_teacher_edits:true });
      await api.waitForJob(pjob.id, watch("AI đang lập kế hoạch sư phạm"));
      const latest = await api.latestPlan(project.id);
      setPlan(latest); setStage("approve"); setBusy(""); setProgress(null);
    } catch(e) { fail(e); }
  }

  async function approveAndGenerate() {
    if (!project || !plan) return;
    setError(""); setBusy("Đang duyệt kế hoạch…");
    try {
      await api.approvePlan(project.id, plan.id);
      setStage("generate");
      const job = await api.createJob(project.id, "generate", { use_ai:true, preserve_teacher_edits:true, fallback_to_local:true });
      await api.waitForJob(job.id, watch("AI đang sinh bài giảng hoàn chỉnh"));
      setStage("done"); setBusy(""); setProgress(null);
    } catch(e) { fail(e); }
  }

  const step = stage==="info"||stage==="files" ? 1 : stage==="analyze"||stage==="plan" ? 2 : stage==="approve" ? 3 : 4;
  const stepItems = [["1","Tài liệu"],["2","AI phân tích"],["3","Tùy chỉnh"],["4","Hoàn thành"]];

  return <main className="min-h-screen bg-[#f6f8fe] text-slate-900">
    <header className="border-b border-indigo-100 bg-white">
      <div className="flex h-[68px] items-center gap-4 px-4 md:px-7">
        <button onClick={()=>location.href="/"} className="flex items-center gap-2.5"><span className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-indigo-600 to-violet-500 text-white">▰</span><span className="hidden text-xl font-black text-indigo-800 sm:block">AI E-Learning Studio</span></button>
        <div className="ml-auto flex items-center gap-2"><span className="hidden rounded-xl bg-violet-50 px-3 py-2 text-[10px] font-black text-violet-700 md:block">V2 · AI LESSON BUILDER</span><button onClick={()=>location.href="/"} className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-black">Đóng</button></div>
      </div>
    </header>

    <div className="mx-auto max-w-7xl p-4 md:p-7">
      <div className="mb-5"><div className="text-[11px] font-black uppercase tracking-[.18em] text-indigo-600">Tạo bài giảng với AI</div><h1 className="mt-1 text-2xl font-black md:text-3xl">Biến tài liệu thành bài học tương tác</h1><p className="mt-1 text-sm text-slate-500">AI phân tích học liệu, lập kế hoạch sư phạm và sinh bài giảng có nguồn tham chiếu.</p></div>

      <div className="mb-6 rounded-2xl border border-indigo-100 bg-white p-3 shadow-sm">
        <div className="grid grid-cols-4 gap-2">
          {stepItems.map(([n,label],i)=>{const active=i+1<=step; return <div key={n} className="flex items-center gap-2 md:gap-3"><span className={"grid h-8 w-8 shrink-0 place-items-center rounded-full text-xs font-black " + (active?"bg-indigo-600 text-white":"bg-slate-100 text-slate-400")}>{n}</span><span className={"hidden text-xs font-black sm:block " + (active?"text-indigo-700":"text-slate-400")}>{label}</span>{i<3&&<span className={"ml-auto h-px flex-1 " + (i+1<step?"bg-indigo-300":"bg-slate-200")}/>}</div>})}
        </div>
      </div>

      {(error||busy) && <div className={"mb-5 rounded-2xl border p-4 text-sm font-semibold " + (error?"border-rose-200 bg-rose-50 text-rose-700":"border-indigo-200 bg-indigo-50 text-indigo-700")}>
        <div className="flex items-center gap-3"><span className={error?"":"animate-spin"}>{error?"!":"◌"}</span><span>{error||busy}</span>{progress&&<span className="ml-auto text-xs font-black">{progress.progress}%</span>}</div>
        {progress&&<div className="mt-3 h-2 overflow-hidden rounded-full bg-white"><div className="h-full rounded-full bg-indigo-600 transition-all" style={{width:String(Math.max(4,progress.progress))+"%"}}/></div>}
      </div>}

      {(stage==="info"||stage==="files") && <div className="grid gap-5 lg:grid-cols-[.88fr_1.12fr]">
        <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between"><div><div className="text-xs font-black text-indigo-600">THÔNG TIN BÀI HỌC</div><h2 className="mt-1 text-lg font-black">Thiết lập nội dung</h2></div><span className="grid h-10 w-10 place-items-center rounded-xl bg-indigo-50 text-xl">✎</span></div>
          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            <Field label="Tên bài *"><input disabled={!!project} value={form.title} onChange={e=>setForm({...form,title:e.target.value})} className="input" placeholder="Ví dụ: Biến đổi khí hậu" /></Field>
            <Field label="Môn học"><input disabled={!!project} value={form.subject} onChange={e=>setForm({...form,subject:e.target.value})} className="input" placeholder="Địa lí" /></Field>
            <Field label="Lớp"><input disabled={!!project} value={form.grade} onChange={e=>setForm({...form,grade:e.target.value})} className="input" placeholder="9" /></Field>
            <Field label="Cấp học"><select disabled={!!project} value={form.education_level} onChange={e=>setForm({...form,education_level:e.target.value})} className="input"><option>Mầm non</option><option>Tiểu học</option><option>THCS</option><option>THPT</option></select></Field>
            <Field label="Thời lượng"><input disabled={!!project} type="number" min={10} value={form.duration_minutes} onChange={e=>setForm({...form,duration_minutes:Number(e.target.value)})} className="input" /></Field>
            <Field label="Mức tương tác"><select disabled={!!project} value={form.interaction_level} onChange={e=>setForm({...form,interaction_level:e.target.value as typeof form.interaction_level})} className="input"><option value="low">Ít</option><option value="medium">Vừa</option><option value="high">Nhiều</option></select></Field>
            <div className="sm:col-span-2"><Field label="Tổ chức / trường"><select disabled={!!project} value={form.organization_id} onChange={e=>setForm({...form,organization_id:e.target.value})} className="input"><option value="">Workspace cá nhân</option>{organizations.map(o=><option key={o.id} value={o.id}>{o.name}</option>)}</select></Field></div>
          </div>
          {!project?<button disabled={!form.title.trim()||!!busy} onClick={create} className="mt-5 w-full rounded-xl bg-indigo-600 px-5 py-3 text-sm font-black text-white shadow-lg shadow-indigo-100 disabled:opacity-40">Tạo bài & chọn tài liệu →</button>:<div className="mt-5 rounded-xl bg-emerald-50 px-4 py-3 text-xs font-bold text-emerald-700">✓ Đã tạo bài: {project.title}</div>}
        </section>

        <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between"><div><div className="text-xs font-black text-indigo-600">TÀI LIỆU NGUỒN</div><h2 className="mt-1 text-lg font-black">Tải học liệu để AI phân tích</h2></div><span className="grid h-10 w-10 place-items-center rounded-xl bg-violet-50 text-xl">⇧</span></div>
          <label className={"mt-5 block rounded-2xl border-2 border-dashed p-8 text-center transition " + (project?"cursor-pointer border-indigo-200 bg-indigo-50/40 hover:bg-indigo-50":"cursor-not-allowed border-slate-200 bg-slate-50 opacity-60")}>
            <input disabled={!project} type="file" multiple className="hidden" accept=".pdf,.doc,.docx,.ppt,.pptx,.txt,.png,.jpg,.jpeg,.webp" onChange={e=>setFiles(Array.from(e.target.files||[]))}/>
            <div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-white text-3xl shadow-sm">⇧</div>
            <div className="mt-3 text-sm font-black">{project?"Kéo thả tài liệu vào đây":"Hoàn thành thông tin bài học trước"}</div>
            <div className="mt-1 text-xs text-slate-400">PDF, DOCX, PPTX, TXT, PNG/JPG</div>
            <div className="mt-4 inline-flex rounded-xl bg-indigo-600 px-4 py-2 text-xs font-black text-white">Chọn file</div>
          </label>
          {files.length>0&&<div className="mt-4 max-h-40 space-y-2 overflow-auto">{files.map(f=><div key={f.name+f.size} className="flex items-center gap-3 rounded-xl border border-slate-100 bg-slate-50 px-3 py-2"><span>📄</span><div className="min-w-0 flex-1"><div className="truncate text-xs font-bold">{f.name}</div><div className="text-[10px] text-slate-400">{(f.size/1024/1024).toFixed(1)} MB</div></div>{uploaded.includes(f.name)&&<span className="text-emerald-600">✓</span>}</div>)}</div>}
          <button disabled={!project||!files.length||!!busy} onClick={uploadAndAnalyze} className="mt-5 w-full rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 px-5 py-3 text-sm font-black text-white shadow-lg shadow-indigo-100 disabled:opacity-40">Phân tích với AI ✦</button>
          <div className="mt-4 flex flex-wrap gap-2">{["Tạo bài về biến đổi khí hậu","Bài học Python","Giáo án Toán","Song ngữ Anh - Việt"].map(x=><span key={x} className="rounded-lg bg-slate-50 px-2.5 py-1.5 text-[10px] font-bold text-slate-500">{x}</span>)}</div>
        </section>
      </div>}

      {(stage==="analyze"||stage==="plan"||stage==="generate") && <section className="mx-auto max-w-4xl rounded-3xl border border-slate-200 bg-white p-6 shadow-sm md:p-8">
        <div className="grid gap-6 md:grid-cols-[1.05fr_.95fr]">
          <div><div className="text-xs font-black uppercase tracking-wider text-indigo-600">AI đang làm việc</div><h2 className="mt-2 text-2xl font-black">{stage==="analyze"?"Đang phân tích tài liệu":stage==="plan"?"Đang xây dựng cấu trúc bài học":"Đang sinh bài giảng hoàn chỉnh"}</h2><p className="mt-2 text-sm leading-6 text-slate-500">Quá trình được thực hiện theo từng bước để giữ nội dung bám sát nguồn và đảm bảo cấu trúc sư phạm.</p>
            <div className="mt-6 space-y-3">{[
              ["Đọc và trích xuất nội dung", stage!=="analyze" || (progress?.progress||0)>20],
              ["Xác định chủ đề chính", stage!=="analyze" || (progress?.progress||0)>45],
              ["Phân tích mục tiêu học tập", stage==="plan"||stage==="generate"||(progress?.progress||0)>65],
              ["Tạo cấu trúc bài học", stage==="plan"||stage==="generate"],
              ["Đề xuất hoạt động & tương tác", stage==="generate"],
            ].map(([label,done])=><div key={String(label)} className="flex items-center gap-3"><span className={"grid h-6 w-6 place-items-center rounded-full text-[10px] font-black " + (done?"bg-emerald-100 text-emerald-700":"bg-slate-100 text-slate-400")}>{done?"✓":"·"}</span><span className="text-sm font-semibold text-slate-600">{label}</span></div>)}</div>
          </div>
          <div className="grid min-h-64 place-items-center rounded-3xl bg-gradient-to-br from-indigo-50 to-violet-50 p-8"><div className="text-center"><div className="mx-auto grid h-24 w-24 place-items-center rounded-[32px] bg-white text-5xl shadow-xl shadow-indigo-100">🤖</div><div className="mt-5 text-sm font-black text-indigo-700">AI đang phân tích...</div><div className="mt-2 text-xs text-slate-400">Thường mất 1–3 phút tùy tài liệu</div></div></div>
        </div>
      </section>}

      {stage==="approve" && <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm md:p-7">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between"><div><div className="text-xs font-black text-indigo-600">TÙY CHỈNH & DUYỆT</div><h2 className="mt-1 text-xl font-black">Kế hoạch sư phạm đã sẵn sàng</h2><p className="mt-1 text-sm text-slate-500">Kiểm tra mục tiêu và cấu trúc trước khi AI sinh slide.</p></div><button disabled={!!busy} onClick={approveAndGenerate} className="rounded-xl bg-indigo-600 px-5 py-3 text-sm font-black text-white">Duyệt & sinh bài giảng →</button></div>
        <div className="mt-6 grid gap-5 lg:grid-cols-[.75fr_1.25fr]">
          <div><h3 className="text-xs font-black uppercase tracking-wider text-slate-400">Yêu cầu cần đạt</h3><div className="mt-3 space-y-2">{objectives.map((o,i)=><div key={i} className="rounded-xl bg-indigo-50/60 p-3 text-sm leading-5"><b className="text-indigo-700">MT{i+1}.</b> {String(o.objective_text||o.text||"")}</div>)}</div></div>
          <div><h3 className="text-xs font-black uppercase tracking-wider text-slate-400">Cấu trúc bài học</h3><div className="mt-3 grid gap-2 md:grid-cols-2">{sections.map((s,i)=><div key={i} className="rounded-xl border border-slate-100 p-3 transition hover:border-indigo-200 hover:bg-indigo-50/30"><div className="text-xs font-black text-indigo-700">{String(s.section_order||i+1)}. {String(s.title||s.section_key||"")}</div><div className="mt-1 line-clamp-2 text-[11px] leading-4 text-slate-500">{String(s.learning_goal||s.purpose||"")}</div></div>)}</div></div>
        </div>
        {plan?.warnings?.length?<div className="mt-4 rounded-xl bg-amber-50 p-3 text-xs text-amber-800">{plan.warnings.join(" · ")}</div>:null}
      </section>}

      {stage==="done" && project && <section className="mx-auto max-w-3xl rounded-3xl border border-emerald-200 bg-white p-8 text-center shadow-sm md:p-12"><div className="mx-auto grid h-20 w-20 place-items-center rounded-full bg-emerald-50 text-4xl">✓</div><h2 className="mt-5 text-2xl font-black">Bài giảng đã sẵn sàng</h2><p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-slate-500">Nội dung, hoạt động học sinh, tương tác, lời giảng, visual prompt và source refs đã được tạo. Tiếp tục sang Editor để tinh chỉnh.</p><button onClick={()=>location.href="/projects/"+project.id+"/editor"} className="mt-6 rounded-xl bg-indigo-600 px-6 py-3 text-sm font-black text-white shadow-lg shadow-indigo-100">Mở trình chỉnh sửa →</button></section>}
    </div>
    <style jsx global>{'.input{width:100%;border:1px solid #e2e8f0;border-radius:.8rem;padding:.7rem .85rem;font-size:.875rem;outline:none;background:white}.input:focus{border-color:#6366f1;box-shadow:0 0 0 3px rgba(99,102,241,.08)}.input:disabled{background:#f8fafc;color:#64748b}'}</style>
  </main>;
}

function Field({label,children}:{label:string;children:React.ReactNode}) { return <label className="block"><span className="mb-1.5 block text-[11px] font-black text-slate-600">{label}</span>{children}</label>; }
\`;

fs.writeFileSync(path.join(root, "frontend/app/projects/new/page.tsx"), newProject);
