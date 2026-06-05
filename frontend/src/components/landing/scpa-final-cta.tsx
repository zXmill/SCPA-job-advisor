'use client';

import { ArrowRight, BarChart3, Brain, BriefcaseBusiness, FileCheck2, Route, UserRound } from 'lucide-react';
import { LogoIcon, LogoLockup } from '@/app/_Logo';
import { LiquidGlassButton } from '@/components/ui/liquid-glass';
import { OrbitBackground } from '@/components/ui/orbit-background';
import RadialOrbitalTimeline from '@/components/ui/radial-orbital-timeline';

const finalTimelineData = [
  {
    id: 1,
    title: 'Profile',
    date: 'Signal 01',
    content: 'Profil, skill, target role, lokasi, dan preferensi menjadi pusat gravitasi rekomendasi.',
    category: 'Profile',
    icon: UserRound,
    relatedIds: [2, 3],
    status: 'completed' as const,
    energy: 92,
  },
  {
    id: 2,
    title: 'Model',
    date: 'Signal 02',
    content: 'SBERT, NCF, DQN, dan aggregator menyusun ranking yang bisa dijelaskan.',
    category: 'Model',
    icon: Brain,
    relatedIds: [1, 4, 6],
    status: 'completed' as const,
    energy: 88,
  },
  {
    id: 3,
    title: 'Skills',
    date: 'Signal 03',
    content: 'Skill gap berubah menjadi prioritas belajar dan milestone yang realistis.',
    category: 'Skills',
    icon: Route,
    relatedIds: [1, 5],
    status: 'in-progress' as const,
    energy: 76,
  },
  {
    id: 4,
    title: 'Jobs',
    date: 'Signal 04',
    content: 'Lowongan aktif melewati quality gate sebelum masuk ke ranking dan UI.',
    category: 'Jobs',
    icon: BriefcaseBusiness,
    relatedIds: [2, 6],
    status: 'completed' as const,
    energy: 84,
  },
  {
    id: 5,
    title: 'Salary',
    date: 'Signal 05',
    content: 'Benchmark kota, industri, range, dan confidence score memberi konteks keputusan.',
    category: 'Salary',
    icon: BarChart3,
    relatedIds: [3, 6],
    status: 'pending' as const,
    energy: 68,
  },
  {
    id: 6,
    title: 'Apply',
    date: 'Signal 06',
    content: 'Readiness, quota, dan checklist role-specific menutup alur menuju apply.',
    category: 'Apply',
    icon: FileCheck2,
    relatedIds: [2, 4, 5],
    status: 'in-progress' as const,
    energy: 81,
  },
];

export function ScpaFinalCTA() {
  return (
    <section className="relative isolate min-h-[90vh] overflow-hidden bg-transparent px-5 py-24 text-white md:px-8 md:py-36">
      <OrbitBackground density="low" />
      <div className="relative z-10 mx-auto grid min-h-[62vh] max-w-[1500px] gap-10 lg:grid-cols-[1fr_0.86fr] lg:items-center">
        <div>
          <LogoIcon size={66} variant="light" glow />
          <h2 className="mt-8 max-w-5xl text-[clamp(2.8rem,7vw,7rem)] font-black uppercase leading-[0.88] text-white">
            Masuk ke Career Universe-mu.
          </h2>
          <p className="mt-6 max-w-2xl text-base leading-relaxed text-slate-300 md:text-lg">
            Bangun profil, lihat alasan rekomendasi, tutup gap skill, dan apply ke role yang benar-benar punya bukti kecocokan.
          </p>
          <div className="mt-9 flex flex-col gap-3 sm:flex-row">
            <LiquidGlassButton href="/auth?mode=signup" className="px-8 py-3.5" icon={<ArrowRight className="h-4 w-4" />}>
              Mulai Gratis
            </LiquidGlassButton>
            <LiquidGlassButton href="/recommendations" variant="ghost" className="px-8 py-3.5">
              Lihat Rekomendasi
            </LiquidGlassButton>
          </div>
        </div>

        <RadialOrbitalTimeline
          timelineData={finalTimelineData}
          radius={170}
          className="border border-cyan-200/16 bg-slate-950/60 shadow-[0_30px_110px_rgba(37,99,235,0.18)]"
        />
      </div>
    </section>
  );
}

export function ScpaFooter() {
  const links = [
    { href: '#how-it-works', label: 'Cara Kerja' },
    { href: '#model-engine', label: 'Model' },
    { href: '#capabilities', label: 'Fitur' },
    { href: '/analytics', label: 'Lowongan' },
    { href: '/recommendations', label: 'Rekomendasi' },
  ];

  return (
    <footer className="border-t border-white/10 bg-black/72 px-5 py-10 text-white md:px-8">
      <div className="mx-auto flex max-w-[1500px] flex-col gap-8 md:flex-row md:items-end md:justify-between">
        <div>
          <LogoLockup iconSize={30} variant="light" glow />
          <p className="mt-4 max-w-md text-sm leading-relaxed text-slate-400">
            SCPA, Smart Career Pathway Assistant untuk rekomendasi karier berbasis bukti di Indonesia.
          </p>
        </div>
        <nav className="flex flex-wrap gap-4 text-sm font-semibold text-slate-300" aria-label="Footer navigation">
          {links.map((link) => (
            <a key={link.href} href={link.href} className="transition-colors duration-300 hover:text-cyan-100">
              {link.label}
            </a>
          ))}
        </nav>
      </div>
    </footer>
  );
}
