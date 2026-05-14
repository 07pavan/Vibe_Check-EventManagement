/**
 * frontend/config.js — GoAttend API Configuration
 *
 * HOW THIS WORKS:
 * ──────────────────────────────────────────────────────────────────────
 * This file is loaded by every HTML page BEFORE api.js.
 * It sets window.GOATTEND_API to the correct backend URL.
 *
 * DEPLOYMENT STRATEGY:
 * ──────────────────────────────────────────────────────────────────────
 * Local development  → this file stays as-is (points to localhost)
 * Vercel production  → Vercel Build Command replaces this file's content
 *                      using the VITE_API_URL environment variable, OR
 *                      you simply update this one line before deploying.
 *
 * WHY NOT hardcode in api.js:
 *   api.js is logic. config.js is configuration.
 *   Separating them means you only touch one file per environment.
 *
 * WHY window.GOATTEND_API (not import/export):
 *   Plain HTML files have no module bundler. Using window.* is the
 *   correct pattern for sharing config across classic script tags.
 *   It is explicit, debuggable in the browser console, and requires
 *   zero build tooling.
 *
 * TO DEPLOY TO PRODUCTION:
 *   Change the line below to your Render backend URL.
 *   Example:
 *     window.GOATTEND_API = 'https://eventmanagement-api1.onrender.com/api';
 */

// ── Active API base URL ──────────────────────────────────────────────────────
// Change this ONE line when switching environments.
window.GOATTEND_API = 'http://127.0.0.1:8001/api';

// ── Build info (for debugging) ───────────────────────────────────────────────
window.GOATTEND_ENV  = window.GOATTEND_API.includes('127.0.0.1') ? 'development' : 'production';
window.GOATTEND_VERSION = '1.0.0';
