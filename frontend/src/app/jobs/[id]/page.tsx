'use client';

import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import Link from 'next/link';
import { useRouter, useParams } from 'next/navigation';
import { AppLayout } from '@/components/AppLayout';
import { GlassCard, Button, Badge, CompanyLogo } from '@/components/ui';
import { CareerLoading } from '@/components/ui/career-loading';
import { useAuth } from '@/lib/auth-context';
import { api, JobData, JobSkillGapResponse } from '@/lib/api';
import { formatJobType, formatEmploymentMode, formatSalary, cleanDescription } from '@/lib/formatters';

interface JobHeaderProps {
  job: JobData;
}

const JobHeader = ({ job }: JobHeaderProps) => (
  <div className="flex items-start gap-4 mb-6">
    <CompanyLogo logoUrl={job.company_logo} companyName={job.company} size={64} />
    <div className="flex-1">
      <h1 className="text-xl font-bold mb-1 text-[var(--text-primary)]">{job.title}</h1>
      <p className="text-base mb-1 text-[var(--text-secondary)]">{job.company}</p>
      <div className="flex flex-wrap gap-2">
        {job.location && <Badge variant="gray">{job.location}</Badge>}
        {job.type && <Badge variant="blue">{formatJobType(job.type)}</Badge>}
        {job.employment_mode && <Badge variant="purple">{formatEmploymentMode(job.employment_mode)}</Badge>}
        {job.source && <Badge variant="amber">{job.source}</Badge>}
        {job.experience_level && <Badge variant="gray">{job.experience_level}</Badge>}
      </div>
    </div>
  </div>
);

interface JobMetaProps {
  salary: string | null;
  salaryText: string | null;
  postedAt: string | null;
  source: string | null;
  job: JobData;
}

const JobMeta = ({ salary, salaryText, postedAt, source, job }: JobMetaProps) => {
  // Prefer numeric range when present, fall back to free-text salary scraped
  // from the source page. Hide the field entirely when neither is available
  // so the layout collapses cleanly instead of rendering an empty cell.
  const salaryDisplay = salary ? `${salary}/month` : salaryText || null;
  const metaItems = [
    { label: 'Tingkat senioritas', value: job.seniority_level },
    { label: 'Jenis pekerjaan', value: job.employment_type },
    { label: 'Fungsi pekerjaan', value: job.job_function },
    { label: 'Industri', value: job.industry },
  ].filter((item) => item.value);

  return (
    <div
      className="mb-6 grid grid-cols-2 gap-4 rounded-2xl border border-cyan-200/14 bg-white/[0.045] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] md:grid-cols-3"
    >
      {salaryDisplay && (
        <div>
          <p className="text-xs mb-1 text-[var(--text-tertiary)]">Gaji</p>
          <p className="font-semibold text-[var(--text-primary)]">{salaryDisplay}</p>
        </div>
      )}
      {postedAt && (
        <div>
          <p className="text-xs mb-1 text-[var(--text-tertiary)]">Diposting</p>
          <p className="font-semibold text-[var(--text-primary)]">
            {new Date(postedAt).toLocaleDateString('id-ID')}
          </p>
        </div>
      )}
      <div>
        <p className="text-xs mb-1 text-[var(--text-tertiary)]">Sumber</p>
        {job.source_url ? (
          <a
            href={job.source_url}
            target="_blank"
            rel="noreferrer"
            className="font-semibold text-[var(--primary)] hover:underline"
          >
            {source || 'Buka sumber'}
          </a>
        ) : (
          <p className="font-semibold text-[var(--text-primary)]">{source || '-'}</p>
        )}
      </div>
      {metaItems.map((item) => (
        <div key={item.label}>
          <p className="text-xs mb-1 text-[var(--text-tertiary)]">{item.label}</p>
          <p className="font-semibold text-[var(--text-primary)]">{item.value}</p>
        </div>
      ))}
    </div>
  );
};

const SkillBadgeList = ({
  skills,
  variant,
  emptyText,
}: {
  skills: string[];
  variant: 'green' | 'amber' | 'gray';
  emptyText: string;
}) => {
  if (skills.length === 0) {
    return <p className="text-xs text-[var(--text-tertiary)]">{emptyText}</p>;
  }

  return (
    <div className="flex flex-wrap gap-2">
      {skills.map((skill) => (
        <Badge key={skill} variant={variant}>
          {skill}
        </Badge>
      ))}
    </div>
  );
};

const SkillGapPanel = ({
  gap,
  error,
}: {
  gap: JobSkillGapResponse | null;
  error: string | null;
}) => {
  if (error) {
    return (
      <section className="mb-6 rounded-2xl border border-cyan-200/14 bg-white/[0.045] p-4">
        <h2 className="font-semibold mb-2 text-[var(--text-primary)]">Skill Gap</h2>
        <p className="text-sm text-[var(--text-secondary)]">{error}</p>
      </section>
    );
  }

  if (!gap) return null;

  const clampedPercent = Math.max(0, Math.min(100, gap.skill_match_percent));

  return (
    <section className="mb-6 rounded-2xl border border-cyan-200/14 bg-white/[0.045] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="font-semibold text-[var(--text-primary)]">Skill Gap</h2>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">{gap.explanation.summary}</p>
        </div>
        <div className="min-w-[120px] text-left sm:text-right">
          <p className="text-2xl font-bold text-[var(--primary)]">{gap.skill_match_percent}%</p>
          <p className="text-xs text-[var(--text-tertiary)]">match skill</p>
        </div>
      </div>

      <div
        className="mb-4 h-2 overflow-hidden rounded-full bg-white/8"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(clampedPercent)}
        aria-label="Skill match percent"
      >
        <div
          className="h-full rounded-full bg-gradient-to-r from-blue-600 to-cyan-300"
          style={{ width: `${clampedPercent}%` }}
        />
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <div>
          <p className="mb-2 text-xs font-semibold uppercase text-[var(--text-tertiary)]">Cocok</p>
          <SkillBadgeList skills={gap.matched_skills} variant="green" emptyText="Belum ada skill yang cocok." />
        </div>
        <div>
          <p className="mb-2 text-xs font-semibold uppercase text-[var(--text-tertiary)]">Perlu Dipelajari</p>
          <SkillBadgeList skills={gap.missing_skills} variant="amber" emptyText="Tidak ada gap skill terdeteksi." />
        </div>
        <div>
          <p className="mb-2 text-xs font-semibold uppercase text-[var(--text-tertiary)]">Syarat Skill</p>
          <SkillBadgeList skills={gap.required_skills} variant="gray" emptyText="Data skill belum tersedia." />
        </div>
        <div>
          <p className="mb-2 text-xs font-semibold uppercase text-[var(--text-tertiary)]">Terekstrak</p>
          <SkillBadgeList skills={gap.extracted_skills || []} variant="gray" emptyText="Belum ada skill tambahan." />
        </div>
      </div>
    </section>
  );
};

const SECTION_LABELS: Array<{ key: keyof NonNullable<JobData['description_sections']>; label: string }> = [
  { key: 'who_we_are', label: 'Who We Are' },
  { key: 'why_join_us', label: 'Why Join Us' },
  { key: 'role_overview', label: 'Role Overview' },
  { key: 'responsibilities', label: 'Job Responsibilities' },
  { key: 'requirements', label: 'Job Requirements' },
  { key: 'nice_to_have', label: 'Nice to Have' },
  { key: 'benefits', label: 'Benefits' },
];

const asList = (value?: string[] | null) => (value || []).filter((item) => item.trim().length > 0);

const DescriptionSection = ({
  title,
  body,
  items,
}: {
  title: string;
  body?: string | null;
  items?: string[];
}) => {
  const visibleItems = asList(items);
  const text = cleanDescription(body || '') || '';
  if (!text && visibleItems.length === 0) return null;

  return (
    <section className="border-t border-cyan-200/12 py-4 first:border-t-0 first:pt-0">
      <h3 className="mb-2 text-sm font-semibold text-[var(--text-primary)]">{title}</h3>
      {visibleItems.length > 0 ? (
        <ul className="list-disc space-y-1 pl-5 text-sm leading-relaxed text-[var(--text-secondary)]">
          {visibleItems.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="text-sm leading-relaxed text-[var(--text-secondary)]">{text}</p>
      )}
    </section>
  );
};

const JobDescriptionPanel = ({ job }: { job: JobData }) => {
  const sections = job.description_sections || {};
  const sectionEntries = SECTION_LABELS.map((section) => ({
    ...section,
    body: sections[section.key],
    items:
      section.key === 'responsibilities'
        ? job.responsibilities
        : section.key === 'requirements'
        ? job.requirements
        : section.key === 'nice_to_have'
        ? job.nice_to_have
        : section.key === 'benefits'
        ? job.benefits
        : undefined,
  }));
  const hasStructuredSections = sectionEntries.some((section) => {
    const itemCount = asList(section.items).length;
    return itemCount > 0 || (cleanDescription(section.body || '') || '').length > 0;
  });
  const description = cleanDescription(job.description_text || job.description || '') || '';

  if (!hasStructuredSections && !description) return null;

  return (
    <div className="mb-6">
      <h2 className="mb-3 font-semibold text-[var(--text-primary)]">Deskripsi Pekerjaan</h2>
      <div className="rounded-2xl border border-cyan-200/14 bg-white/[0.045] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]">
        {hasStructuredSections ? (
          sectionEntries.map((section) => (
            <DescriptionSection
              key={section.key}
              title={section.label}
              body={section.body}
              items={section.items}
            />
          ))
        ) : (
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-[var(--text-secondary)]">
            {description}
          </p>
        )}

        {Boolean(job.required_skills?.length || job.preferred_skills?.length || job.extracted_skills?.length) && (
          <section className="border-t border-cyan-200/12 pt-4">
            <h3 className="mb-3 text-sm font-semibold text-[var(--text-primary)]">Skill Signals</h3>
            <div className="grid gap-4 md:grid-cols-3">
              <div>
                <p className="mb-2 text-xs font-semibold uppercase text-[var(--text-tertiary)]">Required</p>
                <SkillBadgeList skills={job.required_skills || []} variant="amber" emptyText="Belum tersedia." />
              </div>
              <div>
                <p className="mb-2 text-xs font-semibold uppercase text-[var(--text-tertiary)]">Preferred</p>
                <SkillBadgeList skills={job.preferred_skills || []} variant="gray" emptyText="Belum tersedia." />
              </div>
              <div>
                <p className="mb-2 text-xs font-semibold uppercase text-[var(--text-tertiary)]">Extracted</p>
                <SkillBadgeList skills={job.extracted_skills || []} variant="gray" emptyText="Belum tersedia." />
              </div>
            </div>
          </section>
        )}
      </div>
    </div>
  );
};

interface JobCTAProps {
  jobId: string;
}

const JobCTA = ({ jobId }: JobCTAProps) => (
  <div className="flex flex-col gap-3 border-t border-cyan-200/12 pt-4 sm:flex-row">
    <Link href={`/apply?job=${jobId}`} className="flex-1">
      <Button className="w-full">Lamar Sekarang</Button>
    </Link>
    <Link href="/analytics" className="flex-1">
      <Button variant="ghost" className="w-full">
        Kembali
      </Button>
    </Link>
  </div>
);

export default function JobDetailPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const params = useParams();
  const jobId = params.id as string;

  const [job, setJob] = useState<JobData | null>(null);
  const [skillGap, setSkillGap] = useState<JobSkillGapResponse | null>(null);
  const [skillGapError, setSkillGapError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !user) { router.push('/auth'); return; }
    if (!user || !jobId) return;
    (async () => {
      try {
        setSkillGap(null);
        setSkillGapError(null);
        const [data, gapResult] = await Promise.all([
          api.getJob(jobId),
          api.getJobSkillGap(jobId)
            .then((gap) => ({ gap }))
            .catch((err) => ({ error: err instanceof Error ? err.message : 'Gagal memuat skill gap' })),
        ]);
        setJob(data);
        if ('gap' in gapResult) {
          setSkillGap(gapResult.gap);
        } else {
          setSkillGapError(gapResult.error);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Gagal memuat lowongan');
      } finally {
        setLoading(false);
      }
    })();
  }, [user, authLoading, router, jobId]);

  if (authLoading || !user) {
    return <CareerLoading fullScreen title="Memuat Detail Lowongan" />;
  }

  if (loading) {
    return (
      <AppLayout pageTitle="Loading...">
        <div className="max-w-3xl mx-auto">
          <CareerLoading title="Memuat Detail Lowongan" />
        </div>
      </AppLayout>
    );
  }

  if (error || !job) {
    return (
      <AppLayout pageTitle="Not Found">
        <div className="max-w-3xl mx-auto text-center py-12">
          <p className="mb-4 text-[var(--text-secondary)]">{error || 'Lowongan tidak ditemukan'}</p>
          <Link href="/analytics">
            <Button>Kembali ke Lowongan</Button>
          </Link>
        </div>
      </AppLayout>
    );
  }

  const salary = formatSalary(job.min_salary, job.max_salary);

  return (
    <AppLayout pageTitle={job.title}>
      <div className="max-w-3xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <Link href="/analytics" className="text-sm mb-4 inline-block text-[var(--primary)] hover:underline">
            ← Kembali ke daftar lowongan
          </Link>

          <GlassCard>
            <JobHeader job={job} />
            <JobMeta
              salary={salary}
              salaryText={job.salary_text || null}
              postedAt={job.posted_at}
              source={job.source}
              job={job}
            />

            <SkillGapPanel gap={skillGap} error={skillGapError} />

            <JobDescriptionPanel job={job} />

            <JobCTA jobId={job.id} />
          </GlassCard>
        </motion.div>
      </div>
    </AppLayout>
  );
}
