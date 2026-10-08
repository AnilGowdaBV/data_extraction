import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Briefcase, ExternalLink, Users, Search,
  RefreshCw, ChevronRight, Zap, Check, MapPin, UserCheck,
} from 'lucide-react';

import { PrefillJob } from './ApplyModal';
import { API_BASE } from '../config/api';


export interface RecentJob {
  id: number;
  company_name: string;
  job_role: string;
  location?: string | null;
  posted_by?: string | null;
  number_of_people?: string | null;
  job_url?: string | null;
  source_website: string;
  first_seen_at?: string | null;
  posted_date?: string | null;
  role_category: string;
}

interface RecentJobsFeedProps {
  onApplyJob: (job: PrefillJob) => void;
  refreshTrigger?: number;
  source?: string;
}

const CATEGORY_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  'SDE':          { bg: 'bg-indigo-500/12', text: 'text-indigo-300', border: 'border-indigo-500/30' },
  'Frontend':     { bg: 'bg-sky-500/12',    text: 'text-sky-300',    border: 'border-sky-500/30' },
  'Backend':      { bg: 'bg-violet-500/12', text: 'text-violet-300', border: 'border-violet-500/30' },
  'Full Stack':   { bg: 'bg-teal-500/12',   text: 'text-teal-300',   border: 'border-teal-500/30' },
  'DevOps':       { bg: 'bg-orange-500/12', text: 'text-orange-300', border: 'border-orange-500/30' },
  'Data / ML':    { bg: 'bg-emerald-500/12',text: 'text-emerald-300',border: 'border-emerald-500/30' },
  'Mobile':       { bg: 'bg-pink-500/12',   text: 'text-pink-300',   border: 'border-pink-500/30' },
  'QA / Testing': { bg: 'bg-yellow-500/12', text: 'text-yellow-300', border: 'border-yellow-500/30' },
  'Management':   { bg: 'bg-rose-500/12',   text: 'text-rose-300',   border: 'border-rose-500/30' },
  'Other':        { bg: 'bg-slate-700/40',  text: 'text-slate-400',  border: 'border-slate-600/40' },
};

const COMPANY_GRADIENTS = [
  'from-indigo-600 to-violet-600',
  'from-violet-600 to-purple-600',
  'from-sky-600 to-indigo-600',
  'from-emerald-600 to-teal-600',
  'from-pink-600 to-rose-600',
  'from-amber-600 to-orange-600',
];

function getCompanyGradient(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  const idx = Math.abs(hash) % COMPANY_GRADIENTS.length;
  return COMPANY_GRADIENTS[idx];
}

function formatRelativeTime(dateStr?: string | null): string {
  if (!dateStr) return 'Recently';
  try {
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return dateStr;
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  } catch {
    return 'Recently';
  }
}

export const RecentJobsFeed: React.FC<RecentJobsFeedProps> = ({ onApplyJob, refreshTrigger = 0, source = 'himalayas' }) => {
  const [jobs, setJobs] = useState<RecentJob[]>([]);
  const [limit, setLimit] = useState<number>(20);
  const [search, setSearch] = useState<string>('');
  const [selectedCat, setSelectedCat] = useState<string>('All');
  const [loading, setLoading] = useState<boolean>(false);
  const [appliedJobId, setAppliedJobId] = useState<number | null>(null);

  const fetchRecentJobs = useCallback(async () => {
    setLoading(true);
    try {
      const srcParam = encodeURIComponent(source);
      const res = await fetch(`${API_BASE}/api/applications/recent-jobs?limit=${limit}&source=${srcParam}`);
      if (res.ok) {
        const data = await res.json();
        setJobs(data.jobs || []);
      }
    } catch {
      /* silent */
    } finally {
      setLoading(false);
    }
  }, [limit, source]);

  useEffect(() => {
    fetchRecentJobs();
  }, [fetchRecentJobs]);

  useEffect(() => {
    if (refreshTrigger > 0) {
      fetchRecentJobs();
    }
  }, [refreshTrigger, fetchRecentJobs]);

  // Unique categories for filter pills
  const categories = useMemo(() => {
    const set = new Set<string>();
    jobs.forEach(j => set.add(j.role_category || 'Other'));
    return ['All', ...Array.from(set)];
  }, [jobs]);

  // Filtered jobs
  const filteredJobs = useMemo(() => {
    const q = search.trim().toLowerCase();
    return jobs.filter(j => {
      const matchesCat = selectedCat === 'All' || j.role_category === selectedCat;
      const matchesQuery =
        !q ||
        j.job_role.toLowerCase().includes(q) ||
        j.company_name.toLowerCase().includes(q);
      return matchesCat && matchesQuery;
    });
  }, [jobs, search, selectedCat]);

  const handleApplyClick = (job: RecentJob) => {
    setAppliedJobId(job.id);
    onApplyJob({
      job_role: job.job_role,
      company_name: job.company_name,
      job_url: job.job_url || undefined,
      role_category: job.role_category,
    });
    setTimeout(() => setAppliedJobId(null), 1500);
  };

  return (
    <div className="space-y-4">
      {/* ── Control Header ── */}
      <div className="glass rounded-2xl p-4 space-y-3 border-sky-500/20">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          {/* Title & Badge */}
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-xl bg-gradient-to-tr from-sky-600 to-indigo-500 flex items-center justify-center shadow-lg shadow-sky-500/25">
              <Zap className="w-4 h-4 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-extrabold text-white tracking-tight">Recent Scraped Jobs</h3>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-sky-500/15 border border-sky-500/30 text-sky-300 font-semibold">
                  Himalayas Live
                </span>
              </div>
              <p className="text-[11px] text-slate-400">
                Click <span className="text-indigo-400 font-semibold">Apply</span> to pre-fill candidate details for any role
              </p>
            </div>
          </div>

          {/* Right controls: Limit selector + Refresh */}
          <div className="flex items-center gap-2 self-start sm:self-auto">
            {/* Limit selector (10, 15, 20, 25) */}
            <div className="flex items-center bg-slate-900/90 border border-slate-700/80 rounded-xl p-1 gap-1">
              <span className="text-[10px] text-slate-500 font-semibold px-1.5 uppercase">Show</span>
              {[10, 15, 20, 25].map(n => (
                <button
                  key={n}
                  onClick={() => setLimit(n)}
                  className={`px-2 py-0.5 rounded-lg text-xs font-bold transition-all ${
                    limit === n
                      ? 'bg-indigo-600 text-white shadow-sm'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                  }`}
                >
                  {n}
                </button>
              ))}
            </div>

            {/* Refresh */}
            <button
              onClick={fetchRecentJobs}
              disabled={loading}
              title="Refresh recent jobs"
              className="p-2 rounded-xl glass hover:border-indigo-500/30 text-slate-400 hover:text-white transition-all active:scale-95"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-indigo-400' : ''}`} />
            </button>
          </div>
        </div>

        {/* ── Search & Category Filter Row ── */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 pt-1 border-t border-slate-800/60">
          {/* Quick search input */}
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" />
            <input
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search recent roles or companies (e.g. Meesho, SDE, AI)..."
              className="w-full bg-slate-900/80 border border-slate-700/60 rounded-xl pl-9 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
            />
            {search && (
              <button
                onClick={() => setSearch('')}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 text-xs"
              >
                ✕
              </button>
            )}
          </div>

          {/* Category Chips */}
          <div className="flex items-center gap-1 overflow-x-auto pb-0.5 sm:pb-0 scrollbar-none">
            {categories.slice(0, 6).map(cat => (
              <button
                key={cat}
                onClick={() => setSelectedCat(cat)}
                className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold whitespace-nowrap transition-all ${
                  selectedCat === cat
                    ? 'bg-indigo-600 text-white shadow-sm'
                    : 'bg-slate-900/70 border border-slate-800 text-slate-400 hover:text-slate-200 hover:border-slate-700'
                }`}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ── Cards Grid ── */}
      {loading && jobs.length === 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="glass rounded-2xl p-4 space-y-3 animate-pulse">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-slate-800" />
                <div className="space-y-1 flex-1">
                  <div className="h-3.5 bg-slate-800 rounded w-28" />
                  <div className="h-2.5 bg-slate-800/60 rounded w-20" />
                </div>
              </div>
              <div className="h-4 bg-slate-800 rounded w-3/4" />
              <div className="h-8 bg-slate-800/80 rounded-xl" />
            </div>
          ))}
        </div>
      ) : filteredJobs.length === 0 ? (
        <div className="glass rounded-2xl p-10 text-center space-y-2">
          <Briefcase className="w-8 h-8 text-slate-600 mx-auto" />
          <p className="text-sm font-semibold text-slate-400">No jobs match your filter</p>
          <p className="text-xs text-slate-600">Try adjusting your search query or category filter</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {filteredJobs.map(job => {
            const catStyle = CATEGORY_COLORS[job.role_category] ?? CATEGORY_COLORS['Other'];
            const companyInitial = job.company_name ? job.company_name.charAt(0).toUpperCase() : 'J';
            const gradient = getCompanyGradient(job.company_name || 'Job');

            return (
              <div
                key={job.id}
                className="group relative glass rounded-2xl p-4 flex flex-col justify-between gap-3 border border-slate-800/80 hover:border-indigo-500/40 bg-slate-950/40 hover:bg-slate-900/50 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-xl hover:shadow-indigo-950/30"
              >
                {/* Top header: Company + Category */}
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2.5 min-w-0">
                    {/* Company Initial Badge */}
                    <div
                      className={`w-8 h-8 rounded-xl bg-gradient-to-tr ${gradient} flex items-center justify-center text-white font-extrabold text-xs shadow-md shrink-0`}
                    >
                      {companyInitial}
                    </div>

                    <div className="min-w-0">
                      <p className="text-xs font-bold text-white truncate group-hover:text-indigo-200 transition-colors">
                        {job.company_name}
                      </p>
                      <div className="flex items-center gap-2 truncate mt-0.5">
                        {job.number_of_people && (
                          <p className="text-[10px] text-slate-500 truncate flex items-center gap-1">
                            <Users className="w-2.5 h-2.5 shrink-0" />
                            <span>{job.number_of_people.replace('employees', 'emp')}</span>
                          </p>
                        )}
                        {job.location && job.location !== 'N/A' && (
                          <p className="text-[10px] text-indigo-300/90 truncate flex items-center gap-0.5 font-medium">
                            <MapPin className="w-2.5 h-2.5 shrink-0 text-indigo-400" />
                            <span>{job.location}</span>
                          </p>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Category Pill */}
                  <span
                    className={`shrink-0 text-[10px] font-bold px-2 py-0.5 rounded-full border ${catStyle.bg} ${catStyle.text} ${catStyle.border}`}
                  >
                    {job.role_category}
                  </span>
                </div>

                {/* Role Title */}
                <div className="min-h-[38px] flex flex-col justify-center">
                  <h4 className="text-sm font-extrabold text-slate-100 group-hover:text-white line-clamp-2 leading-tight tracking-tight">
                    {job.job_role}
                  </h4>
                </div>

                {/* Recruiter / Posted By */}
                {job.posted_by && job.posted_by !== 'N/A' && (
                  <p
                    className="text-[11px] text-emerald-300 truncate flex items-center gap-1.5 font-medium bg-emerald-950/30 px-2 py-1 rounded-lg border border-emerald-500/20"
                    title={`Posted by: ${job.posted_by}`}
                  >
                    <UserCheck className="w-3.5 h-3.5 shrink-0 text-emerald-400" />
                    <span className="truncate">
                      <span className="text-slate-400 font-normal">Posted by: </span>
                      {job.posted_by}
                    </span>
                  </p>
                )}

                {/* Footer Info & Action */}
                <div className="pt-2 border-t border-slate-800/60 flex items-center justify-between gap-2">
                  {/* Left: Scrape date / relative time + optional external link */}
                  <div className="flex items-center gap-1.5 text-[11px] text-slate-500">
                    <span className="font-mono text-[10px] text-slate-400">
                      {job.posted_date || formatRelativeTime(job.first_seen_at)}
                    </span>
                    {job.source_website && (
                      <span className={`text-[9px] px-1.5 py-0.5 rounded font-medium ${
                        job.source_website.includes('instahyre')
                          ? 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/30'
                          : 'bg-sky-500/10 text-sky-300 border border-sky-500/30'
                      }`}>
                        {job.source_website.includes('instahyre') ? 'Instahyre' : 'Himalayas'}
                      </span>
                    )}

                    {job.job_url && (
                      <a
                        href={job.job_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-slate-500 hover:text-indigo-300 transition-colors p-0.5"
                        title="Open original job posting"
                      >
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    )}
                  </div>

                  {/* Right: Apply Button */}
                  <button
                    onClick={() => handleApplyClick(job)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white shadow-md shadow-indigo-950/40 transition-all active:scale-95"
                  >
                    {appliedJobId === job.id ? (
                      <>
                        <Check className="w-3 h-3 text-emerald-300" />
                        <span>Opening...</span>
                      </>
                    ) : (
                      <>
                        <Briefcase className="w-3 h-3" />
                        <span>Apply</span>
                        <ChevronRight className="w-3 h-3 -ml-0.5 opacity-60" />
                      </>
                    )}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
