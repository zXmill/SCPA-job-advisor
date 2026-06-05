/**
 * AmbientBackground
 * -----------------
 * 2026 Awwwards-style atmospheric layer (Stripe / Linear / Floema inspired).
 *
 * Renders a fixed-position decorative layer that sits BEHIND all page content
 * and provides:
 *   - Two counter-rotating "aurora orbs" (CSS keyframe-driven, GPU-blurred)
 *   - One slow center orb for added depth
 *   - A subtle film grain (SVG turbulence) overlay
 *   - A cursor-following spotlight, driven by --mx / --my CSS variables
 *     updated through requestAnimationFrame for 60fps smoothness without
 *     thrashing layout.
 *
 * The visual styling lives in app/globals.css under "Ambient Aurora
 * Background" so the layer renders the SAME on SSR as it does after hydration
 * (zero hydration mismatch risk). This component only attaches the optional
 * cursor tracker on the client.
 *
 * Accessibility:
 *   - The whole layer is aria-hidden because it carries no semantic info.
 *   - pointer-events: none everywhere so it never blocks clicks.
 *   - prefers-reduced-motion: the global stylesheet caps animation-duration
 *     at 0.01ms inside @media (prefers-reduced-motion: reduce), which pauses
 *     all four CSS keyframe animations. The cursor tracker also returns
 *     early when the user prefers reduced motion.
 *
 * Performance:
 *   - The cursor handler uses a single rAF-throttled pending mutation.
 *   - On <=640px viewports the cursor spotlight and the third orb are
 *     hidden via the CSS media query in globals.css.
 *   - Animations are transform/opacity only, so they run on the compositor.
 *
 * Usage:
 *   import { AmbientBackground } from "@/components/AmbientBackground";
 *   <main className="relative">
 *     <AmbientBackground />
 *     // ... rest of the page ...
 *   </main>
 */

'use client';

import { useEffect, useRef } from 'react';

export function AmbientBackground() {
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduced) return;

    const isCoarsePointer = window.matchMedia('(pointer: coarse)').matches;
    if (isCoarsePointer) return;

    const root = rootRef.current;
    if (!root) return;

    let pendingX = window.innerWidth / 2;
    let pendingY = window.innerHeight / 2;
    let scheduled = false;
    let raf = 0;

    const flush = () => {
      scheduled = false;
      root.style.setProperty('--mx', `${pendingX}px`);
      root.style.setProperty('--my', `${pendingY}px`);
    };

    const onMove = (event: MouseEvent) => {
      pendingX = event.clientX;
      pendingY = event.clientY;
      if (!scheduled) {
        scheduled = true;
        raf = requestAnimationFrame(flush);
      }
    };

    window.addEventListener('mousemove', onMove, { passive: true });

    return () => {
      window.removeEventListener('mousemove', onMove);
      if (raf) cancelAnimationFrame(raf);
    };
  }, []);

  return (
    <div ref={rootRef} aria-hidden="true" className="ambient-bg">
      <div className="aurora-orb aurora-orb-1" />
      <div className="aurora-orb aurora-orb-2" />
      <div className="aurora-orb aurora-orb-3" />
      <div className="cursor-spotlight" />
      <div className="aurora-grain" />
    </div>
  );
}
