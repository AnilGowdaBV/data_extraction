import React from 'react';
import { Download, FileSpreadsheet } from 'lucide-react';

interface DownloadButtonProps {
  downloadUrl: string;
}

export const DownloadButton: React.FC<DownloadButtonProps> = ({ downloadUrl }) => {
  return (
    <a
      href={downloadUrl}
      download="jobs.xlsx"
      className="inline-flex items-center justify-center gap-3 px-8 py-4 rounded-xl font-bold text-base bg-emerald-500 hover:bg-emerald-400 text-slate-950 transition-all shadow-xl shadow-emerald-950/40 hover:shadow-emerald-500/20 active:scale-95 group"
    >
      <FileSpreadsheet className="w-5 h-5 text-slate-950 group-hover:scale-110 transition-transform" />
      <span>Download jobs.xlsx</span>
      <Download className="w-4 h-4 text-slate-800" />
    </a>
  );
};
