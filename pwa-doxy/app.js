// pwa-doxy/app.js

let doxyUser     = null;
let lastCount    = 0;
let pollingTimer = null;

const header = document.getElementById('appHeader');

// ── Utility ──────────────────────────────────────────────────────────────── //
function showScreen(id) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  header.style.display = (id === 'screenMain') ? 'flex' : 'none';
  window.scrollTo(0, 0);
}

function showAlert(cid, msg, type = 'danger') {
  document.getElementById(cid).innerHTML =
    `<div class="alert alert-${type}">${msg}</div>`;
}
function clearAlert(id) { document.getElementById(id).innerHTML = ''; }

function setLoading(btn, on) {
  if (on) {
    btn.disabled = true;
    btn.dataset.orig = btn.innerHTML;
    btn.innerHTML = '<span class="spinner"></span> Attendere...';
  } else {
    btn.disabled = false;
    btn.innerHTML = btn.dataset.orig || btn.innerHTML;
  }
}

function fmtDate(str) {
  if (!str) return '—';
  const d = new Date(str);
  return isNaN(d) ? str : d.toLocaleString('it-IT', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

function truncate(str, n = 90) {
  if (!str) return '';
  return str.length > n ? str.slice(0, n) + '…' : str;
}

// ── Auth ─────────────────────────────────────────────────────────────────── //
async function handleLogin(e) {
  e.preventDefault();
  const btn      = document.getElementById('btnLogin');
  const email    = document.getElementById('loginEmail').value.trim();
  const password = document.getElementById('loginPassword').value.trim();
  clearAlert('loginAlert');
  setLoading(btn, true);
  try {
    const res  = await fetch('/api/doxy/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json();
    if (!res.ok) { showAlert('loginAlert', data.error || 'Credenziali non valide'); return; }
    doxyUser = data;
    localStorage.setItem('doxyUser', JSON.stringify(data));
    enterApp();
  } catch (_) {
    showAlert('loginAlert', 'Errore di rete. Verifica la connessione.');
  } finally {
    setLoading(btn, false);
  }
}

function handleLogout() {
  fetch('/api/doxy/logout', { method: 'POST', credentials: 'include' }).catch(() => {});
  doxyUser = null;
  localStorage.removeItem('doxyUser');
  clearPolling();
  document.getElementById('headerUser').textContent = '';
  document.getElementById('badgeCount').classList.add('d-none');
  document.getElementById('badgeCount').textContent = '';
  showScreen('screenLogin');
}

function enterApp() {
  document.getElementById('headerUser').textContent =
    `${doxyUser.nome} ${doxyUser.cognome}`;
  showScreen('screenMain');
  loadSegnalazioni();
  startPolling();
}

// ── Segnalazioni lista ───────────────────────────────────────────────────── //
async function loadSegnalazioni() {
  const listEl = document.getElementById('segList');
  listEl.innerHTML = `
    <div class="loading-overlay">
      <div class="spin-lg"></div>
      <p>Caricamento...</p>
    </div>`;
  try {
    const res  = await fetch('/api/segnalazioni', { credentials: 'include' });
    if (res.status === 401) { handleLogout(); return; }
    const list = await res.json();
    renderList(list);
    updateBadge(list.filter(s => !s.letta).length);
  } catch (_) {
    listEl.innerHTML = `<div class="empty-state"><p>Errore nel caricamento. Riprova.</p></div>`;
  }
}

function renderList(list) {
  const listEl = document.getElementById('segList');
  if (!list.length) {
    listEl.innerHTML = `
      <div class="empty-state">
        <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" fill="#adb5bd" viewBox="0 0 16 16">
          <path d="M0 2a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H4.414a1 1 0 0 0-.707.293L.854 15.146A.5.5 0 0 1 0 14.793z"/>
        </svg>
        <p>Nessuna segnalazione ricevuta.</p>
      </div>`;
    return;
  }
  listEl.innerHTML = list.map(s => `
    <div class="seg-card ${s.letta ? 'letta' : 'nuova'}"
         data-id="${s.id_segnalazione}"
         role="button" tabindex="0">
      <div class="seg-card-top">
        <span class="seg-veicolo">${s.targa} — ${s.modello}</span>
        ${!s.letta ? '<span class="badge-new">Nuova</span>' : ''}
      </div>
      <div class="seg-desc">${truncate(s.descrizione)}</div>
      <div class="seg-footer">
        <span class="seg-autista">
          <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" fill="currentColor" viewBox="0 0 16 16">
            <path d="M8 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6m2-3a2 2 0 1 1-4 0 2 2 0 0 1 4 0m4 8c0 1-1 1-1 1H3s-1 0-1-1 1-4 6-4 6 3 6 4m-1-.004c-.001-.246-.154-.986-.832-1.664C11.516 10.68 10.384 10.5 9 10.5s-2.516.18-3.168.832C5.154 12.01 5.001 12.75 5 13z"/>
          </svg>
          ${s.autista_nome} ${s.autista_cognome}
        </span>
        <span class="seg-data">${fmtDate(s.data_segnalazione)}</span>
      </div>
    </div>`).join('');

  // Click card → dettaglio
  listEl.querySelectorAll('.seg-card').forEach(card => {
    card.addEventListener('click', () => openDettaglio(+card.dataset.id));
    card.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') openDettaglio(+card.dataset.id);
    });
  });
}

function updateBadge(n) {
  const badge = document.getElementById('badgeCount');
  if (n > 0) {
    badge.textContent = n > 99 ? '99+' : n;
    badge.classList.remove('d-none');
  } else {
    badge.classList.add('d-none');
  }
}

// ── Dettaglio ────────────────────────────────────────────────────────────── //
async function openDettaglio(id) {
  const overlay = document.getElementById('modalOverlay');
  const body    = document.getElementById('modalBody');
  overlay.classList.add('active');
  body.innerHTML = `
    <div class="loading-overlay" style="padding:32px">
      <div class="spin-lg"></div>
      <p>Caricamento dettaglio...</p>
    </div>`;
  try {
    const res = await fetch(`/api/segnalazioni/${id}`, { credentials: 'include' });
    if (!res.ok) throw new Error();
    const s = await res.json();
    body.innerHTML = `
      ${s.foto_path ? `<img class="detail-foto" src="/static/${s.foto_path}" alt="Foto segnalazione">` : ''}
      <div class="detail-row">
        <div class="detail-label">Veicolo</div>
        <div class="detail-value">${s.targa} — ${s.modello}</div>
      </div>
      <div class="detail-row">
        <div class="detail-label">Descrizione</div>
        <div class="detail-value">${s.descrizione}</div>
      </div>
      <hr class="detail-divider">
      <div class="detail-row">
        <div class="detail-label">Segnalato da</div>
        <div class="detail-value">${s.autista_nome} ${s.autista_cognome}${s.autista_tel ? ' · ' + s.autista_tel : ''}</div>
      </div>
      <div class="detail-row">
        <div class="detail-label">Data</div>
        <div class="detail-value">${fmtDate(s.data_segnalazione)}</div>
      </div>
      <div class="detail-row">
        <div class="detail-label">Stato</div>
        <div class="detail-value">${s.letta ? 'Letta' : '<strong style="color:var(--badge-new)">Non letta</strong>'}</div>
      </div>`;
    // Marca come letta
    if (!s.letta) {
      await fetch(`/api/segnalazioni/${id}/letta`, { method: 'PUT', credentials: 'include' });
      loadSegnalazioni();
    }
  } catch (_) {
    body.innerHTML = '<p style="padding:20px;color:var(--danger)">Errore nel caricamento.</p>';
  }
}

function closeModal() {
  document.getElementById('modalOverlay').classList.remove('active');
}

// ── Polling + Notifiche ──────────────────────────────────────────────────── //
function startPolling() {
  clearPolling();
  pollingTimer = setInterval(pollNuove, 30000);
}
function clearPolling() {
  if (pollingTimer) { clearInterval(pollingTimer); pollingTimer = null; }
}

async function pollNuove() {
  try {
    const res  = await fetch('/api/segnalazioni/nuove/count', { credentials: 'include' });
    if (res.status === 401) { handleLogout(); return; }
    const data = await res.json();
    const n    = data.count || 0;
    if (n > lastCount) {
      notifyNuove(n - lastCount);
      loadSegnalazioni();
    }
    lastCount = n;
    updateBadge(n);
  } catch (_) { /* offline */ }
}

function notifyNuove(qty) {
  if (!('Notification' in window)) return;
  if (Notification.permission === 'granted') {
    new Notification('Doxy — Nuova segnalazione', {
      body: `${qty} nuov${qty === 1 ? 'a segnalazione ricevuta' : 'e segnalazioni ricevute'}.`,
      icon: '/pwa/doxy/icon.svg',
    });
  } else if (Notification.permission !== 'denied') {
    Notification.requestPermission().then(p => {
      if (p === 'granted') notifyNuove(qty);
    });
  }
}

// ── Init ─────────────────────────────────────────────────────────────────── //
document.addEventListener('DOMContentLoaded', () => {
  const saved = localStorage.getItem('doxyUser');
  if (saved) {
    try {
      doxyUser = JSON.parse(saved);
      fetch('/api/segnalazioni/nuove/count', { credentials: 'include' })
        .then(r => r.ok ? enterApp() : (() => { localStorage.removeItem('doxyUser'); showScreen('screenLogin'); })())
        .catch(() => showScreen('screenLogin'));
    } catch (_) { showScreen('screenLogin'); }
  } else {
    showScreen('screenLogin');
  }

  document.getElementById('formLogin').addEventListener('submit', handleLogin);
  document.getElementById('btnLogout').addEventListener('click', handleLogout);
  document.getElementById('btnRefresh').addEventListener('click', loadSegnalazioni);
  document.getElementById('btnCloseModal').addEventListener('click', closeModal);
  document.getElementById('modalOverlay').addEventListener('click', e => {
    if (e.target === document.getElementById('modalOverlay')) closeModal();
  });

  // Richiedi permesso notifiche al click sull'header
  document.getElementById('appHeader').addEventListener('click', () => {
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }
  }, { once: true });
});

// Service Worker
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/pwa/doxy/sw.js', { scope: '/pwa/doxy/' })
      .catch(err => console.warn('SW non registrato:', err));
  });
}
