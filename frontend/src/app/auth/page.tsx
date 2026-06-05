'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { AnimatePresence, motion } from 'framer-motion';
import {
  ArrowRight,
  Brain,
  CheckCircle2,
  Eye,
  EyeOff,
  LockKeyhole,
  Mail,
  Network,
  Route,
  ShieldCheck,
  Sparkles,
  Target,
  UserRound,
} from 'lucide-react';
import { useAuth } from '@/lib/auth-context';
import { LogoLockup } from '@/components/ui';
import { Button } from '@/components/ui/Button';
import { ShaderUniverseBackground } from '@/components/ui/animated-shader-hero';

const EASE_OUT: [number, number, number, number] = [0.22, 1, 0.36, 1];

const matchRows = [
  { label: 'Product Manager', company: 'Tokopedia', score: 94 },
  { label: 'Frontend Engineer', company: 'Gojek', score: 91 },
  { label: 'Data Scientist', company: 'BCA', score: 88 },
];

const modelSignals = [
  { label: 'SBERT', icon: Brain, copy: 'semantic fit' },
  { label: 'NCF', icon: Network, copy: 'interaction pattern' },
  { label: 'DQN', icon: Route, copy: 'session rerank' },
];

export default function AuthPage() {
  const [isLogin, setIsLogin] = useState(true);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const router = useRouter();
  const { login, register } = useAuth();

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const params = new URLSearchParams(window.location.search);
    if (params.get('mode') === 'signup') {
      const raf = requestAnimationFrame(() => setIsLogin(false));
      return () => cancelAnimationFrame(raf);
    }
  }, []);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setErrorMsg('');

    try {
      if (isLogin) {
        await login(email, password);
        router.push('/dashboard');
      } else {
        await register(name, email, password);
        router.push('/onboarding');
      }
    } catch (error: unknown) {
      setErrorMsg(error instanceof Error ? error.message : 'Terjadi kesalahan. Coba lagi.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="relative isolate min-h-[100svh] overflow-x-hidden bg-[#020617] text-white">
      <ShaderUniverseBackground className="z-0" opacity={0.34} fps={18} />
      <div aria-hidden className="absolute inset-0 z-0 bg-[linear-gradient(180deg,rgba(2,6,23,0.76)_0%,rgba(0,0,0,0.9)_100%)]" />
      <div
        aria-hidden
        className="absolute inset-0 z-0 bg-[radial-gradient(circle_at_20%_12%,rgba(37,99,235,0.2),transparent_34%),radial-gradient(circle_at_84%_34%,rgba(34,211,238,0.12),transparent_28%)]"
      />

      <div className="relative z-10 mx-auto grid min-h-[100svh] max-w-[1320px] gap-8 px-5 py-8 md:px-8 lg:grid-cols-[0.9fr_1fr] lg:items-center">
        <section className="order-1 mx-auto w-full max-w-[560px] lg:order-1">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, ease: EASE_OUT }}
            className="relative overflow-hidden rounded-[20px] border border-cyan-200/14 bg-slate-950/72 p-5 shadow-[0_8px_8px_rgba(0,0,0,0.22),inset_0_1px_0_rgba(255,255,255,0.08)] backdrop-blur-xl md:p-7"
          >
            <div aria-hidden className="absolute inset-0 bg-[radial-gradient(circle_at_20%_0%,rgba(34,211,238,0.12),transparent_34%),linear-gradient(135deg,rgba(255,255,255,0.09),transparent_36%)]" />
            <div className="relative">
              <LogoLockup iconSize={32} variant="light" />
              <p className="mt-4 text-sm font-semibold text-cyan-100">Indonesian Career Intelligence</p>

              <div className="mt-7 grid grid-cols-2 rounded-full border border-white/10 bg-black/34 p-1">
                <button
                  type="button"
                  onClick={() => {
                    setIsLogin(true);
                    setErrorMsg('');
                  }}
                  className={`rounded-full px-4 py-2.5 text-sm font-semibold transition-colors ${
                    isLogin ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'
                  }`}
                >
                  Masuk
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setIsLogin(false);
                    setErrorMsg('');
                  }}
                  className={`rounded-full px-4 py-2.5 text-sm font-semibold transition-colors ${
                    !isLogin ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'
                  }`}
                >
                  Daftar
                </button>
              </div>

              <div className="mt-8">
                <h1 className="text-3xl font-black tracking-tight text-white md:text-4xl">
                  {isLogin ? 'Masuk ke career cockpit.' : 'Bangun profil kariermu.'}
                </h1>
                <p className="mt-3 max-w-md text-sm leading-relaxed text-slate-300 md:text-base">
                  {isLogin
                    ? 'Lanjutkan dari profil, rekomendasi, skill gap, dan lamaran yang sudah kamu bangun.'
                    : 'Mulai dari profil, lalu biarkan SCPA membaca skill, role target, dan sinyal pasar kerja.'}
                </p>
              </div>

              <AnimatePresence>
                {errorMsg ? (
                  <motion.div
                    initial={{ opacity: 0, y: -8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    transition={{ duration: 0.2, ease: EASE_OUT }}
                    className="mt-5 rounded-xl border border-red-300/24 bg-red-500/10 px-4 py-3 text-sm text-red-100"
                    role="alert"
                  >
                    {errorMsg}
                  </motion.div>
                ) : null}
              </AnimatePresence>

              <form onSubmit={handleSubmit} className="mt-6 space-y-4">
                <AnimatePresence initial={false}>
                  {!isLogin ? (
                    <motion.div
                      key="name"
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0 }}
                      transition={{ duration: 0.2, ease: EASE_OUT }}
                      className="overflow-hidden"
                    >
                      <AuthField
                        id="name"
                        label="Nama lengkap"
                        type="text"
                        value={name}
                        onChange={setName}
                        autoComplete="name"
                        placeholder="Nama lengkap kamu"
                        icon={<UserRound className="h-4 w-4" />}
                        required={!isLogin}
                      />
                    </motion.div>
                  ) : null}
                </AnimatePresence>

                <AuthField
                  id="email"
                  label="Email"
                  type="email"
                  value={email}
                  onChange={setEmail}
                  autoComplete="email"
                  placeholder="nama@email.com"
                  icon={<Mail className="h-4 w-4" />}
                  required
                />

                <div>
                  <label htmlFor="password" className="mb-2 block text-xs font-semibold text-slate-300">
                    Kata sandi
                  </label>
                  <div className="relative">
                    <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-cyan-100/70">
                      <LockKeyhole className="h-4 w-4" />
                    </span>
                    <input
                      id="password"
                      name="password"
                      type={showPassword ? 'text' : 'password'}
                      autoComplete={isLogin ? 'current-password' : 'new-password'}
                      value={password}
                      onChange={(event) => setPassword(event.target.value)}
                      placeholder="Minimal 8 karakter"
                      required
                      className="h-12 w-full rounded-xl border border-white/10 bg-black/32 px-10 pr-12 text-sm text-white outline-none transition-colors placeholder:text-slate-500 focus:border-cyan-200/45 focus:bg-black/44"
                    />
                    <button
                      type="button"
                      aria-label={showPassword ? 'Sembunyikan kata sandi' : 'Tampilkan kata sandi'}
                      aria-pressed={showPassword}
                      onClick={() => setShowPassword((value) => !value)}
                      className="absolute right-1.5 top-1/2 grid h-9 w-9 -translate-y-1/2 place-items-center rounded-lg text-slate-400 transition-colors hover:bg-white/[0.055] hover:text-white"
                    >
                      {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                </div>

                <Button type="submit" loading={loading} className="mt-2 h-12 w-full gap-2" icon={<ArrowRight className="h-4 w-4" />}>
                  {isLogin ? 'Masuk ke Dashboard' : 'Buat Akun SCPA'}
                </Button>
              </form>

              <div className="mt-6 rounded-xl border border-cyan-200/12 bg-cyan-400/8 p-4">
                <div className="flex items-start gap-3">
                  <ShieldCheck className="mt-0.5 h-5 w-5 text-cyan-100" />
                  <div>
                    <p className="text-sm font-semibold text-white">Demo evaluator ready</p>
                    <p className="mt-1 text-xs leading-relaxed text-slate-400">
                      Gunakan <span className="font-mono text-slate-200">budi@example.com</span> dengan{' '}
                      <span className="font-mono text-slate-200">password123</span> untuk melihat data demo.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        </section>

        <section className="order-2 flex min-h-[36svh] flex-col justify-center lg:order-2 lg:min-h-[74svh]">
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.08, ease: EASE_OUT }}
            className="max-w-3xl"
          >
            <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-cyan-200/16 bg-cyan-400/8 px-4 py-2 text-sm font-semibold text-cyan-100">
              <Sparkles className="h-4 w-4" />
              Secure career universe access
            </div>
            <h2 className="max-w-2xl text-[clamp(2.25rem,5.4vw,4.9rem)] font-black uppercase leading-[0.92] text-white lg:leading-[0.9]">
              Masuk ke Career Intelligence.
            </h2>
            <p className="mt-6 max-w-2xl text-base leading-relaxed text-slate-300 md:text-lg">
              SCPA melanjutkan dari profil, rekomendasi, skill gap, dan apply readiness yang sudah kamu bangun.
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 28, rotateZ: -1.8 }}
            animate={{ opacity: 1, y: 0, rotateZ: 0 }}
            transition={{ duration: 0.78, delay: 0.18, ease: EASE_OUT }}
            className="mt-8 overflow-hidden rounded-[20px] border border-cyan-200/14 bg-slate-950/52 p-5 shadow-[0_8px_8px_rgba(0,0,0,0.18),inset_0_1px_0_rgba(255,255,255,0.08)] backdrop-blur-lg"
          >
            <div className="grid gap-4 md:grid-cols-3">
              {modelSignals.map((signal, index) => {
                const Icon = signal.icon;
                return (
                  <div key={signal.label} className="rounded-xl border border-white/10 bg-white/[0.045] p-4">
                    <Icon className="h-5 w-5 text-cyan-100" />
                    <p className="mt-4 text-sm font-black text-white">{signal.label}</p>
                    <p className="mt-1 text-xs text-slate-400">{signal.copy}</p>
                    <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-white/10">
                      <motion.div
                        className="h-full rounded-full bg-[linear-gradient(90deg,#2563eb,#22d3ee)]"
                        initial={{ width: 0 }}
                        animate={{ width: `${86 - index * 7}%` }}
                        transition={{ duration: 0.75, delay: 0.45 + index * 0.08, ease: EASE_OUT }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="mt-5 rounded-xl border border-white/10 bg-black/28 p-4">
              <div className="mb-4 flex items-center gap-2">
                <Target className="h-5 w-5 text-cyan-100" />
                <p className="text-sm font-semibold text-white">Live recommendation preview</p>
              </div>
              <div className="space-y-3">
                {matchRows.map((row, index) => (
                  <motion.div
                    key={row.label}
                    initial={{ opacity: 0, x: 18 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.38, delay: 0.55 + index * 0.08, ease: EASE_OUT }}
                    className="flex items-center justify-between rounded-xl border border-white/10 bg-white/[0.035] p-3"
                  >
                    <div className="flex items-center gap-3">
                      <div className="grid h-9 w-9 place-items-center rounded-lg border border-cyan-200/18 bg-cyan-400/10">
                        <CheckCircle2 className="h-4 w-4 text-cyan-100" />
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-white">{row.label}</p>
                        <p className="text-xs text-slate-400">{row.company}, Jakarta</p>
                      </div>
                    </div>
                    <span className="text-sm font-black tabular-nums text-cyan-100">{row.score}%</span>
                  </motion.div>
                ))}
              </div>
            </div>
          </motion.div>
        </section>
      </div>
    </main>
  );
}

function AuthField({
  id,
  label,
  type,
  value,
  onChange,
  placeholder,
  autoComplete,
  icon,
  required,
}: {
  id: string;
  label: string;
  type: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  autoComplete: string;
  icon: React.ReactNode;
  required?: boolean;
}) {
  return (
    <div>
      <label htmlFor={id} className="mb-2 block text-xs font-semibold text-slate-300">
        {label}
      </label>
      <div className="relative">
        <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-cyan-100/70">{icon}</span>
        <input
          id={id}
          name={id}
          type={type}
          autoComplete={autoComplete}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          required={required}
          className="h-12 w-full rounded-xl border border-white/10 bg-black/32 px-10 text-sm text-white outline-none transition-colors placeholder:text-slate-500 focus:border-cyan-200/45 focus:bg-black/44"
        />
      </div>
    </div>
  );
}
