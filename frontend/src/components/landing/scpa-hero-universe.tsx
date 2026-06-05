'use client';

import { motion, useReducedMotion } from 'framer-motion';
import { ArrowRight, Brain, Database, Network, Route, Sparkles, Target } from 'lucide-react';
import { LiquidGlassButton } from '@/components/ui/liquid-glass';
import { ModelChip } from '@/components/ui/model-chip';
import { OrbitBackground } from '@/components/ui/orbit-background';

const modelNodes = [
  { label: 'SBERT', x: '12%', y: '30%', icon: Brain },
  { label: 'NCF', x: '76%', y: '24%', icon: Network },
  { label: 'DQN', x: '72%', y: '72%', icon: Route },
  { label: 'Jobs', x: '17%', y: '70%', icon: Database },
];

export function ScpaHeroUniverse() {
  const reduceMotion = useReducedMotion();

  return (
    <section id="home" className="relative isolate min-h-[100svh] overflow-hidden bg-transparent text-white">
      <div className="relative min-h-[100svh] overflow-hidden">
        <OrbitBackground density="low" muted />
        <motion.div
          className="absolute inset-0 z-[1]"
          aria-hidden
        >
          <div className="absolute left-1/2 top-[50%] h-[min(86vw,860px)] w-[min(86vw,860px)] -translate-x-1/2 -translate-y-1/2 rounded-full border border-cyan-200/16 shadow-[inset_0_0_80px_rgba(37,99,235,0.18),0_0_130px_rgba(34,211,238,0.12)]" />
          <div className="absolute left-1/2 top-[50%] h-[min(64vw,620px)] w-[min(64vw,620px)] -translate-x-1/2 -translate-y-1/2 rounded-full border border-dashed border-blue-200/18" />
          <div className="absolute left-1/2 top-[50%] h-[min(38vw,390px)] w-[min(38vw,390px)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-[radial-gradient(circle,rgba(34,211,238,0.22),rgba(37,99,235,0.16)_38%,transparent_70%)] blur-sm" />
        </motion.div>

        <div className="relative z-10 mx-auto flex min-h-[100svh] max-w-[1500px] flex-col justify-center px-5 pb-14 pt-28 md:px-8 md:pt-32">
          <motion.div
            initial={reduceMotion ? false : { opacity: 0, y: 34 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
            className="mx-auto max-w-[1400px] text-center"
          >
            <div className="mb-6 flex flex-wrap justify-center gap-2">
              <ModelChip tone="blue">AI Career Recommendation</ModelChip>
              <ModelChip tone="cyan">SBERT + NCF + DQN</ModelChip>
              <ModelChip tone="green">Indonesia Job Signals</ModelChip>
            </div>

            <h1 className="text-[clamp(2.45rem,8.4vw,8.25rem)] font-black uppercase leading-[0.9] text-white">
              Bukan Job Board Biasa.
              <span className="block text-cyan-100">Career Intelligence.</span>
            </h1>

            <p className="mx-auto mt-7 max-w-3xl text-base leading-relaxed text-slate-300 md:text-xl">
              SCPA membaca profil, skill, lowongan, interaksi, dan sinyal pasar kerja untuk menemukan role yang paling tepat.
            </p>

            <motion.div
              initial={reduceMotion ? false : { opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.35, duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
              className="mx-auto mt-7 grid max-w-3xl grid-cols-2 gap-2 md:grid-cols-4"
            >
              {modelNodes.map((node) => {
                const Icon = node.icon;
                return (
                  <div
                    key={node.label}
                    className="flex items-center justify-center gap-2 rounded-full border border-cyan-200/14 bg-slate-950/46 px-3 py-2 text-xs font-semibold text-cyan-100 shadow-[inset_0_1px_0_rgba(255,255,255,0.08)] backdrop-blur-md"
                  >
                    <Icon className="h-3.5 w-3.5" />
                    {node.label}
                  </div>
                );
              })}
            </motion.div>

            <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <LiquidGlassButton href="/auth?mode=signup" className="min-w-[180px] px-7 py-3.5" icon={<ArrowRight className="h-4 w-4" />}>
                Mulai Gratis
              </LiquidGlassButton>
              <LiquidGlassButton href="#how-it-works" variant="ghost" className="min-w-[180px] px-7 py-3.5">
                Lihat Cara Kerja
              </LiquidGlassButton>
            </div>
          </motion.div>

          <div className="absolute bottom-8 left-5 right-5 z-20 flex items-end justify-between text-xs font-semibold text-slate-400 md:left-8 md:right-8">
            <span className="inline-flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-cyan-200" />
              Career universe entry
            </span>
            <span className="hidden items-center gap-2 md:inline-flex">
              <Target className="h-4 w-4 text-blue-200" />
              Evidence-led recommendation
            </span>
          </div>
        </div>

        <div className="absolute inset-x-0 bottom-0 z-[3] h-56 bg-gradient-to-t from-black/95 via-black/68 to-transparent" aria-hidden />
      </div>
    </section>
  );
}
