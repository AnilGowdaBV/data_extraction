export type ExtractionStatus = 'idle' | 'running' | 'completed' | 'stopped' | 'failed';

export interface JobRecord {
  company_name: string;
  job_role: string;
  number_of_people: number | string;
  job_url?: string | null;
  status?: string;
  is_new?: boolean;
}

export interface ExtractionProgress {
  job_id: string;
  status: ExtractionStatus;
  website: string;
  pages_processed: number;
  jobs_discovered: number;
  jobs_processed: number;
  companies_discovered: number;
  duplicates_removed: number;
  missing_employee_counts: number;
  new_jobs_added?: number;
  existing_jobs_seen?: number;
  recent_jobs?: JobRecord[];
  current_action: string;
  download_url?: string | null;
  error?: string | null;
}

export interface ExtractionSummary {
  job_id: string;
  status: ExtractionStatus;
  source_url: string;
  total_jobs: number;
  total_companies: number;
  duplicates_removed: number;
  missing_employee_counts: number;
  new_jobs_added?: number;
  existing_jobs_seen?: number;
  pages_processed: number;
  download_url: string;
  preview_records: JobRecord[];
}

export interface StartExtractionPayload {
  url: string;
  max_records?: number;
  max_pages?: number;
}
