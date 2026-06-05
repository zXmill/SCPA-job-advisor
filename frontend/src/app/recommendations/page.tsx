'use client';

import React, { Suspense, useCallback, useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { AppLayout } from '@/components/AppLayout';
import { GlassCard, Button, Badge, MatchScore, CompanyLogo } from '@/components/ui';
import { PageHeader } from '@/components/ui';
import { CareerLoading } from '@/components/ui/career-loading';
import { useAuth } from '@/lib/auth-context';
import { api, ApiCancellationError, ApiError, RecommendationData } from '@/lib/api';
import { formatJobType, formatEmploymentMode, formatSalary } from '@/lib/formatters';

// Hybrid recommendation calls can include SBERT/pipeline fan-out; keep the
// client timeout above the local gateway/model latency envelope.
const RECOMMENDATION_TIMEOUT_MS = 45_000;

const REASON_SHORT_LABELS: Record<string, string> = {
  semantic_fit: 'Semantic',
  interaction_fit: 'Interact',
  career_signal: 'Career',
  location_fit: 'Location',
  recency: 'Recency',
};

interface AiMethodPanelProps {
  label: string;
  title: string;
  description: string;
}

const AiMethodPanel = ({ label, title, description }: AiMethodPanelProps) => (
  <div
    className="scpa-inner-panel rounded-2xl p-4"
  >
    <Badge variant="amber" className="mb-2">{label}</Badge>
    <p className="text-sm font-medium mt-2 mb-1 text-[var(--text-primary)]">{title}</p>
    <p className="text-xs text-[var(--text-secondary)]">{description}</p>
  </div>
);

interface ScoreBarProps {
  label: string;
  score: number;
}

const ScoreBar = ({ label, score }: ScoreBarProps) => (
  <div className="flex items-center gap-2">
    <Badge variant="amber" className="w-14 justify-center text-xs">{label}</Badge>
    <div className="scpa-progress-track h-1.5 flex-1 overflow-hidden rounded-full">
      <div
        className="h-full rounded-full bg-gradient-to-r from-blue-600 to-cyan-300 transition-all duration-700"
        style={{ width: `${score * 100}%` }}
      />
    </div>
    <span className="text-xs font-semibold w-8 text-right text-[var(--text-secondary)]">
      {Math.round(score * 100)}%
    </span>
  </div>
);

interface RecItemProps {
  rec: RecommendationData;
  index: number;
  slateJobIds: string[];
  onImpression: (jobId: string) => boolean;
  isSaved: boolean;
  actionPending: boolean;
  onSave: (rec: RecommendationData, index: number, slateJobIds: string[]) => void;
  onSkip: (rec: RecommendationData, index: number, slateJobIds: string[]) => void;
  activeSort?: string;
}

const RecItem = ({
  rec,
  index,
  slateJobIds,
  onImpression,
  isSaved,
  actionPending,
  onSave,
  onSkip,
  activeSort,
}: RecItemProps) => {
  const salary = formatSalary(rec.job.min_salary, rec.job.max_salary);
  const sourceUrl = rec.job.source_url;
  const isExternalSource = Boolean(sourceUrl && /^https?:\/\//i.test(sourceUrl));
  const cardRef = React.useRef<HTMLDivElement>(null);
  const dwellTimerRef = React.useRef<number | null>(null);

  const eventContext = {
    recommendation_id: rec.recommendation_id,
    run_id: rec.run_id,
    served_slate_id: rec.recommendation_id,
    slate_job_ids: slateJobIds,
  };

  React.useEffect(() => {
    const node = cardRef.current;
    if (!node) return;

    const emitImpression = () => {
      if (!onImpression(rec.job.id)) return;
      api.trackRecommendationEvent({
        ...eventContext,
        job_id: rec.job.id,
        event: 'impression',
        rank: index,
      }).catch(() => {});
    };

    if (!('IntersectionObserver' in window)) {
      emitImpression();
      return;
    }

    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting && entry.intersectionRatio >= 0.5)) {
        emitImpression();
        observer.disconnect();
      }
    }, { threshold: 0.5 });
    observer.observe(node);
    return () => observer.disconnect();
  }, [rec.job.id, rec.recommendation_id, rec.run_id, index, slateJobIds, onImpression]);

  React.useEffect(() => {
    const node = cardRef.current;
    if (!node || !('IntersectionObserver' in window)) return;
    const observer = new IntersectionObserver((entries) => {
      const visible = entries.some((entry) => entry.isIntersecting && entry.intersectionRatio >= 0.75);
      if (visible && dwellTimerRef.current === null) {
        dwellTimerRef.current = window.setTimeout(() => {
          api.trackRecommendationEvent({
            ...eventContext,
            job_id: rec.job.id,
            event: 'dwell',
            rank: index,
            dwell_ms: 10_000,
          }).catch(() => {});
        }, 10_000);
      } else if (!visible && dwellTimerRef.current !== null) {
        window.clearTimeout(dwellTimerRef.current);
        dwellTimerRef.current = null;
      }
    }, { threshold: 0.75 });
    observer.observe(node);
    return () => {
      observer.disconnect();
      if (dwellTimerRef.current !== null) {
        window.clearTimeout(dwellTimerRef.current);
      }
    };
  }, [rec.job.id, rec.recommendation_id, rec.run_id, index, slateJobIds]);

  const handleClick = () => {
    api.trackRecommendationEvent({
      ...eventContext,
      job_id: rec.job.id,
      event: 'click',
      rank: index,
    }).catch(() => {});
  };

  const handleSourceClick = (e: React.MouseEvent) => {
    if (!isExternalSource) return;
    e.stopPropagation();
    api.trackRecommendationEvent({
      ...eventContext,
      job_id: rec.job.id,
      event: 'source_click',
      rank: index,
    }).catch(() => {});
  };

  const handleSaveClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    if (isSaved || actionPending) return;
    onSave(rec, index, slateJobIds);
  };

  const handleSkipClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    if (actionPending) return;
    onSkip(rec, index, slateJobIds);
  };

  return (
    <motion.div
      ref={cardRef}
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1 + index * 0.05 }}
      onClick={handleClick}
      style={{ cursor: 'pointer' }}
    >
      <GlassCard glow>
        <div className="flex flex-col md:flex-row gap-6">
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-3">
              <Badge variant={rec.match_percent >= 70 ? 'green' : 'gray'}>
                {rec.match_percent}% Match
              </Badge>
              <span className="text-xs text-[var(--text-tertiary)]">{rec.job.source}</span>
            </div>
            <div className="flex items-start gap-3 mb-3">
              <CompanyLogo logoUrl={rec.job.company_logo} companyName={rec.job.company} size={48} />
              <div className="flex-1 min-w-0">
                <h3 className="text-lg font-semibold mb-0.5 text-[var(--text-primary)]">{rec.job.title}</h3>
                <p className="text-sm text-[var(--text-secondary)]">{rec.job.company}</p>
              </div>
            </div>
            <RecMeta rec={rec} salary={salary} />
            {rec.job.description && (
              <p className="text-sm mb-4 line-clamp-2 text-[var(--text-secondary)]">{rec.job.description}</p>
            )}
            {rec.explanation && (
              <p className="text-xs mb-3 text-[var(--text-tertiary)]">{rec.explanation}</p>
            )}
            {sourceUrl && (
              isExternalSource ? (
                <a
                  href={sourceUrl}
                  target="_blank"
                  rel="noreferrer"
                  onClick={handleSourceClick}
                  className="text-xs font-medium text-[var(--primary)] hover:underline"
                >
                  Buka sumber lowongan
                </a>
              ) : (
                <p className="text-xs text-[var(--text-tertiary)]">Sumber: {sourceUrl}</p>
              )
            )}
            <div className="mt-4 flex flex-wrap gap-2">
              <button
                type="button"
                aria-pressed={isSaved}
                disabled={isSaved || actionPending}
                onClick={handleSaveClick}
                className="inline-flex min-h-9 min-w-24 items-center justify-center rounded-full px-3 py-2 text-sm font-semibold transition-all active:scale-95 disabled:cursor-not-allowed disabled:opacity-60"
                style={{
                  color: isSaved ? '#34D399' : 'var(--text-primary)',
                  backgroundColor: isSaved ? 'rgba(16,185,129,0.14)' : 'rgba(255,255,255,0.06)',
                  border: isSaved ? '1px solid rgba(52,211,153,0.35)' : '1px solid rgba(147,197,253,0.16)',
                }}
              >
                {isSaved ? 'Tersimpan' : actionPending ? 'Memproses' : 'Simpan'}
              </button>
              <button
                type="button"
                disabled={actionPending}
                onClick={handleSkipClick}
                className="inline-flex min-h-9 min-w-24 items-center justify-center rounded-full border px-3 py-2 text-sm font-semibold text-[var(--text-secondary)] transition-all hover:bg-[var(--app-control-hover-bg)] hover:text-[var(--text-primary)] active:scale-95 disabled:cursor-not-allowed disabled:opacity-60"
                style={{ backgroundColor: 'var(--app-control-bg)', borderColor: 'var(--app-control-border)' }}
              >
                Lewati
              </button>
            </div>
          </div>
          <RecScoreSidebar rec={rec} index={index} slateJobIds={slateJobIds} activeSort={activeSort} />
        </div>
      </GlassCard>
    </motion.div>
  );
};

const RecMeta = ({ rec, salary }: { rec: RecommendationData; salary: string | null }) => (
  <div className="flex flex-wrap items-center gap-4 text-sm mb-4 text-[var(--text-secondary)]">
    {rec.job.location && <span>{rec.job.location}</span>}
    {rec.job.type && <span>{formatJobType(rec.job.type)}</span>}
    {rec.job.employment_mode && <span>{formatEmploymentMode(rec.job.employment_mode)}</span>}
    {salary && <span>{salary}/month</span>}
  </div>
);

const RecScoreSidebar = ({ rec, index, slateJobIds, activeSort }: { rec: RecommendationData; index: number; slateJobIds: string[]; activeSort?: string }) => (
  <div className="flex flex-col items-center gap-4 min-w-[140px]">
    <MatchScore score={rec.match_percent} size="md" />
    <div className="space-y-2 w-full">
      <ScoreBar label="SBERT" score={rec.sbert_score} />
      <ScoreBar label="NCF" score={rec.ncf_score} />
      <ScoreBar label="DQN" score={rec.dqn_score ?? 0} />
    </div>
    {activeSort && activeSort !== 'match' && activeSort !== 'recent' && rec.reason_filter_scores && rec.reason_filter_scores[activeSort] !== undefined && (
      <div className="w-full border-t border-cyan-200/12 pt-2">
        <ScoreBar label={REASON_SHORT_LABELS[activeSort] || activeSort} score={rec.reason_filter_scores[activeSort]} />
      </div>
    )}
    <Link
      href={`/jobs/${rec.job.id}`}
      onClick={(e) => {
        e.stopPropagation();
        api.trackRecommendationEvent({
          recommendation_id: rec.recommendation_id,
          run_id: rec.run_id,
          served_slate_id: rec.recommendation_id,
          job_id: rec.job.id,
          event: 'view',
          rank: index,
          slate_job_ids: slateJobIds,
        }).catch(() => {});
      }}
      className="mt-2 inline-flex w-full items-center justify-center rounded-full bg-gradient-to-r from-blue-600 to-cyan-400 px-4 py-2 text-sm font-semibold text-white shadow-[0_16px_34px_rgba(37,99,235,0.18)] transition-all hover:brightness-110 active:scale-95"
    >
      Lihat Detail
    </Link>
  </div>
);

const AI_METHODS: AiMethodPanelProps[] = [
  { label: 'SBERT', title: 'Semantic Matching', description: 'Mencocokkan profilmu dengan deskripsi pekerjaan menggunakan model bahasa' },
  { label: 'NCF', title: 'Collaborative Filtering', description: 'Belajar dari pengguna serupa untuk menemukan pola tersembunyi' },
  { label: 'DQN', title: 'Learning Path', description: 'Jalur karier adaptif berdasarkan interaksimu' },
];

function RecommendationsContent() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [recommendations, setRecommendations] = useState<RecommendationData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ message: string; timeout: boolean } | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [savedJobIds, setSavedJobIds] = useState<Set<string>>(() => new Set());
  const [actionPendingJobIds, setActionPendingJobIds] = useState<Set<string>>(() => new Set());
  const [sortBy, setSortBy] = useState('match');
  const inflightController = useRef<AbortController | null>(null);
  const recommendationsRequestSeq = useRef(0);
  const impressedJobs = useRef<Set<string>>(new Set());

  const loadRecommendations = useCallback(async () => {
    // Cancel any in-flight request before starting a new one to avoid
    // resolving the page with stale data when the user retries quickly.
    const requestSeq = recommendationsRequestSeq.current + 1;
    recommendationsRequestSeq.current = requestSeq;
    inflightController.current?.abort();
    const controller = new AbortController();
    inflightController.current = controller;
    let didTimeout = false;
    const timeoutId = window.setTimeout(() => {
      didTimeout = true;
      controller.abort();
    }, RECOMMENDATION_TIMEOUT_MS);
    const isCurrentRequest = () => (
      inflightController.current === controller && recommendationsRequestSeq.current === requestSeq
    );

    setLoading(true);
    setError(null);
    setActionError(null);
    try {
      const [data, saved] = await Promise.all([
        api.getRecommendations(controller.signal),
        api.getSavedJobs(controller.signal).catch(() => ({ jobs: [], total: 0 })),
      ]);
      if (!isCurrentRequest()) return;
      impressedJobs.current.clear();
      setRecommendations(data.recommendations);
      setSavedJobIds(new Set(saved.jobs.map((job) => job.id)));
      setActionPendingJobIds(new Set());
    } catch (err) {
      if (!isCurrentRequest()) return;
      if (controller.signal.aborted || err instanceof ApiCancellationError) {
        if (!didTimeout) return;
        setError({
          message: 'Pencocokan AI memakan waktu terlalu lama. Coba lagi sebentar.',
          timeout: true,
        });
      } else if (err instanceof ApiError) {
        setError({ message: err.message, timeout: err.status === 408 });
      } else {
        setError({
          message: 'Gagal memuat rekomendasi. Silakan coba lagi.',
          timeout: false,
        });
      }
      setRecommendations([]);
    } finally {
      window.clearTimeout(timeoutId);
      if (isCurrentRequest()) {
        inflightController.current = null;
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    if (!authLoading && !user) { router.push('/auth'); return; }
    if (!user) return;
    // Fetch-on-mount is the legitimate use of useEffect that this page
    // exists for; the lint rule only fires because loadRecommendations
    // updates state internally. The dashboard handles this the same way.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadRecommendations();
    return () => {
      const controller = inflightController.current;
      if (controller) {
        inflightController.current = null;
        controller.abort();
      }
    };
    // ``refresh`` query param lets other pages (e.g. profile save) bust the
    // pipeline cache and trigger a fresh fetch when the user navigates here.
  }, [user, authLoading, router, loadRecommendations, searchParams]);

  const markImpressed = useCallback((jobId: string) => {
    if (impressedJobs.current.has(jobId)) return false;
    impressedJobs.current.add(jobId);
    return true;
  }, []);

  const setJobActionPending = useCallback((jobId: string, pending: boolean) => {
    setActionPendingJobIds((prev) => {
      const next = new Set(prev);
      if (pending) next.add(jobId);
      else next.delete(jobId);
      return next;
    });
  }, []);

  const handleSaveJob = useCallback(async (
    rec: RecommendationData,
    index: number,
    slateJobIdsForEvent: string[],
  ) => {
    const jobId = rec.job.id;
    setActionError(null);
    setJobActionPending(jobId, true);
    try {
      await api.saveJob(jobId);
      await api.trackRecommendationEvent({
        recommendation_id: rec.recommendation_id,
        run_id: rec.run_id,
        served_slate_id: rec.recommendation_id,
        job_id: jobId,
        event: 'save',
        rank: index,
        slate_job_ids: slateJobIdsForEvent,
      }).catch(() => {});
      setSavedJobIds((prev) => new Set(prev).add(jobId));
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Gagal menyimpan lowongan. Coba lagi.';
      setActionError(message);
    } finally {
      setJobActionPending(jobId, false);
    }
  }, [setJobActionPending]);

  const handleSkipJob = useCallback(async (
    rec: RecommendationData,
    index: number,
    slateJobIdsForEvent: string[],
  ) => {
    const jobId = rec.job.id;
    setActionError(null);
    setJobActionPending(jobId, true);
    try {
      await api.skipJob(jobId);
      await api.trackRecommendationEvent({
        recommendation_id: rec.recommendation_id,
        run_id: rec.run_id,
        served_slate_id: rec.recommendation_id,
        job_id: jobId,
        event: 'skip',
        rank: index,
        slate_job_ids: slateJobIdsForEvent,
      }).catch(() => {});
      setRecommendations((prev) => prev.filter((item) => item.job.id !== jobId));
      setSavedJobIds((prev) => {
        const next = new Set(prev);
        next.delete(jobId);
        return next;
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Gagal melewati lowongan. Coba lagi.';
      setActionError(message);
    } finally {
      setJobActionPending(jobId, false);
    }
  }, [setJobActionPending]);

  if (authLoading || !user) {
    return <CareerLoading fullScreen title="Memuat Rekomendasi" />;
  }

  const sorted = [...recommendations].sort((a, b) => {
    if (sortBy === 'match') return b.hybrid_score - a.hybrid_score;
    if (sortBy === 'recent') {
      const aTime = a.job.posted_at ? new Date(a.job.posted_at).getTime() : 0;
      const bTime = b.job.posted_at ? new Date(b.job.posted_at).getTime() : 0;
      return bTime - aTime;
    }
    const aScore = a.reason_filter_scores?.[sortBy] ?? 0;
    const bScore = b.reason_filter_scores?.[sortBy] ?? 0;
    return bScore - aScore;
  });
  const slateJobIds = sorted.map((rec) => rec.job.id);

  return (
    <AppLayout pageTitle="AI Recommendations">
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-6">
        <PageHeader
          title="Rekomendasi AI"
          subtitle="Pencocokan lowongan yang dipersonalisasi berdasarkan profilmu"
        />
        <div className="flex items-center gap-3 mt-4 md:mt-0">
          <select
            className="scpa-field rounded-xl px-3 py-2 text-sm"
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
          >
            <option value="match">Match %</option>
            <option value="recent">Terbaru</option>
            <option value="semantic_fit">Semantic Match</option>
            <option value="interaction_fit">Interaction Fit</option>
            <option value="career_signal">Career Signal</option>
            <option value="location_fit">Lokasi</option>
            <option value="recency">Recency</option>
          </select>
        </div>
      </div>

      {actionError && (
        <div
          className="mb-6 rounded-2xl border border-red-300/30 bg-red-500/12 px-4 py-3 text-sm text-red-200"
          role="alert"
        >
          {actionError}
        </div>
      )}

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="mb-6"
      >
        <GlassCard>
          <h3 className="font-semibold mb-4 text-[var(--text-primary)]">Bagaimana rekomendasi bekerja</h3>
          <div className="grid md:grid-cols-3 gap-4">
            {AI_METHODS.map((m) => <AiMethodPanel key={m.label} {...m} />)}
          </div>
        </GlassCard>
      </motion.div>

      {loading ? (
        <CareerLoading
          title="Memuat Rekomendasi"
          messages={[
            'Mengurutkan hybrid score',
            'Memeriksa alasan kecocokan',
            'Menyiapkan daftar lowongan',
          ]}
        />
      ) : error ? (
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          className="scpa-inner-panel rounded-2xl p-12 text-center"
          role="alert"
        >
          <p className="mb-4 text-[var(--text-secondary)]">{error.message}</p>
          <Button onClick={() => void loadRecommendations()} size="sm">
            {error.timeout ? 'Coba Lagi' : 'Muat Ulang'}
          </Button>
        </motion.div>
      ) : sorted.length === 0 ? (
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          className="scpa-inner-panel rounded-2xl p-12 text-center"
        >
          <p className="text-[var(--text-secondary)]">
            Belum ada rekomendasi. Lengkapi profilmu untuk mendapatkan pencocokan yang dipersonalisasi.
          </p>
        </motion.div>
      ) : (
        <div className="space-y-4">
          {sorted.map((rec, i) => (
            <RecItem
              key={rec.job.id}
              rec={rec}
              index={i}
              slateJobIds={slateJobIds}
              onImpression={markImpressed}
              isSaved={savedJobIds.has(rec.job.id)}
              actionPending={actionPendingJobIds.has(rec.job.id)}
              onSave={handleSaveJob}
              onSkip={handleSkipJob}
              activeSort={sortBy}
            />
          ))}
        </div>
      )}
    </AppLayout>
  );
}

function RecommendationsFallback() {
  return <CareerLoading fullScreen title="Memuat Rekomendasi" />;
}

export default function RecommendationsPage() {
  // useSearchParams in App Router triggers client-side rendering up to the
  // nearest Suspense boundary. Wrapping here keeps the rest of the app
  // prerenderable while still letting us read ?refresh=... for cache busts.
  return (
    <Suspense fallback={<RecommendationsFallback />}>
      <RecommendationsContent />
    </Suspense>
  );
}
