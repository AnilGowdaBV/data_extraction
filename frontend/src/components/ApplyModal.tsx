import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  X, User, Phone, Linkedin, Briefcase, Upload,
  Search, CheckCircle2, Loader2, AlertCircle, ChevronRight, FileText,
} from "lucide-react";

import { API_BASE } from "../config/api";

interface RoleResult {
  job_role: string;
  company_name: string;
  job_url: string;
  role_category: string;
}

export interface PrefillJob {
  job_role: string;
  company_name?: string;
  job_url?: string;
  role_category?: string;
}

interface ApplyModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
  prefillRole?: PrefillJob | null;
}

type SubmitState = "idle" | "loading" | "success" | "error";

const CATEGORY_COLORS: Record<string, string> = {
  "SDE":          "bg-indigo-500/15 text-indigo-300 border-indigo-500/30",
  "Frontend":     "bg-sky-500/15 text-sky-300 border-sky-500/30",
  "Backend":      "bg-violet-500/15 text-violet-300 border-violet-500/30",
  "Full Stack":   "bg-teal-500/15 text-teal-300 border-teal-500/30",
  "DevOps":       "bg-orange-500/15 text-orange-300 border-orange-500/30",
  "Data / ML":    "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  "Mobile":       "bg-pink-500/15 text-pink-300 border-pink-500/30",
  "QA / Testing": "bg-yellow-500/15 text-yellow-300 border-yellow-500/30",
  "Management":   "bg-rose-500/15 text-rose-300 border-rose-500/30",
  "Other":        "bg-slate-700 text-slate-400 border-slate-600",
};

export const ApplyModal: React.FC<ApplyModalProps> = ({ isOpen, onClose, onSuccess, prefillRole }) => {

  const [name, setName] = useState("");
  const [contact, setContact] = useState("");
  const [linkedin, setLinkedin] = useState("");
  const [currentSalary, setCurrentSalary] = useState("");
  const [expectedSalary, setExpectedSalary] = useState("");
  const [noticePeriod, setNoticePeriod] = useState("");
  const [roleQuery, setRoleQuery] = useState("");
  const [selectedRole, setSelectedRole] = useState<RoleResult | null>(null);
  const [roleResults, setRoleResults] = useState<RoleResult[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [searchLoading, setSearchLoading] = useState(false);
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [submitState, setSubmitState] = useState<SubmitState>("idle");
  const [submitMsg, setSubmitMsg] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});

  const searchRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Search roles with debounce
  const searchRoles = useCallback(async (q: string) => {
    if (!q.trim()) { setRoleResults([]); setShowDropdown(false); return; }
    setSearchLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/applications/search-roles?q=${encodeURIComponent(q)}&limit=20`);
      if (res.ok) {
        const data = await res.json();
        setRoleResults(data.results || []);
        setShowDropdown(true);
      }
    } catch { /* silent */ }
    finally { setSearchLoading(false); }
  }, []);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => searchRoles(roleQuery), 300);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [roleQuery, searchRoles]);

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // Reset when closed
  useEffect(() => {
    if (!isOpen) {
      setTimeout(() => {
        setName(""); setContact(""); setLinkedin(""); setRoleQuery("");
        setCurrentSalary(""); setExpectedSalary(""); setNoticePeriod("");
        setSelectedRole(null); setRoleResults([]); setShowDropdown(false);
        setResumeFile(null); setSubmitState("idle"); setSubmitMsg(""); setErrors({});
      }, 300);
    }
  }, [isOpen]);

  // Handle pre-filled role from recent job cards
  useEffect(() => {
    if (isOpen && prefillRole) {
      setSelectedRole({
        job_role: prefillRole.job_role,
        company_name: prefillRole.company_name || "",
        job_url: prefillRole.job_url || "",
        role_category: prefillRole.role_category || "Other",
      });
      setRoleQuery(prefillRole.job_role);
      setShowDropdown(false);
    }
  }, [isOpen, prefillRole]);


  const validate = () => {
    const errs: Record<string, string> = {};
    if (!name.trim()) errs.name = "Required";
    if (!contact.trim()) errs.contact = "Required";
    if (!selectedRole && !roleQuery.trim()) errs.role = "Search and select a role";
    if (!currentSalary.trim()) errs.currentSalary = "Required";
    if (!expectedSalary.trim()) errs.expectedSalary = "Required";
    if (!noticePeriod.trim()) errs.noticePeriod = "Required";
    return errs;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length > 0) { setErrors(errs); return; }
    setErrors({});
    setSubmitState("loading");

    try {
      const fd = new FormData();
      fd.append("name", name.trim());
      fd.append("contact", contact.trim());
      if (linkedin.trim()) fd.append("linkedin_url", linkedin.trim());
      fd.append("job_role", selectedRole ? selectedRole.job_role : roleQuery.trim());
      if (selectedRole?.company_name) fd.append("company_name", selectedRole.company_name);
      if (selectedRole?.job_url) fd.append("job_url", selectedRole.job_url);
      if (currentSalary.trim()) fd.append("current_salary", currentSalary.trim());
      if (expectedSalary.trim()) fd.append("expected_salary", expectedSalary.trim());
      if (noticePeriod.trim()) fd.append("notice_period", noticePeriod.trim());
      if (resumeFile) fd.append("resume", resumeFile);

      const res = await fetch(`${API_BASE}/api/applications/apply`, { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Submission failed");
      setSubmitState("success");
      setSubmitMsg(`Application submitted! Categorized as: ${data.role_category}`);
      onSuccess?.();
    } catch (err: unknown) {
      setSubmitState("error");
      setSubmitMsg(err instanceof Error ? err.message : "Submission failed");
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4"
      style={{ backgroundColor: "rgba(0,0,0,0.75)", backdropFilter: "blur(6px)" }}
    >
      <div className="relative w-full max-w-lg bg-slate-950 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden animate-fadeIn">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-gradient-to-r from-indigo-950/60 to-slate-950">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center shadow-lg">
              <Briefcase className="w-4 h-4 text-white" />
            </div>
            <div>
              <h2 className="text-base font-extrabold text-white">Apply for a Job</h2>
              <p className="text-[11px] text-slate-400">Search from 5,000+ Instahyre roles</p>
            </div>
          </div>
          <button onClick={onClose} className="text-slate-500 hover:text-white p-1.5 rounded-lg hover:bg-slate-800 transition-all">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Success state */}
        {submitState === "success" ? (
          <div className="flex flex-col items-center justify-center py-14 px-6 gap-4 text-center">
            <div className="h-16 w-16 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center">
              <CheckCircle2 className="w-8 h-8 text-emerald-400" />
            </div>
            <h3 className="text-xl font-bold text-white">Application Submitted!</h3>
            <p className="text-sm text-slate-400 max-w-xs">{submitMsg}</p>
            <p className="text-xs text-slate-500">Your details have been saved to the applications archive. Download the Excel to see all applicants.</p>
            <button onClick={onClose} className="mt-2 px-6 py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-sm transition-all">
              Close
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="px-6 py-4 space-y-3">
            {/* Error banner */}
            {submitState === "error" && (
              <div className="flex items-center gap-2 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs">
                <AlertCircle className="w-4 h-4 shrink-0" />
                {submitMsg}
              </div>
            )}

            {/* Name + Contact — side by side */}
            <div className="grid grid-cols-2 gap-2.5">
              <Field label="Full Name" icon={<User className="w-3.5 h-3.5" />} error={errors.name} required>
                <input value={name} onChange={e => setName(e.target.value)} placeholder="Rahul Sharma" className={inputClass(!!errors.name)} />
              </Field>
              <Field label="Contact" icon={<Phone className="w-3.5 h-3.5" />} error={errors.contact} required>
                <input value={contact} onChange={e => setContact(e.target.value)} placeholder="+91 98765 43210" type="tel" className={inputClass(!!errors.contact)} />
              </Field>
            </div>

            {/* LinkedIn */}
            <Field label="LinkedIn URL" icon={<Linkedin className="w-3.5 h-3.5" />}>
              <input value={linkedin} onChange={e => setLinkedin(e.target.value)} placeholder="https://linkedin.com/in/yourname" className={inputClass(false)} />
            </Field>


            {/* Role search */}
            <div ref={searchRef} className="relative">
              <Field label="Job Role" icon={<Search className="w-3.5 h-3.5" />} error={errors.role} required>
                {selectedRole ? (
                  <div className="flex items-center gap-2 px-3 py-2.5 rounded-xl bg-indigo-500/10 border border-indigo-500/40 text-sm">
                    <span className="flex-1 text-indigo-200 font-medium truncate">{selectedRole.job_role}</span>
                    {selectedRole.company_name && <span className="text-xs text-slate-400 truncate hidden sm:block">{selectedRole.company_name}</span>}
                    <span className={`text-[10px] px-1.5 py-0.5 rounded border font-semibold ${CATEGORY_COLORS[selectedRole.role_category] ?? CATEGORY_COLORS.Other}`}>
                      {selectedRole.role_category}
                    </span>
                    <button type="button" onClick={() => { setSelectedRole(null); setRoleQuery(""); }} className="text-slate-500 hover:text-rose-400 ml-1"><X className="w-3.5 h-3.5" /></button>
                  </div>
                ) : (
                  <div className="relative">
                    <input
                      value={roleQuery}
                      onChange={e => { setRoleQuery(e.target.value); setSelectedRole(null); }}
                      onFocus={() => roleResults.length > 0 && setShowDropdown(true)}
                      placeholder="Type to search: SDE, Frontend, DevOps..."
                      className={inputClass(!!errors.role)}
                    />
                    {searchLoading && <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-indigo-400 animate-spin" />}
                  </div>
                )}
              </Field>

              {/* Dropdown */}
              {showDropdown && roleResults.length > 0 && !selectedRole && (
                <div className="absolute z-50 w-full mt-1 bg-slate-900 border border-slate-700 rounded-xl shadow-2xl overflow-hidden max-h-56 overflow-y-auto">
                  {roleResults.map((r, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => { setSelectedRole(r); setShowDropdown(false); setErrors(prev => ({...prev, role: ""})); }}
                      className="w-full flex items-center gap-2 px-3 py-2.5 hover:bg-slate-800 text-left transition-colors group"
                    >
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-slate-200 font-medium truncate">{r.job_role}</p>
                        {r.company_name && <p className="text-xs text-slate-500 truncate">{r.company_name}</p>}
                      </div>
                      <span className={`shrink-0 text-[10px] px-1.5 py-0.5 rounded border font-semibold ${CATEGORY_COLORS[r.role_category] ?? CATEGORY_COLORS.Other}`}>
                        {r.role_category}
                      </span>
                      <ChevronRight className="w-3 h-3 text-slate-600 group-hover:text-slate-300 shrink-0" />
                    </button>
                  ))}
                </div>
              )}
              {showDropdown && roleResults.length === 0 && roleQuery && !searchLoading && (
                <div className="absolute z-50 w-full mt-1 bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-xs text-slate-400">
                  No matching roles found. Your typed role will still be recorded.
                </div>
              )}
            </div>

            {/* Salary & Notice Period — 2-col compact grid */}
            <div className="grid grid-cols-2 gap-2.5">
              <Field label="Current Salary" icon={<span className="text-xs font-bold">₹</span>} error={errors.currentSalary} required>
                <input
                  value={currentSalary}
                  onChange={e => setCurrentSalary(e.target.value)}
                  placeholder="e.g. 8 LPA"
                  className={inputClass(!!errors.currentSalary)}
                />
              </Field>
              <Field label="Expected Salary" icon={<span className="text-xs font-bold">₹</span>} error={errors.expectedSalary} required>
                <input
                  value={expectedSalary}
                  onChange={e => setExpectedSalary(e.target.value)}
                  placeholder="e.g. 14 LPA"
                  className={inputClass(!!errors.expectedSalary)}
                />
              </Field>
            </div>

            <Field label="Notice Period" icon={<span className="text-xs font-bold">⏱</span>} error={errors.noticePeriod} required>
              <div className="grid grid-cols-4 gap-1.5">
                {['Immediate', '15 days', '30 days', '60 days', '90 days', '3 months', '6 months', 'Serving NP'].map(opt => (
                  <button
                    key={opt}
                    type="button"
                    onClick={() => setNoticePeriod(opt)}
                    className={`px-2 py-1.5 rounded-lg text-[11px] font-semibold transition-all text-center ${
                      noticePeriod === opt
                        ? 'bg-indigo-600 text-white'
                        : 'bg-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-700 border border-slate-700'
                    }`}
                  >
                    {opt}
                  </button>
                ))}
              </div>
              {noticePeriod && (
                <p className="text-[10px] text-indigo-400 mt-1">Selected: <span className="font-bold">{noticePeriod}</span></p>
              )}
            </Field>

            {/* Resume upload */}

            <Field label="Resume (PDF / DOCX)" icon={<FileText className="w-3.5 h-3.5" />}>
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.doc,.docx"
                className="hidden"
                onChange={e => setResumeFile(e.target.files?.[0] ?? null)}
              />
              {resumeFile ? (
                <div className="flex items-center gap-2 px-3 py-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-sm">
                  <FileText className="w-4 h-4 text-emerald-400 shrink-0" />
                  <span className="flex-1 text-emerald-200 truncate text-xs">{resumeFile.name}</span>
                  <button type="button" onClick={() => setResumeFile(null)} className="text-slate-500 hover:text-rose-400"><X className="w-3.5 h-3.5" /></button>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl border border-dashed border-slate-700 hover:border-indigo-500/60 text-slate-400 hover:text-indigo-300 text-xs transition-all"
                >
                  <Upload className="w-4 h-4" />
                  Click to upload resume
                </button>
              )}
            </Field>

            {/* Submit */}
            <div className="pt-2">
              <button
                type="submit"
                disabled={submitState === "loading"}
                className={`w-full flex items-center justify-center gap-2 py-3.5 rounded-xl font-bold text-sm transition-all active:scale-95 ${
                  submitState === "loading"
                    ? "bg-indigo-700 text-white/60 cursor-not-allowed"
                    : "bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white shadow-xl shadow-indigo-950/50"
                }`}
              >
                {submitState === "loading" ? (
                  <><Loader2 className="w-4 h-4 animate-spin" />Submitting Application...</>
                ) : (
                  <><Briefcase className="w-4 h-4" />Submit Application</>
                )}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};

// ─── Helper sub-components ────────────────────────────────────────────────────
const inputClass = (hasError: boolean) =>
  `w-full bg-slate-900 border ${hasError ? "border-rose-500/60" : "border-slate-700/80"} rounded-xl px-3 py-2.5 text-sm text-slate-200 placeholder-slate-500 focus:outline-none ${hasError ? "focus:border-rose-400" : "focus:border-indigo-500"} transition-colors`;

interface FieldProps {
  label: string;
  icon: React.ReactNode;
  error?: string;
  required?: boolean;
  children: React.ReactNode;
}
const Field: React.FC<FieldProps> = ({ label, icon, error, required, children }) => (
  <div className="space-y-1.5">
    <label className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
      <span className="text-indigo-400">{icon}</span>
      {label}{required && <span className="text-rose-400 ml-0.5">*</span>}
    </label>
    {children}
    {error && <p className="text-[11px] text-rose-400">{error}</p>}
  </div>
);
