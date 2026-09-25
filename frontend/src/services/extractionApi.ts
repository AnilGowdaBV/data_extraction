import {
  ExtractionProgress,
  ExtractionSummary,
  StartExtractionPayload,
} from '../types/extraction';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/extraction';

export async function startExtraction(
  payload: StartExtractionPayload
): Promise<{ job_id: string; message: string }> {
  const res = await fetch(`${API_BASE}/start`, {
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
  const res = await fetch(`${API_BASE}/stop/${jobId}`, {
    method: 'POST',
  });
  if (!res.ok) {
    throw new Error('Failed to stop extraction');
  }
}

export async function getExtractionSummary(jobId: string): Promise<ExtractionSummary> {
  const res = await fetch(`${API_BASE}/summary/${jobId}`);
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
  const eventSource = new EventSource(`${API_BASE}/progress/${jobId}`);

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
