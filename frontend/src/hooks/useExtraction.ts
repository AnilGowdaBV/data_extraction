import { useState, useCallback, useRef, useEffect } from 'react';
import {
  ExtractionProgress,
  ExtractionStatus,
  ExtractionSummary,
} from '../types/extraction';
import {
  startExtraction,
  stopExtraction,
  getExtractionSummary,
  subscribeToProgress,
} from '../services/extractionApi';

export function useExtraction() {
  const [status, setStatus] = useState<ExtractionStatus>('idle');
  const [jobId, setJobId] = useState<string | null>(null);
  const [progress, setProgress] = useState<ExtractionProgress | null>(null);
  const [summary, setSummary] = useState<ExtractionSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [logs, setLogs] = useState<Array<{ timestamp: string; message: string }>>([]);

  const unsubscribeRef = useRef<(() => void) | null>(null);

  const addLog = useCallback((message: string) => {
    const time = new Date().toLocaleTimeString();
    setLogs((prev) => [...prev.slice(-30), { timestamp: time, message }]);
  }, []);

  const start = useCallback(
    async (url: string, maxRecords = 100000) => {
      try {
        setError(null);
        setSummary(null);
        setProgress(null);
        setLogs([]);
        setStatus('running');

        addLog(`Initiating extraction pipeline for: ${url}`);
        const res = await startExtraction({ url, max_records: maxRecords });
        setJobId(res.job_id);

        addLog(`Job created [${res.job_id}]. Connecting to live stream...`);

        // Connect SSE progress
        const unsubscribe = subscribeToProgress(
          res.job_id,
          async (update) => {
            setProgress(update);
            setStatus(update.status);
            if (update.current_action) {
              addLog(update.current_action);
            }

            if (update.status === 'completed' || update.status === 'stopped') {
              addLog(`Extraction ${update.status}! Generating summary and Excel sheet...`);
              try {
                const finalSummary = await getExtractionSummary(res.job_id);
                setSummary(finalSummary);
              } catch (e) {
                console.error('Failed to load summary', e);
              }
            } else if (update.status === 'failed') {
              setError(update.error || 'Extraction failed');
              addLog(`Error: ${update.error || 'Extraction failed'}`);
            }
          },
          (err) => {
            console.error('SSE connection error:', err);
          }
        );

        unsubscribeRef.current = unsubscribe;
      } catch (err: unknown) {
        setStatus('failed');
        const msg = err instanceof Error ? err.message : 'Failed to launch extraction';
        setError(msg);
        addLog(`Failed to start: ${msg}`);
      }
    },
    [addLog]
  );

  const stop = useCallback(async () => {
    try {
      addLog('Stopping extraction and finalizing Excel file...');
      const targetId = jobId || 'active';
      try {
        await stopExtraction(targetId);
      } catch {
        try { await stopExtraction('active'); } catch { /* silent */ }
      }
      setStatus('stopped');
      setTimeout(async () => {
        if (jobId) {
          try {
            const finalSummary = await getExtractionSummary(jobId);
            setSummary(finalSummary);
          } catch (e) {
            console.warn('Summary not ready yet', e);
          }
        }
      }, 800);
    } catch (e: unknown) {
      console.warn('Stop warning:', e);
      setStatus('stopped');
    }
  }, [jobId, addLog]);

  const reset = useCallback(() => {
    if (unsubscribeRef.current) {
      unsubscribeRef.current();
    }
    setStatus('idle');
    setJobId(null);
    setProgress(null);
    setSummary(null);
    setError(null);
    setLogs([]);
  }, []);

  useEffect(() => {
    return () => {
      if (unsubscribeRef.current) {
        unsubscribeRef.current();
      }
    };
  }, []);

  return {
    status,
    jobId,
    progress,
    summary,
    error,
    logs,
    start,
    stop,
    reset,
  };
}
