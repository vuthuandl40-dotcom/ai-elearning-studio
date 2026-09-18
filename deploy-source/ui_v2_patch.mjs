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
