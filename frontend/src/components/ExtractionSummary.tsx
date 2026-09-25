import React, { useState, useMemo } from 'react';
import {
  CheckCircle2,
  Building2,
  Briefcase,
  Sparkles,
  History,
  Layers,
  RotateCcw,
  Filter,
  Search,
} from 'lucide-react';
import { ExtractionSummary as SummaryData } from '../types/extraction';
import { formatNumber, formatPeopleCount } from '../utils/formatters';
import { DownloadButton } from './DownloadButton';

interface ExtractionSummaryProps {
  summary: SummaryData | null;
  onReset: () => void;
}

export const ExtractionSummary: React.FC<ExtractionSummaryProps> = ({ summary, onReset }) => {
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'NEW' | 'EXISTING'>('ALL');
  const [sizeFilter, setSizeFilter] = useState<string>('ALL');
  const [searchTerm, setSearchTerm] = useState<string>('');

  const previewRecords = useMemo(() => summary?.preview_records ?? [], [summary?.preview_records]);

  const statItems = [
    {
      label: 'Total Jobs Extracted',
      value: formatNumber(summary?.total_jobs ?? 0),
      icon: Briefcase,
      color: 'text-indigo-400',
    },
    {
      label: 'New Additions Today',
      value: `+${formatNumber(summary?.new_jobs_added ?? summary?.total_jobs ?? 0)}`,
      icon: Sparkles,
      color: 'text-emerald-400',
      highlight: true,
    },
    {
      label: 'Existing Retained',
      value: formatNumber(summary?.existing_jobs_seen ?? 0),
      icon: History,
      color: 'text-cyan-400',
    },
    {
      label: 'Companies Discovered',
      value: formatNumber(summary?.total_companies ?? 0),
      icon: Building2,
      color: 'text-violet-400',
    },
    {
      label: 'Pages Crawled',
      value: formatNumber(summary?.pages_processed ?? 0),
      icon: Layers,
      color: 'text-sky-400',
    },
  ];

  const uniqueSizes = useMemo(() => {
    const sizes = new Set<string>();
    previewRecords.forEach((r) => {
      if (r.number_of_people && r.number_of_people !== 'N/A') {
        sizes.add(String(r.number_of_people));
      }
    });
    return Array.from(sizes).sort();
  }, [previewRecords]);

  const filteredRecords = useMemo(() => {
    return previewRecords.filter((job) => {
      // Status filter
      if (statusFilter !== 'ALL') {
        const jobStatus = job.status || (job.is_new ? 'NEW' : 'EXISTING');
        if (jobStatus !== statusFilter) return false;
      }
      // Size filter
      if (sizeFilter !== 'ALL') {
        if (String(job.number_of_people) !== sizeFilter) return false;
      }
      // Search term
      if (searchTerm.trim()) {
        const term = searchTerm.toLowerCase();
        const matchesComp = job.company_name.toLowerCase().includes(term);
        const matchesRole = job.job_role.toLowerCase().includes(term);
        if (!matchesComp && !matchesRole) return false;
      }
      return true;
    });
  }, [previewRecords, statusFilter, sizeFilter, searchTerm]);

  if (!summary) return null;

  return (
    <div className="w-full max-w-4xl mx-auto space-y-8 animate-fadeIn">
      {/* Success Hero Card */}
      <div className="bg-gradient-to-b from-slate-900 to-slate-950 border border-slate-800 rounded-2xl p-8 text-center space-y-6 shadow-2xl relative overflow-hidden">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-96 h-32 bg-indigo-500/10 blur-3xl pointer-events-none rounded-full" />

        <div className="inline-flex p-3 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 mb-2">
          <CheckCircle2 className="w-8 h-8" />
        </div>

        <div>
          <h2 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
            Extraction Complete
          </h2>
          <p className="text-sm text-slate-400 mt-2 max-w-lg mx-auto">
            All records have been indexed, compared against past database runs, and packaged with green highlights into Excel.
          </p>
        </div>

        {/* Metrics Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 pt-2">
          {statItems.map((item, idx) => {
            const Icon = item.icon;
            return (
              <div
                key={idx}
                className={`bg-slate-950/60 border rounded-xl p-3 flex flex-col items-center justify-center text-center ${
                  item.highlight
                    ? 'border-emerald-500/40 bg-emerald-500/10'
                    : 'border-slate-800/80'
                }`}
              >
                <Icon className={`w-4 h-4 ${item.color} mb-1.5`} />
                <span className="text-[10px] font-medium text-slate-400 uppercase tracking-wider">
                  {item.label}
                </span>
                <span
                  className={`text-lg font-bold font-mono mt-1 ${
                    item.highlight ? 'text-emerald-300' : 'text-white'
                  }`}
                >
                  {item.value}
                </span>
              </div>
            );
          })}
        </div>

        {/* Primary Download Action */}
        <div className="pt-4 flex flex-col sm:flex-row items-center justify-center gap-4">
          <DownloadButton downloadUrl={summary.download_url} />
          <button
            type="button"
            onClick={onReset}
            className="inline-flex items-center gap-2 px-6 py-4 rounded-xl text-sm font-semibold text-slate-400 hover:text-white bg-slate-800/60 hover:bg-slate-800 border border-slate-700/60 transition-all active:scale-95"
          >
            <RotateCcw className="w-4 h-4" />
            <span>Extract Another Website</span>
          </button>
        </div>
      </div>

      {/* Dataset Sample Preview with Interactive Filters */}
      {summary.preview_records && summary.preview_records.length > 0 && (
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-5">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
            <div>
              <h3 className="text-base font-bold text-slate-200">
                Interactive Preview & Filters ({filteredRecords.length} of{' '}
                {summary.preview_records.length} shown)
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Filter instantly by Status (New / Existing) or Employee Count range
              </p>
            </div>
            <div className="text-xs text-slate-500 font-mono">
              Total Extracted: {formatNumber(summary.total_jobs)}
            </div>
          </div>

          {/* Filter Bar */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-3.5 bg-slate-950/70 border border-slate-800/80 rounded-xl">
            {/* Status Filter */}
            <div className="flex flex-col gap-1.5">
              <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <Filter className="w-3 h-3 text-indigo-400" /> Filter by Status
              </label>
              <select
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value as 'ALL' | 'NEW' | 'EXISTING');
                }}
                className="bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
              >
                <option value="ALL">All Statuses (New & Existing)</option>
                <option value="NEW">🟢 NEW Only (Fresh Additions)</option>
                <option value="EXISTING">⚪ EXISTING Only (Previously Indexed)</option>
              </select>
            </div>

            {/* Employee Count Range Filter */}
            <div className="flex flex-col gap-1.5">
              <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <Building2 className="w-3 h-3 text-emerald-400" /> Filter by Employees
              </label>
              <select
                value={sizeFilter}
                onChange={(e) => setSizeFilter(e.target.value)}
                className="bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-emerald-500"
              >
                <option value="ALL">All Employee Sizes</option>
                {uniqueSizes.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>

            {/* Search Filter */}
            <div className="flex flex-col gap-1.5">
              <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <Search className="w-3 h-3 text-sky-400" /> Search Company / Role
              </label>
              <input
                type="text"
                placeholder="Type to filter..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-sky-500"
              />
            </div>
          </div>

          {/* Table */}
          <div className="overflow-x-auto rounded-xl border border-slate-800">
            <table className="w-full text-left border-collapse text-xs sm:text-sm">
              <thead>
                <tr className="bg-slate-950 border-b border-slate-800 text-slate-400 font-semibold uppercase tracking-wider text-[11px]">
                  <th className="py-3 px-4">Company Name</th>
                  <th className="py-3 px-4">Job Role</th>
                  <th className="py-3 px-4">Number of People</th>
                  <th className="py-3 px-4 text-center">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {filteredRecords.map((job, idx) => (
                  <tr
                    key={idx}
                    className={`transition-colors ${
                      job.status === 'NEW' ? 'bg-emerald-500/5 hover:bg-emerald-500/10' : 'hover:bg-slate-800/30'
                    }`}
                  >
                    <td className="py-3 px-4 font-medium text-slate-200">{job.company_name}</td>
                    <td className="py-3 px-4 text-slate-300">{job.job_role}</td>
                    <td className="py-3 px-4 font-mono text-slate-300">
                      {formatPeopleCount(job.number_of_people)}
                    </td>
                    <td className="py-3 px-4 text-center">
                      <span
                        className={`inline-flex px-2 py-0.5 rounded text-[11px] font-bold font-mono ${
                          job.status === 'NEW'
                            ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                            : 'bg-slate-800 text-slate-400 border border-slate-700'
                        }`}
                      >
                        {job.status ?? 'NEW'}
                      </span>
                    </td>
                  </tr>
                ))}
                {filteredRecords.length === 0 && (
                  <tr>
                    <td colSpan={4} className="py-8 text-center text-slate-500 italic">
                      No records match the selected filters.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
