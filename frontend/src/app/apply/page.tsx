'use client';

import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { AppLayout } from '@/components/AppLayout';
import { GlassCard, Button, Avatar, CompanyLogo } from '@/components/ui';
import { PageHeader } from '@/components/ui';
import { CareerLoading } from '@/components/ui/career-loading';
import { useAuth } from '@/lib/auth-context';
import { api, JobData, UserData } from '@/lib/api';
import { formatSalary } from '@/lib/formatters';

interface ApplySuccessViewProps {
  count: number;
}

const ApplySuccessView = ({ count }: ApplySuccessViewProps) => (
  <motion.div
    initial={{ opacity: 0, y: 16 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.5 }}
    className="flex items-center justify-center min-h-[60vh]"
  >
    <div className="text-center max-w-md">
      <motion.div
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{ delay: 0.2, type: 'spring', stiffness: 200 }}
        className="w-20 h-20 mx-auto mb-6 rounded-full flex items-center justify-center bg-[rgba(16,185,129,0.1)] border border-[rgba(16,185,129,0.2)]"
      >
        <div className="w-12 h-12 rounded-full flex items-center justify-center bg-[var(--success)]">
          <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
          </svg>
        </div>
      </motion.div>
      <h2 className="text-2xl font-bold mb-2 text-[var(--text-primary)]">Lamaran Terkirim!</h2>
      <p className="text-[var(--success)] font-semibold mb-2">{count} lamaran berhasil dikirim</p>
      <p className="text-sm mb-6 text-[var(--text-secondary)]">Lamaranmu telah disimpan dan dikirim ke perusahaan.</p>
      <div className="flex flex-col sm:flex-row gap-3 justify-center">
        <Link href="/dashboard">
          <Button className="w-full sm:w-auto">Kembali ke Dashboard</Button>
        </Link>
        <Link href="/recommendations">
          <Button variant="ghost" className="w-full sm:w-auto">Lihat Lowongan Lainnya</Button>
        </Link>
      </div>
    </div>
  </motion.div>
);

interface JobListItemProps {
  job: JobData;
  isSelected: boolean;
  onToggle: (id: string) => void;
  index: number;
}

const JobListItem = ({ job, isSelected, onToggle, index }: JobListItemProps) => {
  const salary = formatSalary(job.min_salary, job.max_salary);
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
    >
      <div className="cursor-pointer" onClick={() => onToggle(job.id)}>
        <GlassCard glow={isSelected}>
          <div className="flex items-center gap-3">
            <div
              className={`flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full border transition-colors ${
                isSelected ? 'bg-[var(--primary)] border-[var(--primary)]' : 'border-[#444] bg-[#111]'
              }`}
            >
              {isSelected && (
                <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                </svg>
              )}
            </div>
            <Link href={`/jobs/${job.id}`} onClick={(e) => e.stopPropagation()}>
              <CompanyLogo logoUrl={job.company_logo} companyName={job.company} size={36} />
            </Link>
            <div className="flex-1 min-w-0">
              <h4 className="text-sm font-semibold truncate text-[var(--text-primary)]">{job.title}</h4>
              <p className="text-xs truncate mt-0.5 text-[var(--text-secondary)]">
                {job.company}{job.location ? ` – ${job.location}` : ''}
              </p>
              {salary && <p className="text-xs mt-1 text-[var(--text-tertiary)]">{salary}/month</p>}
            </div>
          </div>
        </GlassCard>
      </div>
    </motion.div>
  );
};

interface ProfileWidgetProps {
  user: UserData;
}

const ProfileWidget = ({ user }: ProfileWidgetProps) => (
  <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
    <GlassCard>
      <h4 className="font-semibold mb-3 text-[var(--text-primary)]">Profil Kamu</h4>
      <div className="flex items-center gap-3 mb-3">
        <Avatar name={user.name} size="md" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold truncate text-[var(--text-primary)]">{user.name}</p>
          <p className="text-xs truncate text-[var(--text-secondary)]">{user.program_studi || 'Belum ditentukan'}</p>
        </div>
      </div>
      <Link href="/profile" className="text-xs text-[var(--primary)] hover:underline font-medium">
        Edit Profil →
      </Link>
    </GlassCard>
  </motion.div>
);

interface ActionWidgetProps {
  selectedCount: number;
  applyState: 'idle' | 'applying' | 'success';
  onApply: () => void;
}

const ActionWidget = ({ selectedCount, applyState, onApply }: ActionWidgetProps) => (
  <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
    <GlassCard>
      <p className="font-semibold text-sm mb-2 text-[var(--text-primary)]">{selectedCount} lowongan dipilih</p>
      {applyState === 'applying' ? (
        <div>
          <div className="mb-3 h-1.5 w-full overflow-hidden rounded-full bg-white/8">
            <div className="h-full animate-pulse rounded-full bg-gradient-to-r from-blue-600 to-cyan-300" style={{ width: '75%' }} />
          </div>
          <p className="text-xs text-center text-[var(--text-secondary)]">Mengirim...</p>
        </div>
      ) : (
        <Button onClick={onApply} disabled={selectedCount === 0} className="w-full">
          Kirim Lamaran
        </Button>
      )}
    </GlassCard>
  </motion.div>
);

export default function ApplyPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [jobs, setJobs] = useState<JobData[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [applyState, setApplyState] = useState<'idle' | 'applying' | 'success'>('idle');
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [applyError, setApplyError] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !user) { router.push('/auth'); return; }
    if (!user) return;
    (async () => {
      try {
        const data = await api.getJobs({ page: 1, limit: 25 });
        setJobs(data.jobs.slice(0, 6));
        if (data.jobs.length > 0) setSelectedIds([data.jobs[0].id]);
      } catch (err) {
        setLoadError(
          err instanceof Error
            ? err.message
            : 'Gagal memuat lowongan untuk dilamar.',
        );
      } finally {
        setLoading(false);
      }
    })();
  }, [user, authLoading, router]);

  const toggleJob = (id: string) =>
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((j) => j !== id) : [...prev, id]));

  const handleApply = async () => {
    setApplyState('applying');
    setApplyError(null);
    try {
      await api.submitApplications(selectedIds);
      setApplyState('success');
    } catch (err) {
      setApplyError(
        err instanceof Error
          ? err.message
          : 'Gagal mengirim lamaran. Coba lagi.',
      );
      setApplyState('idle');
    }
  };

  if (authLoading || !user) {
    return <CareerLoading fullScreen title="Memuat Lamaran" />;
  }

  if (applyState === 'success') {
    return (
      <AppLayout pageTitle="Application Success">
        <ApplySuccessView count={selectedIds.length} />
      </AppLayout>
    );
  }

  return (
    <AppLayout pageTitle="One-Click Application">
      <PageHeader
        title="One-Click Application"
        subtitle="Lamar ke banyak lowongan sekaligus menggunakan profilmu"
      />

      <div className="grid md:grid-cols-5 gap-6">
        <div className="md:col-span-3 space-y-4">
          <h4 className="font-semibold mb-4 text-[var(--text-primary)]">Pilih Lowongan</h4>
          {loadError && (
            <div
              className="rounded-2xl border border-cyan-200/14 bg-white/[0.045] p-4 text-sm text-[var(--text-secondary)]"
              role="alert"
            >
              {loadError}
            </div>
          )}
          {loading ? (
            <div className="space-y-4">
              {[1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="h-20 animate-pulse rounded-2xl border border-cyan-200/12 bg-white/[0.045] p-4"
                />
              ))}
            </div>
          ) : (
            <div className="space-y-4">
              {jobs.map((job, i) => (
                <JobListItem
                  key={job.id}
                  job={job}
                  isSelected={selectedIds.includes(job.id)}
                  onToggle={toggleJob}
                  index={i}
                />
              ))}
            </div>
          )}
        </div>

        <div className="md:col-span-2 space-y-4">
          <ProfileWidget user={user} />
          <ActionWidget
            selectedCount={selectedIds.length}
            applyState={applyState}
            onApply={handleApply}
          />
          {applyError && (
            <p className="text-xs text-red-400" role="alert">
              {applyError}
            </p>
          )}
        </div>
      </div>
    </AppLayout>
  );
}
