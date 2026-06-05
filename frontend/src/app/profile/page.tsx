'use client';

import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { AppLayout } from '@/components/AppLayout';
import { GlassCard, Button, Badge, Avatar } from '@/components/ui';
import { PageHeader } from '@/components/ui';
import { CareerLoading } from '@/components/ui/career-loading';
import { useAuth } from '@/lib/auth-context';
import { api, SkillData, ApplicationData, SkillSearchItem, ProfileCompletenessResponse, JobData, JobAlertData, CvUploadResponse } from '@/lib/api';
import { colors } from '@/lib/design-tokens';

const INPUT_STYLE = {
  color: 'var(--text-primary)',
  backgroundColor: 'var(--app-field-bg)',
  border: '1px solid var(--app-field-border)',
  outline: 'none',
};

interface EditFieldProps {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  className?: string;
}

const EditField = ({ value, onChange, placeholder, className = '' }: EditFieldProps) => (
  <input
    className={`scpa-field w-full rounded-xl px-3 py-2 text-sm transition-colors ${className}`}
    style={INPUT_STYLE}
    value={value}
    onChange={(e) => onChange(e.target.value)}
    placeholder={placeholder}
  />
);

interface SkillsCardProps {
  skills: SkillData[];
  editing: boolean;
  newSkill: string;
  suggestions: SkillSearchItem[];
  suggestionsLoading: boolean;
  onNewSkill: (v: string) => void;
  onRemove: (skill: string) => void;
  onAdd: () => void;
  onSelectSuggestion: (skill: SkillSearchItem) => void;
}

const SkillsCard = ({
  skills,
  editing,
  newSkill,
  suggestions,
  suggestionsLoading,
  onNewSkill,
  onRemove,
  onAdd,
  onSelectSuggestion,
}: SkillsCardProps) => (
  <GlassCard className="relative z-[60] overflow-visible">
    <h4 className="font-semibold mb-4 text-[var(--text-primary)]">Keahlian</h4>
    <div className="flex flex-wrap gap-2 mb-4">
      {skills.map((s) => (
        <span
          key={s.skill}
          className="scpa-chip inline-flex items-center gap-1 rounded-full px-3 py-1 text-sm font-medium"
        >
          {s.skill}
          {editing && (
            <button
              onClick={() => onRemove(s.skill)}
              className="ml-1 text-[var(--text-tertiary)] hover:text-red-400 transition-colors"
            >
              ×
            </button>
          )}
        </span>
      ))}
      {skills.length === 0 && (
        <p className="text-xs text-[var(--text-secondary)]">
          Belum ada keahlian ditambahkan. Klik Edit untuk menambah keahlian.
        </p>
      )}
    </div>
    {editing && (
      <div className="flex gap-2 items-start">
        <div className="relative z-[70] flex-1">
          <input
            className="scpa-field w-full rounded-xl px-3 py-2 text-sm"
            style={INPUT_STYLE}
            placeholder="Tambah keahlian baru"
            value={newSkill}
            aria-autocomplete="list"
            aria-controls="skill-suggestions"
            onChange={(e) => onNewSkill(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                onAdd();
              }
            }}
          />
          {(suggestionsLoading || suggestions.length > 0) && (
            <div
              id="skill-suggestions"
              role="listbox"
              className="absolute left-0 right-0 top-[calc(100%+8px)] z-[90] max-h-64 overflow-y-auto rounded-2xl border backdrop-blur-xl"
              style={{
                backgroundColor: 'var(--app-menu-bg)',
                borderColor: 'var(--app-control-border)',
                boxShadow: 'var(--app-card-shadow)',
              }}
            >
              {suggestionsLoading && (
                <div className="px-3 py-2 text-xs text-[var(--text-secondary)]">Memuat...</div>
              )}
              {!suggestionsLoading && suggestions.map((skill) => (
                <button
                  key={skill.id}
                  type="button"
                  role="option"
                  aria-selected={false}
                  className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm text-[var(--text-primary)] transition-colors hover:bg-cyan-300/10"
                  onMouseDown={(event) => {
                    event.preventDefault();
                    onSelectSuggestion(skill);
                  }}
                >
                  <span className="min-w-0">
                    <span className="block truncate">{skill.name}</span>
                    {skill.aliases.length > 0 && (
                      <span className="block truncate text-xs text-[var(--text-tertiary)]">
                        alias: {skill.aliases.slice(0, 3).join(', ')}
                      </span>
                    )}
                  </span>
                  <span className="shrink-0 rounded-full border border-cyan-200/14 px-2 py-0.5 text-[10px] uppercase tracking-[0.08em] text-[var(--text-tertiary)]">
                    {skill.category}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
        <button
          onClick={onAdd}
          className="rounded-full border px-4 py-2 text-sm font-medium text-[var(--text-primary)] transition-colors hover:bg-[var(--app-control-hover-bg)]"
          style={{ backgroundColor: 'var(--app-control-bg)', borderColor: 'var(--app-control-border)' }}
        >
          +
        </button>
      </div>
    )}
  </GlassCard>
);

interface ApplicationsCardProps {
  applications: ApplicationData[];
}

const ApplicationsCard = ({ applications }: ApplicationsCardProps) => (
  <GlassCard>
    <h4 className="font-semibold mb-4 text-[var(--text-primary)]">Riwayat Lamaran</h4>
    {applications.length === 0 ? (
      <p className="text-xs text-[var(--text-secondary)]">Belum ada lamaran.</p>
    ) : (
      <div className="space-y-3">
        {applications.map((app) => (
          <div
            key={app.id}
            className="scpa-list-item flex items-center gap-3 rounded-xl p-3"
          >
            <div
              className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-blue-600 to-cyan-400 text-xs font-bold text-white"
            >
              {app.company[0]}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate text-[var(--text-primary)]">{app.job_title}</p>
              <p className="text-xs text-[var(--text-secondary)]">{app.company}{app.location ? ` – ${app.location}` : ''}</p>
            </div>
            <Badge variant={app.status === 'accepted' ? 'green' : app.status === 'rejected' ? 'red' : 'gray'}>
              {app.status}
            </Badge>
          </div>
        ))}
      </div>
    )}
  </GlassCard>
);

interface CvUploadCardProps {
  completeness: ProfileCompletenessResponse | null;
  uploading: boolean;
  error: string | null;
  result: CvUploadResponse | null;
  onUpload: (file: File | null) => void;
}

const CvUploadCard = ({
  completeness,
  uploading,
  error,
  result,
  onUpload,
}: CvUploadCardProps) => {
  const cvItem = completeness?.items.find((item) => item.id === 'cv');
  const isUploaded = Boolean(cvItem?.completed || completeness?.cv_uploaded_at);

  return (
    <GlassCard>
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div className="min-w-0">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <h4 className="font-semibold text-[var(--text-primary)]">CV/Resume</h4>
            <Badge variant={isUploaded ? 'green' : 'gray'}>
              {isUploaded ? 'Sudah upload' : 'Belum upload'}
            </Badge>
          </div>
          <p className="max-w-2xl text-sm leading-relaxed text-[var(--text-secondary)]">
            Upload PDF atau TXT agar SCPA bisa mengekstrak skill nyata dari CV dan menyesuaikan rekomendasi lowongan.
          </p>
          {completeness?.cv_uploaded_at && (
            <p className="mt-2 text-xs text-[var(--text-tertiary)]">
              Upload terakhir: {new Date(completeness.cv_uploaded_at).toLocaleString('id-ID')}
            </p>
          )}
        </div>
        <div className="shrink-0">
          <input
            id="cv-upload"
            type="file"
            accept=".pdf,.txt,application/pdf,text/plain"
            className="sr-only"
            disabled={uploading}
            onChange={(event) => {
              onUpload(event.target.files?.[0] ?? null);
              event.currentTarget.value = '';
            }}
          />
          <label
            htmlFor="cv-upload"
            className="inline-flex h-10 cursor-pointer items-center justify-center rounded-full bg-gradient-to-r from-blue-600 to-cyan-400 px-5 text-sm font-semibold text-white shadow-[0_16px_34px_rgba(37,99,235,0.18)] transition-all hover:brightness-110"
            aria-disabled={uploading}
          >
            {uploading ? 'Mengunggah...' : 'Upload CV/Resume'}
          </label>
        </div>
      </div>

      {result && (
        <div className="mt-4 rounded-2xl border border-emerald-300/24 bg-emerald-400/10 p-4 text-sm text-emerald-100">
          <p className="font-semibold">{result.filename} berhasil diproses.</p>
          <p className="mt-1 text-emerald-100/80">
            {result.skills_added} skill baru ditambahkan, {result.extracted_skills.length} skill terdeteksi.
          </p>
          {result.extracted_skills.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {result.extracted_skills.map((skill) => (
                <span key={skill} className="rounded-full border border-emerald-200/24 px-2.5 py-1 text-xs">
                  {skill}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {error && (
        <p className="mt-4 text-xs text-red-400" role="alert">{error}</p>
      )}
    </GlassCard>
  );
};

interface SavedJobsCardProps {
  jobs: JobData[];
}

const SavedJobsCard = ({ jobs }: SavedJobsCardProps) => (
  <GlassCard>
    <div className="mb-4 flex items-center justify-between gap-3">
      <h4 className="font-semibold text-[var(--text-primary)]">Lowongan Tersimpan</h4>
      {jobs.length > 0 && (
        <Badge variant="blue">{jobs.length}</Badge>
      )}
    </div>
    {jobs.length === 0 ? (
      <p className="text-xs text-[var(--text-secondary)]">Belum ada lowongan tersimpan.</p>
    ) : (
      <div className="space-y-3">
        {jobs.map((job) => (
          <div
            key={job.id}
            className="scpa-list-item flex items-center gap-3 rounded-xl p-3"
          >
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-blue-600 to-cyan-400 text-xs font-bold text-white">
              {(job.company || job.title || 'L').charAt(0).toUpperCase()}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-[var(--text-primary)]">{job.title}</p>
              <p className="truncate text-xs text-[var(--text-secondary)]">
                {job.company}{job.location ? ` - ${job.location}` : ''}
              </p>
            </div>
            <Link
              href={`/jobs/${job.id}`}
              className="shrink-0 rounded-full border px-3 py-1.5 text-xs font-semibold text-[var(--text-primary)] transition-colors hover:bg-[var(--app-control-hover-bg)]"
              style={{ backgroundColor: 'var(--app-control-bg)', borderColor: 'var(--app-control-border)' }}
            >
              Lihat
            </Link>
          </div>
        ))}
      </div>
    )}
  </GlassCard>
);

interface JobAlertsCardProps {
  alerts: JobAlertData[];
  name: string;
  query: string;
  location: string;
  minMatchPercent: number;
  frequency: 'daily' | 'weekly';
  saving: boolean;
  error: string | null;
  disablingAlertId: number | null;
  onName: (value: string) => void;
  onQuery: (value: string) => void;
  onLocation: (value: string) => void;
  onMinMatchPercent: (value: string) => void;
  onFrequency: (value: 'daily' | 'weekly') => void;
  onCreate: () => void;
  onDisable: (alertId: number) => void;
}

const JobAlertsCard = ({
  alerts,
  name,
  query,
  location,
  minMatchPercent,
  frequency,
  saving,
  error,
  disablingAlertId,
  onName,
  onQuery,
  onLocation,
  onMinMatchPercent,
  onFrequency,
  onCreate,
  onDisable,
}: JobAlertsCardProps) => (
  <GlassCard>
    <div className="mb-4 flex items-center justify-between gap-3">
      <h4 className="font-semibold text-[var(--text-primary)]">Job Alerts</h4>
      {alerts.length > 0 && <Badge variant="blue">{alerts.length}</Badge>}
    </div>

    <form
      className="mb-4 grid gap-3 md:grid-cols-2"
      onSubmit={(event) => {
        event.preventDefault();
        onCreate();
      }}
    >
      <input
        className="scpa-field rounded-xl px-3 py-2 text-sm"
        style={INPUT_STYLE}
        value={name}
        onChange={(event) => onName(event.target.value)}
        placeholder="Nama alert"
        aria-label="Nama alert"
      />
      <input
        className="scpa-field rounded-xl px-3 py-2 text-sm"
        style={INPUT_STYLE}
        value={query}
        onChange={(event) => onQuery(event.target.value)}
        placeholder="Kata kunci"
        aria-label="Kata kunci alert"
      />
      <input
        className="scpa-field rounded-xl px-3 py-2 text-sm"
        style={INPUT_STYLE}
        value={location}
        onChange={(event) => onLocation(event.target.value)}
        placeholder="Lokasi"
        aria-label="Lokasi alert"
      />
      <div className="grid grid-cols-[1fr_120px] gap-2">
        <select
          className="scpa-field rounded-xl px-3 py-2 text-sm"
          style={INPUT_STYLE}
          value={frequency}
          onChange={(event) => onFrequency(event.target.value as 'daily' | 'weekly')}
          aria-label="Frekuensi alert"
        >
          <option value="daily">Harian</option>
          <option value="weekly">Mingguan</option>
        </select>
        <input
          type="number"
          min={0}
          max={100}
          className="scpa-field rounded-xl px-3 py-2 text-sm"
          style={INPUT_STYLE}
          value={minMatchPercent}
          onChange={(event) => onMinMatchPercent(event.target.value)}
          aria-label="Minimum match percent"
        />
      </div>
      <div className="md:col-span-2 flex justify-end">
        <Button type="submit" size="sm" loading={saving}>
          Buat Alert
        </Button>
      </div>
    </form>

    {error && <p className="mb-4 text-xs text-red-400" role="alert">{error}</p>}

    {alerts.length === 0 ? (
      <p className="text-xs text-[var(--text-secondary)]">Belum ada alert aktif.</p>
    ) : (
      <div className="space-y-3">
        {alerts.map((alert) => (
          <div
            key={alert.id}
            className="scpa-list-item flex flex-col gap-3 rounded-xl p-3 sm:flex-row sm:items-center"
          >
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-[var(--text-primary)]">{alert.name}</p>
              <p className="mt-1 truncate text-xs text-[var(--text-secondary)]">
                {(alert.query || 'Semua lowongan')}{alert.location ? ` - ${alert.location}` : ''} · Min {alert.min_match_percent}% · {alert.frequency === 'daily' ? 'Harian' : 'Mingguan'}
              </p>
            </div>
            <Button
              size="sm"
              variant="ghost"
              loading={disablingAlertId === alert.id}
              onClick={() => onDisable(alert.id)}
            >
              Nonaktifkan
            </Button>
          </div>
        ))}
      </div>
    )}
  </GlassCard>
);

export default function ProfilePage() {
  const { user, loading: authLoading, refreshUser, logout } = useAuth();
  const router = useRouter();
  const [skills, setSkills] = useState<SkillData[]>([]);
  const [applications, setApplications] = useState<ApplicationData[]>([]);
  const [savedJobs, setSavedJobs] = useState<JobData[]>([]);
  const [jobAlerts, setJobAlerts] = useState<JobAlertData[]>([]);
  const [profileCompleteness, setProfileCompleteness] = useState<ProfileCompletenessResponse | null>(null);
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState('');
  const [editPS, setEditPS] = useState('');
  const [editUni, setEditUni] = useState('');
  const [newSkill, setNewSkill] = useState('');
  const [alertName, setAlertName] = useState('');
  const [alertQuery, setAlertQuery] = useState('');
  const [alertLocation, setAlertLocation] = useState('');
  const [alertMinMatchPercent, setAlertMinMatchPercent] = useState(60);
  const [alertFrequency, setAlertFrequency] = useState<'daily' | 'weekly'>('daily');
  const [alertSaving, setAlertSaving] = useState(false);
  const [alertError, setAlertError] = useState<string | null>(null);
  const [disablingAlertId, setDisablingAlertId] = useState<number | null>(null);
  const [skillSuggestions, setSkillSuggestions] = useState<SkillSearchItem[]>([]);
  const [skillSuggestionsLoading, setSkillSuggestionsLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [cvUploading, setCvUploading] = useState(false);
  const [cvUploadError, setCvUploadError] = useState<string | null>(null);
  const [cvUploadResult, setCvUploadResult] = useState<CvUploadResponse | null>(null);

  useEffect(() => {
    if (!authLoading && !user) { router.push('/auth'); return; }
    if (!user) return;
    (async () => {
      try {
        const [me, apps, completeness, saved, alerts] = await Promise.all([
          api.getMe(),
          api.getApplications(),
          api.getProfileCompleteness(),
          api.getSavedJobs(),
          api.getJobAlerts(),
        ]);
        setSkills(me.skills || []);
        setApplications(apps.applications);
        setSavedJobs(saved.jobs);
        setJobAlerts(alerts.alerts);
        setProfileCompleteness(completeness);
        setEditName(me.name);
        setEditPS(me.program_studi || '');
        setEditUni(me.university || '');
      } catch { /* silently fail */ }
    })();
  }, [user, authLoading, router]);

  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    if (!editing || !newSkill.trim()) return;

    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setSkillSuggestionsLoading(true);
      void api.searchSkills(
        newSkill.trim(),
        { limit: 20, exclude: skills.map((skill) => skill.skill) },
        controller.signal,
      )
        .then((response) => setSkillSuggestions(response.skills))
        .catch(() => setSkillSuggestions([]))
        .finally(() => setSkillSuggestionsLoading(false));
    }, 160);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [editing, newSkill, skills]);

  const handleSave = async (): Promise<boolean> => {
    setSaving(true);
    setSaveError(null);
    try {
      const skillNames = skills.map((s) => s.skill);
      if (newSkill.trim()) skillNames.push(newSkill.trim());
      await api.updateProfile({ name: editName, program_studi: editPS, university: editUni, skills: skillNames });
      // Gateway has already invalidated the pipeline cache by the time this
      // resolves, so refreshing the auth context is enough to surface the new
      // skills. Callers can route to /recommendations?refresh=... to force the
      // recommendation page to re-fetch with the updated profile.
      await refreshUser();
      setProfileCompleteness(await api.getProfileCompleteness());
      setEditing(false);
      setNewSkill('');
      setSkillSuggestions([]);
      return true;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Gagal menyimpan profil. Coba lagi.';
      setSaveError(message);
      return false;
    } finally {
      setSaving(false);
    }
  };

  const handleSaveAndShowRecommendations = async () => {
    const ok = await handleSave();
    if (ok) router.push(`/recommendations?refresh=${Date.now()}`);
  };

  const handleNewSkillChange = (value: string) => {
    setNewSkill(value);
    if (!value.trim()) {
      setSkillSuggestions([]);
      setSkillSuggestionsLoading(false);
    }
  };

  const addSkill = (skillName?: string) => {
    const selectedSkill = skillName || skillSuggestions[0]?.name || newSkill.trim();
    if (!selectedSkill) return;
    const exists = skills.some((item) => item.skill.toLowerCase() === selectedSkill.toLowerCase());
    if (exists) {
      setNewSkill('');
      setSkillSuggestions([]);
      return;
    }
    setSkills((prev) => [...prev, { skill: selectedSkill, category: 'technical', proficiency_level: 'intermediate' }]);
    setNewSkill('');
    setSkillSuggestions([]);
  };

  const selectSkillSuggestion = (skill: SkillSearchItem) => addSkill(skill.name);

  const removeSkill = (skill: string) => setSkills((prev) => prev.filter((s) => s.skill !== skill));

  const handleCvUpload = async (file: File | null) => {
    if (!file) return;
    setCvUploading(true);
    setCvUploadError(null);
    setCvUploadResult(null);
    try {
      const result = await api.uploadCv(file);
      setCvUploadResult(result);
      const [me, completeness] = await Promise.all([
        api.getMe(),
        api.getProfileCompleteness(),
      ]);
      setSkills(me.skills || []);
      setProfileCompleteness(completeness);
      await refreshUser();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Gagal mengunggah CV/Resume.';
      setCvUploadError(message);
    } finally {
      setCvUploading(false);
    }
  };

  const handleAlertMinMatchPercent = (value: string) => {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) {
      setAlertMinMatchPercent(0);
      return;
    }
    setAlertMinMatchPercent(Math.max(0, Math.min(100, parsed)));
  };

  const createJobAlert = async () => {
    if (!alertName.trim()) {
      setAlertError('Nama alert wajib diisi.');
      return;
    }
    setAlertSaving(true);
    setAlertError(null);
    try {
      const created = await api.createJobAlert({
        name: alertName.trim(),
        query: alertQuery.trim() || null,
        location: alertLocation.trim() || null,
        min_match_percent: alertMinMatchPercent,
        frequency: alertFrequency,
      });
      setJobAlerts((prev) => [created, ...prev.filter((alert) => alert.id !== created.id)]);
      setAlertName('');
      setAlertQuery('');
      setAlertLocation('');
      setAlertMinMatchPercent(60);
      setAlertFrequency('daily');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Gagal membuat job alert. Coba lagi.';
      setAlertError(message);
    } finally {
      setAlertSaving(false);
    }
  };

  const disableJobAlert = async (alertId: number) => {
    setDisablingAlertId(alertId);
    setAlertError(null);
    try {
      await api.disableJobAlert(alertId);
      setJobAlerts((prev) => prev.filter((alert) => alert.id !== alertId));
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Gagal menonaktifkan job alert. Coba lagi.';
      setAlertError(message);
    } finally {
      setDisablingAlertId(null);
    }
  };

  if (authLoading || !user) {
    return <CareerLoading fullScreen title="Memuat Profil" />;
  }

  const completionPercent = profileCompleteness?.percent ?? user.completion_percent;
  const completionItems = profileCompleteness?.items ?? [];
  const completedCount = profileCompleteness?.completed_item_ids.length ?? 0;
  const missingCount = profileCompleteness?.missing_item_ids.length ?? 0;

  return (
    <AppLayout pageTitle="My Profile">
      <PageHeader
        title="Profil Saya"
        subtitle="Kelola profil, skill, alert, dan bukti kesiapan kariermu."
        actions={(
          <Button variant="danger" size="sm" onClick={() => { logout(); router.push('/auth'); }}>
            Logout
          </Button>
        )}
      />

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="relative z-20 mb-6"
      >
        <GlassCard>
          <div className="flex items-start gap-4 mb-6">
            <Avatar name={user.name} size="lg" />
            <div className="flex-1">
              {editing ? (
                <EditField
                  value={editName}
                  onChange={setEditName}
                  className="text-base font-bold mb-1"
                />
              ) : (
                <h3 className="text-base font-bold text-[var(--text-primary)]">{user.name}</h3>
              )}
              <p className="text-sm text-[var(--text-secondary)]">{user.email}</p>
              <div className="flex items-center gap-2 mt-1">
                <Badge variant="blue">{user.role}</Badge>
                <span className="text-xs text-[var(--text-secondary)]">{completionPercent}% lengkap</span>
              </div>
            </div>
            <div className="flex flex-col gap-2 items-end">
              <Button onClick={() => editing ? void handleSave() : setEditing(true)} loading={saving} size="sm">
                {saving ? 'Menyimpan...' : editing ? 'Simpan' : 'Edit'}
              </Button>
              {editing && (
                <Button
                  onClick={() => void handleSaveAndShowRecommendations()}
                  loading={saving}
                  size="sm"
                  variant="ghost"
                >
                  Simpan & Lihat Rekomendasi
                </Button>
              )}
            </div>
          </div>
          {saveError && (
            <p className="text-xs mb-4 text-red-400" role="alert">{saveError}</p>
          )}

          <div className="grid md:grid-cols-2 gap-4 mb-6">
            <div>
              <p className="text-xs mb-2 tracking-widest text-[var(--text-tertiary)]">PROGRAM STUDI</p>
              {editing
                ? <EditField value={editPS} onChange={setEditPS} placeholder="e.g. Teknik Informatika" />
                : <p className="text-sm text-[var(--text-primary)]">{user.program_studi || '—'}</p>}
            </div>
            <div>
              <p className="text-xs mb-2 tracking-widest text-[var(--text-tertiary)]">UNIVERSITAS</p>
              {editing
                ? <EditField value={editUni} onChange={setEditUni} placeholder="e.g. Universitas Indonesia" />
                : <p className="text-sm text-[var(--text-primary)]">{user.university || '—'}</p>}
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <div>
                <p className="text-xs tracking-widest text-[var(--text-tertiary)]">PROFIL LENGKAP</p>
                {profileCompleteness && (
                  <p className="mt-1 text-xs text-[var(--text-secondary)]">
                    {completedCount} selesai · {missingCount} belum lengkap
                  </p>
                )}
              </div>
              <p className="text-sm font-semibold" style={{ color: colors.success }}>{completionPercent}%</p>
            </div>
            <div className="scpa-progress-track h-1.5 w-full overflow-hidden rounded-full">
              <div
                className="h-full rounded-full bg-gradient-to-r from-blue-600 to-cyan-300 transition-all duration-700"
                style={{ width: `${completionPercent}%` }}
              />
            </div>
            {completionItems.length > 0 && (
              <div className="mt-4 grid gap-2 sm:grid-cols-2">
                {completionItems.map((item) => (
                  <div
                    key={item.id}
                    className="flex min-w-0 items-center gap-2 text-xs text-[var(--text-secondary)]"
                  >
                    <span
                      aria-hidden="true"
                      className={`h-2 w-2 shrink-0 rounded-full ${item.completed ? 'bg-emerald-400' : 'bg-[var(--text-tertiary)]'}`}
                    />
                    <span className="truncate">{item.label}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </GlassCard>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="relative z-30 mb-6"
      >
        <CvUploadCard
          completeness={profileCompleteness}
          uploading={cvUploading}
          error={cvUploadError}
          result={cvUploadResult}
          onUpload={(file) => void handleCvUpload(file)}
        />
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.25 }}
        className="relative z-40 mb-6"
      >
        <SkillsCard
          skills={skills}
          editing={editing}
          newSkill={newSkill}
          suggestions={skillSuggestions}
          suggestionsLoading={skillSuggestionsLoading}
          onNewSkill={handleNewSkillChange}
          onRemove={removeSkill}
          onAdd={addSkill}
          onSelectSuggestion={selectSkillSuggestion}
        />
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="relative z-10 mb-6"
      >
        <JobAlertsCard
          alerts={jobAlerts}
          name={alertName}
          query={alertQuery}
          location={alertLocation}
          minMatchPercent={alertMinMatchPercent}
          frequency={alertFrequency}
          saving={alertSaving}
          error={alertError}
          disablingAlertId={disablingAlertId}
          onName={setAlertName}
          onQuery={setAlertQuery}
          onLocation={setAlertLocation}
          onMinMatchPercent={handleAlertMinMatchPercent}
          onFrequency={setAlertFrequency}
          onCreate={() => void createJobAlert()}
          onDisable={(alertId) => void disableJobAlert(alertId)}
        />
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
        className="mb-6"
      >
        <SavedJobsCard jobs={savedJobs} />
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
      >
        <ApplicationsCard applications={applications} />
      </motion.div>
    </AppLayout>
  );
}
