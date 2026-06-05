// Lightweight className joiner. Avoids pulling in clsx/tailwind-merge
// for a project that does not already use them.
export type ClassValue =
  | string
  | number
  | null
  | undefined
  | false
  | Record<string, boolean | null | undefined>
  | ClassValue[];

export function cn(...inputs: ClassValue[]): string {
  const out: string[] = [];
  const push = (value: ClassValue): void => {
    if (!value && value !== 0) return;
    if (typeof value === 'string' || typeof value === 'number') {
      out.push(String(value));
      return;
    }
    if (Array.isArray(value)) {
      value.forEach(push);
      return;
    }
    if (typeof value === 'object') {
      for (const key of Object.keys(value)) {
        if ((value as Record<string, boolean | null | undefined>)[key]) {
          out.push(key);
        }
      }
    }
  };
  inputs.forEach(push);
  return out.join(' ');
}
