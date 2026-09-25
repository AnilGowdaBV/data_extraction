import React, { useState } from 'react';
import { Globe, ArrowRight, Square, SlidersHorizontal } from 'lucide-react';
import { ExtractionStatus } from '../types/extraction';

interface UrlInputProps {
  status: ExtractionStatus;
  onStart: (url: string, maxRecords: number) => void;
  onStop: () => void;
}

export const UrlInput: React.FC<UrlInputProps> = ({ status, onStart, onStop }) => {
  const [url, setUrl] = useState('');
  const [maxRecords, setMaxRecords] = useState(100000);
  const [inputError, setInputError] = useState<string | null>(null);

  const isRunning = status === 'running';

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setInputError(null);

    const trimmed = url.trim();
    if (!trimmed) {
      setInputError('Please enter a website URL.');
      return;
    }

    try {
      const parsed = new URL(trimmed.startsWith('http') ? trimmed : `https://${trimmed}`);
      if (!['http:', 'https:'].includes(parsed.protocol)) {
        setInputError('URL must use HTTP or HTTPS protocol.');
        return;
      }
      onStart(parsed.toString(), maxRecords);
    } catch {
      setInputError('Please enter a valid website URL (e.g., https://example.com/jobs).');
    }
  };

  return (
    <div className="w-full max-w-3xl mx-auto bg-slate-900/80 border border-slate-800 rounded-2xl p-6 shadow-2xl backdrop-blur-xl">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="job-url-input" className="block text-sm font-medium text-slate-300 mb-2">
            Enter Job Website URL
          </label>
          <div className="relative flex items-center">
            <div className="absolute left-4 pointer-events-none text-slate-500">
              <Globe className="w-5 h-5" />
            </div>
            <input
              id="job-url-input"
              type="text"
              value={url}
              onChange={(e) => {
                setUrl(e.target.value);
                if (inputError) setInputError(null);
              }}
              disabled={isRunning}
              placeholder="https://company.com/careers or https://jobboard.com/jobs"
              className="w-full pl-12 pr-4 py-3.5 bg-slate-950/60 border border-slate-700/60 rounded-xl text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 transition-all text-sm sm:text-base disabled:opacity-50 disabled:cursor-not-allowed"
            />
          </div>
          {inputError && (
            <p className="mt-2 text-xs font-medium text-rose-400">{inputError}</p>
          )}
        </div>

        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4 pt-2">
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <SlidersHorizontal className="w-4 h-4 text-slate-500" />
            <span>Safety Limit:</span>
            <select
              value={maxRecords}
              onChange={(e) => setMaxRecords(Number(e.target.value))}
              disabled={isRunning}
              aria-label="Extraction Safety Limit"
              className="bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1 text-slate-300 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              <option value={1000}>1,000 jobs</option>
              <option value={5000}>5,000 jobs</option>
              <option value={20000}>20,000 jobs</option>
              <option value={50000}>50,000 jobs</option>
              <option value={100000}>100,000 jobs (Default)</option>
            </select>
          </div>

          <div className="flex items-center gap-3">
            {isRunning ? (
              <button
                type="button"
                onClick={onStop}
                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl font-medium text-sm bg-rose-600 hover:bg-rose-500 text-white transition-all shadow-lg shadow-rose-950/40 active:scale-95"
              >
                <Square className="w-4 h-4 fill-current" />
                Stop Extraction
              </button>
            ) : (
              <button
                type="submit"
                id="start-extraction-button"
                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-8 py-3.5 rounded-xl font-semibold text-sm bg-gradient-to-r from-indigo-500 to-indigo-600 hover:from-indigo-400 hover:to-indigo-500 text-white transition-all shadow-xl shadow-indigo-950/50 hover:shadow-indigo-500/20 active:scale-95"
              >
                <span>Start Extraction</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
      </form>
    </div>
  );
};
