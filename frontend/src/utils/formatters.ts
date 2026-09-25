/**
 * Number and string formatting utilities.
 */

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return '0';
  return new Intl.NumberFormat().format(value);
}

export function extractDomain(url: string): string {
  try {
    const parsed = new URL(url);
    return parsed.hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
}

export function formatPeopleCount(count: number | string): string {
  if (typeof count === 'number') {
    return formatNumber(count);
  }
  return count || 'N/A';
}
