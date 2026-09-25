import React, { useState, useEffect, useMemo } from 'react';
import {
  Layers,
  Briefcase,
  Building2,
  Sparkles,
  Terminal,
  History,
  Activity,
  Search,
  Zap,
  Clock,
  ExternalLink,
} from 'lucide-react';
import { ExtractionProgress as ProgressData } from '../types/extraction';
import { formatNumber, extractDomain, formatPeopleCount } from '../utils/formatters';

interface ExtractionProgressProps {
  progress: ProgressData | null;
  logs: Array<{ timestamp: string; message: string }>;
}

const AVATAR_COLORS = [
  'bg-indigo-500/20 text-indigo-300 border-indigo-500/30',
  'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
  'bg-violet-500/20 text-violet-300 border-violet-500/30',
  'bg-sky-500/20 text-sky-300 border-sky-500/30',
  'bg-amber-500/20 text-amber-300 border-amber-500/30',
  'bg-rose-500/20 text-rose-300 border-rose-500/30',
  'bg-cyan-500/20 text-cyan-300 border-cyan-500/30',
];

function getAvatarColor(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

export const ExtractionProgress: React.FC<ExtractionProgressProps> = ({ progress, logs }) => {
  const [activeTab, setActiveTab] = useState<'stream' | 'logs'>('stream');
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [elapsedSeconds, setElapsedSeconds] = useState<number>(0);

  // Live timer tracking crawl duration
  useEffect(() => {
    const timer = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const formatElapsed = (sec: number): string => {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  // Speed: jobs per minute
  const jobsPerMinute = useMemo(() => {
    if (elapsedSeconds < 3 || !progress?.jobs_processed) return 0;
    return Math.round((progress.jobs_processed / elapsedSeconds) * 60);
  }, [elapsedSeconds, progress?.jobs_processed]);

  const recentJobs = useMemo(() => progress?.recent_jobs ?? [], [progress?.recent_jobs]);

  // Total new and existing counts
  const newCount = progress?.new_jobs_added ?? progress?.jobs_processed ?? 0;
  const existingCount = progress?.existing_jobs_seen ?? 0;
  const totalCount = progress?.jobs_processed || 1;
  const newPercent = Math.round((newCount / totalCount) * 100);

  const stats = [
    {
      label: 'Pages Processed',
      value: formatNumber(progress?.pages_processed ?? 0),
      icon: Layers,
      color: 'text-sky-400',
      bgColor: 'bg-sky-500/10',
      borderColor: 'border-sky-500/20',
    },
    {
      label: 'Jobs Extracted',
      value: formatNumber(progress?.jobs_processed ?? 0),
      icon: Briefcase,
      color: 'text-indigo-400',
      bgColor: 'bg-indigo-500/10',
      borderColor: 'border-indigo-500/20',
    },
    {
      label: 'New Additions Today',
      value: `+${formatNumber(newCount)}`,
      icon: Sparkles,
      color: 'text-emerald-400',
      bgColor: 'bg-emerald-500/15',
      borderColor: 'border-emerald-500/30',
      highlight: true,
    },
    {
      label: 'Existing Retained',
      value: formatNumber(existingCount),
      icon: History,
      color: 'text-cyan-400',
      bgColor: 'bg-cyan-500/10',
      borderColor: 'border-cyan-500/20',
    },
    {
      label: 'Companies Found',
      value: formatNumber(progress?.companies_discovered ?? 0),
      icon: Building2,
      color: 'text-violet-400',
      bgColor: 'bg-violet-500/10',
      borderColor: 'border-violet-500/20',
    },
  ];

  // Filter recent jobs by search term
  const filteredJobs = useMemo(() => {
    if (!searchTerm.trim()) return recentJobs;
    const term = searchTerm.toLowerCase();
    return recentJobs.filter(
      (j) =>
        j.company_name.toLowerCase().includes(term) ||
        j.job_role.toLowerCase().includes(term) ||
        String(j.number_of_people).toLowerCase().includes(term)
    );
  }, [recentJobs, searchTerm]);

  if (!progress) return null;

  return (
    <div className="w-full max-w-4xl mx-auto space-y-5 animate-fadeIn">
      {/* Target website and speed banner */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-4 bg-slate-900/80 border border-slate-800 rounded-2xl shadow-xl backdrop-blur-md">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-950 border border-slate-800">
            <span className="text-[11px] uppercase tracking-wider font-bold text-slate-400">Target:</span>
            <span className="text-sm font-semibold text-indigo-300 font-mono">
              {extractDomain(progress.website)}
            </span>
          </div>

          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-300 font-mono">
            <Clock className="w-3.5 h-3.5 text-sky-400" />
            <span>{formatElapsed(elapsedSeconds)}</span>
          </div>

          {jobsPerMinute > 0 && (
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs text-amber-300 font-mono">
              <Zap className="w-3.5 h-3.5 text-amber-400" />
              <span>~{formatNumber(jobsPerMinute)}/min</span>
            </div>
          )}
        </div>

        <div className="flex items-center gap-2 text-xs text-slate-400 w-full sm:w-auto justify-start sm:justify-end">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
          </span>
          <span className="font-mono truncate max-w-[280px] sm:max-w-xs text-slate-300">
            {progress.current_action}
          </span>
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {stats.map((item, idx) => {
          const Icon = item.icon;
          return (
            <div
              key={idx}
              className={`p-3.5 rounded-xl border ${item.borderColor} ${item.bgColor} flex flex-col justify-between transition-all duration-300 shadow-md`}
            >
              <div className="flex items-center justify-between text-slate-400 mb-2">
                <span className="text-[11px] font-medium leading-tight">{item.label}</span>
                <Icon className={`w-3.5 h-3.5 ${item.color} shrink-0`} />
              </div>
              <div
                className={`text-xl font-bold tracking-tight font-mono ${
                  item.highlight ? 'text-emerald-300' : 'text-white'
                }`}
              >
                {item.value}
              </div>
            </div>
          );
        })}
      </div>

      {/* Live Delta Progress Ratio Bar */}
      {progress.jobs_processed > 0 && (
        <div className="bg-slate-900/60 border border-slate-800/80 rounded-xl p-3.5 space-y-2">
          <div className="flex items-center justify-between text-xs font-mono">
            <span className="text-emerald-400 font-semibold flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-400 inline-block" />
              New Additions: +{formatNumber(newCount)} ({newPercent}%)
            </span>
            <span className="text-slate-400 flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-slate-500 inline-block" />
              Existing Retained: {formatNumber(existingCount)} ({100 - newPercent}%)
            </span>
          </div>
          <div className="w-full h-2 rounded-full bg-slate-950 overflow-hidden flex">
            <div
              className="h-full bg-gradient-to-r from-emerald-500 to-teal-400 transition-all duration-500"
              style={{ width: `${newPercent}%` }}
            />
            <div
              className="h-full bg-slate-700 transition-all duration-500"
              style={{ width: `${100 - newPercent}%` }}
            />
          </div>
        </div>
      )}

      {/* Interactive Tabs Header */}
      <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 border-b border-slate-800/80 pb-4">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setActiveTab('stream')}
              className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
                activeTab === 'stream'
                  ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30'
                  : 'bg-slate-800/60 text-slate-400 hover:text-white hover:bg-slate-800'
              }`}
            >
              <Activity className="w-3.5 h-3.5" />
              <span>Live Discovered Jobs ({recentJobs.length})</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('logs')}
              className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
                activeTab === 'logs'
                  ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30'
                  : 'bg-slate-800/60 text-slate-400 hover:text-white hover:bg-slate-800'
              }`}
            >
              <Terminal className="w-3.5 h-3.5" />
              <span>Activity Log ({logs.length})</span>
            </button>
          </div>

          {activeTab === 'stream' && recentJobs.length > 0 && (
            <div className="relative flex items-center">
              <Search className="w-3.5 h-3.5 text-slate-500 absolute left-3 pointer-events-none" />
              <input
                type="text"
                placeholder="Quick search live stream..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full sm:w-60 pl-8 pr-3 py-1.5 text-xs bg-slate-950/80 border border-slate-700/80 rounded-lg text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              />
            </div>
          )}
        </div>

        {/* Tab 1: Live Stream of Discovered Jobs */}
        {activeTab === 'stream' && (
          <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
            {filteredJobs.length > 0 ? (
              filteredJobs
                .slice()
                .reverse()
                .map((job, idx) => {
                  const initial = (job.company_name || 'C').charAt(0).toUpperCase();
                  const avatarClass = getAvatarColor(job.company_name || '');
                  const isNew = job.is_new ?? (job.status === 'NEW');

                  return (
                    <div
                      key={idx}
                      className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-3 rounded-xl bg-slate-950/70 border border-slate-800/80 hover:border-slate-700 transition-all group"
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <div
                          className={`w-8 h-8 rounded-lg border flex items-center justify-center font-bold text-xs shrink-0 ${avatarClass}`}
                        >
                          {initial}
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-sm text-slate-100 truncate">
                              {job.company_name}
                            </span>
                            {job.job_url && (
                              <a
                                href={job.job_url}
                                target="_blank"
                                rel="noreferrer"
                                className="text-slate-500 hover:text-indigo-400 transition-colors"
                              >
                                <ExternalLink className="w-3 h-3" />
                              </a>
                            )}
                          </div>
                          <span className="text-xs text-slate-400 block truncate">
                            {job.job_role}
                          </span>
                        </div>
                      </div>

                      <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
                        <span className="px-2.5 py-1 rounded-md text-[11px] font-mono bg-slate-900 border border-slate-800 text-slate-300">
                          👥 {formatPeopleCount(job.number_of_people)}
                        </span>
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold font-mono border ${
                            isNew
                              ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                              : 'bg-slate-800/80 text-slate-400 border-slate-700'
                          }`}
                        >
                          {isNew ? '🟢 NEW' : '⚪ EXISTING'}
                        </span>
                      </div>
                    </div>
                  );
                })
            ) : (
              <div className="text-center py-10 text-slate-500 text-xs italic">
                {recentJobs.length === 0
                  ? 'Connecting to stream and waiting for initial job cards...'
                  : 'No live jobs match your search filter.'}
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Activity Terminal Stream */}
        {activeTab === 'logs' && (
          <div className="space-y-1.5 max-h-72 overflow-y-auto pr-2 font-mono text-xs">
            {logs.map((log, i) => (
              <div key={i} className="flex items-start gap-2.5 text-slate-300 leading-relaxed">
                <span className="text-slate-500 select-none text-[11px]">{log.timestamp}</span>
                <span className="text-indigo-400 select-none">&rsaquo;</span>
                <span className="flex-1 break-words">{log.message}</span>
              </div>
            ))}
            {logs.length === 0 && (
              <div className="text-slate-500 italic py-4 text-center">
                Waiting for initial crawler activity log...
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
