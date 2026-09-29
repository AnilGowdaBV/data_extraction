import {
  ExtractionProgress,
  ExtractionSummary,
  StartExtractionPayload,
} from '../types/extraction';
import { API_BASE } from '../config/api';

const EXTRACTION_API = `${API_BASE}/api/extraction`;


export async function startExtraction(
  payload: StartExtractionPayload
): Promise<{ job_id: string; message: string }> {
  const res = await fetch(`${EXTRACTION_API}/start`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: 'Failed to start extraction' }));
    throw new Error(errorData.detail || `Server responded with status ${res.status}`);
  }

  return res.json();
}

export async function stopExtraction(jobId: string): Promise<void> {
  const res = await fetch(`${EXTRACTION_API}/stop/${jobId}`, {
    method: 'POST',
  });
  if (!res.ok) {
    throw new Error('Failed to stop extraction');
  }
}

export async function getExtractionSummary(jobId: string): Promise<ExtractionSummary> {
  const res = await fetch(`${EXTRACTION_API}/summary/${jobId}`);
  if (!res.ok) {
    throw new Error('Failed to load extraction summary');
  }
  return res.json();
}

export function subscribeToProgress(
  jobId: string,
  onUpdate: (data: ExtractionProgress) => void,
  onError: (err: Error) => void
): () => void {
  const eventSource = new EventSource(`${EXTRACTION_API}/progress/${jobId}`);

  eventSource.onmessage = (event) => {
    try {
      const data: ExtractionProgress = JSON.parse(event.data);
      onUpdate(data);

      if (['completed', 'stopped', 'failed'].includes(data.status)) {
        eventSource.close();
      }
    } catch (err) {
      console.error('Failed to parse SSE payload', err);
    }
  };

  eventSource.onerror = (err) => {
    onError(new Error(`SSE connection encountered an error: ${JSON.stringify(err)}`));
    eventSource.close();
  };

  return () => {
    eventSource.close();
  };
}

export interface DatabaseStats {
  total_jobs: number;
  new_today: number;
  total_companies: number;
  sources: {
    instahyre: number;
    himalayas: number;
    other: number;
  };
}

export async function getDatabaseStats(): Promise<DatabaseStats> {
  const res = await fetch(`${API_BASE}/api/database/stats`);
  if (!res.ok) {
    throw new Error('Failed to load database stats');
  }
  return res.json();
}

export function getDatabaseExportUrl(source?: string): string {
  return source ? `${API_BASE}/api/database/export?source=${encodeURIComponent(source)}` : `${API_BASE}/api/database/export`;
}

export interface CategoryOverview {
  id: string;
  name: string;
  filename: string;
  icon: string;
  color: string;
  keywords: string[];
  total_jobs: number;
  under_100_jobs: number;
  keyword_breakdown: Record<string, { total: number; under_100: number }>;
}

export async function getCategoriesOverview(): Promise<CategoryOverview[]> {
  const res = await fetch(`${API_BASE}/api/database/categories`);
  if (!res.ok) {
    throw new Error('Failed to load categories overview');
  }
  return res.json();
}

export function getCategoryExportUrl(categoryId: string): string {
  return `${API_BASE}/api/database/export/category?category_id=${encodeURIComponent(categoryId)}`;
}


