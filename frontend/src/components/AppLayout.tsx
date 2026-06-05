'use client';

import React, { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { Menu, Monitor, Moon, Sun, UserRound, X } from 'lucide-react';
import { LogoLockup } from './ui/Logo';
import { colors } from '@/lib/design-tokens';
import { useAuth } from '@/lib/auth-context';
import { useTheme, type Theme } from '@/lib/theme-context';
import { ShaderUniverseBackground } from '@/components/ui/animated-shader-hero';

interface AppLayoutProps {
  children: React.ReactNode;
  showSidebar?: boolean;
  sidebarContent?: React.ReactNode;
  pageTitle?: string;
}

function initialsFor(name: string | undefined | null): string {
  if (!name) return '?';
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0].charAt(0).toUpperCase();
  return (parts[0].charAt(0) + parts[parts.length - 1].charAt(0)).toUpperCase();
}

export const AppLayout: React.FC<AppLayoutProps> = ({
  children,
  showSidebar = false,
  sidebarContent = null,
}) => {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();
  const { theme, resolvedTheme, setTheme } = useTheme();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const navLinks = [
    { href: '/analytics', label: 'Temukan Kerja' },
    { href: '/dashboard', label: 'Karierku' },
    { href: '/recommendations', label: 'Rekomendasi' },
    { href: '/apply', label: 'Lamaran' },
  ];

  const isActive = (href: string) => pathname === href;

  // Close dropdown on click outside
  useEffect(() => {
    if (!userMenuOpen) return;
    const onClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setUserMenuOpen(false);
      }
    };
    window.addEventListener('mousedown', onClick);
    return () => window.removeEventListener('mousedown', onClick);
  }, [userMenuOpen]);

  // Escape closes menus
  useEffect(() => {
    if (!mobileMenuOpen && !userMenuOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setMobileMenuOpen(false);
        setUserMenuOpen(false);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [mobileMenuOpen, userMenuOpen]);

  const handleLogout = () => {
    setUserMenuOpen(false);
    logout();
    router.push('/auth');
  };

  const userInitials = initialsFor(user?.name);
  const userName = user?.name ?? 'Tamu';
  const userEmail = user?.email ?? '';
  const themeOptions: Array<{ value: Theme; label: string; icon: React.ElementType }> = [
    { value: 'light', label: 'Light', icon: Sun },
    { value: 'dark', label: 'Dark', icon: Moon },
    { value: 'system', label: 'System', icon: Monitor },
  ];

  return (
    <div className="relative isolate min-h-screen overflow-x-clip text-[var(--text-primary)]" style={{ backgroundColor: 'var(--bg-deep)' }}>
        <ShaderUniverseBackground fixed className="z-0" opacity={resolvedTheme === 'light' ? 0.06 : 0.2} intensity={0.86} fps={18} />
        <div aria-hidden className="fixed inset-0 z-0" style={{ background: 'var(--app-background-wash)' }} />
        <div
          aria-hidden
          className="pointer-events-none fixed inset-0 z-0"
          style={{ background: 'var(--app-background-orbs)' }}
        />
        <div aria-hidden className="shader-noise pointer-events-none fixed inset-0 z-0" style={{ opacity: 'var(--app-noise-opacity)' }} />
        {/* Fixed Navigation */}
        <nav
          className="fixed left-0 right-0 top-0 z-50 h-16 px-3 pt-3 md:px-5"
          style={{
            backgroundColor: 'transparent',
          }}
        >
          <div
            className="mx-auto flex h-full max-w-[1500px] items-center justify-between rounded-2xl border px-3 backdrop-blur-xl md:px-5"
            style={{
              backgroundColor: 'var(--app-nav-bg)',
              borderColor: 'var(--app-control-border)',
              boxShadow: 'var(--app-card-shadow)',
            }}
          >
            {/* Logo */}
            <Link href="/dashboard">
              <LogoLockup iconSize={24} variant="compact" />
            </Link>

            {/* Desktop Nav Links */}
            <div className="hidden items-center gap-2 md:flex">
              {navLinks.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className="relative rounded-full border px-3 py-2 text-xs font-semibold transition-colors hover:bg-[var(--app-control-hover-bg)]"
                  style={{
                    backgroundColor: isActive(link.href) ? 'var(--app-nav-active-bg)' : 'transparent',
                    borderColor: isActive(link.href) ? 'var(--app-control-border)' : 'transparent',
                    color: isActive(link.href) ? 'var(--app-nav-active-text)' : 'var(--app-control-muted)',
                  }}
                >
                  {link.label}
                </Link>
              ))}
            </div>

            {/* Right cluster */}
            <div className="flex items-center gap-2 md:gap-3">
              {/* Theme control */}
              <div
                className="theme-segmented-control hidden grid-cols-3 rounded-xl border p-1 sm:grid"
                role="group"
                aria-label={`Theme preference, resolved ${resolvedTheme}`}
                style={{
                  backgroundColor: 'var(--app-control-bg)',
                  borderColor: 'var(--app-control-border)',
                  boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.08)',
                }}
              >
                {themeOptions.map((option) => {
                  const Icon = option.icon;
                  const selected = theme === option.value;
                  return (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => setTheme(option.value)}
                      aria-label={`${option.label} theme`}
                      aria-pressed={selected}
                      title={`${option.label} theme`}
                      className="grid h-8 w-8 place-items-center rounded-lg border transition-colors hover:bg-[var(--app-control-hover-bg)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-200/55"
                      style={{
                        backgroundColor: selected ? 'var(--app-control-selected-bg)' : 'transparent',
                        borderColor: selected ? 'var(--app-control-border)' : 'transparent',
                        color: selected ? 'var(--app-control-selected-text)' : 'var(--app-control-muted)',
                      }}
                    >
                      <Icon className="h-4 w-4" />
                    </button>
                  );
                })}
              </div>

              {/* Mobile menu toggle */}
              <button
                className="grid h-9 w-9 place-items-center rounded-lg border transition-colors hover:bg-[var(--app-control-hover-bg)] md:hidden"
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                aria-label={mobileMenuOpen ? 'Tutup menu' : 'Buka menu'}
                aria-expanded={mobileMenuOpen}
                aria-controls="mobile-nav-menu"
                style={{
                  backgroundColor: 'var(--app-control-bg)',
                  borderColor: 'var(--app-control-border)',
                  color: 'var(--app-control-muted)',
                }}
              >
                {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
              </button>

              {/* Desktop user avatar */}
              <div className="hidden md:block relative" ref={menuRef}>
                <button
                  type="button"
                  onClick={() => setUserMenuOpen((v) => !v)}
                  aria-label="User menu"
                  aria-expanded={userMenuOpen}
                  aria-haspopup="menu"
                  className="flex h-9 w-9 items-center justify-center rounded-lg border text-sm font-bold transition-colors hover:bg-[var(--app-control-hover-bg)]"
                  style={{
                    backgroundColor: 'var(--app-control-selected-bg)',
                    borderColor: 'var(--app-control-border)',
                    color: 'var(--app-control-selected-text)',
                  }}
                >
                  {userInitials}
                </button>
                {userMenuOpen && (
                  <div
                    role="menu"
                className="absolute right-0 top-12 w-64 overflow-hidden rounded-2xl border backdrop-blur-xl"
                    style={{
                      backgroundColor: 'var(--app-menu-bg)',
                      borderColor: 'var(--app-control-border)',
                      boxShadow: 'var(--app-card-shadow)',
                    }}
                  >
                    <div className="p-4" style={{ borderBottom: `1px solid ${colors.border}` }}>
                      <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{userName}</p>
                      {userEmail && <p className="text-xs truncate" style={{ color: 'var(--text-secondary)' }}>{userEmail}</p>}
                    </div>
                    <div className="p-2">
                      <Link
                        href="/profile"
                        role="menuitem"
                        onClick={() => setUserMenuOpen(false)}
                        className="flex items-center gap-3 rounded-lg px-3 py-2 text-xs font-semibold transition-colors hover:bg-[var(--app-control-hover-bg)]"
                        style={{ color: 'var(--text-primary)' }}
                      >
                        <UserRound className="h-4 w-4" />
                        Profil Saya
                      </Link>
                      <button
                        role="menuitem"
                        type="button"
                        onClick={handleLogout}
                        className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-xs font-semibold transition-colors hover:bg-[var(--app-control-hover-bg)]"
                        style={{ color: 'var(--alert)' }}
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0 0 13.5 3h-6a2.25 2.25 0 0 0-2.25 2.25v13.5A2.25 2.25 0 0 0 7.5 21h6a2.25 2.25 0 0 0 2.25-2.25V15M12 9l-3 3m0 0 3 3m-3-3h12.75" />
                        </svg>
                        Keluar
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Mobile Menu Drawer */}
          {mobileMenuOpen && (
            <div
              id="mobile-nav-menu"
              role="region"
              aria-label="Mobile navigation"
                className="absolute right-0 top-16 w-72 rounded-2xl border backdrop-blur-xl md:hidden"
                style={{
                backgroundColor: 'var(--app-menu-bg)',
                borderColor: 'var(--app-control-border)',
                boxShadow: 'var(--app-card-shadow)',
              }}
            >
              <div className="p-4 space-y-2">
                {navLinks.map((link) => (
                  <Link
                    key={link.href}
                    href={link.href}
                    className="block rounded-lg px-4 py-2 text-sm font-semibold transition-colors hover:bg-[var(--app-control-hover-bg)]"
                    style={{
                      backgroundColor: isActive(link.href) ? 'var(--app-nav-active-bg)' : 'transparent',
                      color: isActive(link.href) ? 'var(--app-nav-active-text)' : 'var(--app-control-muted)',
                    }}
                    onClick={() => setMobileMenuOpen(false)}
                  >
                    {link.label}
                  </Link>
                ))}
                <div
                  className="rounded-2xl border p-3 sm:hidden"
                  style={{ backgroundColor: 'var(--app-control-bg)', borderColor: 'var(--app-control-border)' }}
                >
                  <p className="mb-2 text-xs font-semibold uppercase tracking-[0.14em]" style={{ color: 'var(--text-tertiary)' }}>Theme</p>
                  <div className="grid grid-cols-3 gap-2" role="group" aria-label={`Theme preference, resolved ${resolvedTheme}`}>
                    {themeOptions.map((option) => {
                      const Icon = option.icon;
                      const selected = theme === option.value;
                      return (
                        <button
                          key={option.value}
                          type="button"
                          onClick={() => setTheme(option.value)}
                          aria-pressed={selected}
                          className="flex items-center justify-center gap-2 rounded-xl border px-3 py-2 text-xs font-semibold transition-colors hover:bg-[var(--app-control-hover-bg)]"
                          style={{
                            backgroundColor: selected ? 'var(--app-control-selected-bg)' : 'transparent',
                            borderColor: selected ? 'var(--app-control-border)' : 'transparent',
                            color: selected ? 'var(--app-control-selected-text)' : 'var(--app-control-muted)',
                          }}
                        >
                          <Icon className="h-3.5 w-3.5" />
                          {option.label}
                        </button>
                      );
                    })}
                  </div>
                </div>
                <div className="pt-4 mt-2" style={{ borderTop: `1px solid ${colors.border}` }}>
                  <div className="flex items-center gap-3 px-4 py-2">
                    <div
                      className="flex h-9 w-9 items-center justify-center rounded-full border text-xs font-bold shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]"
                      style={{
                        backgroundColor: 'var(--app-control-selected-bg)',
                        borderColor: 'var(--app-control-border)',
                        color: 'var(--app-control-selected-text)',
                      }}
                    >
                      {userInitials}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold truncate" style={{ color: 'var(--text-primary)' }}>{userName}</p>
                      {userEmail && <p className="text-xs truncate" style={{ color: 'var(--text-secondary)' }}>{userEmail}</p>}
                    </div>
                  </div>
                  <Link
                    href="/profile"
                    onClick={() => setMobileMenuOpen(false)}
                    className="block rounded-xl px-4 py-2 text-xs font-semibold uppercase tracking-wider transition-colors"
                    style={{ color: 'var(--text-secondary)' }}
                  >
                    Profil Saya
                  </Link>
                  <button
                    type="button"
                    onClick={handleLogout}
                    className="w-full rounded-xl px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider transition-colors"
                    style={{ color: 'var(--alert)' }}
                  >
                    Keluar
                  </button>
                </div>
              </div>
            </div>
          )}
        </nav>

        {/* Main Content */}
        <div className="relative z-10 pt-20">
          {showSidebar ? (
            <div className="flex">
              <aside
                className="hidden min-h-screen w-56 animate-fade-in lg:block sticky top-20"
                style={{
                  backgroundColor: 'var(--app-sidebar-bg)',
                  borderRight: `1px solid ${colors.border}`,
                }}
              >
                <div className="p-4">{sidebarContent}</div>
              </aside>

              <main className="mx-auto w-full max-w-[1500px] flex-1 animate-fade-in px-4 py-8 md:px-6 lg:px-8">
                {children}
              </main>
            </div>
          ) : (
            <main className="mx-auto max-w-[1500px] animate-fade-in px-4 py-8 md:px-6 lg:px-8">
              {children}
            </main>
          )}
        </div>
    </div>
  );
};
