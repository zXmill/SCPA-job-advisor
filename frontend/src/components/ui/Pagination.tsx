'use client';

import React from 'react';

interface PaginationProps {
  page: number;
  totalPages: number;
  onChange: (page: number) => void;
  loading?: boolean;
  className?: string;
}

const ARROW_BUTTON =
  'inline-flex h-9 w-9 items-center justify-center rounded-full border border-cyan-300/20 ' +
  'bg-white/[0.06] text-sm font-semibold text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.08)] ' +
  'transition-all hover:border-cyan-200/40 hover:bg-cyan-300/12 active:scale-95 disabled:cursor-not-allowed disabled:opacity-40';

const INPUT_STYLE: React.CSSProperties = {
  color: 'var(--text-primary)',
  backgroundColor: 'rgba(2,6,23,0.56)',
  border: '1px solid rgba(147,197,253,0.16)',
  outline: 'none',
};

/**
 * Maroon-styled pagination control matching the reference screenshot:
 * `<<` `<` [ page ] `dari N` `>` `>>`. The current-page input lets users
 * jump to any page; values are clamped to [1, totalPages] before firing.
 *
 * The input is intentionally uncontrolled (``key={page}`` resets the local
 * value when the parent commits a new page) so we avoid an effect that just
 * syncs prop -> state, which the React 19 lint rule would flag.
 */
export const Pagination: React.FC<PaginationProps> = ({
  page,
  totalPages,
  onChange,
  loading = false,
  className = '',
}) => {
  const safeTotal = Math.max(1, totalPages);
  const canPrev = !loading && page > 1;
  const canNext = !loading && page < safeTotal;

  const commit = (value: string) => {
    const parsed = Number.parseInt(value, 10);
    if (Number.isNaN(parsed)) return;
    const next = Math.min(safeTotal, Math.max(1, parsed));
    if (next !== page) onChange(next);
  };

  return (
    <nav
      className={`flex items-center gap-2 ${className}`}
      role="navigation"
      aria-label="Pagination"
    >
      <button
        type="button"
        className={ARROW_BUTTON}
        onClick={() => onChange(1)}
        disabled={!canPrev}
        aria-label="Halaman pertama"
      >
        {'\u00ab'}
      </button>
      <button
        type="button"
        className={ARROW_BUTTON}
        onClick={() => onChange(Math.max(1, page - 1))}
        disabled={!canPrev}
        aria-label="Halaman sebelumnya"
      >
        {'\u2039'}
      </button>
      <input
        key={page}
        type="number"
        min={1}
        max={safeTotal}
        defaultValue={page}
        onBlur={(e) => commit(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault();
            commit((e.target as HTMLInputElement).value);
          }
        }}
        className="w-14 rounded-xl py-1.5 text-center text-sm"
        style={INPUT_STYLE}
        aria-label="Nomor halaman"
        disabled={loading}
      />
      <span className="text-xs text-[var(--text-secondary)]">dari {safeTotal}</span>
      <button
        type="button"
        className={ARROW_BUTTON}
        onClick={() => onChange(Math.min(safeTotal, page + 1))}
        disabled={!canNext}
        aria-label="Halaman berikutnya"
      >
        {'\u203a'}
      </button>
      <button
        type="button"
        className={ARROW_BUTTON}
        onClick={() => onChange(safeTotal)}
        disabled={!canNext}
        aria-label="Halaman terakhir"
      >
        {'\u00bb'}
      </button>
    </nav>
  );
};
