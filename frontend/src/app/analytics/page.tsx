'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { Briefcase, ChevronDown, MapPin } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { AppLayout } from '@/components/AppLayout';
import { GlassCard, Button, Badge, CompanyLogo, Pagination } from '@/components/ui';
import { PageHeader } from '@/components/ui';
import { CareerLoading } from '@/components/ui/career-loading';
import { useAuth } from '@/lib/auth-context';
import {
  api,
  ApiCancellationError,
  ApiError,
  type AdminModelHealthResponse,
  type AdminModelHealthStage,
  type JobData,
} from '@/lib/api';
import { formatJobType, formatEmploymentMode, formatSalary } from '@/lib/formatters';

const JOBS_PAGE_SIZE = 25;
const JOBS_REQUEST_TIMEOUT_MS = 45_000;
const MODEL_STAGE_ORDER = ['scrape', 'sbert', 'ncf', 'dqn', 'calibrator', 'aggregation'];
const MODEL_LABELS: Record<string, string> = {
  scrape: 'Scraper',
  scraper: 'Scraper',
  sbert: 'SBERT',
  ncf: 'NCF',
  dqn: 'DQN',
  calibrator: 'Calibrator',
  aggregation: 'Aggregation',
};

const formatLatency = (value?: number) => {
  if (typeof value !== 'number') return '-';
  return `${value >= 10 ? value.toFixed(0) : value.toFixed(1)} ms`;
};

const formatCount = (value?: number) => {
  if (typeof value !== 'number') return '0';
  return new Intl.NumberFormat('id-ID').format(value);
};

const modelLabel = (name: string) => MODEL_LABELS[name] || name.toUpperCase();

const statusVariant = (status: string): 'green' | 'amber' | 'red' | 'gray' => {
  const normalized = status.toLowerCase();
  if (['healthy', 'configured', 'active'].includes(normalized)) return 'green';
  if (['degraded', 'inactive', 'unconfigured', 'unknown'].includes(normalized)) return 'amber';
  if (['failed', 'error', 'unhealthy'].includes(normalized)) return 'red';
  return 'gray';
};

interface FilterPanelProps {
  location: string;
  experience: string;
  onChangeLocation: (v: string) => void;
  onChangeExperience: (v: string) => void;
  onFilter: () => void;
}

const FilterPanel = ({
  location,
  experience,
  onChangeLocation,
  onChangeExperience,
  onFilter,
}: FilterPanelProps) => (
  <GlassCard className="scpa-filter-panel">
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(260px,0.78fr)_auto] lg:items-end">
      <div className="min-w-0">
        <label htmlFor="loc" className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--text-tertiary)]">
          LOKASI
        </label>
        <div className="scpa-filter-control">
          <MapPin className="scpa-filter-icon" aria-hidden="true" />
          <input
            id="loc"
            className="scpa-filter-input"
            placeholder="Jakarta, Bandung, Remote..."
            value={location}
            onChange={(e) => onChangeLocation(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') onFilter();
            }}
          />
        </div>
      </div>
      <div className="min-w-0">
        <label htmlFor="exp" className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--text-tertiary)]">
          PENGALAMAN
        </label>
        <div className="scpa-filter-control">
          <Briefcase className="scpa-filter-icon" aria-hidden="true" />
          <select
            id="exp"
            className="scpa-filter-input scpa-filter-select"
            value={experience}
            onChange={(e) => onChangeExperience(e.target.value)}
          >
            <option value="">Semua pengalaman</option>
            <option value="entry">Entry level</option>
            <option value="mid">Mid level</option>
            <option value="senior">Senior level</option>
          </select>
          <ChevronDown className="scpa-filter-chevron" aria-hidden="true" />
        </div>
      </div>
      <div className="lg:pb-[1px]">
        <Button onClick={onFilter} size="md" className="h-12 w-full px-6 lg:w-auto">
          Filter
        </Button>
      </div>
    </div>
  </GlassCard>
);

interface JobCardProps {
  job: JobData;
  index: number;
}

const JobCard = ({ job, index }: JobCardProps) => {
  const salary = formatSalary(job.min_salary, job.max_salary);
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1 + index * 0.05 }}
    >
      <GlassCard glow href={`/jobs/${job.id}`}>
        <div className="flex items-start justify-between mb-3 gap-3">
          <div className="flex items-center gap-3">
            <CompanyLogo logoUrl={job.company_logo} companyName={job.company} size={48} />
            <div>
              <h4 className="font-semibold text-[var(--text-primary)]">{job.title}</h4>
              <p className="text-sm text-[var(--text-secondary)]">{job.company}</p>
            </div>
          </div>
          {job.experience_level && <Badge variant="blue">{job.experience_level}</Badge>}
        </div>

        <div className="flex flex-wrap gap-2 mb-3">
          {job.location && <Badge variant="gray">{job.location}</Badge>}
          {job.type && <Badge variant="gray">{formatJobType(job.type)}</Badge>}
          {job.employment_mode && <Badge variant="purple">{formatEmploymentMode(job.employment_mode)}</Badge>}
          {job.source && <Badge variant="amber">{job.source}</Badge>}
        </div>

        {salary && (
          <div className="mb-3">
            <p className="text-xs text-[var(--text-tertiary)]">Salary</p>
            <p className="text-sm font-medium text-[var(--text-primary)]">{salary}/month</p>
          </div>
        )}

        {job.description && (
          <p className="text-sm line-clamp-2 mb-4 text-[var(--text-secondary)]">{job.description}</p>
        )}

        <div className="flex items-center justify-between border-t border-cyan-200/12 pt-3">
          <span className="text-xs text-[var(--text-tertiary)]">
            Posted {job.posted_at ? new Date(job.posted_at).toLocaleDateString() : 'Recently'}
          </span>
          <Button size="sm">Lihat Detail</Button>
        </div>
      </GlassCard>
    </motion.div>
  );
};

interface EmptyStateProps {
  onClear: () => void;
}

const EmptyStateView = ({ onClear }: EmptyStateProps) => (
  <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="text-center py-12">
    <div
      className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full text-lg font-bold text-cyan-100"
      style={{ backgroundColor: 'rgba(34,211,238,0.12)', border: '1px solid rgba(103,232,249,0.25)' }}
    >
      ?
    </div>
    <h3 className="text-lg font-semibold mb-2 text-[var(--text-primary)]">Tidak ada lowongan ditemukan</h3>
    <p className="text-sm mb-4 text-[var(--text-secondary)]">Coba ubah filter pencarian atau periksa kembali nanti.</p>
    <Button onClick={onClear} size="sm" variant="ghost">Clear Filters</Button>
  </motion.div>
);

interface AdminModelHealthPanelProps {
  health: AdminModelHealthResponse | null;
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
}

const AdminModelHealthPanel = ({
  health,
  loading,
  error,
  onRefresh,
}: AdminModelHealthPanelProps) => {
  const services = health
    ? MODEL_STAGE_ORDER
        .map((stageName) => (stageName === 'scrape' ? 'scraper' : stageName))
        .filter((name) => Boolean(health.models[name]))
    : [];
  const stages: Array<[string, AdminModelHealthStage]> = health
    ? MODEL_STAGE_ORDER.reduce<Array<[string, AdminModelHealthStage]>>((items, name) => {
        const stage = health.telemetry?.stages?.[name]
          || health.models[name === 'scrape' ? 'scraper' : name]?.stage;
        if (stage) items.push([name, stage]);
        return items;
      }, [])
    : [];
  const training = health?.continual_training;
  const pipelineTarget = health?.pipeline.p95_target_ms ?? health?.telemetry?.p95_target_ms;

  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="mb-6">
      <GlassCard>
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between mb-5">
          <div>
            <p className="text-xs tracking-widest text-[var(--text-tertiary)] mb-1">ADMIN</p>
            <h2 className="text-lg font-semibold text-[var(--text-primary)]">Model Health</h2>
          </div>
          <Button onClick={onRefresh} size="sm" variant="ghost" loading={loading}>
            Segarkan
          </Button>
        </div>

        {loading && !health ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3" role="status" aria-live="polite">
            <span className="sr-only">Memuat model health...</span>
            {Array.from({ length: 3 }).map((_, index) => (
              <div
                key={index}
                className="h-24 animate-pulse rounded-2xl border border-cyan-200/12 bg-white/[0.045]"
              />
            ))}
          </div>
        ) : error && !health ? (
          <div
            className="rounded-2xl border border-red-300/30 bg-red-500/12 p-4 text-sm"
            role="alert"
          >
            <p className="text-[var(--text-secondary)]">{error}</p>
          </div>
        ) : health ? (
          <div className="space-y-5">
            {error && (
              <div
                className="rounded-2xl border border-cyan-300/24 bg-cyan-300/10 p-3 text-sm"
                role="alert"
              >
                <p className="text-[var(--text-secondary)]">{error}</p>
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div className="border-b border-cyan-200/12 py-3 md:border-b-0 md:border-r">
                <p className="text-xs text-[var(--text-tertiary)] mb-1">Pipeline</p>
                <div className="flex items-center gap-2 mb-1">
                  <Badge variant={statusVariant(health.pipeline.status)}>{health.pipeline.status}</Badge>
                  {health.pipeline.mode && <span className="text-xs text-[var(--text-secondary)]">{health.pipeline.mode}</span>}
                </div>
                <p className="text-xs text-[var(--text-tertiary)]">Target p95 {formatLatency(pipelineTarget ?? undefined)}</p>
              </div>
              <div className="border-b border-cyan-200/12 py-3 md:border-b-0 md:border-r">
                <p className="text-xs text-[var(--text-tertiary)] mb-1">Telemetry Window</p>
                <p className="text-xl font-semibold text-[var(--text-primary)]">{formatCount(health.telemetry?.window_size)}</p>
                <p className="text-xs text-[var(--text-tertiary)]">events retained</p>
              </div>
              <div className="py-3">
                <p className="text-xs text-[var(--text-tertiary)] mb-1">Training Cycles</p>
                <div className="flex items-center gap-2">
                  <p className="text-xl font-semibold text-[var(--text-primary)]">{formatCount(training?.cycles)}</p>
                  <Badge variant={training?.enabled ? 'green' : 'gray'}>{training?.enabled ? 'enabled' : 'paused'}</Badge>
                </div>
                {training?.last_error && <p className="text-xs text-[var(--alert)] mt-1">{training.last_error}</p>}
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div>
                <h3 className="text-sm font-semibold mb-3 text-[var(--text-primary)]">Services</h3>
                <div className="space-y-3">
                  {services.map((name) => {
                    const service = health.models[name];
                    return (
                      <div key={name} className="flex items-center justify-between gap-3 border-b border-cyan-200/12 pb-3 last:border-b-0">
                        <div className="min-w-0">
                          <p className="text-sm font-medium text-[var(--text-primary)]">{modelLabel(name)}</p>
                          <p className="text-xs truncate text-[var(--text-tertiary)]">{service.url || 'internal'}</p>
                        </div>
                        <Badge variant={statusVariant(service.status)}>{service.status}</Badge>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div>
                <h3 className="text-sm font-semibold mb-3 text-[var(--text-primary)]">Stage Latency</h3>
                <div className="space-y-3">
                  {stages.map(([name, stage]) => (
                    <div key={name} className="grid grid-cols-[1fr_auto_auto_auto] items-center gap-3 border-b border-cyan-200/12 pb-3 last:border-b-0">
                      <p className="text-sm font-medium text-[var(--text-primary)]">{modelLabel(name)}</p>
                      <p className="text-xs text-[var(--text-tertiary)]">{formatCount(stage.count)}x</p>
                      <p className="text-xs text-[var(--text-secondary)]">p50 {formatLatency(stage.p50_ms)}</p>
                      <p className="text-xs text-[var(--text-secondary)]">p95 {formatLatency(stage.p95_ms)}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        ) : null}
      </GlassCard>
    </motion.div>
  );
};

export default function AnalyticsPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [jobs, setJobs] = useState<JobData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [locationFilter, setLocationFilter] = useState('');
  const [expFilter, setExpFilter] = useState('');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [modelHealth, setModelHealth] = useState<AdminModelHealthResponse | null>(null);
  const [modelHealthLoading, setModelHealthLoading] = useState(false);
  const [modelHealthError, setModelHealthError] = useState<string | null>(null);
  const inflightController = useRef<AbortController | null>(null);
  const jobsRequestSeq = useRef(0);
  const modelHealthController = useRef<AbortController | null>(null);
  const isAdmin = (user?.role || '').toLowerCase() === 'admin';

  const fetchJobs = useCallback(
    async (opts: { loc?: string; exp?: string; page?: number } = {}) => {
      const requestSeq = jobsRequestSeq.current + 1;
      jobsRequestSeq.current = requestSeq;
      inflightController.current?.abort();
      const controller = new AbortController();
      inflightController.current = controller;
      let didTimeout = false;
      const timeoutId = window.setTimeout(
        () => {
          didTimeout = true;
          controller.abort();
        },
        JOBS_REQUEST_TIMEOUT_MS,
      );
      const isCurrentRequest = () => (
        inflightController.current === controller && jobsRequestSeq.current === requestSeq
      );

      const targetPage = opts.page ?? page;
      setLoading(true);
      setError(null);
      try {
        const data = await api.getJobs(
          {
            location: opts.loc,
            experience: opts.exp,
            page: targetPage,
            limit: JOBS_PAGE_SIZE,
          },
          controller.signal,
        );
        if (!isCurrentRequest()) return;
        setJobs(data.jobs);
        setTotal(data.total ?? data.jobs.length);
        setTotalPages(Math.max(1, data.total_pages ?? 1));
        setPage(data.page ?? targetPage);
      } catch (err) {
        if (!isCurrentRequest()) return;
        if (controller.signal.aborted || err instanceof ApiCancellationError) {
          if (!didTimeout) return;
          setError('Permintaan kehabisan waktu. Coba lagi.');
        } else if (err instanceof ApiError) {
          setError(err.message);
        } else {
          setError('Gagal memuat lowongan. Coba lagi.');
        }
        setJobs([]);
      } finally {
        window.clearTimeout(timeoutId);
        if (isCurrentRequest()) {
          inflightController.current = null;
          setLoading(false);
        }
      }
    },
    [page],
  );

  const fetchModelHealth = useCallback(async () => {
    modelHealthController.current?.abort();
    const controller = new AbortController();
    modelHealthController.current = controller;

    setModelHealthLoading(true);
    setModelHealthError(null);
    try {
      const data = await api.getAdminModelHealth(controller.signal);
      setModelHealth(data);
    } catch (err) {
      if (controller.signal.aborted) return;
      if (err instanceof ApiError) {
        setModelHealthError(err.message);
      } else {
        setModelHealthError('Gagal memuat model health.');
      }
    } finally {
      if (modelHealthController.current === controller) {
        modelHealthController.current = null;
        setModelHealthLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    if (!authLoading && !user) { router.push('/auth'); return; }
    if (!user) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void fetchJobs({ page: 1 });
    if (isAdmin) {
      void fetchModelHealth();
    }
    return () => {
      const jobsController = inflightController.current;
      if (jobsController) {
        inflightController.current = null;
        jobsController.abort();
      }
      const healthController = modelHealthController.current;
      if (healthController) {
        modelHealthController.current = null;
        healthController.abort();
      }
    };
    // fetchJobs reference depends on `page`, so we only rerun on user/auth.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, authLoading, router, isAdmin, fetchModelHealth]);

  const handleFilter = () => {
    setPage(1);
    void fetchJobs({ loc: locationFilter, exp: expFilter, page: 1 });
  };

  const clearFilters = () => {
    setLocationFilter('');
    setExpFilter('');
    setPage(1);
    void fetchJobs({ loc: '', exp: '', page: 1 });
  };

  const handlePageChange = (next: number) => {
    if (next === page) return;
    setPage(next);
    void fetchJobs({ loc: locationFilter, exp: expFilter, page: next });
  };

  if (authLoading || !user) {
    return <CareerLoading fullScreen title="Memuat Lowongan Kerja" />;
  }

  return (
    <AppLayout pageTitle="Job Vacancies">
      <PageHeader
        title="Lowongan Kerja"
        subtitle={`Jelajahi lowongan terbaru — ${total} posisi tersedia`}
      />

      {isAdmin && (
        <AdminModelHealthPanel
          health={modelHealth}
          loading={modelHealthLoading}
          error={modelHealthError}
          onRefresh={() => void fetchModelHealth()}
        />
      )}

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="mb-6"
      >
        <FilterPanel
          location={locationFilter}
          experience={expFilter}
          onChangeLocation={setLocationFilter}
          onChangeExperience={setExpFilter}
          onFilter={handleFilter}
        />
      </motion.div>

      {loading ? (
        <CareerLoading
          title="Memuat Lowongan Kerja"
          messages={[
            'Mengambil data lowongan',
            'Mengecek filter lokasi',
            'Menyiapkan daftar kerja',
          ]}
        />
      ) : error ? (
        <div
          className="rounded-2xl border border-cyan-200/14 bg-white/[0.045] p-12 text-center shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]"
          role="alert"
        >
          <p className="mb-4 text-[var(--text-secondary)]">{error}</p>
          <Button onClick={() => void fetchJobs({ loc: locationFilter, exp: expFilter, page })} size="sm">
            Coba Lagi
          </Button>
        </div>
      ) : jobs.length === 0 ? (
        <EmptyStateView onClear={clearFilters} />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {jobs.map((job, i) => (
            <JobCard key={job.id} job={job} index={i} />
          ))}
        </div>
      )}

      {!loading && !error && totalPages > 1 && (
        <div className="mt-6 flex justify-center">
          <Pagination
            page={page}
            totalPages={totalPages}
            onChange={handlePageChange}
            loading={loading}
          />
        </div>
      )}
    </AppLayout>
  );
}
