// pwa-autista/app.js

let autista = null;
const header = document.getElementById('appHeader');

// ── Utility ──────────────────────────────────────────────────────────────── //
function showScreen(id) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  header.style.display = id === 'screenMain' ? 'flex' : 'none';
  window.scrollTo(0, 0);
}

function showAlert(containerId, msg, type = 'danger') {
  const el = document.getElementById(containerId);
  el.innerHTML = `<div class="alert alert-${type}">${msg}</div>`;
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

// ── Veicoli ──────────────────────────────────────────────────────────────── //
async function loadVeicoli() {
  try {
    const res  = await fetch('/api/veicoli', { credentials: 'include' });
    if (!res.ok) return;
    const list = await res.json();
    const sel  = document.getElementById('segnVeicolo');
    sel.innerHTML = '<option value="">— Seleziona veicolo —</option>';
    list.forEach(v => {
      const o = document.createElement('option');
      o.value = v.id_veicolo;
      o.textContent = `${v.targa} — ${v.modello}`;
      sel.appendChild(o);
    });
  } catch (_) { /* ignore offline */ }
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
    const res  = await fetch('/api/autista/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json();
    if (!res.ok) { showAlert('loginAlert', data.error || 'Credenziali non valide'); return; }
    autista = data;
    localStorage.setItem('autista', JSON.stringify(data));
    enterApp();
  } catch (_) {
    showAlert('loginAlert', 'Errore di rete. Verifica la connessione.');
  } finally {
    setLoading(btn, false);
  }
}

async function handleRegister(e) {
  e.preventDefault();
  const btn      = document.getElementById('btnRegister');
  const nome     = document.getElementById('regNome').value.trim();
  const cognome  = document.getElementById('regCognome').value.trim();
  const email    = document.getElementById('regEmail').value.trim();
  const password = document.getElementById('regPassword').value.trim();
  const telefono = document.getElementById('regTelefono').value.trim();
  clearAlert('registerAlert');
  setLoading(btn, true);
  try {
    const res  = await fetch('/api/autista/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ nome, cognome, email, password, telefono }),
    });
    const data = await res.json();
    if (!res.ok) { showAlert('registerAlert', data.error || 'Errore di registrazione'); return; }
    showAlert('registerAlert', 'Account creato! Ora puoi accedere.', 'success');
    setTimeout(() => showScreen('screenLogin'), 1800);
  } catch (_) {
    showAlert('registerAlert', 'Errore di rete.');
  } finally {
    setLoading(btn, false);
  }
}

function handleLogout() {
  fetch('/api/autista/logout', { method: 'POST', credentials: 'include' }).catch(() => {});
  autista = null;
  localStorage.removeItem('autista');
  document.getElementById('headerUser').textContent = '';
  document.getElementById('formSegnalazione').reset();
  document.getElementById('fotoPreview').style.display = 'none';
  showScreen('screenLogin');
}

function enterApp() {
  document.getElementById('headerUser').textContent =
    `${autista.nome} ${autista.cognome}`;
  loadVeicoli();
  showScreen('screenMain');
}

// ── Segnalazione ─────────────────────────────────────────────────────────── //
async function handleSegnalazione(e) {
  e.preventDefault();
  const btn        = document.getElementById('btnInvia');
  const id_veicolo = document.getElementById('segnVeicolo').value;
  const descrizione = document.getElementById('segnDescrizione').value.trim();
  const fotoInput  = document.getElementById('segnFoto');
  clearAlert('segnAlert');
  if (!id_veicolo)   { showAlert('segnAlert', 'Seleziona un veicolo.'); return; }
  if (!descrizione)  { showAlert('segnAlert', 'Inserisci la descrizione del problema.'); return; }
  setLoading(btn, true);
  const fd = new FormData();
  fd.append('id_veicolo', id_veicolo);
  fd.append('descrizione', descrizione);
  if (fotoInput.files[0]) fd.append('foto', fotoInput.files[0]);
  try {
    const res  = await fetch('/api/segnalazioni', {
      method: 'POST',
      credentials: 'include',
      body: fd,
    });
    const data = await res.json();
    if (!res.ok) {
      if (res.status === 401) { handleLogout(); return; }
      showAlert('segnAlert', data.error || 'Errore nell\'invio.');
      return;
    }
    document.getElementById('formSegnalazione').reset();
    document.getElementById('fotoPreview').style.display = 'none';
    showAlert('segnAlert', '✓ Segnalazione inviata con successo!', 'success');
  } catch (_) {
    showAlert('segnAlert', 'Errore di rete. Controlla la connessione.');
  } finally {
    setLoading(btn, false);
  }
}

function handleFotoChange(e) {
  const preview = document.getElementById('fotoPreview');
  const file    = e.target.files[0];
  if (file) {
    preview.src = URL.createObjectURL(file);
    preview.style.display = 'block';
  } else {
    preview.style.display = 'none';
  }
}

// ── Init ─────────────────────────────────────────────────────────────────── //
document.addEventListener('DOMContentLoaded', () => {
  // Ripristina sessione da localStorage
  const saved = localStorage.getItem('autista');
  if (saved) {
    try {
      autista = JSON.parse(saved);
      fetch('/api/veicoli', { credentials: 'include' })
        .then(r => r.ok ? enterApp() : (() => { localStorage.removeItem('autista'); showScreen('screenLogin'); })())
        .catch(() => showScreen('screenLogin'));
    } catch (_) { showScreen('screenLogin'); }
  } else {
    showScreen('screenLogin');
  }

  document.getElementById('formLogin').addEventListener('submit', handleLogin);
  document.getElementById('formRegister').addEventListener('submit', handleRegister);
  document.getElementById('formSegnalazione').addEventListener('submit', handleSegnalazione);
  document.getElementById('segnFoto').addEventListener('change', handleFotoChange);
  document.getElementById('btnLogout').addEventListener('click', handleLogout);
  document.getElementById('btnGoRegister').addEventListener('click', () => showScreen('screenRegister'));
  document.getElementById('btnGoLogin').addEventListener('click', () => showScreen('screenLogin'));
});

// Service Worker
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/pwa/autista/sw.js', { scope: '/pwa/autista/' })
      .catch(err => console.warn('SW non registrato:', err));
  });
}
