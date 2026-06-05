'use client';

import { motion, useReducedMotion } from 'framer-motion';
import { BarChart3, Brain, Database, FileCheck2, Map, Route } from 'lucide-react';
import { GlassPanel } from '@/components/ui/glass-panel';
import { ModelChip } from '@/components/ui/model-chip';

const capabilities = [
  {
    title: 'AI Career Matching',
    copy: 'Ranking role yang memadukan semantic fit, interaction signal, dan readiness.',
    icon: Brain,
    code: '01',
    className: 'md:col-span-4 md:min-h-[360px]',
  },
  {
    title: 'Skill Gap Analysis',
    copy: 'Jarak skill saat ini dan skill role target ditampilkan sebagai prioritas belajar.',
    icon: Route,
    code: '02',
    className: 'md:col-span-2 md:min-h-[300px]',
  },
  {
    title: 'Salary Intelligence',
    copy: 'Benchmark kota, industri, dan confidence score membantu keputusan apply.',
    icon: BarChart3,
    code: '03',
    className: 'md:col-span-3 md:min-h-[320px]',
  },
  {
    title: 'Career Roadmap',
    copy: 'Milestone 6, 12, dan 24 bulan membuat rekomendasi terasa seperti rute.',
    icon: Map,
    code: '04',
    className: 'md:col-span-3 md:min-h-[320px]',
  },
  {
    title: 'Live Job Pipeline',
    copy: 'Scraper, quality gate, PostgreSQL, embedding, ranking, dan UI berjalan sebagai satu aliran.',
    icon: Database,
    code: '05',
    className: 'md:col-span-2 md:min-h-[300px]',
  },
  {
    title: '1-Click Apply',
    copy: 'Checklist readiness menjaga apply tetap jelas, siap, dan berbasis bukti.',
    icon: FileCheck2,
    code: '06',
    className: 'md:col-span-4 md:min-h-[360px]',
  },
];

export function ScpaCareerGallery() {
  const reduceMotion = useReducedMotion();

  return (
    <section id="capabilities" className="relative isolate overflow-hidden bg-transparent px-5 py-24 text-white md:px-8 md:py-36">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_12%,rgba(34,211,238,0.12),transparent_26%),radial-gradient(circle_at_80%_42%,rgba(37,99,235,0.16),transparent_30%)]" />
      <div className="relative z-10 mx-auto max-w-[1500px]">
        <div className="mb-14 max-w-5xl">
          <p className="text-sm font-semibold uppercase text-cyan-200">Product Capability Gallery</p>
          <h2 className="mt-4 text-[clamp(2.4rem,6vw,6rem)] font-black uppercase leading-[0.9] text-white">
            Bukan galeri lowongan. Galeri sinyal keputusan.
          </h2>
          <p className="mt-6 max-w-2xl text-base leading-relaxed text-slate-300 md:text-lg">
            Referensi visualnya galeri sinematik, tetapi kontennya sepenuhnya SCPA: model, skill, salary, roadmap, pipeline, dan apply readiness.
          </p>
        </div>

        <div className="grid gap-5 md:grid-cols-6">
          {capabilities.map((capability, index) => {
            const Icon = capability.icon;
            return (
              <motion.article
                key={capability.title}
                initial={reduceMotion ? false : { opacity: 0, y: 34, scale: 0.97 }}
                whileInView={{ opacity: 1, y: 0, scale: 1 }}
                viewport={{ once: true, amount: 0.22 }}
                transition={{ duration: 0.64, delay: index * 0.045, ease: [0.22, 1, 0.36, 1] }}
                className={capability.className}
              >
                <GlassPanel className="group h-full p-5 transition-transform duration-700 hover:-translate-y-1" variant={index % 2 ? 'blue' : 'strong'}>
                  <div className="flex h-full min-h-[260px] flex-col justify-between">
                    <div className="flex items-start justify-between gap-4">
                      <ModelChip tone="cyan">[{capability.code}]</ModelChip>
                      <div className="grid h-12 w-12 place-items-center rounded-lg border border-cyan-200/16 bg-cyan-400/10 transition-transform duration-700 group-hover:rotate-6">
                        <Icon className="h-6 w-6 text-cyan-100" />
                      </div>
                    </div>

                    <div className="my-10">
                      <CapabilityVisual index={index} />
                    </div>

                    <div>
                      <h3 className="text-3xl font-black uppercase leading-none text-white md:text-4xl">{capability.title}</h3>
                      <p className="mt-4 max-w-md text-sm leading-relaxed text-slate-300 md:text-base">{capability.copy}</p>
                    </div>
                  </div>
                </GlassPanel>
              </motion.article>
            );
          })}
        </div>
      </div>
    </section>
  );
}

function CapabilityVisual({ index }: { index: number }) {
  return (
    <div className="relative h-32 overflow-hidden rounded-lg border border-white/10 bg-black/32">
      <div className="absolute left-1/2 top-1/2 h-40 w-40 -translate-x-1/2 -translate-y-1/2 rounded-full border border-cyan-200/16" />
      <div className="scpa-orbit-slow absolute left-1/2 top-1/2 h-28 w-28 -translate-x-1/2 -translate-y-1/2 rounded-full border border-dashed border-blue-200/16" />
      {Array.from({ length: 5 }, (_, itemIndex) => (
        <span
          key={itemIndex}
          className="absolute h-2 w-2 rounded-full bg-cyan-200 shadow-[0_0_18px_rgba(34,211,238,0.65)]"
          style={{
            left: `${16 + ((itemIndex * 17 + index * 11) % 68)}%`,
            top: `${20 + ((itemIndex * 23 + index * 9) % 56)}%`,
          }}
        />
      ))}
      <div className="absolute inset-x-6 bottom-5 h-px bg-gradient-to-r from-transparent via-cyan-200/70 to-transparent" />
    </div>
  );
}
