// ── Shared API Client ─────────────────────────────────────────────────────
const API = 'http://127.0.0.1:8000/api';

// ── Token / user storage ──────────────────────────────────────────────────
function getToken()    { return localStorage.getItem('goattend_token'); }
function getRefresh()  { return localStorage.getItem('goattend_refresh'); }
function setToken(t)   { localStorage.setItem('goattend_token', t); }
function setRefresh(t) { localStorage.setItem('goattend_refresh', t); }
function clearAuth()   {
  localStorage.removeItem('goattend_token');
  localStorage.removeItem('goattend_refresh');
  localStorage.removeItem('goattend_user');
}
function getUser() { try { return JSON.parse(localStorage.getItem('goattend_user')); } catch { return null; } }
function setUser(u) { localStorage.setItem('goattend_user', JSON.stringify(u)); }
function isLoggedIn() { return !!getToken(); }

// ── Silent token refresh ──────────────────────────────────────────────────
async function tryRefreshToken() {
  const refresh = getRefresh();
  if (!refresh) return false;
  try {
    const res = await fetch(`${API}/auth/token/refresh/`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ refresh }),
    });
    if (!res.ok) { clearAuth(); return false; }
    const data = await res.json();
    setToken(data.access);
    if (data.refresh) setRefresh(data.refresh); // ROTATE_REFRESH_TOKENS support
    return true;
  } catch { return false; }
}

// ── Core fetch wrapper with auto-retry on 401 ─────────────────────────────
async function apiFetch(path, opts = {}, _retried = false) {
  const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
  const token = getToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(API + path, { ...opts, headers });

  // Access token expired — try a silent refresh once before giving up
  if (res.status === 401 && !_retried) {
    const refreshed = await tryRefreshToken();
    if (refreshed) return apiFetch(path, opts, true);
    clearAuth();
    window.location.href = 'login.html';
    return;
  }

  const data = res.status === 204 ? {} : await res.json();
  if (!res.ok) throw data;
  return data;
}

// ── Auth ──────────────────────────────────────────────────────────────────
async function login(username, password) {
  const data = await apiFetch('/auth/token/', {
    method: 'POST',
    body:   JSON.stringify({ username, password }),
  });
  setToken(data.access);
  setRefresh(data.refresh);
  const profile = await apiFetch('/auth/profile/');
  setUser(profile);
  return profile;
}

async function register(payload) {
  return apiFetch('/auth/register/', { method: 'POST', body: JSON.stringify(payload) });
}

async function logout() {
  const refresh = getRefresh();
  if (refresh) {
    try {
      await apiFetch('/auth/logout/', {
        method: 'POST',
        body: JSON.stringify({ refresh }),
      });
    } catch { /* server-side blacklist failed — still clear locally */ }
  }
  clearAuth();
  window.location.href = 'login.html';
}

// ── Events ────────────────────────────────────────────────────────────────
function fetchEvents(params = {}) {
  const qs = new URLSearchParams(params).toString();
  return apiFetch('/events/' + (qs ? '?' + qs : ''));
}
function fetchEvent(id) { return apiFetch(`/events/${id}/`); }

// ── Tickets ───────────────────────────────────────────────────────────────
function purchaseTicket(eventId) {
  return apiFetch('/tickets/purchase/', { method: 'POST', body: JSON.stringify({ event: eventId }) });
}
function fetchMyTickets() { return apiFetch('/user/tickets/'); }
function checkIsOrganizer() { return apiFetch('/auth/is-organizer/'); }
function verifyTicket(ticketHash) {
  return apiFetch('/tickets/verify/', {
    method: 'POST',
    body: JSON.stringify({ ticket_hash: ticketHash }),
  });
}

// ── Organizer API ─────────────────────────────────────────────────────────
function fetchOrganizerEvents(params = {}) {
  const qs = new URLSearchParams(params).toString();
  return apiFetch('/organizer/events/' + (qs ? '?' + qs : ''));
}
function fetchOrganizerAttendees(eventId) {
  return apiFetch(`/organizer/events/${eventId}/attendees/`);
}

function createEvent(formData) {
  // formData is a FormData object so the browser sets multipart/form-data
  // automatically — do NOT set Content-Type header manually here.
  const token = getToken();
  return fetch(`${API}/events/`, {
    method:  'POST',
    headers: token ? { 'Authorization': `Bearer ${token}` } : {},
    body:    formData,
  }).then(async res => {
    const data = await res.json();
    if (!res.ok) throw data;
    return data;
  });
}

function updateEvent(id, formData) {
  const token = getToken();
  return fetch(`${API}/events/${id}/`, {
    method:  'PATCH',
    headers: token ? { 'Authorization': `Bearer ${token}` } : {},
    body:    formData,
  }).then(async res => {
    const data = await res.json();
    if (!res.ok) throw data;
    return data;
  });
}

function deleteEvent(id) {
  return apiFetch(`/events/${id}/`, { method: 'DELETE' });
}

// ── Format helpers ────────────────────────────────────────────────────────
function fmtDate(iso) {
  return new Date(iso).toLocaleDateString('en-IN', {
    day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}
function fmtPrice(p) { return parseFloat(p) === 0 ? 'FREE' : '₹' + parseFloat(p).toFixed(0); }

const CATEGORY_EMOJI = { music: '🎵', tech: '💻', food: '🍜', arts: '🎨' };

// ── Liked Events (localStorage) ───────────────────────────────────────────
// Stores full event objects so liked.html works offline / without refetch
function getLikedMap()     { try { return JSON.parse(localStorage.getItem('goattend_liked') || '{}'); } catch { return {}; } }
function saveLikedMap(map) { localStorage.setItem('goattend_liked', JSON.stringify(map)); }
function isLiked(id)       { return !!getLikedMap()[id]; }
function toggleLike(eventObj) {
  const map = getLikedMap();
  const id  = eventObj.id;
  if (map[id]) { delete map[id]; saveLikedMap(map); return false; }
  else         { map[id] = eventObj; saveLikedMap(map); return true; }
}
function getLikedEvents()  { return Object.values(getLikedMap()); }
