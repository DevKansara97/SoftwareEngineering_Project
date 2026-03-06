/* ── api.js  –  Shared utilities for Seva Connect frontend ───────────────── */

const API = '/api';

/* ── Auth helpers ───────────────────────────────────────────────────────── */
function getUser() {
  try { return JSON.parse(localStorage.getItem('seva_user') || 'null'); }
  catch { return null; }
}
function setUser(u) { localStorage.setItem('seva_user', JSON.stringify(u)); }
function clearUser() { localStorage.removeItem('seva_user'); }

function requireAuth(role = null) {
  const u = getUser();
  if (!u) { window.location.href = '/login'; return null; }
  if (role && u.role !== role) {
    alert('Access denied. Redirecting.');
    window.location.href = u.role === 'NGO' ? '/ngo/dashboard' : '/donor/dashboard';
    return null;
  }
  return u;
}

/* ── HTTP helpers ────────────────────────────────────────────────────────── */
async function apiGet(path, params = {}) {
  const qs = new URLSearchParams(params).toString();
  const url = API + path + (qs ? '?' + qs : '');
  const res = await fetch(url);
  return res.json();
}

async function apiPost(path, body = {}) {
  const res = await fetch(API + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  return res.json();
}

async function apiPut(path, body = {}) {
  const res = await fetch(API + path, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  return res.json();
}

async function apiDelete(path, params = {}) {
  const qs = new URLSearchParams(params).toString();
  const res = await fetch(API + path + (qs ? '?' + qs : ''), { method: 'DELETE' });
  return res.json();
}

/* ── DOM helpers ─────────────────────────────────────────────────────────── */
function showAlert(containerId, message, type = 'info') {
  const el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = `<div class="alert alert-${type}">${message}</div>`;
  el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function clearAlert(containerId) {
  const el = document.getElementById(containerId);
  if (el) el.innerHTML = '';
}

function spinner(containerId) {
  const el = document.getElementById(containerId);
  if (el) el.innerHTML = '<div class="spinner"></div>';
}

function setNavUser() {
  const u = getUser();
  const nameEl = document.getElementById('nav-user-name');
  if (nameEl && u) nameEl.textContent = u.name;

  // load unread notification count
  if (u) {
    apiGet('/notifications/unread-count', { user_id: u.user_id })
      .then(d => {
        const badge = document.getElementById('notif-badge');
        if (badge) {
          badge.textContent = d.unread_count || '';
          badge.style.display = d.unread_count ? 'inline' : 'none';
        }
      }).catch(() => {});
  }
}

function badgeClass(status) {
  const map = {
    'OPEN': 'badge-open',
    'PARTIALLY_FULFILLED': 'badge-partially-fulfilled',
    'FULFILLED': 'badge-fulfilled',
    'INITIATED': 'badge-initiated',
    'CONFIRMED': 'badge-confirmed',
    'IN_PROGRESS': 'badge-in-progress',
    'COMPLETED': 'badge-completed',
    'CANCELLED': 'badge-cancelled',
    'NOT_DELIVERED': 'badge-initiated',
    'DELIVERING': 'badge-in-progress',
    'DELIVERED': 'badge-completed'
  };
  return map[status] || 'badge-initiated';
}

function fmtDate(str) {
  if (!str) return '-';
  return new Date(str).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

function openModal(id)  { document.getElementById(id).classList.add('open'); }
function closeModal(id) { document.getElementById(id).classList.remove('open'); }

async function logout() {
  await apiPost('/auth/logout');
  clearUser();
  window.location.href = '/';
}

// Expose for inline onclick
window.logout     = logout;
window.openModal  = openModal;
window.closeModal = closeModal;

document.addEventListener('DOMContentLoaded', setNavUser);
