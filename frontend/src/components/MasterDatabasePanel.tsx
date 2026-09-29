import React, { useState, useEffect, useCallback } from 'react';
import {
  Database, RefreshCw, BarChart3,
  Building2, Briefcase, CalendarDays, Sparkles, Globe2,
  CheckCircle2, Loader2, Users, ArrowDownToLine,
  FileSpreadsheet, Filter, Check
} from 'lucide-react';

import { RecentJobsFeed } from './RecentJobsFeed';
import { PrefillJob } from './ApplyModal';
import { API_BASE } from '../config/api';
import { getCategoriesOverview, getCategoryExportUrl, CategoryOverview } from '../services/extractionApi';

interface DbStats {
  total_jobs: number; new_today: number; total_companies: number;
  sources: { instahyre: number; himalayas: number; other: number; };
}
interface AppStats { total_applications: number; by_category: Record<string, number>; }
type DL = 'idle' | 'loading' | 'done' | 'error';

interface MasterDatabasePanelProps {
  refreshTrigger?: number;
  onApplyJob?: (job: PrefillJob) => void;
}

export const MasterDatabasePanel: React.FC<MasterDatabasePanelProps> = ({
  refreshTrigger = 0,
  onApplyJob,
}) => {

  const [stats, setStats] = useState<DbStats | null>(null);
  const [appStats, setAppStats] = useState<AppStats | null>(null);
  const [categories, setCategories] = useState<CategoryOverview[]>([]);
  const [loading, setLoading] = useState(false);
  const [dlJob, setDlJob] = useState<DL>('idle');
  const [dlApps, setDlApps] = useState<DL>('idle');
  const [dlCat, setDlCat] = useState<Record<string, DL>>({});
  const [lastRefresh, setLastRefresh] = useState('');

  const fetchStats = useCallback(async () => {
    setLoading(true);
    try {
      const [j, a, cats] = await Promise.all([
        fetch(`${API_BASE}/api/database/stats`).then(r => r.json()),
        fetch(`${API_BASE}/api/applications/stats`).then(r => r.json()),
        getCategoriesOverview().catch(() => []),
      ]);
      setStats(j); setAppStats(a);
      if (Array.isArray(cats)) setCategories(cats);
      setLastRefresh(new Date().toLocaleTimeString());
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchStats(); }, [fetchStats]);
  useEffect(() => { if (refreshTrigger > 0) fetchStats(); }, [refreshTrigger, fetchStats]);

  const download = async (source?: string, type: 'jobs' | 'apps' = 'jobs') => {
    const setter = type === 'jobs' ? setDlJob : setDlApps;
    setter('loading');
    try {
      const url = type === 'apps'
        ? `${API_BASE}/api/applications/export`
        : source ? `${API_BASE}/api/database/export?source=${encodeURIComponent(source)}` : `${API_BASE}/api/database/export`;
      const res = await fetch(url);
      if (!res.ok) throw new Error();
      const blob = await res.blob();
      const disp = res.headers.get('content-disposition') || '';
      const match = disp.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
      const filename = match ? match[1].replace(/['"]/g, '') : 'export.xlsx';
      const obj = URL.createObjectURL(blob);
      const a = document.createElement('a'); a.href = obj; a.download = filename;
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
      URL.revokeObjectURL(obj);
      setter('done'); setTimeout(() => setter('idle'), 3000);
    } catch { setter('error'); setTimeout(() => setter('idle'), 3000); }
  };

  const downloadCategory = async (cat: CategoryOverview) => {
    setDlCat(prev => ({ ...prev, [cat.id]: 'loading' }));
    try {
      const url = getCategoryExportUrl(cat.id);
      const res = await fetch(url);
      if (!res.ok) throw new Error('Download failed');
      const blob = await res.blob();
      const disp = res.headers.get('content-disposition') || '';
      const match = disp.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
      const filename = match ? match[1].replace(/['"]/g, '') : cat.filename;
      const obj = URL.createObjectURL(blob);
      const a = document.createElement('a'); a.href = obj; a.download = filename;
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
      URL.revokeObjectURL(obj);
      setDlCat(prev => ({ ...prev, [cat.id]: 'done' }));
      setTimeout(() => setDlCat(prev => ({ ...prev, [cat.id]: 'idle' })), 3000);
    } catch {
      setDlCat(prev => ({ ...prev, [cat.id]: 'error' }));
      setTimeout(() => setDlCat(prev => ({ ...prev, [cat.id]: 'idle' })), 3000);
    }
  };

  const isEmpty = !stats || stats.total_jobs === 0;

  return (
    <div className="space-y-6">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-black text-white tracking-tight">Data Archive & Dedicated Workbooks</h2>
          <p className="text-xs text-slate-500 mt-0.5">Filter-ready Excel workbooks per domain with &lt;100 employees sheets</p>
        </div>
        <button
          onClick={fetchStats} disabled={loading}
          className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-white px-3 py-1.5 rounded-lg glass hover:border-indigo-500/30 transition-all active:scale-95"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-indigo-400' : ''}`} />
          {lastRefresh ? lastRefresh : 'Refresh'}
        </button>
      </div>

      {/* Stat grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { icon: Briefcase, label: 'Total Jobs', value: stats?.total_jobs.toLocaleString() ?? '—', color: 'text-indigo-400', glow: 'from-indigo-600 to-indigo-500' },
          { icon: Sparkles,  label: 'Added Today', value: stats ? `+${stats.new_today.toLocaleString()}` : '—', color: 'text-emerald-400', glow: 'from-emerald-600 to-emerald-500' },
          { icon: Building2, label: 'Companies', value: stats?.total_companies.toLocaleString() ?? '—', color: 'text-violet-400', glow: 'from-violet-600 to-violet-500' },
          { icon: BarChart3, label: 'Applicants', value: appStats?.total_applications.toLocaleString() ?? '—', color: 'text-sky-400', glow: 'from-sky-600 to-sky-500' },
        ].map(({ icon: Icon, label, value, color, glow }) => (
          <div key={label} className="glass rounded-2xl p-4 space-y-3 hover:border-indigo-500/20 transition-all">
            <div className={`w-8 h-8 rounded-xl bg-gradient-to-tr ${glow} flex items-center justify-center shadow-lg`}>
              <Icon className="w-4 h-4 text-white" />
            </div>
            <div>
              {loading ? <div className="h-6 w-20 rounded-lg bg-slate-800 animate-pulse" />
                : <p className="text-xl font-black font-mono text-white">{value}</p>}
              <p className={`text-[11px] font-semibold uppercase tracking-widest mt-0.5 ${color}`}>{label}</p>
            </div>
          </div>
        ))}
      </div>

      {/* ── Category & Domain Dedicated Workbooks Section ── */}
      {categories.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileSpreadsheet className="w-5 h-5 text-emerald-400" />
              <div>
                <h3 className="text-sm font-bold text-white">Domain & Keyword Workbooks</h3>
                <p className="text-[11px] text-slate-400">
                  Each Excel file has dedicated tabs per keyword + separate sheets for companies with <strong className="text-emerald-300">&lt; 100 people</strong>
                </p>
              </div>
            </div>
            <span className="text-[11px] px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 font-medium">
              8 Category Workbooks Available
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
            {categories.map((cat) => {
              const dlState = dlCat[cat.id] || 'idle';
              return (
                <div
                  key={cat.id}
                  className="glass rounded-2xl p-4 border border-slate-800/80 hover:border-indigo-500/30 transition-all flex flex-col justify-between space-y-3.5"
                >
                  <div className="space-y-2.5">
                    {/* Title row */}
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-slate-800 to-slate-700 flex items-center justify-center border border-slate-700/60 font-mono text-base">
                          {cat.icon || '📁'}
                        </div>
                        <div>
                          <h4 className="text-sm font-black text-white">{cat.name}</h4>
                          <span className="text-[10px] font-mono text-slate-400">{cat.filename}</span>
                        </div>
                      </div>

                      {/* Job Count Badges */}
                      <div className="flex flex-col items-end gap-1">
                        <span className="text-[11px] font-mono font-bold px-2 py-0.5 rounded-md bg-indigo-500/15 border border-indigo-500/30 text-indigo-300">
                          {cat.total_jobs.toLocaleString()} jobs
                        </span>
                        <span className="text-[10px] font-mono font-semibold px-1.5 py-0.5 rounded-md bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 flex items-center gap-1">
                          🌱 &lt;100: {cat.under_100_jobs}
                        </span>
                      </div>
                    </div>

                    {/* Sheet Breakdown Note */}
                    <div className="text-[11px] text-slate-400 bg-slate-900/60 rounded-lg p-2 border border-slate-800/60 space-y-1">
                      <div className="flex items-center gap-1.5 text-slate-300 font-medium text-[10px]">
                        <Filter className="w-3 h-3 text-indigo-400" />
                        <span>Included Sheets:</span>
                      </div>
                      <div className="flex flex-wrap gap-1 text-[10px]">
                        <span className="px-1.5 py-0.5 rounded bg-slate-800/90 text-slate-300 border border-slate-700/50">All Jobs</span>
                        <span className="px-1.5 py-0.5 rounded bg-emerald-950/60 text-emerald-300 border border-emerald-800/50 font-semibold">&lt; 100 People (All)</span>
                        {cat.keywords.map(kw => {
                          const kwData = cat.keyword_breakdown?.[kw];
                          const total = kwData ? kwData.total : 0;
                          return (
                            <span key={kw} className="px-1.5 py-0.5 rounded bg-indigo-950/40 text-indigo-300 border border-indigo-800/40">
                              {kw} ({total})
                            </span>
                          );
                        })}
                      </div>
                    </div>
                  </div>

                  {/* Action Button */}
                  <button
                    onClick={() => downloadCategory(cat)}
                    disabled={dlState === 'loading'}
                    className={`w-full flex items-center justify-center gap-2 py-2 px-3 rounded-xl text-xs font-bold transition-all active:scale-95 ${
                      dlState === 'done'
                        ? 'bg-emerald-500 text-slate-950'
                        : 'bg-gradient-to-r from-emerald-600/90 to-teal-600/90 hover:from-emerald-500 hover:to-teal-500 text-white shadow-md'
                    } ${dlState === 'loading' ? 'opacity-60 cursor-not-allowed' : ''}`}
                  >
                    {dlState === 'loading' ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        <span>Building Multi-Tab Excel...</span>
                      </>
                    ) : dlState === 'done' ? (
                      <>
                        <Check className="w-3.5 h-3.5" />
                        <span>Downloaded {cat.filename}!</span>
                      </>
                    ) : (
                      <>
                        <ArrowDownToLine className="w-3.5 h-3.5" />
                        <span>Download {cat.name} ({cat.filename})</span>
                      </>
                    )}
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Source breakdown + All-Time downloads */}
      {!isEmpty && (
        <div className="glass rounded-2xl overflow-hidden">
          {/* Source badges */}
          <div className="px-5 py-4 border-b border-slate-800/60 flex flex-wrap items-center gap-2">
            <span className="text-[11px] font-semibold uppercase tracking-widest text-slate-500 mr-1">Global Database Export</span>
            {stats!.sources.instahyre > 0 && (
              <SourceBadge label="Instahyre" count={stats!.sources.instahyre} color="indigo" />
            )}
            {stats!.sources.himalayas > 0 && (
              <SourceBadge label="Himalayas" count={stats!.sources.himalayas} color="sky" />
            )}
            {stats!.sources.other > 0 && (
              <SourceBadge label="Other" count={stats!.sources.other} color="slate" />
            )}
          </div>

          {/* Download actions */}
          <div className="p-5 space-y-3">
            {/* Primary: Download All */}
            <DlBtn
              label={`Download Entire Database (${stats!.total_jobs.toLocaleString()} jobs)`}
              state={dlJob}
              onClick={() => download()}
              variant="primary"
            />

            {/* Source-specific row */}
            <div className="flex flex-col sm:flex-row gap-2">
              {stats!.sources.instahyre > 0 && (
                <DlBtn
                  label={`Instahyre (${stats!.sources.instahyre.toLocaleString()})`}
                  state={dlJob}
                  onClick={() => download('instahyre')}
                  variant="indigo"
                />
              )}
              {stats!.sources.himalayas > 0 && (
                <DlBtn
                  label={`Himalayas (${stats!.sources.himalayas.toLocaleString()})`}
                  state={dlJob}
                  onClick={() => download('himalayas')}
                  variant="sky"
                />
              )}
            </div>

            {/* Applications download */}
            {appStats && appStats.total_applications > 0 && (
              <div className="pt-1 border-t border-slate-800/50 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <div className="w-7 h-7 rounded-lg bg-gradient-to-tr from-violet-600 to-indigo-500 flex items-center justify-center">
                    <Users className="w-3.5 h-3.5 text-white" />
                  </div>
                  <div>
                    <p className="text-xs font-bold text-slate-200">Applications Archive</p>
                    <div className="flex flex-wrap gap-1 mt-0.5">
                      {Object.entries(appStats.by_category).map(([cat, n]) => (
                        <span key={cat} className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">
                          {cat}: <span className="text-white font-bold">{String(n)}</span>
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
                <DlBtn
                  label="Download Applications"
                  state={dlApps}
                  onClick={() => download(undefined, 'apps')}
                  variant="violet"
                />
              </div>
            )}

            <p className="text-[11px] text-slate-600 flex items-center gap-1.5">
              <CalendarDays className="w-3 h-3" />
              Data accumulates each session — download anytime for updated archive.
            </p>
          </div>
        </div>
      )}

      {/* ── Recent Scraped Jobs Feed with 1-Click Apply ── */}
      {!isEmpty && (
        <RecentJobsFeed
          onApplyJob={(job) => onApplyJob?.(job)}
          refreshTrigger={refreshTrigger}
        />
      )}

      {isEmpty && (
        <div className="glass rounded-2xl p-16 text-center space-y-3">
          <Database className="w-12 h-12 text-slate-700 mx-auto" />
          <p className="text-slate-400 font-semibold">No data yet</p>
          <p className="text-slate-600 text-xs">Switch to Job Extractor tab and run an extraction.</p>
        </div>
      )}
    </div>
  );
};

/* ── Helper components ── */
const SourceBadge: React.FC<{ label: string; count: number; color: 'indigo'|'sky'|'slate' }> = ({ label, count, color }) => {
  const cls = { indigo: 'bg-indigo-500/10 border-indigo-500/30 text-indigo-300', sky: 'bg-sky-500/10 border-sky-500/30 text-sky-300', slate: 'bg-slate-800 border-slate-700 text-slate-400' }[color];
  return (
    <span className={`flex items-center gap-1 px-2.5 py-1 rounded-full border text-xs font-semibold ${cls}`}>
      <Globe2 className="w-3 h-3" />{label}
      <span className="font-mono opacity-70">{count.toLocaleString()}</span>
    </span>
  );
};

type BtnVariant = 'primary' | 'indigo' | 'sky' | 'violet';
const DlBtn: React.FC<{ label: string; state: DL; onClick: () => void; variant: BtnVariant }> = ({ label, state, onClick, variant }) => {
  const base = 'flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-sm font-bold transition-all active:scale-95';
  const styles: Record<BtnVariant, string> = {
    primary: 'bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white shadow-lg shadow-indigo-950/40',
    indigo:  'bg-indigo-500/12 hover:bg-indigo-500/20 border border-indigo-500/30 text-indigo-300 hover:text-white',
    sky:     'bg-sky-500/12 hover:bg-sky-500/20 border border-sky-500/30 text-sky-300 hover:text-white',
    violet:  'bg-violet-500/12 hover:bg-violet-500/20 border border-violet-500/30 text-violet-300 hover:text-white text-xs',
  };
  return (
    <button onClick={onClick} disabled={state === 'loading'} className={`${base} ${state === 'done' ? 'bg-emerald-500 text-slate-950' : styles[variant]} ${state === 'loading' ? 'opacity-60 cursor-not-allowed' : ''}`}>
      {state === 'loading' ? <><Loader2 className="w-4 h-4 animate-spin" /><span>Generating...</span></>
      : state === 'done' ? <><CheckCircle2 className="w-4 h-4" /><span>Downloaded!</span></>
      : <><ArrowDownToLine className="w-4 h-4" /><span>{label}</span></>}
    </button>
  );
};
