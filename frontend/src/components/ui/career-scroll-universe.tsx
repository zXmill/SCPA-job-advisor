'use client';

import { useRef, useState, type ReactNode } from 'react';
import {
  motion,
  useMotionValueEvent,
  useReducedMotion,
  useScroll,
  useTransform,
  type MotionValue,
} from 'framer-motion';
import { cn } from '@/lib/utils';
import { GlassPanel } from './glass-panel';
import { ModelChip } from './model-chip';
import { OrbitBackground } from './orbit-background';

export interface CareerScene {
  id: string;
  eyebrow: string;
  title: string;
  description: string;
  chips: string[];
  type: string;
}

interface CareerScrollUniverseProps {
  scenes: CareerScene[];
  renderVisual: (scene: CareerScene, index: number, active: boolean) => ReactNode;
  className?: string;
}

const scenePresets = [
  {
    layout: 'split',
    grid: 'lg:grid-cols-[0.78fr_1.22fr]',
    copy: 'lg:order-1',
    visual: 'lg:order-2 lg:origin-center',
    copyX: [-120, 0, -78],
    copyY: [70, 0, -96],
    visualX: [150, 0, 92],
    visualY: [110, 0, -90],
    visualScale: [0.82, 1, 0.88],
    visualRotate: [-5, 0, 5],
    glow: 'from-blue-500/30 via-cyan-300/10 to-transparent',
  },
  {
    layout: 'reverse',
    grid: 'lg:grid-cols-[1.16fr_0.84fr]',
    copy: 'lg:order-2',
    visual: 'lg:order-1 lg:origin-right',
    copyX: [115, 0, 70],
    copyY: [80, 0, -110],
    visualX: [-155, 0, -82],
    visualY: [130, 0, -75],
    visualScale: [0.86, 1, 0.9],
    visualRotate: [4, 0, -4],
    glow: 'from-cyan-300/26 via-blue-500/12 to-transparent',
  },
  {
    layout: 'wide',
    grid: 'lg:grid-cols-1',
    copy: 'mx-auto max-w-5xl text-center',
    visual: 'mx-auto w-full max-w-[1180px]',
    copyX: [0, 0, 0],
    copyY: [105, 0, -95],
    visualX: [0, 0, 0],
    visualY: [185, 0, -120],
    visualScale: [0.78, 1, 0.88],
    visualRotate: [-2, 0, 2],
    glow: 'from-sky-400/22 via-blue-700/16 to-transparent',
  },
  {
    layout: 'split',
    grid: 'lg:grid-cols-[0.92fr_1.08fr]',
    copy: 'lg:order-1',
    visual: 'lg:order-2 lg:-translate-y-4',
    copyX: [-92, 0, -110],
    copyY: [130, 0, -60],
    visualX: [130, 0, 120],
    visualY: [40, 0, -150],
    visualScale: [0.9, 1, 0.86],
    visualRotate: [6, 0, -6],
    glow: 'from-blue-400/22 via-cyan-500/10 to-transparent',
  },
  {
    layout: 'reverse',
    grid: 'lg:grid-cols-[1fr_0.9fr]',
    copy: 'lg:order-2',
    visual: 'lg:order-1 lg:origin-bottom',
    copyX: [125, 0, 95],
    copyY: [85, 0, -85],
    visualX: [-110, 0, -135],
    visualY: [95, 0, -95],
    visualScale: [0.84, 1, 0.9],
    visualRotate: [-6, 0, 4],
    glow: 'from-cyan-200/20 via-blue-500/18 to-transparent',
  },
  {
    layout: 'feature',
    grid: 'lg:grid-cols-[0.72fr_1.28fr]',
    copy: 'lg:order-1',
    visual: 'lg:order-2 lg:origin-left',
    copyX: [-140, 0, -80],
    copyY: [60, 0, -140],
    visualX: [170, 0, 80],
    visualY: [130, 0, -70],
    visualScale: [0.82, 1, 0.92],
    visualRotate: [3, 0, -5],
    glow: 'from-blue-600/24 via-cyan-300/12 to-transparent',
  },
  {
    layout: 'center',
    grid: 'lg:grid-cols-1',
    copy: 'mx-auto max-w-5xl text-center',
    visual: 'mx-auto w-full max-w-[980px]',
    copyX: [0, 0, 0],
    copyY: [120, 0, -75],
    visualX: [0, 0, 0],
    visualY: [165, 0, -110],
    visualScale: [0.76, 1, 1.04],
    visualRotate: [0, 0, 0],
    glow: 'from-cyan-300/28 via-blue-500/16 to-transparent',
  },
];

export function CareerScrollUniverse({ scenes, renderVisual, className }: CareerScrollUniverseProps) {
  const sectionRef = useRef<HTMLElement>(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const activeIndexRef = useRef(0);
  const { scrollYProgress } = useScroll({
    target: sectionRef,
    offset: ['start start', 'end end'],
  });

  useMotionValueEvent(scrollYProgress, 'change', (latest) => {
    const nextIndex = Math.min(scenes.length - 1, Math.max(0, Math.floor(latest * scenes.length)));
    if (activeIndexRef.current !== nextIndex) {
      activeIndexRef.current = nextIndex;
      setActiveIndex(nextIndex);
    }
  });

  const activeScene = scenes[activeIndex] || scenes[0];

  return (
    <section
      ref={sectionRef}
      className={cn('relative isolate bg-transparent text-white', className)}
      style={{ height: `${scenes.length * 118}vh` }}
      aria-label="SCPA scroll-based career intelligence narrative"
    >
      <div className="sticky top-0 h-screen overflow-hidden">
        <div
          aria-hidden
          className="absolute inset-0 bg-[radial-gradient(circle_at_18%_16%,rgba(37,99,235,0.16),transparent_34%),radial-gradient(circle_at_78%_40%,rgba(34,211,238,0.1),transparent_30%)]"
        />
        <OrbitBackground muted density="low" className="opacity-55" />
        <div className="absolute inset-x-0 top-0 z-[1] h-32 bg-gradient-to-b from-black via-black/72 to-transparent" />
        <div className="absolute inset-x-0 bottom-0 z-[1] h-32 bg-gradient-to-t from-black via-black/72 to-transparent" />

        <div className="absolute left-4 top-1/2 z-20 hidden -translate-y-1/2 flex-col gap-3 xl:flex">
          {scenes.map((scene, index) => (
            <button
              key={scene.id}
              type="button"
              className={cn(
                'h-9 w-1 rounded-full transition-all duration-500',
                activeIndex === index ? 'bg-cyan-200 shadow-[0_0_22px_rgba(34,211,238,0.75)]' : 'bg-white/16',
              )}
              aria-label={`Scene ${index + 1}: ${scene.title}`}
            />
          ))}
        </div>

        {activeScene && (
          <SceneFrame
            key={activeScene.id}
            scene={activeScene}
            index={activeIndex}
            total={scenes.length}
            active
            progress={scrollYProgress}
            visual={renderVisual(activeScene, activeIndex, true)}
          />
        )}
      </div>
    </section>
  );
}

function SceneFrame({
  scene,
  index,
  total,
  active,
  progress,
  visual,
}: {
  scene: CareerScene;
  index: number;
  total: number;
  active: boolean;
  progress: MotionValue<number>;
  visual: ReactNode;
}) {
  const reduceMotion = useReducedMotion();
  const segment = 1 / total;
  const start = index * segment;
  const mid = start + segment * 0.5;
  const end = start + segment;
  const preset = scenePresets[index % scenePresets.length];

  const rawOpacity = useTransform(progress, [start, start + segment * 0.18, end - segment * 0.18, end], [index === 0 ? 1 : 0, 1, 1, index === total - 1 ? 1 : 0]);
  const opacity = useTransform(rawOpacity, (value) => (value < 0.14 ? 0 : value));
  const y = useTransform(progress, [start, mid, end], [90, 0, -80]);
  const scale = useTransform(progress, [start, mid, end], [0.92, 1, 0.94]);
  const rotateX = useTransform(progress, [start, mid, end], [5, 0, -4]);
  const rotateZ = useTransform(progress, [start, mid, end], [-1.8, 0, 1.2]);
  const copyX = useTransform(progress, [start, mid, end], preset.copyX);
  const copyY = useTransform(progress, [start, mid, end], preset.copyY);
  const visualX = useTransform(progress, [start, mid, end], preset.visualX);
  const visualY = useTransform(progress, [start, mid, end], preset.visualY);
  const visualScale = useTransform(progress, [start, mid, end], preset.visualScale);
  const visualRotate = useTransform(progress, [start, mid, end], preset.visualRotate);

  return (
    <motion.div
      className="absolute inset-0 z-10 grid place-items-center px-5 pt-24 md:px-8"
      style={
        reduceMotion
          ? { opacity: active ? 1 : 0, pointerEvents: active ? 'auto' : 'none' }
          : { opacity, y, scale, rotateX, rotateZ, transformPerspective: 1200, pointerEvents: active ? 'auto' : 'none' }
      }
    >
      <div
        aria-hidden
        className={cn('absolute h-[420px] w-[420px] rounded-full bg-gradient-radial opacity-45 blur-2xl', preset.glow)}
      />

      <div className={cn('grid w-full max-w-[1500px] gap-8 lg:items-center', preset.grid)}>
        <motion.div
          className={cn('scene-copy', preset.copy)}
          style={
            reduceMotion
              ? undefined
              : {
                  x: copyX,
                  y: copyY,
                }
          }
        >
          <p className="mb-4 text-sm font-semibold uppercase text-cyan-200">{scene.eyebrow}</p>
          <h2 className="max-w-3xl text-[clamp(2.35rem,5.8vw,5.9rem)] font-black uppercase leading-[0.92] text-white">
            {scene.title}
          </h2>
          <p className={cn('mt-6 max-w-xl text-base leading-relaxed text-slate-300 md:text-lg', preset.layout === 'wide' || preset.layout === 'center' ? 'mx-auto' : '')}>
            {scene.description}
          </p>
          <div className={cn('mt-7 flex flex-wrap gap-2', preset.layout === 'wide' || preset.layout === 'center' ? 'justify-center' : '')}>
            {scene.chips.map((chip) => (
              <ModelChip key={chip} tone="cyan">
                {chip}
              </ModelChip>
            ))}
          </div>
        </motion.div>
        <motion.div
          className={cn('scene-visual', preset.visual)}
          style={
            reduceMotion
              ? undefined
              : {
                  x: visualX,
                  y: visualY,
                  scale: visualScale,
                  rotateZ: visualRotate,
                  transformPerspective: 1200,
                }
          }
        >
          {visual}
        </motion.div>
      </div>
    </motion.div>
  );
}

export function CareerScrollMobile({ scenes, renderVisual }: CareerScrollUniverseProps) {
  return (
    <section className="bg-transparent px-5 py-20 text-white md:px-8 lg:hidden" aria-label="SCPA career intelligence narrative">
      <div className="mx-auto max-w-3xl space-y-6">
        {scenes.map((scene, index) => (
          <motion.article
            key={scene.id}
            initial={{ opacity: 0, y: 28 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.24 }}
            transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
          >
            <GlassPanel className="p-4" variant="strong">
              <p className="text-xs font-semibold uppercase text-cyan-200">{scene.eyebrow}</p>
              <h3 className="mt-3 text-3xl font-black uppercase leading-none text-white">{scene.title}</h3>
              <p className="mt-4 text-sm leading-relaxed text-slate-300">{scene.description}</p>
              <div className="mt-4 flex flex-wrap gap-2">
                {scene.chips.map((chip) => (
                  <ModelChip key={chip} tone="cyan">
                    {chip}
                  </ModelChip>
                ))}
              </div>
              <div className="mt-5">{renderVisual(scene, index, false)}</div>
            </GlassPanel>
          </motion.article>
        ))}
      </div>
    </section>
  );
}
