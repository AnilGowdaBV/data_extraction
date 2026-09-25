import React from 'react';
import { UrlInput } from '../components/UrlInput';
import { ExtractionProgress } from '../components/ExtractionProgress';
import { ExtractionSummary } from '../components/ExtractionSummary';
import { StatusIndicator } from '../components/StatusIndicator';
import { useExtraction } from '../hooks/useExtraction';
import { Database, Cpu, Zap, AlertCircle } from 'lucide-react';

export const HomePage: React.FC = () => {
  const { status, progress, summary, error, logs, start, stop, reset } = useExtraction();

  return (
    <div className="min-h-screen flex flex-col justify-between selection:bg-indigo-500 selection:text-white">
      {/* Top Navigation / Header */}
      <header className="border-b border-slate-800/80 bg-slate-950/60 backdrop-blur-xl sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-xl bg-gradient-to-tr from-indigo-600 to-indigo-400 flex items-center justify-center shadow-lg shadow-indigo-500/20">
              <Zap className="w-5 h-5 text-white" />
            </div>
            <div>
              <span className="font-extrabold text-base tracking-tight text-white">
                Bulk Job Extractor
              </span>
              <span className="hidden sm:inline-block ml-2 text-xs text-indigo-400 font-mono bg-indigo-500/10 px-2 py-0.5 rounded-full border border-indigo-500/20">
                v1.0 Production
              </span>
            </div>
          </div>

          <StatusIndicator status={status} />
        </div>
      </header>

      {/* Main Content Body */}
      <main className="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-6 py-10 space-y-10">
        {/* Title & Subheading */}
        <div className="text-center space-y-3 max-w-2xl mx-auto">
          <h1 className="text-3xl sm:text-4xl md:text-5xl font-black text-white tracking-tight leading-tight">
            Extract Thousands of Jobs to{' '}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 via-sky-300 to-emerald-400">
              Excel
            </span>
          </h1>
          <p className="text-slate-400 text-sm sm:text-base leading-relaxed">
            Autonomous multi-page job scraper. Discovers all records, extracts Company Name,
            Job Role, and Number of People, deduplicates, and generates a clean Excel file.
          </p>
        </div>

        {/* Global Error Banner */}
        {error && (
          <div className="max-w-3xl mx-auto p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-sm flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <span className="font-semibold block">Extraction Issue:</span>
              <p className="text-rose-200/90 text-xs sm:text-sm">{error}</p>
            </div>
          </div>
        )}

        {/* URL Input Form (Shown unless completed) */}
        {status !== 'completed' && (
          <UrlInput
            status={status}
            onStart={(url, maxRecords) => start(url, maxRecords)}
            onStop={stop}
          />
        )}

        {/* Live Progress Section (Shown when running, stopped, or error with progress) */}
        {status !== 'completed' && (status === 'running' || progress) && (
          <ExtractionProgress progress={progress} logs={logs} />
        )}

        {/* Final Completion Summary & Download */}
        {status === 'completed' && (
          <ExtractionSummary summary={summary} onReset={reset} />
        )}

        {/* Feature Highlights Grid (Shown in idle state) */}
        {status === 'idle' && (
          <div className="max-w-4xl mx-auto grid grid-cols-1 sm:grid-cols-3 gap-4 pt-6">
            <div className="p-5 rounded-2xl bg-slate-900/40 border border-slate-800/60 space-y-2.5">
              <div className="w-8 h-8 rounded-lg bg-indigo-500/10 flex items-center justify-center text-indigo-400">
                <Cpu className="w-4 h-4" />
              </div>
              <h3 className="font-semibold text-slate-200 text-sm">Autonomous Discovery</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Zero manual XPath or CSS selectors required. Automatically inspects JSON-LD,
                hydration data, and DOM repeated card structures.
              </p>
            </div>

            <div className="p-5 rounded-2xl bg-slate-900/40 border border-slate-800/60 space-y-2.5">
              <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center text-emerald-400">
                <Zap className="w-4 h-4" />
              </div>
              <h3 className="font-semibold text-slate-200 text-sm">Bulk Traversal</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Exhaustively traverses multi-page paginations, Load More buttons, and infinite
                scrolling without arbitrary early cutoffs.
              </p>
            </div>

            <div className="p-5 rounded-2xl bg-slate-900/40 border border-slate-800/60 space-y-2.5">
              <div className="w-8 h-8 rounded-lg bg-sky-500/10 flex items-center justify-center text-sky-400">
                <Database className="w-4 h-4" />
              </div>
              <h3 className="font-semibold text-slate-200 text-sm">Stateless & Clean</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Zero persistent database footprint. In-memory profile caching, strict deduplication,
                and instant OpenPyXL spreadsheet generation.
              </p>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-900 py-6 text-center text-xs text-slate-500 space-y-1">
        <p>Bulk Job Website → Excel Extractor · Industry-standard Autonomous Pipeline</p>
        <p className="text-slate-600 font-mono text-[11px]">
          Playwright Chromium · FastAPI · Pandas · OpenPyXL · React · TypeScript
        </p>
      </footer>
    </div>
  );
};
