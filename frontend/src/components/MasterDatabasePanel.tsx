import React, { useState, useEffect, useCallback } from 'react';
import {
  Database, RefreshCw, BarChart3,
  Building2, Briefcase, CalendarDays, Sparkles, Globe2,
  CheckCircle2, Loader2, Users, ArrowDownToLine,
  FileSpreadsheet, Filter, Check,
  CheckSquare, Cloud, Layout, Server,
  Palette, Zap, ExternalLink
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

const CATEGORY_ICON_MAP: Record<string, React.ElementType> = {
  CheckSquare,
  Cloud,
  Layout,
  Server,
  BarChart3,
  Database,
  Palette,
  Zap,
};

const CATEGORY_THEME: Record<string, { bg: string; border: string; text: string; btn: string }> = {
  qa_automation: {
    bg: 'bg-emerald-500/10',
    border: 'border-emerald-500/30',
    text: 'text-emerald-400',
    btn: 'from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500',
  },
  devops_cloud: {
    bg: 'bg-sky-500/10',
    border: 'border-sky-500/30',
    text: 'text-sky-400',
    btn: 'from-sky-600 to-blue-600 hover:from-sky-500 hover:to-blue-500',
  },
  frontend_mobile: {
    bg: 'bg-cyan-500/10',
    border: 'border-cyan-500/30',
    text: 'text-cyan-400',
    btn: 'from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500',
  },
  backend: {
    bg: 'bg-indigo-500/10',
    border: 'border-indigo-500/30',
    text: 'text-indigo-400',
    btn: 'from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500',
  },
  data_analytics: {
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/30',
    text: 'text-amber-400',
    btn: 'from-amber-600 to-orange-600 hover:from-amber-500 hover:to-orange-500',
  },
  data_engineering: {
    bg: 'bg-orange-500/10',
    border: 'border-orange-500/30',
    text: 'text-orange-400',
    btn: 'from-orange-600 to-red-600 hover:from-orange-500 hover:to-red-500',
  },
  ux_design: {
    bg: 'bg-purple-500/10',
    border: 'border-purple-500/30',
    text: 'text-purple-400',
    btn: 'from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500',
  },
  fde: {
    bg: 'bg-rose-500/10',
    border: 'border-rose-500/30',
    text: 'text-rose-400',
    btn: 'from-rose-600 to-red-600 hover:from-rose-500 hover:to-red-500',
  },
};

type SourceFilter = 'himalayas' | 'instahyre' | 'all';

export const MasterDatabasePanel: React.FC<MasterDatabasePanelProps> = ({
  refreshTrigger = 0,
  onApplyJob,
}) => {

  const [stats, setStats] = useState<DbStats | null>(null);
  const [appStats, setAppStats] = useState<AppStats | null>(null);
  const [categories, setCategories] = useState<CategoryOverview[]>([]);
  const [activeSource, setActiveSource] = useState<SourceFilter>('himalayas');
  const [loading, setLoading] = useState(false);
  const [loadingCats, setLoadingCats] = useState(false);
  const [dlJob, setDlJob] = useState<DL>('idle');
  const [dlApps, setDlApps] = useState<DL>('idle');
  const [dlCat, setDlCat] = useState<Record<string, DL>>({});
  const [lastRefresh, setLastRefresh] = useState('');
  const [gsSyncState, setGsSyncState] = useState<'idle' | 'loading' | 'done' | 'error'>('idle');
  const [gsSyncMsg, setGsSyncMsg] = useState<string>('');

  const syncGoogleSheet = async () => {
    setGsSyncState('loading');
    setGsSyncMsg('');
    try {
      const srcParam = activeSource !== 'all' ? `?source=${encodeURIComponent(activeSource)}` : '';
      const res = await fetch(`${API_BASE}/api/database/sync-google-sheet${srcParam}`, {
        method: 'POST',
      });
      if (!res.ok) throw new Error('Sync failed');
      const data = await res.json();
      if (data.success) {
        setGsSyncState('done');
        const tabSummary = data.date_tabs
          ? Object.keys(data.date_tabs).join(', ')
          : (data.sheet_name || 'date tabs');
        setGsSyncMsg(`Successfully dumped ${data.total_synced || data.synced_count} jobs across date tabs (${tabSummary})!`);
        setTimeout(() => setGsSyncState('idle'), 8000);
      } else {
        setGsSyncState('error');
        setGsSyncMsg(data.error || 'Failed to sync to Google Sheet');
        setTimeout(() => setGsSyncState('idle'), 6000);
      }
    } catch {
      setGsSyncState('error');
      setGsSyncMsg('Could not connect to Google Sheets backend');
      setTimeout(() => setGsSyncState('idle'), 6000);
    }
  };

  const fetchCategoryData = useCallback(async (sourceKey: SourceFilter) => {
    setLoadingCats(true);
    try {
      const cats = await getCategoriesOverview(sourceKey);
      if (Array.isArray(cats)) setCategories(cats);
    } catch {
      /* silent */
    } finally {
      setLoadingCats(false);
    }
  }, []);

  const fetchStats = useCallback(async () => {
    setLoading(true);
    try {
      const [j, a] = await Promise.all([
        fetch(`${API_BASE}/api/database/stats`).then(r => r.json()),
        fetch(`${API_BASE}/api/applications/stats`).then(r => r.json()),
      ]);
      setStats(j);
      setAppStats(a);
      setLastRefresh(new Date().toLocaleTimeString());
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  useEffect(() => {
    fetchCategoryData(activeSource);
  }, [activeSource, fetchCategoryData]);

  useEffect(() => {
    if (refreshTrigger > 0) {
      fetchStats();
      fetchCategoryData(activeSource);
    }
  }, [refreshTrigger, fetchStats, fetchCategoryData, activeSource]);

  const handleSourceChange = (newSource: SourceFilter) => {
    setActiveSource(newSource);
  };

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
      const url = getCategoryExportUrl(cat.id, activeSource);
      const res = await fetch(url);
      if (!res.ok) throw new Error('Download failed');
      const blob = await res.blob();
      const disp = res.headers.get('content-disposition') || '';
      const match = disp.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
      const prefix = activeSource !== 'all' ? `${activeSource.charAt(0).toUpperCase() + activeSource.slice(1)}_` : '';
      const fallback = `${prefix}${cat.filename}`;
      const filename = match ? match[1].replace(/['"]/g, '') : fallback;
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
          <h2 className="text-xl font-black text-white tracking-tight">Data Archive & Domain Workbooks</h2>
          <p className="text-xs text-slate-500 mt-0.5">Filter-ready Excel workbooks per domain with separate &lt;100 employees sheets</p>
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

      {/* ── Platform / Source Switcher ── */}
      <div className="glass rounded-2xl p-4 sm:p-5 border border-slate-800/80 space-y-3 bg-slate-950/40">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-indigo-500/10 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
              <Globe2 className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold text-white tracking-tight">Platform / Company Filter</h3>
                <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-indigo-500/15 text-indigo-300 border border-indigo-500/30">
                  Live Segregation
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Segregate all 8 domain workbooks & recent jobs by your chosen platform
              </p>
            </div>
          </div>

          {loadingCats && (
            <div className="flex items-center gap-1.5 text-xs text-indigo-400 font-medium">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              <span>Updating dataset...</span>
            </div>
          )}
        </div>

        {/* Switcher Buttons */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 pt-1">
          {/* Himalayas */}
          <button
            type="button"
            onClick={() => handleSourceChange('himalayas')}
            className={`relative flex items-center justify-between p-3 rounded-xl border text-left transition-all active:scale-[0.99] cursor-pointer ${
              activeSource === 'himalayas'
                ? 'bg-sky-500/15 border-sky-500/60 shadow-lg shadow-sky-950/40 text-white ring-1 ring-sky-500/40'
                : 'bg-slate-900/60 border-slate-800/80 text-slate-400 hover:text-slate-200 hover:border-slate-700/80 hover:bg-slate-900/90'
            }`}
          >
            <div className="flex items-center gap-2.5">
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center font-bold text-xs ${
                activeSource === 'himalayas'
                  ? 'bg-sky-500 text-slate-950 shadow-md shadow-sky-500/30'
                  : 'bg-slate-800 text-sky-400 border border-slate-700'
              }`}>
                🏔️
              </div>
              <div>
                <p className="text-xs font-bold leading-tight text-white">Himalayas</p>
                <p className="text-[10px] font-mono text-slate-400">himalayas.app</p>
              </div>
            </div>
            <div className="text-right">
              <span className={`text-xs font-mono font-bold px-2 py-0.5 rounded-md ${
                activeSource === 'himalayas'
                  ? 'bg-sky-500/25 text-sky-200 border border-sky-400/40'
                  : 'bg-slate-800 text-slate-400'
              }`}>
                {stats?.sources.himalayas.toLocaleString() ?? '17,691'} jobs
              </span>
            </div>
          </button>

          {/* Instahyre */}
          <button
            type="button"
            onClick={() => handleSourceChange('instahyre')}
            className={`relative flex items-center justify-between p-3 rounded-xl border text-left transition-all active:scale-[0.99] cursor-pointer ${
              activeSource === 'instahyre'
                ? 'bg-emerald-500/15 border-emerald-500/60 shadow-lg shadow-emerald-950/40 text-white ring-1 ring-emerald-500/40'
                : 'bg-slate-900/60 border-slate-800/80 text-slate-400 hover:text-slate-200 hover:border-slate-700/80 hover:bg-slate-900/90'
            }`}
          >
            <div className="flex items-center gap-2.5">
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center font-bold text-xs ${
                activeSource === 'instahyre'
                  ? 'bg-emerald-500 text-slate-950 shadow-md shadow-emerald-500/30'
                  : 'bg-slate-800 text-emerald-400 border border-slate-700'
              }`}>
                ⚡
              </div>
              <div>
                <p className="text-xs font-bold leading-tight text-white">Instahyre</p>
                <p className="text-[10px] font-mono text-slate-400">instahyre.com</p>
              </div>
            </div>
            <div className="text-right">
              <span className={`text-xs font-mono font-bold px-2 py-0.5 rounded-md ${
                activeSource === 'instahyre'
                  ? 'bg-emerald-500/25 text-emerald-200 border border-emerald-400/40'
                  : 'bg-slate-800 text-slate-400'
              }`}>
                {stats?.sources.instahyre.toLocaleString() ?? '1,861'} jobs
              </span>
            </div>
          </button>

          {/* All Sources */}
          <button
            type="button"
            onClick={() => handleSourceChange('all')}
            className={`relative flex items-center justify-between p-3 rounded-xl border text-left transition-all active:scale-[0.99] cursor-pointer ${
              activeSource === 'all'
                ? 'bg-violet-500/15 border-violet-500/60 shadow-lg shadow-violet-950/40 text-white ring-1 ring-violet-500/40'
                : 'bg-slate-900/60 border-slate-800/80 text-slate-400 hover:text-slate-200 hover:border-slate-700/80 hover:bg-slate-900/90'
            }`}
          >
            <div className="flex items-center gap-2.5">
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center font-bold text-xs ${
                activeSource === 'all'
                  ? 'bg-violet-500 text-slate-950 shadow-md shadow-violet-500/30'
                  : 'bg-slate-800 text-violet-400 border border-slate-700'
              }`}>
                🌐
              </div>
              <div>
                <p className="text-xs font-bold leading-tight text-white">All Platforms</p>
                <p className="text-[10px] font-mono text-slate-400">Combined Dataset</p>
              </div>
            </div>
            <div className="text-right">
              <span className={`text-xs font-mono font-bold px-2 py-0.5 rounded-md ${
                activeSource === 'all'
                  ? 'bg-violet-500/25 text-violet-200 border border-violet-400/40'
                  : 'bg-slate-800 text-slate-400'
              }`}>
                {stats?.total_jobs.toLocaleString() ?? '19,552'} jobs
              </span>
            </div>
          </button>
        </div>
      </div>

      {/* ── Google Sheets Live Dump Card ── */}
      <div className="glass rounded-2xl p-5 border border-emerald-500/30 bg-gradient-to-r from-emerald-950/30 via-slate-900/60 to-slate-950/80 shadow-xl shadow-emerald-950/20 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400 text-lg shadow-sm">
              📊
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold text-white">
                  {activeSource === 'instahyre' ? '⚡ Instahyre Google Sheet Live Dump' : activeSource === 'himalayas' ? '🏔️ Himalayas Google Sheet Live Dump' : 'Google Spreadsheet Live Dump'}
                </h3>
                <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                  Date-Wise Tabs (Sep 23, Sep 24, Oct 8...)
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Automatically organizes all <strong className="text-white">{activeSource === 'instahyre' ? '1,861 Instahyre' : activeSource === 'himalayas' ? '17,691 Himalayas' : 'All'}</strong> jobs into separate tabs based on the day each job was scraped. Existing tabs &amp; rows are 100% safe.
              </p>
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-2.5 shrink-0">
            <button
              type="button"
              onClick={syncGoogleSheet}
              disabled={gsSyncState === 'loading'}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all shadow-md active:scale-95 cursor-pointer ${
                gsSyncState === 'loading'
                  ? 'bg-slate-800 text-slate-400 border border-slate-700'
                  : gsSyncState === 'done'
                  ? 'bg-emerald-600 text-white shadow-emerald-900/40'
                  : gsSyncState === 'error'
                  ? 'bg-rose-600 text-white'
                  : 'bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white shadow-emerald-950/50'
              }`}
            >
              {gsSyncState === 'loading' ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Dumping to Sheet...</span>
                </>
              ) : gsSyncState === 'done' ? (
                <>
                  <Check className="w-3.5 h-3.5" />
                  <span>Dumped to Sheet!</span>
                </>
              ) : (
                <>
                  <Zap className="w-3.5 h-3.5 text-emerald-200" />
                  <span>Sync to Google Sheet</span>
                </>
              )}
            </button>

            <a
              href="https://docs.google.com/spreadsheets/d/1wrwZlp3kJRDdRvwIgCrrbd3rCJFHEsIigLop-hwHPSs/edit?usp=sharing"
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold glass border border-slate-700/80 hover:border-emerald-500/40 text-slate-300 hover:text-white transition-all"
              title="Open Google Spreadsheet in new tab"
            >
              <span>Open Sheet</span>
              <ExternalLink className="w-3 h-3 text-emerald-400" />
            </a>
          </div>
        </div>

        {/* Live sync notification banner */}
        {gsSyncMsg && (
          <div className={`p-2.5 rounded-xl text-xs font-medium border flex items-center justify-between ${
            gsSyncState === 'error'
              ? 'bg-rose-500/10 border-rose-500/30 text-rose-300'
              : 'bg-emerald-500/15 border-emerald-500/30 text-emerald-200'
          }`}>
            <span>{gsSyncMsg}</span>
          </div>
        )}
      </div>

      {/* ── Category & Domain Dedicated Workbooks Section ── */}
      {categories.length > 0 && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
                <FileSpreadsheet className="w-4 h-4" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-bold text-white">Domain & Keyword Workbooks</h3>
                  <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-md ${
                    activeSource === 'instahyre'
                      ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                      : activeSource === 'himalayas'
                      ? 'bg-sky-500/20 text-sky-300 border border-sky-500/30'
                      : 'bg-violet-500/20 text-violet-300 border border-violet-500/30'
                  }`}>
                    {activeSource === 'instahyre' ? '⚡ Instahyre Active' : activeSource === 'himalayas' ? '🏔️ Himalayas Active' : '🌐 All Active'}
                  </span>
                </div>
                <p className="text-[11px] text-slate-400">
                  Each Excel file has dedicated tabs per keyword + separate sheets for companies with <strong className="text-emerald-300">&lt; 100 people</strong>
                </p>
              </div>
            </div>
            <span className="self-start sm:self-auto text-[11px] px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 font-medium">
              8 Category Workbooks Available
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {categories.map((cat) => {
              const dlState = dlCat[cat.id] || 'idle';
              const IconComp = CATEGORY_ICON_MAP[cat.icon] || FileSpreadsheet;
              const theme = CATEGORY_THEME[cat.id] || CATEGORY_THEME.qa_automation;
              const prefix = activeSource !== 'all' ? `${activeSource.charAt(0).toUpperCase() + activeSource.slice(1)}_` : '';
              const displayFilename = `${prefix}${cat.filename}`;

              return (
                <div
                  key={cat.id}
                  className="glass rounded-2xl p-4 sm:p-5 border border-slate-800/80 hover:border-slate-700 transition-all flex flex-col justify-between space-y-4"
                >
                  <div className="space-y-3">
                    {/* Header: Icon + Title + Counts */}
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-center gap-3 min-w-0">
                        <div className={`w-10 h-10 rounded-xl ${theme.bg} border ${theme.border} ${theme.text} flex items-center justify-center shrink-0 shadow-sm`}>
                          <IconComp className="w-5 h-5" />
                        </div>
                        <div className="min-w-0">
                          <h4 className="text-sm font-bold text-white tracking-tight truncate">{cat.name}</h4>
                          <p className="text-[11px] font-mono text-slate-400 truncate">{displayFilename}</p>
                        </div>
                      </div>

                      {/* Job Count Badges */}
                      <div className="flex flex-col items-end gap-1 shrink-0">
                        <span className="text-[11px] font-mono font-semibold px-2 py-0.5 rounded-lg bg-slate-800 text-slate-200 border border-slate-700/60">
                          {cat.total_jobs.toLocaleString()} jobs
                        </span>
                        <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-lg bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 flex items-center gap-1">
                          🌱 &lt;100: {cat.under_100_jobs}
                        </span>
                      </div>
                    </div>

                    {/* Sheet Tabs Preview */}
                    <div className="bg-slate-900/70 border border-slate-800/80 rounded-xl p-3 space-y-2">
                      <div className="flex items-center justify-between text-[11px] text-slate-400">
                        <span className="flex items-center gap-1.5 font-semibold text-slate-300">
                          <Filter className="w-3.5 h-3.5 text-indigo-400" />
                          Included Sheets
                        </span>
                        <span className="text-[10px] text-emerald-400 font-medium">Includes &lt;100 People Tabs</span>
                      </div>

                      <div className="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto pr-1">
                        <span className="px-2 py-0.5 rounded-md bg-slate-800 text-slate-300 border border-slate-700/60 text-[10px] font-medium">
                          All Jobs ({cat.total_jobs})
                        </span>
                        <span className="px-2 py-0.5 rounded-md bg-emerald-950/70 text-emerald-300 border border-emerald-800/60 text-[10px] font-bold">
                          &lt; 100 People (All) ({cat.under_100_jobs})
                        </span>
                        {cat.keywords.map(kw => {
                          const kwData = cat.keyword_breakdown?.[kw];
                          const total = kwData ? kwData.total : 0;
                          return (
                            <span key={kw} className="px-2 py-0.5 rounded-md bg-indigo-950/40 text-indigo-300 border border-indigo-800/40 text-[10px]">
                              {kw} ({total})
                            </span>
                          );
                        })}
                      </div>
                    </div>
                  </div>

                  {/* Download Action Button */}
                  <button
                    onClick={() => downloadCategory(cat)}
                    disabled={dlState === 'loading'}
                    className={`w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-xs font-bold transition-all active:scale-[0.98] shadow-md cursor-pointer ${
                      dlState === 'done'
                        ? 'bg-emerald-500 text-slate-950'
                        : `bg-gradient-to-r ${theme.btn} text-white`
                    } ${dlState === 'loading' ? 'opacity-60 cursor-not-allowed' : ''}`}
                  >
                    {dlState === 'loading' ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span>Generating {displayFilename}...</span>
                      </>
                    ) : dlState === 'done' ? (
                      <>
                        <Check className="w-4 h-4" />
                        <span>Downloaded {displayFilename}!</span>
                      </>
                    ) : (
                      <>
                        <ArrowDownToLine className="w-4 h-4" />
                        <span>Download {cat.name} ({displayFilename})</span>
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
          source={activeSource}
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
