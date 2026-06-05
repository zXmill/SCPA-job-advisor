'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { AppLayout } from '@/components/AppLayout';
import { GlassCard, Button, Badge, MatchScore, CompanyLogo } from '@/components/ui';
import { CareerLoading } from '@/components/ui/career-loading';
import { useAuth } from '@/lib/auth-context';
import { api, RecommendationData, ApplicationData, SkillData, UserData, ProfileCompletenessResponse } from '@/lib/api';
import { formatJobType, formatEmploymentMode, formatSalary } from '@/lib/formatters';
import { colors, animation } from '@/lib/design-tokens';

interface ActivityItem {
  id: string;
  label: string;
  timestamp: string;
  color: string;
}

interface DashboardData {
  recommendations: RecommendationData[];
  applications: ApplicationData[];
  skills: SkillData[];
  profileCompleteness: ProfileCompletenessResponse | null;
}

function formatRelative(iso: string | null): string {
  if (!iso) return '';
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '';
  const diffMs = Date.now() - then;
  const min = Math.floor(diffMs / 60000);
  if (min < 1) return 'Baru saja';
  if (min < 60) return `${min} menit lalu`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr} jam lalu`;
  const days = Math.floor(hr / 24);
  if (days < 30) return `${days} hari lalu`;
  return new Date(iso).toLocaleDateString('id-ID');
}

const STATUS_COLOR: Record<string, 'green' | 'blue' | 'amber' | 'gray' | 'red'> = {
  submitted: 'blue',
  reviewed: 'amber',
  accepted: 'green',
  rejected: 'red',
  draft: 'gray',
};

async function fetchDashboardData(
  currentUser: UserData,
  setData: React.Dispatch<React.SetStateAction<DashboardData>>,
  setLoadError: React.Dispatch<React.SetStateAction<string | null>>,
  setLoadingData: React.Dispatch<React.SetStateAction<boolean>>,
  cancelledRef: { current: boolean }
) {
  setLoadingData(true);
  setLoadError(null);
  try {
    const [recsRes, appsRes, completenessRes] = await Promise.allSettled([
      api.getRecommendations(),
      api.getApplications(),
      api.getProfileCompleteness(),
    ]);
    if (cancelledRef.current) return;

    const recommendations = recsRes.status === 'fulfilled' ? recsRes.value.recommendations ?? [] : [];
    const applications = appsRes.status === 'fulfilled' ? appsRes.value.applications ?? [] : [];
    const profileCompleteness = completenessRes.status === 'fulfilled' ? completenessRes.value : null;
    const skills = currentUser.skills ?? [];

    setData({ recommendations, applications, skills, profileCompleteness });

    if ([recsRes, appsRes, completenessRes].some((r) => r.status === 'rejected')) {
      setLoadError('Sebagian data tidak dapat dimuat. Silakan refresh untuk mencoba lagi.');
    }
  } catch (e) {
    if (!cancelledRef.current) {
      setLoadError(e instanceof Error ? e.message : 'Gagal memuat dashboard');
    }
  } finally {
    if (!cancelledRef.current) setLoadingData(false);
  }
}

function getRecommendedCompanies(recommendations: RecommendationData[]) {
  const seen = new Set<string>();
  const out: { name: string; jobs: number }[] = [];
  for (const rec of recommendations) {
    const c = rec.job.company;
    if (!c || seen.has(c)) continue;
    seen.add(c);
    const count = recommendations.filter((r) => r.job.company === c).length;
    out.push({ name: c, jobs: count });
    if (out.length >= 6) break;
  }
  return out;
}

interface WelcomeHeaderProps {
  firstName: string;
  recCount: number;
  completionPercent: number;
  loadError: string | null;
}

const WelcomeHeader = ({ firstName, recCount, completionPercent, loadError }: WelcomeHeaderProps) => (
  <motion.div
    initial={animation.pageEntrance.initial}
    animate={animation.pageEntrance.animate}
    transition={animation.pageEntrance.transition}
    className="scpa-page-hero relative mb-8 overflow-hidden rounded-2xl p-6"
  >
    <div aria-hidden className="absolute inset-0 bg-[radial-gradient(circle_at_16%_0%,rgba(34,211,238,0.13),transparent_34%),linear-gradient(135deg,rgba(37,99,235,0.12),transparent_46%)]" />
    <div className="relative flex items-center justify-between gap-6 flex-wrap">
      <div>
        <h1 className="text-2xl md:text-3xl font-bold mb-2 text-[var(--text-primary)]">Halo, {firstName}</h1>
        <p className="text-[var(--text-secondary)]">
          {recCount > 0 ? `Kamu punya ${recCount} rekomendasi berdasarkan profilmu.` : 'Lengkapi profilmu agar SCPA bisa menemukan lowongan yang cocok.'}
        </p>
        {loadError && <p className="mt-2 text-xs text-[var(--primary)]">{loadError}</p>}
      </div>
      <div className="hidden md:flex items-center gap-4">
        <div className="text-center">
          <MatchScore score={completionPercent} size="lg" />
          <p className="text-xs mt-2 text-[var(--text-secondary)]">Profil Lengkap</p>
          {completionPercent < 100 && (
            <Link href="/profile" className="text-xs text-[var(--primary)] hover:underline">Lengkapi profilmu →</Link>
          )}
        </div>
      </div>
    </div>
  </motion.div>
);

const RecsLoading = () => (
  <CareerLoading
    title="Memuat Karierku"
    messages={[
      'Membaca profil dan skill',
      'Mengambil rekomendasi terbaru',
      'Menyusun ringkasan aktivitas',
    ]}
  />
);

interface RecCardProps {
  rec: RecommendationData;
  index: number;
}

const RecCard = ({ rec, index }: RecCardProps) => {
  const salary = formatSalary(rec.job.min_salary, rec.job.max_salary);
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1 + index * 0.06 }}
    >
      <GlassCard glow href={`/jobs/${rec.job.id}`}>
        <div className="flex items-start gap-3 mb-3">
          <CompanyLogo logoUrl={rec.job.company_logo} companyName={rec.job.company} size={40} />
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold truncate text-[var(--text-primary)]">{rec.job.title}</h3>
            <p className="text-sm truncate text-[var(--text-secondary)]">
              {rec.job.company}{rec.job.location ? ` • ${rec.job.location}` : ''}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2 mb-3">
          {rec.job.type && <Badge variant="blue">{formatJobType(rec.job.type)}</Badge>}
          {rec.job.employment_mode && <Badge variant="purple">{formatEmploymentMode(rec.job.employment_mode)}</Badge>}
          {rec.job.experience_level && <Badge variant="gray">{rec.job.experience_level}</Badge>}
          {rec.job.source && <Badge variant="amber">{rec.job.source}</Badge>}
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-[var(--text-primary)]">{salary ?? '—'}</span>
          <MatchScore score={rec.match_percent} size="sm" />
        </div>
      </GlassCard>
    </motion.div>
  );
};

interface RecentActivityProps {
  recentActivity: ActivityItem[];
}

const RecentActivityList = ({ recentActivity }: RecentActivityProps) => (
  <GlassCard>
    {recentActivity.length === 0 ? (
      <p className="text-sm text-[var(--text-secondary)]">
        Belum ada aktivitas. Mulai melamar untuk melihat riwayatmu di sini.
      </p>
    ) : (
      <ul className="space-y-3">
        {recentActivity.map((item) => (
          <li key={item.id} className="flex items-center gap-3">
            <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: item.color }} />
            <p className="text-sm flex-1 truncate text-[var(--text-primary)]">{item.label}</p>
            <span className="text-xs text-[var(--text-tertiary)]">{item.timestamp}</span>
          </li>
        ))}
      </ul>
    )}
  </GlassCard>
);

interface ProfileCompletionProps {
  completionPercent: number;
  hasName: boolean;
  hasProgram: boolean;
  hasUniversity: boolean;
  hasCv: boolean;
  skillsCount: number;
}

const ProfileCompletionWidget = ({
  completionPercent,
  hasName,
  hasProgram,
  hasUniversity,
  hasCv,
  skillsCount,
}: ProfileCompletionProps) => (
  <GlassCard>
    <h3 className="font-semibold mb-4 text-[var(--text-primary)]">Profil Lengkap</h3>
    <div className="mb-4">
      <div className="flex justify-between text-sm mb-2">
        <span className="text-[var(--text-secondary)]">Overall</span>
        <span className="font-semibold text-[var(--text-primary)]">{completionPercent}%</span>
      </div>
      <div className="scpa-progress-track h-2 w-full overflow-hidden rounded-full">
        <div
          className="h-full rounded-full bg-gradient-to-r from-blue-600 to-cyan-300 transition-all"
          style={{ width: `${completionPercent}%` }}
        />
      </div>
    </div>
    <ul className="space-y-2 mb-4 text-sm">
      <li className="flex items-center justify-between">
        <span className="text-[var(--text-secondary)]">Nama</span>
        <span style={{ color: hasName ? colors.success : 'var(--text-tertiary)' }}>{hasName ? '✓' : '○'}</span>
      </li>
      <li className="flex items-center justify-between">
        <span className="text-[var(--text-secondary)]">Program Studi</span>
        <span style={{ color: hasProgram ? colors.success : 'var(--text-tertiary)' }}>{hasProgram ? '✓' : '○'}</span>
      </li>
      <li className="flex items-center justify-between">
        <span className="text-[var(--text-secondary)]">Universitas</span>
        <span style={{ color: hasUniversity ? colors.success : 'var(--text-tertiary)' }}>{hasUniversity ? '✓' : '○'}</span>
      </li>
      <li className="flex items-center justify-between">
        <span className="text-[var(--text-secondary)]">Keahlian</span>
        <span style={{ color: skillsCount > 0 ? colors.success : 'var(--text-tertiary)' }}>
          {skillsCount > 0 ? `${skillsCount} skill` : '○'}
        </span>
      </li>
      <li className="flex items-center justify-between">
        <span className="text-[var(--text-secondary)]">CV/Resume</span>
        <span style={{ color: hasCv ? colors.success : 'var(--text-tertiary)' }}>{hasCv ? '✓' : '○'}</span>
      </li>
    </ul>
    <Link href="/profile"><Button className="w-full" size="sm">Lengkapi Profil →</Button></Link>
  </GlassCard>
);

interface ApplicationStatusProps {
  applications: ApplicationData[];
  activeApps: number;
}

const ApplicationStatusWidget = ({ applications, activeApps }: ApplicationStatusProps) => (
  <GlassCard>
    <div className="flex items-center justify-between mb-4">
      <h3 className="font-semibold text-[var(--text-primary)]">Lamaranmu</h3>
      <Badge variant="blue">{activeApps} aktif</Badge>
    </div>
    {applications.length === 0 ? (
      <p className="text-sm text-[var(--text-secondary)]">Belum ada lamaran. Lihat rekomendasi untuk mulai melamar.</p>
    ) : (
      <ul className="space-y-3">
        {applications.slice(0, 4).map((app) => (
          <li
            key={app.id}
            className="scpa-list-item flex items-center gap-3 rounded-xl p-3"
          >
            <div
              className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-blue-600 to-cyan-400 text-xs font-bold text-white"
            >
              {app.company.charAt(0).toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate text-[var(--text-primary)]">{app.job_title}</p>
              <p className="text-xs truncate text-[var(--text-tertiary)]">{app.company}</p>
            </div>
            <Badge variant={STATUS_COLOR[app.status] ?? 'gray'}>{app.status}</Badge>
          </li>
        ))}
      </ul>
    )}
    {applications.length > 4 && (
      <Link href="/apply" className="text-sm mt-3 inline-block hover:underline text-[var(--primary)]">
        Lihat semua ({applications.length}) →
      </Link>
    )}
  </GlassCard>
);

interface SuggestedSkillsProps {
  suggestedSkills: string[];
}

const SuggestedSkillsWidget = ({ suggestedSkills }: SuggestedSkillsProps) => (
  <GlassCard>
    <h3 className="font-semibold mb-4 text-[var(--text-primary)]">Disarankan Untuk Dipelajari</h3>
    {suggestedSkills.length === 0 ? (
      <p className="text-sm text-[var(--text-secondary)]">
        Tambahkan keahlian di profilmu agar SCPA dapat menyarankan jalur pembelajaran.
      </p>
    ) : (
      <div className="flex flex-wrap gap-2">
        {suggestedSkills.map((skill, i) => (
          <span
            key={`${skill}-${i}`}
            className="scpa-chip rounded-full px-3 py-1 text-xs font-medium"
          >
            {skill}
          </span>
        ))}
      </div>
    )}
  </GlassCard>
);

interface RecommendedCompaniesProps {
  companies: { name: string; jobs: number }[];
}

const RecommendedCompaniesList = ({ companies }: RecommendedCompaniesProps) => (
  <div className="mt-8">
    <h3 className="text-lg font-semibold mb-4 text-[var(--text-primary)]">Perusahaan dengan Lowongan Cocok</h3>
    <div className="flex gap-4 overflow-x-auto pb-4">
      {companies.map((c) => (
        <GlassCard key={c.name} className="min-w-[200px]">
          <div className="w-12 h-12 rounded-full mb-3 flex items-center justify-center text-xl font-bold text-white bg-[var(--primary)]">
            {c.name.charAt(0).toUpperCase()}
          </div>
          <h4 className="font-semibold mb-1 text-[var(--text-primary)]">{c.name}</h4>
          <p className="text-sm text-[var(--text-secondary)]">{c.jobs} lowongan cocok</p>
        </GlassCard>
      ))}
    </div>
  </div>
);

interface MainSectionProps {
  loadingData: boolean;
  topRecs: RecommendationData[];
  recentActivity: ActivityItem[];
}

const DashboardMainSection = ({ loadingData, topRecs, recentActivity }: MainSectionProps) => (
  <div className="lg:col-span-2 space-y-6">
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold text-[var(--text-primary)]">Rekomendasi Untukmu</h2>
        <Link href="/recommendations" className="text-sm hover:underline text-[var(--primary)]">Lihat semua →</Link>
      </div>
      {loadingData ? (
        <RecsLoading />
      ) : topRecs.length === 0 ? (
        <GlassCard>
          <p className="text-[var(--text-secondary)]">Belum ada rekomendasi. Lengkapi profilmu dan tambahkan keahlian agar AI dapat mencocokkanmu dengan lowongan terbaik.</p>
          <div className="mt-4"><Link href="/onboarding"><Button size="sm">Lengkapi profilmu</Button></Link></div>
        </GlassCard>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {topRecs.map((rec, i) => <RecCard key={rec.job.id} rec={rec} index={i} />)}
        </div>
      )}
    </motion.div>

    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
      <h2 className="text-xl font-semibold mb-4 text-[var(--text-primary)]">Aktivitas Terakhir</h2>
      <RecentActivityList recentActivity={recentActivity} />
    </motion.div>
  </div>
);

interface SidebarSectionProps {
  user: UserData;
  data: DashboardData;
  suggestedSkills: string[];
}

const DashboardSidebarSection = ({ user, data, suggestedSkills }: SidebarSectionProps) => (
  <div className="space-y-6">
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
      <ProfileCompletionWidget
        completionPercent={data.profileCompleteness?.percent ?? user.completion_percent}
        hasName={data.profileCompleteness?.completed_item_ids.includes('name') ?? !!user.name}
        hasProgram={data.profileCompleteness?.completed_item_ids.includes('program_studi') ?? !!user.program_studi}
        hasUniversity={data.profileCompleteness?.completed_item_ids.includes('university') ?? !!user.university}
        hasCv={data.profileCompleteness?.completed_item_ids.includes('cv') ?? Boolean(user.cv_uploaded_at)}
        skillsCount={data.skills.length}
      />
    </motion.div>

    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }}>
      <ApplicationStatusWidget applications={data.applications} activeApps={data.applications.filter((a) => a.status !== 'rejected').length} />
    </motion.div>

    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
      <SuggestedSkillsWidget suggestedSkills={suggestedSkills} />
    </motion.div>
  </div>
);

export default function DashboardPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [data, setData] = useState<DashboardData>({ recommendations: [], applications: [], skills: [], profileCompleteness: null });
  const [loadingData, setLoadingData] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !user) { router.push('/auth'); return; }
    if (!user) return;
    const cancelledRef = { current: false };
    fetchDashboardData(user, setData, setLoadError, setLoadingData, cancelledRef);
    return () => { cancelledRef.current = true; };
  }, [user, authLoading, router]);

  const recentActivity = useMemo(() => data.applications
    .filter((a) => a.applied_at)
    .slice(0, 5)
    .map((a) => ({
      id: a.id,
      label: `Kamu melamar ke ${a.company}`,
      timestamp: formatRelative(a.applied_at),
      color: a.status === 'accepted' ? colors.success : colors.blue400,
    })), [data.applications]);

  const topRecommendations = useMemo(() => data.recommendations.slice(0, 4), [data.recommendations]);
  const recommendedCompanies = useMemo(() => getRecommendedCompanies(data.recommendations), [data.recommendations]);
  const suggestedSkills = useMemo(() => data.skills.slice(0, 6).map((s) => s.skill), [data.skills]);
  const completionPercent = data.profileCompleteness?.percent ?? user?.completion_percent ?? 0;

  if (authLoading || !user) {
    return <CareerLoading fullScreen title="Memuat Karierku" />;
  }

  return (
    <AppLayout pageTitle={undefined}>
      <WelcomeHeader firstName={user.name?.split(' ')[0] ?? 'Kamu'} recCount={data.recommendations.length} completionPercent={completionPercent} loadError={loadError} />
      <div className="grid lg:grid-cols-3 gap-6">
        <DashboardMainSection loadingData={loadingData} topRecs={topRecommendations} recentActivity={recentActivity} />
        <DashboardSidebarSection user={user} data={data} suggestedSkills={suggestedSkills} />
      </div>
      {recommendedCompanies.length > 0 && <RecommendedCompaniesList companies={recommendedCompanies} />}
    </AppLayout>
  );
}
