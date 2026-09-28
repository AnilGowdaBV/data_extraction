import React, { useState } from 'react';
import { UrlInput } from '../components/UrlInput';
import { ExtractionProgress } from '../components/ExtractionProgress';
import { ExtractionSummary } from '../components/ExtractionSummary';
import { MasterDatabasePanel } from '../components/MasterDatabasePanel';
import { ApplyModal, PrefillJob } from '../components/ApplyModal';
import { StatusIndicator } from '../components/StatusIndicator';
import { RecentJobsFeed } from '../components/RecentJobsFeed';
import { useExtraction } from '../hooks/useExtraction';
import {
  Zap, Database, Users, Cpu, AlertCircle, Briefcase,
} from 'lucide-react';

type Tab = 'extractor' | 'archive' | 'applications';

const TABS: { id: Tab; label: string; icon: React.ElementType }[] = [
  { id: 'extractor',    label: 'Job Extractor',  icon: Zap      },
  { id: 'archive',      label: 'Data Archive',   icon: Database },
  { id: 'applications', label: 'Applications',   icon: Users    },
];

export const HomePage: React.FC = () => {
  const { status, progress, summary, error, logs, start, stop, reset } = useExtraction();
  const [applyOpen, setApplyOpen] = useState(false);
  const [prefillJob, setPrefillJob] = useState<PrefillJob | null>(null);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [activeTab, setActiveTab] = useState<Tab>('extractor');

  const handleApplyForJob = (job: PrefillJob) => {
    setPrefillJob(job);
    setApplyOpen(true);
  };


  return (
    <div className="min-h-screen flex flex-col bg-[#080B14] overflow-hidden relative selection:bg-indigo-500/40">
      {/* ── Ambient background blobs ── */}
      <div className="pointer-events-none fixed inset-0 overflow-hidden z-0">
        <div className="animate-floatA absolute -top-32 -left-32 w-[520px] h-[520px] rounded-full bg-indigo-600/10 blur-[120px]" />
        <div className="animate-floatB absolute top-1/2 -right-40 w-[480px] h-[480px] rounded-full bg-violet-600/10 blur-[120px]" />
        <div className="animate-floatC absolute bottom-0 left-1/3 w-[360px] h-[360px] rounded-full bg-sky-600/8 blur-[100px]" />
        <div className="absolute inset-0" style={{ backgroundImage: 'radial-gradient(ellipse 80% 50% at 50% 0%, rgba(99,102,241,0.06) 0%, transparent 60%)' }} />
      </div>

      {/* ── Header ── */}
      <header className="relative z-50 shrink-0">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
          {/* Logo */}
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center shadow-lg shadow-indigo-500/30 rotate-3">
              <Zap className="w-4 h-4 text-white" />
            </div>
            <div className="flex items-center gap-2">
              <span className="font-black text-sm tracking-tight text-white">JobExtractor</span>
              <span className="text-[10px] text-indigo-400 font-mono bg-indigo-500/10 px-1.5 py-0.5 rounded-full border border-indigo-500/20 hidden sm:inline">PRO</span>
            </div>
          </div>

          {/* Tab bar in header */}
          <nav className="hidden sm:flex items-center gap-1 glass rounded-xl px-1 py-1">
            {TABS.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => setActiveTab(id)}
                className={`flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-semibold transition-all duration-200 ${
                  activeTab === id
                    ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/30'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                {label}
              </button>
            ))}
          </nav>

          {/* Right actions */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setApplyOpen(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white shadow-lg shadow-indigo-950/50 transition-all active:scale-95"
            >
              <Briefcase className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Apply Here</span>
            </button>
            <StatusIndicator status={status} />
          </div>
        </div>

        {/* Mobile tab bar */}
        <div className="sm:hidden flex items-center gap-1 px-4 pb-2 overflow-x-auto">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-all ${
                activeTab === id ? 'bg-indigo-600 text-white' : 'text-slate-400 bg-slate-800/60'
              }`}
            >
              <Icon className="w-3 h-3" />
              {label}
            </button>
          ))}
        </div>

        {/* Separator glow line */}
        <div className="h-px bg-gradient-to-r from-transparent via-indigo-500/30 to-transparent" />
      </header>

      {/* ── Main Content ── */}
      <main className="relative z-10 flex-1 overflow-y-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6">

          {/* ══ TAB: EXTRACTOR ══ */}
          {activeTab === 'extractor' && (
            <div className="animate-fadeIn space-y-5">
              {/* Hero text */}
              {status === 'idle' && !summary && (
                <div className="text-center pt-2 pb-1">
                  <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight leading-tight">
                    Extract Jobs to{' '}
                    <span className="text-shimmer">Excel Instantly</span>
                  </h1>
                  <p className="text-slate-500 text-xs sm:text-sm mt-1.5 max-w-xl mx-auto">
                    Autonomous scraper · Deduplication · Live progress · One-click download
                  </p>
                </div>
              )}

              {/* Error */}
              {error && (
                <div className="max-w-3xl mx-auto p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>{error}</span>
                </div>
              )}

              {/* URL Input */}
              {!summary && status !== 'completed' && (
                <UrlInput status={status} onStart={(url, maxRecords) => start(url, maxRecords)} onStop={stop} />
              )}

              {/* Progress */}
              {!summary && status !== 'completed' && (status === 'running' || progress) && (
                <ExtractionProgress progress={progress} logs={logs} />
              )}

              {/* Summary */}
              {(summary || status === 'completed') && (
                <ExtractionSummary summary={summary} onReset={reset} />
              )}

              {/* Feature cards — idle only */}
              {status === 'idle' && !summary && (
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-1">
                  {[
                    { icon: Cpu, label: 'Autonomous Discovery', color: 'text-indigo-400', bg: 'bg-indigo-500/8', desc: 'JSON-LD, hydration data, DOM card structures — no XPath needed.' },
                    { icon: Zap, label: 'Bulk Traversal', color: 'text-violet-400', bg: 'bg-violet-500/8', desc: 'Paginations, Load More, infinite scroll — all exhaustively covered.' },
                    { icon: Database, label: 'Persistent Archive', color: 'text-emerald-400', bg: 'bg-emerald-500/8', desc: 'Every run adds to the master DB. Download all-time data in one click.' },
                  ].map(({ icon: Icon, label, color, bg, desc }) => (
                    <div key={label} className="glass rounded-2xl p-4 space-y-2 hover:border-indigo-500/25 transition-all group">
                      <div className={`w-8 h-8 rounded-lg ${bg} flex items-center justify-center`}>
                        <Icon className={`w-4 h-4 ${color}`} />
                      </div>
                      <p className="font-semibold text-slate-200 text-sm">{label}</p>
                      <p className="text-xs text-slate-500 leading-relaxed">{desc}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ══ TAB: ARCHIVE ══ */}
          {activeTab === 'archive' && (
            <div className="animate-fadeIn">
              <MasterDatabasePanel
                refreshTrigger={refreshTrigger}
                onApplyJob={handleApplyForJob}
              />
            </div>
          )}

          {/* ══ TAB: APPLICATIONS ══ */}
          {activeTab === 'applications' && (
            <div className="animate-fadeIn">
              <ApplicationsPanel
                refreshTrigger={refreshTrigger}
                onApply={() => setApplyOpen(true)}
                onApplyJob={handleApplyForJob}
              />
            </div>
          )}

        </div>
      </main>

      {/* ── Apply Modal ── */}
      <ApplyModal
        isOpen={applyOpen}
        onClose={() => {
          setApplyOpen(false);
          setPrefillJob(null);
        }}
        onSuccess={() => setRefreshTrigger((n) => n + 1)}
        prefillRole={prefillJob}
      />
    </div>
  );
};


import { API_BASE } from '../config/api';


interface AppStats { total_applications: number; by_category: Record<string, number>; }

const CATEGORY_COLORS: Record<string, string> = {
  'SDE':          'from-indigo-600 to-indigo-500',
  'Frontend':     'from-sky-600 to-sky-500',
  'Backend':      'from-violet-600 to-violet-500',
  'Full Stack':   'from-teal-600 to-teal-500',
  'DevOps':       'from-orange-600 to-orange-500',
  'Data / ML':    'from-emerald-600 to-emerald-500',
  'Mobile':       'from-pink-600 to-pink-500',
  'QA / Testing': 'from-yellow-600 to-yellow-500',
  'Management':   'from-rose-600 to-rose-500',
  'Other':        'from-slate-600 to-slate-500',
};

const ApplicationsPanel: React.FC<{
  refreshTrigger: number;
  onApply: () => void;
  onApplyJob?: (job: PrefillJob) => void;
}> = ({ refreshTrigger, onApply, onApplyJob }) => {
  const [appStats, setAppStats] = React.useState<AppStats | null>(null);
  const [dlState, setDlState] = React.useState<'idle'|'loading'|'done'|'error'>('idle');

  const fetchStats = React.useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/applications/stats`);
      if (res.ok) setAppStats(await res.json());
    } catch { /* silent */ }
  }, []);

  React.useEffect(() => { fetchStats(); }, [fetchStats, refreshTrigger]);

  const handleDownload = async () => {
    setDlState('loading');
    try {
      const res = await fetch(`${API_BASE}/api/applications/export`);
      if (!res.ok) throw new Error();
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a'); a.href = url; a.download = 'Job_Applications.xlsx';
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
      URL.revokeObjectURL(url);
      setDlState('done'); setTimeout(() => setDlState('idle'), 3000);
    } catch { setDlState('error'); setTimeout(() => setDlState('idle'), 3000); }
  };

  const isEmpty = !appStats || appStats.total_applications === 0;

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-black text-white tracking-tight">Candidate Applications</h2>
          <p className="text-xs text-slate-500 mt-0.5">All submitted applications, organized by role category</p>
        </div>
        <div className="flex items-center gap-2">
          {!isEmpty && (
            <button
              onClick={handleDownload}
              disabled={dlState === 'loading'}
              className={`flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold transition-all active:scale-95 ${
                dlState === 'done' ? 'bg-emerald-500 text-slate-950'
                : dlState === 'loading' ? 'bg-violet-700/60 text-white/60 cursor-not-allowed'
                : 'bg-violet-600 hover:bg-violet-500 text-white'
              }`}
            >
              {dlState === 'loading' ? 'Generating...' : dlState === 'done' ? '✓ Downloaded!' : '⬇ Download Excel'}
            </button>
          )}
          <button
            onClick={onApply}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white transition-all active:scale-95"
          >
            <Briefcase className="w-3.5 h-3.5" />
            New Application
          </button>
        </div>
      </div>

      {isEmpty ? (
        <div className="glass rounded-2xl p-16 text-center space-y-3">
          <Users className="w-12 h-12 text-slate-700 mx-auto" />
          <p className="text-slate-400 font-semibold">No applications yet</p>
          <p className="text-slate-600 text-xs max-w-xs mx-auto">Candidates can click "Apply Here" or click Apply on any recent job below to submit their profile.</p>
          <button onClick={onApply} className="mt-2 px-6 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs transition-all active:scale-95">
            Be the First to Apply
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
          {Object.entries(appStats!.by_category)
            .sort(([, a], [, b]) => (b as number) - (a as number))
            .map(([cat, count]) => {
              const gradient = CATEGORY_COLORS[cat] ?? CATEGORY_COLORS['Other'];
              return (
                <div key={cat} className="glass rounded-2xl p-4 space-y-3 hover:scale-[1.02] transition-all">
                  <div className={`w-9 h-9 rounded-xl bg-gradient-to-tr ${gradient} flex items-center justify-center shadow-lg`}>
                    <Users className="w-4 h-4 text-white" />
                  </div>
                  <div>
                    <p className="text-xl font-black text-white font-mono">{count as number}</p>
                    <p className="text-xs text-slate-400 font-medium mt-0.5 leading-tight">{cat}</p>
                  </div>
                </div>
              );
            })}
          {/* Total card */}
          <div className="glass rounded-2xl p-4 space-y-3 border-indigo-500/25 bg-indigo-500/5">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-600 flex items-center justify-center shadow-lg">
              <Database className="w-4 h-4 text-white" />
            </div>
            <div>
              <p className="text-xl font-black text-indigo-300 font-mono">{appStats!.total_applications}</p>
              <p className="text-xs text-slate-400 font-medium mt-0.5">Total Applied</p>
            </div>
          </div>
        </div>
      )}

      {/* ── Recent Scraped Jobs Feed with 1-Click Apply ── */}
      {onApplyJob && (
        <div className="pt-2">
          <RecentJobsFeed onApplyJob={onApplyJob} refreshTrigger={refreshTrigger} />
        </div>
      )}
    </div>
  );
};

