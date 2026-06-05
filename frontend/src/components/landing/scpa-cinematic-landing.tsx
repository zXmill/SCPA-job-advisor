'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Menu, X } from 'lucide-react';
import { AnimatePresence, motion } from 'framer-motion';
import { LogoLockup } from '@/app/_Logo';
import { LiquidGlassButton, LiquidGlassFilter } from '@/components/ui/liquid-glass';
import { ScpaHeroUniverse } from './scpa-hero-universe';
import { ScpaScrollNarrative } from './scpa-scroll-narrative';
import { ScpaModelEngine } from './scpa-model-engine';
import { ScpaCareerGallery } from './scpa-career-gallery';
import { ScpaFinalCTA, ScpaFooter } from './scpa-final-cta';

const navLinks = [
  { href: '#how-it-works', label: 'Cara Kerja' },
  { href: '#model-engine', label: 'Model' },
  { href: '#capabilities', label: 'Fitur' },
  { href: '/analytics', label: 'Lowongan' },
];

export function ScpaCinematicLanding() {
  return (
    <main className="scpa-cinematic relative isolate min-h-screen overflow-x-clip bg-black text-white">
      <LiquidGlassFilter />
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 z-0 bg-[radial-gradient(circle_at_48%_10%,rgba(37,99,235,0.24),transparent_34%),radial-gradient(circle_at_82%_28%,rgba(34,211,238,0.12),transparent_28%),linear-gradient(180deg,#020617_0%,#000_72%)]"
      />
      <div aria-hidden className="pointer-events-none fixed inset-0 z-0 bg-black/42" />
      <ScpaNavbar />
      <div className="relative z-10">
        <ScpaHeroUniverse />
        <ScpaScrollNarrative />
        <ScpaModelEngine />
        <ScpaCareerGallery />
        <ScpaFinalCTA />
        <ScpaFooter />
      </div>
      <LandingStyles />
    </main>
  );
}

function ScpaNavbar() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open]);

  return (
    <header className="fixed inset-x-0 top-0 z-50 px-4 pt-4 md:px-8 md:pt-6">
      <div className="scpa-nav-glass mx-auto flex h-16 max-w-[1500px] items-center justify-between rounded-lg px-4 md:px-5">
        <Link href="/" aria-label="SCPA home" className="shrink-0">
          <LogoLockup iconSize={30} variant="light" glow />
        </Link>

        <nav className="hidden items-center gap-6 text-sm font-semibold text-slate-300 md:flex" aria-label="Landing navigation">
          {navLinks.map((link) =>
            link.href.startsWith('/') ? (
              <Link key={link.href} href={link.href} className="transition-colors duration-300 hover:text-cyan-100">
                {link.label}
              </Link>
            ) : (
              <a key={link.href} href={link.href} className="transition-colors duration-300 hover:text-cyan-100">
                {link.label}
              </a>
            ),
          )}
        </nav>

        <div className="hidden items-center gap-3 md:flex">
          <Link href="/auth" className="text-sm font-semibold text-slate-300 transition-colors duration-300 hover:text-white">
            Masuk
          </Link>
          <LiquidGlassButton href="/auth?mode=signup" className="px-5 py-2.5">
            Mulai Gratis
          </LiquidGlassButton>
        </div>

        <button
          type="button"
          className="grid h-10 w-10 place-items-center rounded-lg border border-white/12 bg-white/[0.055] text-white md:hidden"
          aria-label={open ? 'Tutup menu' : 'Buka menu'}
          aria-expanded={open}
          onClick={() => setOpen((value) => !value)}
        >
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      <AnimatePresence>
        {open ? (
          <motion.div
            initial={{ opacity: 0, y: -12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
            className="scpa-nav-glass mx-auto mt-3 max-w-[1500px] rounded-lg p-4 md:hidden"
          >
            <nav className="flex flex-col gap-3 text-xl font-black uppercase text-white" aria-label="Mobile landing navigation">
              {navLinks.map((link) =>
                link.href.startsWith('/') ? (
                  <Link key={link.href} href={link.href} onClick={() => setOpen(false)}>
                    {link.label}
                  </Link>
                ) : (
                  <a key={link.href} href={link.href} onClick={() => setOpen(false)}>
                    {link.label}
                  </a>
                ),
              )}
              <LiquidGlassButton href="/auth?mode=signup" className="mt-2 w-full py-3">
                Mulai Gratis
              </LiquidGlassButton>
            </nav>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </header>
  );
}

function LandingStyles() {
  const css = `
.scpa-cinematic {
  font-family: var(--font-jakarta), var(--font-inter), system-ui, sans-serif;
  color-scheme: dark;
}

.scpa-cinematic h1,
.scpa-cinematic h2,
.scpa-cinematic h3 {
  letter-spacing: 0;
}

.scpa-nav-glass {
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(2, 6, 23, 0.72);
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.09), 0 24px 80px rgba(0,0,0,0.34);
  backdrop-filter: blur(10px) saturate(1.05);
  -webkit-backdrop-filter: blur(10px) saturate(1.05);
}

.scpa-noise {
  opacity: 0.055;
  mix-blend-mode: overlay;
  background-image: url("data:image/svg+xml;utf8,%3Csvg viewBox='0 0 180 180' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.56'/%3E%3C/svg%3E");
  background-size: 220px 220px;
}

.scpa-orbit-slow {
  animation: scpa-orbit 38s linear infinite;
}

.scpa-orbit-reverse {
  animation: scpa-orbit-reverse 52s linear infinite;
}

@keyframes scpa-orbit {
  from { transform: translate(-50%, -50%) rotate(0deg); }
  to { transform: translate(-50%, -50%) rotate(360deg); }
}

@keyframes scpa-orbit-reverse {
  from { transform: translate(-50%, -50%) rotate(0deg); }
  to { transform: translate(-50%, -50%) rotate(-360deg); }
}

@media (prefers-reduced-motion: reduce) {
  .scpa-orbit-slow,
  .scpa-orbit-reverse {
    animation: none !important;
  }
}
`;

  return <style dangerouslySetInnerHTML={{ __html: css }} />;
}
