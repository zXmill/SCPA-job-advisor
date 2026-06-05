// SCPA Design Tokens - Theme-aware via CSS variables.
//
// All color values resolve at runtime to `var(--*)` defined in globals.css.
// This means every component that reads `colors.bg` (etc.) automatically
// switches when ThemeProvider toggles data-theme="light|dark" on <html>.
//
// Brand blues are kept as fixed hex because they read the same across
// themes by design and are also used for glows / SVG fills.

export const colors = {
  // Backgrounds
  bg: 'var(--bg-deep)' as const,
  surface: 'var(--bg-surface)' as const,
  surfaceHover: 'var(--bg-elevated)' as const,
  surfaceActive: 'var(--bg-elevated)' as const,

  // Accent (surgical accent color)
  blue600: '#1d4ed8' as const,
  blue500: 'var(--primary)' as const,
  blue400: 'var(--primary)' as const,
  blue300: 'var(--primary)' as const,
  blue200: 'var(--primary)' as const,

  // Glows (No glows in premium design, map to safe transparent values)
  glowSoft: 'rgba(34,211,238,0.12)' as const,
  glowMed: 'rgba(37,99,235,0.18)' as const,
  glowStrong: 'rgba(37,99,235,0.26)' as const,

  // Borders (hairline border system)
  border: 'var(--glass-border)' as const,
  borderHover: 'var(--glass-border)' as const,
  borderActive: 'var(--primary)' as const,

  // Text
  textPrimary: 'var(--text-primary)' as const,
  textSecondary: 'var(--text-secondary)' as const,
  textMuted: 'var(--text-secondary)' as const,
  textDisabled: 'var(--text-secondary)' as const,

  // Status colors
  success: 'var(--success)' as const,
  warning: 'var(--warning)' as const,
  danger: 'var(--alert)' as const,
  info: 'var(--primary)' as const,
} as const;

export const spacing = {
  pagePadding: 'px-4 md:px-6 lg:px-8' as const,
  maxWidth: 'max-w-screen-xl mx-auto' as const,
  cardPadding: 'p-6' as const,
  sectionGap: 'gap-6' as const,
  majorSectionGap: 'mb-12' as const,
} as const;

export const animation = {
  easeOut: [0.16, 1, 0.3, 1] as const, // Expo out
  pageEntrance: {
    initial: { opacity: 0, y: 12 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.24, ease: [0.16, 1, 0.3, 1] },
  },
  cardHover: {
    duration: 0.24,
    ease: [0.16, 1, 0.3, 1],
  },
  buttonPress: {
    duration: 0.1,
    ease: [0.16, 1, 0.3, 1],
  },
} as const;

export const glassMorphism = {
  background: 'rgba(15, 23, 42, 0.68)',
  border: '1px solid var(--glass-border)',
  backdropFilter: 'blur(18px)',
  borderRadius: '16px',
} as const;

export const glassMorphismHover = {
  background: 'rgba(15, 23, 42, 0.82)',
  border: '1px solid var(--glass-border-strong)',
  backdropFilter: 'blur(18px)',
  borderRadius: '16px',
} as const;

export const glowButton = {
  background: 'linear-gradient(135deg, #2563EB, #22D3EE)',
  boxShadow: '0 18px 44px rgba(37,99,235,0.22)',
  transition: 'all 0.24s cubic-bezier(0.16, 1, 0.3, 1)',
} as const;

export const typography = {
  pageTitle: 'clamp(24px, 3.5vw, 36px)' as const,
  sectionHead: 'text-[20px] md:text-[24px]' as const,
  cardTitle: 'text-[15px] md:text-[16px]' as const,
  body: 'text-[13px] md:text-[14px]' as const,
  labelCaps: 'text-[11px] md:text-[12px]' as const,
} as const;

export const viewport = {
  once: true,
  amount: 0.1,
} as const;

export const textGradient = 'text-text-primary';
