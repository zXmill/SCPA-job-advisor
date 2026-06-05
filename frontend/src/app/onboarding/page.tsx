'use client';

import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { GlassCard, Button, LogoLockup, ShaderUniverseBackground } from '@/components/ui';
import { api, ApiError, SkillSearchItem } from '@/lib/api';
import { useAuth } from '@/lib/auth-context';

/**
 * SCPA Onboarding Wizard — 5-step profile completion.
 *
 * The visual wizard has 5 steps but only 2 of them currently have
 * matching columns in the production schema, so we map them to the
 * gateway's onboarding API as follows:
 *
 *   visual step 2  Education      -> POST /api/profile/onboarding step=1
 *                                    (program_studi, university)
 *   visual step 3  Skills         -> POST /api/profile/onboarding step=2
 *                                    (skills[])
 *   visual step 5  Interests/done -> POST /api/profile/onboarding step=3
 *                                    (marks profile complete at 85%)
 *
 * Visual steps 1 (Demographics) and 4 (Certifications) are placeholders
 * for future schema extension; advancing through them is a no-op on
 * the backend.
 */

const steps = [
  { id: 1, title: 'Demographics', titleId: 'DEMOGRAFIS' },
  { id: 2, title: 'Education', titleId: 'EDUKASI' },
  { id: 3, title: 'Skills', titleId: 'KEAHLIAN' },
  { id: 4, title: 'Certifications', titleId: 'SERTIFIKASI' },
  { id: 5, title: 'Interests', titleId: 'MINAT' },
];

export default function OnboardingPage() {
  const router = useRouter();
  const { refreshUser } = useAuth();
  const [currentStep, setCurrentStep] = useState(2); // Land on Education per Figma

  // ── Education form state (visual step 2 -> gateway step 1) ──
  const [degree, setDegree] = useState('');
  const [institution, setInstitution] = useState('');
  const [fieldOfStudy, setFieldOfStudy] = useState('');
  const [graduationYear, setGraduationYear] = useState('');

  // ── Skills form state (visual step 3 -> gateway step 2) ──
  const [skillsInput, setSkillsInput] = useState('');
  const [skillChips, setSkillChips] = useState<string[]>([]);
  const [skillSuggestions, setSkillSuggestions] = useState<SkillSearchItem[]>([]);
  const [skillSuggestionsLoading, setSkillSuggestionsLoading] = useState(false);
  const [skillInputError, setSkillInputError] = useState('');

  // ── Async / UX state ──
  const [saving, setSaving] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  // ── Skill chip helpers ──
  const addSkill = (raw: string) => {
    const value = raw.trim();
    if (!value) return;
    setSkillChips((prev) =>
      prev.some((skill) => skill.toLowerCase() === value.toLowerCase()) ? prev : [...prev, value]
    );
    setSkillsInput('');
    setSkillSuggestions([]);
    setSkillInputError('');
  };

  const bestSuggestionForInput = () => {
    const query = skillsInput.trim().toLowerCase();
    if (!query) return undefined;
    return (
      skillSuggestions.find((skill) => skill.name.toLowerCase() === query)
      || skillSuggestions.find((skill) => skill.aliases.some((alias) => alias.toLowerCase() === query))
      || skillSuggestions[0]
    );
  };

  const commitSkillInput = () => {
    const pending = skillsInput.trim();
    if (!pending) return;
    const suggestion = bestSuggestionForInput();
    addSkill(suggestion?.name || pending);
  };

  const handleSkillKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      commitSkillInput();
    } else if (e.key === 'Backspace' && !skillsInput && skillChips.length) {
      // Easy chip removal: backspace on empty input pops the last chip
      setSkillChips((prev) => prev.slice(0, -1));
    }
  };

  useEffect(() => {
    if (currentStep !== 3 || !skillsInput.trim()) {
      return;
    }

    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setSkillSuggestionsLoading(true);
      void api.searchSkills(
        skillsInput.trim(),
        { limit: 12, exclude: skillChips },
        controller.signal,
      )
        .then((response) => setSkillSuggestions(response.skills))
        .catch(() => setSkillSuggestions([]))
        .finally(() => setSkillSuggestionsLoading(false));
    }, 140);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [currentStep, skillsInput, skillChips]);

  // ── Step submission — translates UI step to gateway step ──
  const persistCurrentStep = async (): Promise<boolean> => {
    try {
      if (currentStep === 2) {
        // Save program_studi + university if user filled either field
        if (institution.trim() || fieldOfStudy.trim()) {
          await api.saveOnboarding(1, {
            program_studi: fieldOfStudy.trim() || null,
            university: institution.trim() || null,
          });
        }
      } else if (currentStep === 3) {
        // Flush any pending text in the input as a chip first
        const pending = skillsInput.trim();
        const suggestion = bestSuggestionForInput();
        const finalSkills = pending
          ? skillChips.some((skill) => skill.toLowerCase() === (suggestion?.name || pending).toLowerCase())
            ? skillChips
            : [...skillChips, suggestion?.name || pending]
          : skillChips;
        if (finalSkills.length > 0) {
          await api.saveOnboarding(2, { skills: finalSkills });
        }
        setSkillChips(finalSkills);
        setSkillsInput('');
      } else if (currentStep === 5) {
        // Final visual step — mark profile complete at 85%
        await api.saveOnboarding(3, {});
      }
      return true;
    } catch (e) {
      const message = e instanceof ApiError
        ? e.message
        : 'Gagal menyimpan progres onboarding.';
      if (currentStep === 3) setSkillInputError(message);
      setErrorMsg(
        message
      );
      return false;
    }
  };

  const handleNext = async () => {
    setErrorMsg('');
    setSaving(true);
    try {
      const ok = await persistCurrentStep();
      if (!ok) return;
      if (currentStep >= 5) {
        // Refresh the cached user before redirecting so the dashboard
        // greeting reflects the new completion_percent and profile
        // fields immediately, not the stale post-registration value.
        await refreshUser();
        router.push('/dashboard');
      } else {
        setCurrentStep((s) => s + 1);
      }
    } finally {
      setSaving(false);
    }
  };

  const handleBack = () => {
    setErrorMsg('');
    setCurrentStep((s) => Math.max(1, s - 1));
  };

  const handleSkip = async () => {
    // Best-effort completion mark, then go to dashboard.
    // Always refresh the cached user so the dashboard renders the
    // latest server state, even if the mark-complete call failed.
    setSaving(true);
    setErrorMsg('');
    try {
      await api.saveOnboarding(3, {}).catch(() => undefined);
      await refreshUser();
    } finally {
      setSaving(false);
      router.push('/dashboard');
    }
  };

  return (
    <div className="relative isolate min-h-screen overflow-hidden bg-black text-white" data-node-id="OnboardingWizard">
      <ShaderUniverseBackground className="z-0" opacity={0.42} />
      <div aria-hidden className="absolute inset-0 z-0 bg-black/58" />
      {/* Top Bar */}
      <div className="relative z-10 mx-auto mt-5 max-w-screen-xl rounded-2xl border border-cyan-200/14 bg-slate-950/74 py-4 shadow-[0_8px_8px_rgba(0,0,0,0.22),inset_0_1px_0_rgba(255,255,255,0.08)] backdrop-blur-2xl">
        <div className="max-w-screen-xl mx-auto px-4 md:px-6 lg:px-8 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <LogoLockup iconSize={32} variant="light" />
          </Link>
          <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>
            Langkah {currentStep} dari {steps.length}
          </span>
        </div>
      </div>

      {/* Step Indicator */}
      <div className="relative z-10 mx-auto max-w-screen-xl px-4 py-8 md:px-6 lg:px-8">
        <div className="flex items-center justify-between max-w-2xl mx-auto mb-8">
          {steps.map((step, index) => (
            <React.Fragment key={step.id}>
              <div className="flex flex-col items-center gap-2">
                <motion.div
                  initial={{ scale: step.id === currentStep ? 0.95 : 1 }}
                  animate={{ scale: step.id === currentStep ? 1 : 1 }}
                  className="w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold"
                  style={{
                    background: step.id <= currentStep ? 'linear-gradient(135deg, #2563EB, #22D3EE)' : 'rgba(255,255,255,0.06)',
                    color: step.id <= currentStep ? 'white' : 'var(--text-secondary)',
                    border: step.id <= currentStep ? '1px solid rgba(103,232,249,0.36)' : '1px solid rgba(147,197,253,0.16)',
                    boxShadow: step.id === currentStep ? '0 0 34px rgba(37,99,235,0.24)' : 'none',
                  }}
                >
                  {step.id < currentStep ? (
                    <svg
                      className="w-4 h-4"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M5 13l4 4L19 7"
                      />
                    </svg>
                  ) : (
                    step.id
                  )}
                </motion.div>
                <span
                  className="text-xs font-medium"
                  style={{
                    color: step.id <= currentStep ? 'var(--primary)' : 'var(--text-secondary)',
                  }}
                >
                  {step.title}
                </span>
              </div>

              {index < steps.length - 1 && (
                <div className="flex-1 h-[1px] mx-2 -mt-6">
                  <div
                    className="h-full transition-all"
                    style={{
                      width: '100%',
                      background: step.id < currentStep ? 'linear-gradient(90deg, #2563EB, #22D3EE)' : 'rgba(147,197,253,0.16)',
                    }}
                  />
                </div>
              )}
            </React.Fragment>
          ))}
        </div>

      {/* Content Card */}
      <div className="max-w-2xl mx-auto pb-16">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <GlassCard>
            {/* ── Step 1: Demographics (placeholder) ── */}
            {currentStep === 1 && (
              <>
                <h2 className="mb-2 text-[16px] font-semibold" style={{ color: 'var(--text-primary)' }}>Demografis</h2>
                <p className="text-sm mb-8" style={{ color: 'var(--text-secondary)' }}>
                  Bagian ini akan tersedia segera. Lanjut ke Education
                  untuk melengkapi profil utamamu.
                </p>
              </>
            )}

            {/* ── Step 2: Education ── */}
            {currentStep === 2 && (
              <>
                <h2 className="mb-2 text-[16px] font-semibold" style={{ color: 'var(--text-primary)' }}>Latar Belakang Pendidikan</h2>
                <p className="text-sm mb-8" style={{ color: 'var(--text-secondary)' }}>
                  Ceritakan tentang perjalanan akademismu. Ini membantu AI
                  kami mencocokkanmu dengan jalur karier yang sesuai.
                </p>

                <div className="grid md:grid-cols-2 gap-6">
                  <div>
                    <label
                      htmlFor="degree"
                      className="text-sm block mb-2"
                      style={{ color: 'var(--text-secondary)' }}
                    >
                      Degree / Tingkat Pendidikan
                    </label>
                    <select
                      id="degree"
                      className="w-full rounded-xl px-4 py-2.5 text-sm outline-none transition-all focus:border-cyan-300/45"
                      style={{
                        color: 'var(--text-primary)',
                        backgroundColor: 'rgba(2,6,23,0.54)',
                        border: '1px solid rgba(147,197,253,0.16)',
                      }}
                      value={degree}
                      onChange={(e) => setDegree(e.target.value)}
                    >
                      <option value="">Pilih tingkat pendidikan</option>
                      <option value="s1">S1 - Sarjana</option>
                      <option value="s2">S2 - Magister</option>
                      <option value="d3">D3 - Diploma</option>
                      <option value="sma">SMA/SMK</option>
                    </select>
                  </div>

                  <div>
                    <label
                      htmlFor="institution"
                      className="text-sm block mb-2"
                      style={{ color: 'var(--text-secondary)' }}
                    >
                      Institution / Institut
                    </label>
                    <div className="relative">
                      <input
                        id="institution"
                        type="text"
                        placeholder="Nama Universitas, Kampus atau Sekolah"
                        className="w-full rounded-xl px-4 py-2.5 text-sm text-white outline-none transition-all placeholder:text-slate-500 focus:border-cyan-300/45"
                        style={{
                          backgroundColor: 'rgba(2,6,23,0.54)',
                          border: '1px solid rgba(147,197,253,0.16)',
                        }}
                        value={institution}
                        onChange={(e) => setInstitution(e.target.value)}
                      />
                    </div>
                  </div>

                  <div>
                    <label
                      htmlFor="field-of-study"
                      className="text-sm block mb-2"
                      style={{ color: 'var(--text-secondary)' }}
                    >
                      Field of Study / Jurusan
                    </label>
                    <div className="relative">
                      <input
                        id="field-of-study"
                        type="text"
                        placeholder="e.g. Computer Science"
                        className="w-full rounded-xl px-4 py-2.5 text-sm text-white outline-none transition-all placeholder:text-slate-500 focus:border-cyan-300/45"
                        style={{
                          backgroundColor: 'rgba(2,6,23,0.54)',
                          border: '1px solid rgba(147,197,253,0.16)',
                        }}
                        value={fieldOfStudy}
                        onChange={(e) => setFieldOfStudy(e.target.value)}
                      />
                    </div>
                    <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>
                      Jurusan utama atau fokus area
                    </p>
                  </div>

                  <div>
                    <label
                      htmlFor="grad-year"
                      className="text-sm block mb-2"
                      style={{ color: 'var(--text-secondary)' }}
                    >
                      Graduation Year / Tahun Lulus
                    </label>
                    <div className="relative">
                      <input
                        id="grad-year"
                        type="text"
                        placeholder="YYYY"
                        inputMode="numeric"
                        className="w-full rounded-xl px-4 py-2.5 text-sm text-white outline-none transition-all placeholder:text-slate-500 focus:border-cyan-300/45"
                        style={{
                          backgroundColor: 'rgba(2,6,23,0.54)',
                          border: '1px solid rgba(147,197,253,0.16)',
                        }}
                        value={graduationYear}
                        onChange={(e) => setGraduationYear(e.target.value)}
                      />
                    </div>
                    <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>
                      Perkiraan jika belum lulus
                    </p>
                  </div>
                </div>
              </>
            )}

            {/* ── Step 3: Keahlian ── */}
            {currentStep === 3 && (
              <>
                <h2 className="mb-2 text-[16px] font-semibold" style={{ color: 'var(--text-primary)' }}>Keahlian</h2>
                <p className="text-sm mb-6" style={{ color: 'var(--text-secondary)' }}>
                  Tambahkan kemampuan teknis dan soft skills kamu. Tekan
                  Enter atau koma untuk menambahkan setiap skill.
                </p>

                <label
                  htmlFor="skills-input"
                  className="text-sm block mb-2"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  Skills / Keahlian
                </label>

                <div
                  className="flex flex-wrap items-center gap-2 rounded-2xl p-3 transition-all"
                  style={{
                    backgroundColor: 'rgba(2,6,23,0.54)',
                    border: '1px solid rgba(147,197,253,0.16)',
                  }}
                >
                  {skillChips.map((skill) => (
                    <span
                      key={skill}
                      className="inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium"
                      style={{
                        backgroundColor: 'rgba(34,211,238,0.12)',
                        color: '#CFFAFE',
                        border: '1px solid rgba(103,232,249,0.24)',
                      }}
                    >
                      {skill}
                      <button
                        type="button"
                        aria-label={`Hapus skill ${skill}`}
                        onClick={() =>
                          setSkillChips((prev) =>
                            prev.filter((s) => s !== skill)
                          )
                        }
                        className="text-blue-400 hover:text-red-400 leading-none cursor-pointer"
                      >
                        ×
                      </button>
                    </span>
                  ))}
                  <input
                    id="skills-input"
                    type="text"
                    value={skillsInput}
                    onChange={(e) => {
                      const value = e.target.value;
                      setSkillsInput(value);
                      if (!value.trim()) {
                        setSkillSuggestions([]);
                        setSkillSuggestionsLoading(false);
                      }
                      setSkillInputError('');
                    }}
                    onKeyDown={handleSkillKey}
                    placeholder={
                      skillChips.length === 0
                        ? 'e.g. Python, SQL, React'
                        : 'Tambah skill lain...'
                    }
                    className="flex-1 min-w-[120px] outline-none text-sm bg-transparent placeholder-gray-500"
                    style={{ color: 'var(--text-primary)' }}
                  />
                </div>
                {(skillSuggestionsLoading || skillSuggestions.length > 0) && (
                  <div
                    role="listbox"
                    className="mt-2 max-h-48 overflow-y-auto rounded-2xl border border-cyan-200/14 bg-slate-950/92 shadow-[0_18px_48px_rgba(0,0,0,0.34)]"
                  >
                    {skillSuggestionsLoading && (
                      <div className="px-3 py-2 text-xs text-slate-400">Memuat skill...</div>
                    )}
                    {!skillSuggestionsLoading && skillSuggestions.map((skill) => (
                      <button
                        key={skill.id}
                        type="button"
                        role="option"
                        aria-selected={false}
                        className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm text-slate-100 transition-colors hover:bg-cyan-300/10"
                        onMouseDown={(event) => {
                          event.preventDefault();
                          addSkill(skill.name);
                        }}
                      >
                        <span className="min-w-0">
                          <span className="block truncate">{skill.name}</span>
                          {skill.aliases.length > 0 && (
                            <span className="block truncate text-xs text-slate-500">
                              alias: {skill.aliases.slice(0, 3).join(', ')}
                            </span>
                          )}
                        </span>
                        <span className="shrink-0 rounded-full border border-cyan-200/14 px-2 py-0.5 text-[10px] uppercase tracking-[0.08em] text-slate-400">
                          {skill.category}
                        </span>
                      </button>
                    ))}
                  </div>
                )}
                <p className="text-xs mt-2" style={{ color: 'var(--text-tertiary)' }}>
                  {skillChips.length} skill ditambahkan. Kamu bisa
                  menambahkan dan menghapus sebanyak yang kamu mau.
                </p>
                {skillInputError && (
                  <p className="mt-2 text-xs text-red-300" role="alert">{skillInputError}</p>
                )}
              </>
            )}

            {/* ── Step 4: Certifications (placeholder) ── */}
            {currentStep === 4 && (
              <>
                <h2 className="mb-2 text-[16px] font-semibold" style={{ color: 'var(--text-primary)' }}>Sertifikasi</h2>
                <p className="text-sm mb-8" style={{ color: 'var(--text-secondary)' }}>
                  Penyimpanan sertifikasi belum aktif di database — fitur
                  ini akan tersedia segera. Klik Lanjut untuk melanjutkan.
                </p>
              </>
            )}

            {/* ── Step 5: Interests (mark complete) ── */}
            {currentStep === 5 && (
              <>
                <h2 className="mb-2 text-[16px] font-semibold" style={{ color: 'var(--text-primary)' }}>Minat & Penyelesaian</h2>
                <p className="text-sm mb-4" style={{ color: 'var(--text-secondary)' }}>
                  Klik Lanjut untuk menandai profilmu siap. Setelah ini
                  kamu akan diarahkan ke dashboard dan mulai mendapatkan
                  rekomendasi karier dari AI Match.
                </p>
                <div
                  className="rounded-2xl p-4 text-sm"
                  style={{
                    backgroundColor: 'rgba(34,211,238,0.10)',
                    border: '1px solid rgba(103,232,249,0.24)',
                    color: '#CFFAFE',
                  }}
                >
                  Profilmu akan ditandai 85% lengkap setelah langkah ini.
                </div>
              </>
            )}

            {/* ── Error banner ── */}
            {errorMsg && (
              <motion.div
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                role="alert"
                className="mt-6 rounded-2xl px-4 py-3 text-sm"
                style={{
                  backgroundColor: 'rgba(239,68,68,0.08)',
                  border: '1px solid rgba(239,68,68,0.3)',
                  color: '#FCA5A5',
                }}
              >
                {errorMsg}
              </motion.div>
            )}

            {/* ── Navigation ── */}
            <div
              className="flex items-center justify-between mt-12 pt-6"
              style={{ borderTop: '1px solid rgba(147,197,253,0.16)' }}
            >
              <button
                type="button"
                onClick={handleSkip}
                disabled={saving}
                className="text-sm transition-colors disabled:opacity-50 cursor-pointer"
                style={{ color: 'var(--text-secondary)' }}
              >
                Lewati untuk sekarang
              </button>

              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={handleBack}
                  disabled={saving || currentStep === 1}
                  className="cursor-pointer rounded-full px-6 py-2.5 text-sm font-medium transition-all disabled:opacity-50"
                  style={{
                    backgroundColor: 'rgba(255,255,255,0.06)',
                    border: '1px solid rgba(147,197,253,0.16)',
                    color: 'var(--text-primary)',
                  }}
                >
                  ← Kembali
                </button>
                <Button
                  onClick={handleNext}
                  loading={saving}
                >
                  {saving
                    ? 'Menyimpan...'
                    : currentStep >= 5
                    ? 'Selesai & ke Dashboard'
                    : 'Lanjut (Next) →'}
                </Button>
              </div>
            </div>
          </GlassCard>
        </motion.div>
        </div>
      </div>
    </div>
  );
}
