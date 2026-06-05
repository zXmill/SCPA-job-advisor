'use client';

import { ArrowRight, CheckCircle2, Database, FileCheck2, Gauge, Network, Route, Send, ShieldCheck, Target } from 'lucide-react';
import {
  CareerScrollMobile,
  CareerScrollUniverse,
  type CareerScene,
} from '@/components/ui/career-scroll-universe';
import { GlassPanel } from '@/components/ui/glass-panel';
import { ModelChip } from '@/components/ui/model-chip';
import { AnimatedMetricBar } from '@/components/ui/animated-metric-bar';

const scenes: CareerScene[] = [
  {
    id: 'matching',
    eyebrow: 'CORE ENGINE',
    title: 'AI Career Matching',
    description:
      'SBERT, NCF, dan DQN membaca profil, skill, dan perilaku sesi untuk menyusun ranking karier yang lebih presisi.',
    chips: ['SBERT', 'NCF', 'DQN'],
    type: 'matching',
  },
  {
    id: 'skill-gap',
    eyebrow: 'GAP INTELLIGENCE',
    title: 'Skill Gap Analysis',
    description: 'SCPA melihat jarak antara skill kamu dan kebutuhan role target, lalu mengubahnya menjadi langkah belajar.',
    chips: ['Skill Signal', 'Course', 'Readiness'],
    type: 'skill-gap',
  },
  {
    id: 'pipeline',
    eyebrow: 'LIVE PIPELINE',
    title: 'Lowongan Masuk, Kualitas Dijaga',
    description: 'Job scraping, quality gate, PostgreSQL, embedding, dan recommendation API bekerja sebagai satu aliran data.',
    chips: ['Scraper', 'PostgreSQL', 'Embedding'],
    type: 'pipeline',
  },
  {
    id: 'roadmap',
    eyebrow: 'CAREER ROADMAP',
    title: '6, 12, 24 Bulan Ke Depan',
    description: 'Rekomendasi tidak berhenti pada apply. SCPA membentuk milestone realistis menuju role target.',
    chips: ['Milestone', 'Portfolio', 'Target Role'],
    type: 'roadmap',
  },
  {
    id: 'salary',
    eyebrow: 'SALARY SIGNAL',
    title: 'Salary Intelligence',
    description: 'Range gaji, benchmark kota, benchmark industri, dan confidence score tampil sebagai konteks keputusan.',
    chips: ['Range', 'City', 'Confidence'],
    type: 'salary',
  },
  {
    id: 'apply',
    eyebrow: 'READY TO APPLY',
    title: '1-Click Apply Dengan Bukti',
    description: 'Profil, kuota, readiness, dan checklist role-specific membuat apply terasa siap, bukan impulsif.',
    chips: ['Profile Fit', 'Quota', 'Checklist'],
    type: 'apply',
  },
  {
    id: 'universe',
    eyebrow: 'CAREER UNIVERSE',
    title: 'Semua Sinyal Bertemu',
    description: 'Model, lowongan, skill, salary, roadmap, dan apply flow mengorbit satu keputusan karier yang bisa dijelaskan.',
    chips: ['Decision Core', 'Explainable', 'Actionable'],
    type: 'universe',
  },
];

export function ScpaScrollNarrative() {
  return (
    <div id="how-it-works">
      <div className="hidden lg:block">
        <CareerScrollUniverse scenes={scenes} renderVisual={renderSceneVisual} />
      </div>
      <CareerScrollMobile scenes={scenes} renderVisual={renderSceneVisual} />
    </div>
  );
}

function renderSceneVisual(scene: CareerScene, index: number, active: boolean) {
  switch (scene.type) {
    case 'matching':
      return <MatchingVisual active={active} />;
    case 'skill-gap':
      return <SkillGapVisual />;
    case 'pipeline':
      return <PipelineVisual />;
    case 'roadmap':
      return <RoadmapVisual />;
    case 'salary':
      return <SalaryVisual />;
    case 'apply':
      return <ApplyVisual />;
    default:
      return <UniverseVisual index={index} />;
  }
}

function MatchingVisual({ active }: { active: boolean }) {
  return (
    <GlassPanel className="p-5 md:p-7" variant="strong">
      <div className="relative min-h-[420px] overflow-hidden rounded-lg border border-white/10 bg-black/42 p-5">
        <div className="absolute left-1/2 top-1/2 h-72 w-72 -translate-x-1/2 -translate-y-1/2 rounded-full border border-cyan-200/20" />
        <div className="scpa-orbit-slow absolute left-1/2 top-1/2 h-96 w-96 -translate-x-1/2 -translate-y-1/2 rounded-full border border-dashed border-blue-200/16" />
        <div className="absolute left-1/2 top-1/2 grid h-36 w-36 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full border border-cyan-200/24 bg-blue-500/14 shadow-[0_0_80px_rgba(37,99,235,0.3)]">
          <div className="text-center">
            <Target className="mx-auto h-8 w-8 text-cyan-100" />
            <p className="mt-2 text-sm font-black uppercase text-white">Profile Core</p>
          </div>
        </div>
        {['SBERT', 'NCF', 'DQN', 'Aggregator'].map((label, nodeIndex) => (
          <div
            key={label}
            className="absolute rounded-full border border-cyan-200/18 bg-slate-950/82 px-4 py-2 text-sm font-bold text-cyan-100"
            style={{
              left: ['8%', '70%', '14%', '68%'][nodeIndex],
              top: ['20%', '18%', '72%', '68%'][nodeIndex],
              transform: active ? 'translateY(0)' : 'translateY(10px)',
            }}
          >
            {label}
          </div>
        ))}
        <div className="absolute bottom-5 left-5 right-5 grid gap-3 md:grid-cols-3">
          <AnimatedMetricBar label="Product Strategy" value={92} />
          <AnimatedMetricBar label="System Design" value={85} />
          <AnimatedMetricBar label="Stakeholder Fit" value={78} />
        </div>
      </div>
    </GlassPanel>
  );
}

function SkillGapVisual() {
  const missing = ['Data storytelling', 'A/B testing', 'Cloud deployment'];
  return (
    <GlassPanel className="p-5 md:p-7" variant="blue">
      <div className="grid gap-4 md:grid-cols-2">
        <GapColumn title="Current Skills" items={['Python', 'React', 'SQL', 'User Research']} />
        <GapColumn title="Required Skills" items={['Python', 'React', 'SQL', 'A/B testing', 'Cloud deployment']} />
      </div>
      <div className="mt-5 rounded-lg border border-cyan-200/16 bg-black/30 p-4">
        <p className="text-sm font-semibold text-cyan-100">Missing skills detected</p>
        <div className="mt-3 flex flex-wrap gap-2">
          {missing.map((skill) => (
            <ModelChip key={skill} tone="cyan">
              {skill}
            </ModelChip>
          ))}
        </div>
        <div className="mt-5 space-y-3">
          <AnimatedMetricBar label="Role readiness" value={73} caption="Readiness naik saat missing skill ditutup." />
          <AnimatedMetricBar label="Learning priority" value={88} caption="SCPA memilih gap yang paling berpengaruh." />
        </div>
      </div>
    </GlassPanel>
  );
}

function GapColumn({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.04] p-4">
      <p className="text-sm font-semibold text-slate-200">{title}</p>
      <div className="mt-4 space-y-2">
        {items.map((item) => (
          <div key={item} className="flex items-center gap-2 text-sm text-slate-300">
            <CheckCircle2 className="h-4 w-4 text-cyan-200" />
            {item}
          </div>
        ))}
      </div>
    </div>
  );
}

function PipelineVisual() {
  const nodes = [
    { label: 'Scraper', icon: Network },
    { label: 'Quality Gate', icon: ShieldCheck },
    { label: 'PostgreSQL', icon: Database },
    { label: 'SBERT Embedding', icon: Gauge },
    { label: 'Ranking API', icon: Route },
    { label: 'User UI', icon: Target },
  ];
  return (
    <GlassPanel className="p-5 md:p-7" variant="strong">
      <div className="grid gap-3 md:grid-cols-3">
        {nodes.map((node, index) => {
          const Icon = node.icon;
          return (
            <div key={node.label} className="relative rounded-lg border border-white/10 bg-white/[0.045] p-4">
              <Icon className="h-6 w-6 text-cyan-100" />
              <p className="mt-5 text-lg font-black uppercase leading-none text-white">{node.label}</p>
              <p className="mt-2 text-xs text-slate-400">Step {index + 1}</p>
              {index < nodes.length - 1 ? <ArrowRight className="absolute -right-4 top-1/2 hidden h-5 w-5 -translate-y-1/2 text-cyan-200 md:block" /> : null}
            </div>
          );
        })}
      </div>
      <div className="mt-5 grid gap-3 md:grid-cols-2">
        <div className="rounded-lg border border-emerald-200/14 bg-emerald-400/8 p-4 text-sm text-emerald-50">
          Accepted: source, title, location, salary signal, and description pass quality checks.
        </div>
        <div className="rounded-lg border border-red-200/14 bg-red-500/8 p-4 text-sm text-red-50">
          Rejected: duplicate, thin description, missing source, or weak role signal.
        </div>
      </div>
    </GlassPanel>
  );
}

function RoadmapVisual() {
  const steps = [
    ['6 bulan', 'Tutup gap prioritas dan bangun portfolio mini.'],
    ['12 bulan', 'Target role menengah dengan fit score lebih tinggi.'],
    ['24 bulan', 'Pindah ke jalur senior atau specialist.'],
  ];
  return (
    <GlassPanel className="p-5 md:p-7" variant="blue">
      <div className="relative space-y-4">
        <div className="absolute bottom-10 left-5 top-10 w-px bg-gradient-to-b from-cyan-200 via-blue-400 to-transparent md:left-1/2" />
        {steps.map(([time, copy], index) => (
          <div key={time} className="relative grid gap-4 md:grid-cols-[1fr_auto_1fr] md:items-center">
            <div className={index % 2 ? 'hidden md:block' : ''} />
            <div className="z-[1] grid h-12 w-12 place-items-center rounded-full border border-cyan-200/24 bg-blue-500/18 text-sm font-bold text-cyan-50 shadow-[0_0_30px_rgba(34,211,238,0.24)]">
              {index + 1}
            </div>
            <div className="rounded-lg border border-white/10 bg-white/[0.045] p-4">
              <p className="text-xl font-black uppercase text-white">{time}</p>
              <p className="mt-2 text-sm leading-relaxed text-slate-300">{copy}</p>
            </div>
          </div>
        ))}
      </div>
    </GlassPanel>
  );
}

function SalaryVisual() {
  return (
    <GlassPanel className="p-5 md:p-7" variant="strong">
      <div className="grid gap-4 md:grid-cols-[1fr_0.9fr]">
        <div className="rounded-lg border border-cyan-200/16 bg-blue-500/10 p-5">
          <p className="text-sm font-semibold text-cyan-100">Estimated range</p>
          <p className="mt-5 text-5xl font-black text-white">Rp 12-18jt</p>
          <p className="mt-3 text-sm text-slate-300">Product Manager, Jakarta, technology sector.</p>
        </div>
        <div className="space-y-4">
          <AnimatedMetricBar label="City benchmark" value={82} />
          <AnimatedMetricBar label="Industry benchmark" value={76} />
          <AnimatedMetricBar label="Confidence" value={88} />
        </div>
      </div>
    </GlassPanel>
  );
}

function ApplyVisual() {
  const items = ['CV signal aligned', 'Skill gap acknowledged', 'Salary range visible', 'Source verified'];
  return (
    <GlassPanel className="p-5 md:p-7" variant="blue">
      <div className="grid gap-4 md:grid-cols-[0.8fr_1.2fr]">
        <div className="rounded-lg border border-cyan-200/16 bg-black/32 p-5">
          <Send className="h-8 w-8 text-cyan-100" />
          <p className="mt-8 text-4xl font-black uppercase leading-none text-white">7 / 10</p>
          <p className="mt-2 text-sm text-slate-300">Apply quota ready this week.</p>
          <AnimatedMetricBar className="mt-5" label="Readiness" value={91} />
        </div>
        <div className="space-y-3">
          {items.map((item) => (
            <div key={item} className="flex items-center justify-between rounded-lg border border-white/10 bg-white/[0.045] p-4">
              <span className="text-sm font-semibold text-slate-100">{item}</span>
              <FileCheck2 className="h-5 w-5 text-cyan-100" />
            </div>
          ))}
        </div>
      </div>
    </GlassPanel>
  );
}

function UniverseVisual({ index }: { index: number }) {
  return (
    <GlassPanel className="p-5 md:p-7" variant="strong">
      <div className="relative min-h-[420px] overflow-hidden rounded-lg border border-white/10 bg-black/42">
        <div className="scpa-orbit-slow absolute left-1/2 top-1/2 h-[420px] w-[420px] -translate-x-1/2 -translate-y-1/2 rounded-full border border-cyan-200/20" />
        <div className="scpa-orbit-reverse absolute left-1/2 top-1/2 h-[310px] w-[310px] -translate-x-1/2 -translate-y-1/2 rounded-full border border-dashed border-blue-200/16" />
        <div className="absolute left-1/2 top-1/2 grid h-40 w-40 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full border border-cyan-200/24 bg-blue-500/16 text-center shadow-[0_0_90px_rgba(37,99,235,0.34)]">
          <div>
            <p className="text-sm font-semibold text-cyan-100">Decision Core</p>
            <p className="mt-2 text-3xl font-black text-white">{index + 1}</p>
          </div>
        </div>
        {['Model', 'Skill', 'Salary', 'Roadmap', 'Apply', 'Jobs'].map((label, itemIndex) => (
          <div
            key={label}
            className="absolute rounded-full border border-white/12 bg-white/[0.055] px-3 py-1 text-xs font-semibold text-slate-100"
            style={{
              left: ['14%', '52%', '78%', '18%', '67%', '43%'][itemIndex],
              top: ['24%', '15%', '42%', '68%', '74%', '84%'][itemIndex],
            }}
          >
            {label}
          </div>
        ))}
      </div>
    </GlassPanel>
  );
}
