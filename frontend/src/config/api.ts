/**
 * Global API configuration supporting local development, Render backend, and Vercel hosting.
 */
const RAW_URL: string = (
  import.meta.env.VITE_API_URL ||
  import.meta.env.VITE_BACKEND_URL ||
  import.meta.env.VITE_API_BASE_URL ||
  ''
).trim();

// Strip trailing slashes or subpaths if full URL provided
const CLEAN_URL = RAW_URL.replace(/\/api\/extraction\/?$/, '').replace(/\/api\/?$/, '').replace(/\/$/, '');

export const API_BASE = CLEAN_URL
  ? CLEAN_URL
  : (import.meta.env.DEV ? 'http://127.0.0.1:8000' : '');
