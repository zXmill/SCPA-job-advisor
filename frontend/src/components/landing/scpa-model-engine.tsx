'use client';

import { motion, useReducedMotion } from 'framer-motion';
import { Brain, Gauge, GitMerge, Network, Route } from 'lucide-react';
import { AnimatedMetricBar } from '@/components/ui/animated-metric-bar';
import { GlassPanel } from '@/components/ui/glass-panel';
import { ModelChip } from '@/components/ui/model-chip';

const engineNodes = [
  {
    title: 'SBERT',
    subtitle: 'Semantic matching',
    copy: 'Membandingkan makna profil, skill, dan deskripsi pekerjaan.',
    icon: Brain,
    tone: 'cyan' as const,
  },
  {
    title: 'NCF',
    subtitle: 'Collaborative fit',
    copy: 'Membaca pola simpan, klik, dan apply untuk memperkaya rekomendasi.',
    icon: Network,
    tone: 'blue' as const,
  },
  {
    title: 'DQN',
    subtitle: 'Session reranking',
    copy: 'Menyesuaikan ranking berdasarkan aksi dan konteks sesi pengguna.',
    icon: Route,
    tone: 'green' as const,
  },
  {
    title: 'Aggregator',
    subtitle: 'Final ranking',
    copy: 'Menggabungkan model score, recency, lokasi, kualitas data, dan salary signal.',
    icon: GitMerge,
    tone: 'slate' as const,
  },
];

export function ScpaModelEngine() {
  const reduceMotion = useReducedMotion();

  return (
    <section id="model-engine" className="relative isolate overflow-hidden bg-transparent px-5 py-24 text-white md:px-8 md:py-36">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_10%,rgba(37,99,235,0.18),transparent_32%),linear-gradient(180deg,rgba(0,0,0,0.86),rgba(2,6,23,0.58)_48%,rgba(0,0,0,0.82))]" />
      <div className="relative z-10 mx-auto max-w-[1500px]">
        <div className="grid gap-12 lg:grid-cols-[0.78fr_1.22fr] lg:items-center">
          <div>
            <p className="text-sm font-semibold uppercase text-cyan-200">Model Architecture</p>
            <h2 className="mt-4 text-[clamp(2.4rem,6vw,6rem)] font-black uppercase leading-[0.9] text-white">
              Empat mesin, satu ranking karier.
            </h2>
            <p className="mt-6 max-w-xl text-base leading-relaxed text-slate-300 md:text-lg">
              Bagian ini menjelaskan cara SCPA menyusun rekomendasi tanpa membuat panggilan backend palsu. Data di sini adalah visual statis untuk memahami alur sistem.
            </p>
            <div className="mt-7 flex flex-wrap gap-2">
              <ModelChip tone="cyan">Explainable ranking</ModelChip>
              <ModelChip tone="blue">No fake API call</ModelChip>
              <ModelChip tone="green">Model-aware UI</ModelChip>
            </div>
          </div>

          <GlassPanel className="p-4 md:p-6" variant="strong">
            <div className="relative grid gap-4 md:grid-cols-2">
              {engineNodes.map((node, index) => {
                const Icon = node.icon;
                return (
                  <motion.article
                    key={node.title}
                    initial={reduceMotion ? false : { opacity: 0, y: 28 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, amount: 0.32 }}
                    transition={{ duration: 0.58, delay: index * 0.07, ease: [0.22, 1, 0.36, 1] }}
                    className="rounded-lg border border-white/10 bg-white/[0.045] p-5"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <ModelChip tone={node.tone}>{node.subtitle}</ModelChip>
                        <h3 className="mt-5 text-3xl font-black uppercase leading-none text-white">{node.title}</h3>
                      </div>
                      <div className="grid h-12 w-12 place-items-center rounded-lg border border-cyan-200/16 bg-cyan-400/10">
                        <Icon className="h-6 w-6 text-cyan-100" />
                      </div>
                    </div>
                    <p className="mt-5 text-sm leading-relaxed text-slate-300">{node.copy}</p>
                  </motion.article>
                );
              })}
            </div>

            <div className="mt-5 rounded-lg border border-cyan-200/16 bg-black/32 p-5">
              <div className="mb-5 flex items-center gap-3">
                <Gauge className="h-5 w-5 text-cyan-100" />
                <p className="text-sm font-semibold text-cyan-100">Example ranking blend</p>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <AnimatedMetricBar label="Semantic fit" value={91} />
                <AnimatedMetricBar label="Interaction fit" value={84} />
                <AnimatedMetricBar label="Career signal" value={79} />
                <AnimatedMetricBar label="Freshness and quality" value={88} />
              </div>
            </div>
          </GlassPanel>
        </div>
      </div>
    </section>
  );
}
