'use client';

import React from 'react';

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  breadcrumb?: React.ReactNode;
  actions?: React.ReactNode;
}

export const PageHeader: React.FC<PageHeaderProps> = ({
  title,
  subtitle,
  breadcrumb,
  actions,
}) => {
  return (
    <div className="scpa-page-hero relative mb-8 w-full overflow-hidden rounded-2xl p-5 md:p-6">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_14%_0%,rgba(34,211,238,0.12),transparent_34%),linear-gradient(135deg,rgba(255,255,255,0.07),transparent_38%)]"
      />
      <div className="relative">
        {breadcrumb && (
          <div className="mb-4 text-sm" style={{ color: 'var(--text-secondary)' }}>{breadcrumb}</div>
        )}
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <h1 className="mb-2 text-[clamp(1.65rem,3.2vw,2.6rem)] font-black tracking-tight">{title}</h1>
            {subtitle && <p className="max-w-3xl text-sm leading-relaxed md:text-base">{subtitle}</p>}
          </div>
          {actions && <div className="flex shrink-0 gap-3">{actions}</div>}
        </div>
      </div>
    </div>
  );
};
