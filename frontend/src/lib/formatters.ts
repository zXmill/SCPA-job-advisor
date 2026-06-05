export function formatJobType(type: string | null): string | null {
  if (!type) return null;
  const map: Record<string, string> = {
    fulltime: 'Full-time',
    parttime: 'Part-time',
    contract: 'Contract',
    internship: 'Internship',
    freelance: 'Freelance',
  };
  return map[type.toLowerCase()] || type.replace(/[_-]/g, ' ');
}

export function formatEmploymentMode(mode: string | null): string | null {
  if (!mode) return null;
  const map: Record<string, string> = {
    remote: 'Remote',
    hybrid: 'Hybrid',
    onsite: 'On-site',
    'on-site': 'On-site',
  };
  return map[mode.toLowerCase()] || mode;
}

export function formatSalary(min: number | null, max: number | null): string | null {
  if (!min && !max) return null;
  const fmt = (n: number) => `Rp ${(n / 1_000_000).toFixed(0)} jt`;
  if (min && max) return `${fmt(min)} - ${fmt(max)}`;
  return min ? fmt(min) : fmt(max!);
}

export function cleanDescription(text: string | null): string | null {
  if (!text) return null;
  return text
    .replace(/\*{2,}/g, ' ')
    .replace(/#{2,}/g, ' ')
    .replace(/\n{3,}/g, '\n\n')
    .replace(/\t+/g, ' ')
    .replace(/ {2,}/g, ' ')
    .trim();
}
