// Entry Guard web app. Plain JavaScript, no build step. Read it top to bottom:
//   1 helpers   2 camera   3 login + shell   4 pages   5 security console (/tf-check)   6 start-up

// =============================================================================== 1. helpers
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const esc = (text) => String(text ?? '').replace(/[&<>"']/g,
  (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const pad = (n) => String(n).padStart(2, '0');
const fmtTime = (s) => { const d = new Date(s * 1000); return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`; };
const fmtDateTime = (s) => `${new Date(s * 1000).toLocaleDateString([], { day: '2-digit', month: 'short' })} ${fmtTime(s)}`;
const ago = (s) => { const d = Math.max(0, Date.now() / 1000 - s); return d < 5 ? 'just now' : d < 60 ? `${Math.floor(d)} s ago` : d < 3600 ? `${Math.floor(d / 60)} min ago` : fmtDateTime(s); };
const initials = (name) => (name || '?').split(/\s+/).map((w) => w[0]).slice(0, 2).join('').toUpperCase();
const details = (fields) => Object.values(fields || {}).filter(Boolean).join(' · ');

// Small line icons (24x24 grid).
const ICONS = {
  shield: '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/>',
  scan: '<path d="M4 8V6a2 2 0 0 1 2-2h2M16 4h2a2 2 0 0 1 2 2v2M20 16v2a2 2 0 0 1-2 2h-2M8 20H6a2 2 0 0 1-2-2v-2"/><circle cx="12" cy="10.5" r="2.5"/><path d="M7.5 17c.8-2.2 2.4-3.2 4.5-3.2s3.7 1 4.5 3.2"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.5-3.5 3-5.5 6.5-5.5s6 2 6.5 5.5M16 4.5a3.5 3.5 0 0 1 0 7M18.5 14.8c1.9.7 3 2.4 3.3 5.2"/>',
  userPlus: '<circle cx="10" cy="8" r="3.5"/><path d="M3 20c.5-3.5 3-5.5 7-5.5s6.5 2 7 5.5M19 8v6M16 11h6"/>',
  video: '<rect x="3" y="6" width="13" height="12" rx="2"/><path d="M16 10l5-3v10l-5-3"/>',
  clipboard: '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4V3h6v1M9 10h6M9 14h6"/>',
  logout: '<path d="M9 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h3M16 8l4 4-4 4M20 12H9"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  moon: '<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/>',
  plus: '<path d="M12 5v14M5 12h14"/>', search: '<circle cx="11" cy="11" r="6"/><path d="M20 20l-4-4"/>',
  download: '<path d="M12 4v11M7 11l5 5 5-5M5 20h14"/>', trash: '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v6M14 11v6"/>',
  edit: '<path d="M4 20h4L19 9l-4-4L4 16z"/>', check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>', x: '<path d="M6 6l12 12M18 6L6 18"/>',
  alert: '<path d="M12 4l9 16H3z"/><path d="M12 10v4M12 17v.5"/>', info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8v.5"/>',
  expand: '<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>', volume: '<path d="M4 10v4h4l5 4V6L8 10zM17 9a4 4 0 0 1 0 6"/>',
  volumeOff: '<path d="M4 10v4h4l5 4V6L8 10zM17 9l4 6M21 9l-4 6"/>', play: '<path d="M7 5l12 7-12 7z"/>', pause: '<path d="M8 5v14M16 5v14"/>',
  wifi: '<path d="M2 9a15 15 0 0 1 20 0M5 12.5a10 10 0 0 1 14 0M8.5 16a5 5 0 0 1 7 0"/><circle cx="12" cy="19" r="1"/>',
  lock: '<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>', arrowLeft: '<path d="M19 12H5M11 6l-6 6 6 6"/>',
  refresh: '<path d="M20 11a8 8 0 0 0-14-4L4 9M4 4v5h5M4 13a8 8 0 0 0 14 4l2-2M20 20v-5h-5"/>',
};
const icon = (name) => `<svg class="i" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name] || ''}</svg>`;

const state = { me: null, config: null };
let cleanup = () => {};          // a page can set this to stop its timers/camera when we leave it

// ---- theme (light / dark), remembered in this browser ----
function storage(key, value) {
  try { if (value === undefined) return localStorage.getItem(key); localStorage.setItem(key, value); } catch { /* storage blocked */ }
  return null;
}
function applyTheme() { const t = storage('theme'); if (t) document.documentElement.dataset.theme = t; }
function toggleTheme() {
  const dark = getComputedStyle(document.body).colorScheme === 'dark';
  storage('theme', dark ? 'light' : 'dark'); applyTheme(); renderThemeButtons();
}
function renderThemeButtons() {
  const dark = getComputedStyle(document.body).colorScheme === 'dark';
  $$('[data-theme-toggle]').forEach((b) => { b.innerHTML = icon(dark ? 'sun' : 'moon') + (b.dataset.label ? (dark ? 'Light mode' : 'Dark mode') : ''); });
}

// ---- toasts and dialogs ----
function toast(message, kind = 'ok') {
  const el = document.createElement('div');
  el.className = `toast ${kind}`; el.innerHTML = `${icon(kind === 'ok' ? 'check' : 'alert')}<span>${esc(message)}</span>`;
  $('#toasts').append(el); setTimeout(() => el.remove(), 4200);
}
// A dialog can register a cleanup (for example "stop the camera stream"). It runs when the dialog is
// closed by a button, by closeDialog(), by Esc, or when another dialog replaces it.
let dialogCleanup = null;
function runDialogCleanup() { const fn = dialogCleanup; dialogCleanup = null; if (fn) fn(); }
function openDialog(html, narrow = false, wide = false) {
  const dialog = $('#dialog');
  runDialogCleanup();
  dialog.className = narrow ? 'narrow' : wide ? 'wide' : ''; dialog.innerHTML = html;
  if (!dialog.open) dialog.showModal();
  $$('[data-close]', dialog).forEach((b) => { b.onclick = () => closeDialog(); });
  return dialog;
}
function closeDialog() { const dialog = $('#dialog'); if (dialog.open) dialog.close(); runDialogCleanup(); dialog.innerHTML = ''; }
$('#dialog').addEventListener('close', runDialogCleanup);
function confirmDialog({ title, message, confirm = 'Confirm', danger = false }) {
  return new Promise((resolve) => {
    const d = openDialog(`<div class="dlg-head"><h2>${esc(title)}</h2></div><div class="dlg-body"><p class="muted">${esc(message)}</p></div>
      <div class="dlg-foot"><button data-close id="no">Cancel</button><button id="yes" class="primary ${danger ? 'danger solid' : ''}">${esc(confirm)}</button></div>`, true);
    $('#yes', d).onclick = () => { closeDialog(); resolve(true); };
    d.onclose = () => resolve(false);
  });
}

// ---- forms ----
const fieldHtml = ({ name, label, value = '', type = 'text', optional = false, placeholder = '', full = false, extra = '' }) =>
  `<label class="field ${full ? 'full' : ''}">${esc(label)}${optional ? ' <span class="opt">(optional)</span>' : ''}
     <input name="${esc(name)}" type="${type}" value="${esc(value)}" placeholder="${esc(placeholder)}" autocomplete="off" ${extra}>
     <span class="field-error" data-for="${esc(name)}"></span></label>`;
function setFieldError(root, field, message) {
  $$('.invalid', root).forEach((e) => e.classList.remove('invalid')); $$('.field-error', root).forEach((e) => { e.textContent = ''; });
  const input = $(`[name="${CSS.escape(field || '')}"]`, root), slot = $(`.field-error[data-for="${CSS.escape(field || '')}"]`, root);
  if (input && slot) { input.classList.add('invalid'); slot.textContent = message; input.focus(); return true; }
  return false;
}

// ---- server calls ----
async function api(path, method = 'GET', body, extra = {}) {
  const response = await fetch('/api' + path, {
    method, headers: { 'X-Requested-With': 'entryguard', ...extra, ...(body ? { 'Content-Type': 'application/json' } : {}) }, body: body ? JSON.stringify(body) : undefined,
  });
  if (response.status === 204) return null;
  const data = await response.json().catch(() => ({ error: { message: `Server error (${response.status})` } }));
  if (response.status === 401 && !path.startsWith('/login') && data.error?.code !== 'STEP_UP_FAILED') {   // a refused sign-in is a normal error, not an expired session
    showLogin(); throw Object.assign(new Error('login'), { silent: true }); }
  if (!response.ok) {
    // A risky action: ask the person to confirm (face / PIN / password), then repeat the request once with the token.
    if (data.error?.code === 'STEP_UP_REQUIRED' && !extra['X-Step-Up']) {
      const token = await confirmRisk(data.error);
      if (!token) throw Object.assign(new Error('Confirmation cancelled'), { cancelled: true });
      return api(path, method, body, { ...extra, 'X-Step-Up': token });
    }
    throw Object.assign(new Error(data.error?.message || 'Something went wrong'), data.error);
  }
  return data;
}

// =============================================================================== 2. camera
const camera = {
  stream: null,
  async start(video, deviceId) {
    this.stop();
    this.stream = await navigator.mediaDevices.getUserMedia({ video: deviceId ? { deviceId: { exact: deviceId } } : true });
    video.srcObject = this.stream; await video.play();
    return (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === 'videoinput');
  },
  stop() { this.stream?.getTracks().forEach((t) => t.stop()); this.stream = null; },
  currentId() { return this.stream?.getVideoTracks()[0]?.getSettings().deviceId; },
  // Returns {data, scale}. `scale` < 1 when the picture was shrunk to maxWidth (faster upload);
  // boxes from the server are in the shrunk picture, so we divide by `scale` to draw them.
  snapshot(video, maxWidth = 0, quality = 0.9) {
    const scale = maxWidth && video.videoWidth > maxWidth ? maxWidth / video.videoWidth : 1;
    const canvas = document.createElement('canvas');
    canvas.width = Math.round(video.videoWidth * scale); canvas.height = Math.round(video.videoHeight * scale);
    canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
    return { data: canvas.toDataURL('image/jpeg', quality), scale };
  },
};

const stageHtml = ({ guide = false, hud = '' } = {}) => `
  <div class="stage"><video autoplay playsinline muted></video><canvas></canvas>
    ${guide ? '<div class="guide"></div>' : ''}<div class="flash"></div>${hud}
    <div class="turn-cue" hidden><span class="arr l">&#9664;</span><span class="arr r">&#9654;</span></div>
    <div class="turn-meter" hidden><div class="turn-label">Turn your head slightly, LEFT or RIGHT (either way works)</div><div class="bar-track"><div class="bar-fill"></div><div class="bar-goal"></div></div></div></div>`;

async function startCamera(stage, select) {
  const video = $('video', stage);
  $('.camera-error', stage)?.remove();
  try {
    const devices = await camera.start(video, select?.value || null);
    if (select) {
      select.innerHTML = devices.map((d, i) => `<option value="${esc(d.deviceId)}" ${d.deviceId === camera.currentId() ? 'selected' : ''}>${esc(d.label || 'Camera ' + (i + 1))}</option>`).join('');
      select.onchange = () => startCamera(stage, select);
    }
    return true;
  } catch (e) {
    stage.insertAdjacentHTML('beforeend', `<div class="camera-error"><div>${icon('video')}<p style="margin-top:8px"><b>Camera not available</b></p>
      <p class="faint">Allow camera access for this site in the browser, then press Retry. (${esc(e.name)})</p><button id="retryCam" style="margin-top:12px">Retry</button></div></div>`);
    $('#retryCam', stage).onclick = () => startCamera(stage, select);
    return false;
  }
}

// Draw corner brackets and a label for each face. The video can have black bars, so compute the
// real picture position first. `toVideo` converts server boxes back to full-size picture pixels.
function drawBoxes(stage, boxes, toVideo = 1) {
  const video = $('video', stage), canvas = $('canvas', stage);
  const w = canvas.clientWidth, h = canvas.clientHeight, dpr = devicePixelRatio || 1;
  canvas.width = w * dpr; canvas.height = h * dpr;
  const g = canvas.getContext('2d'); g.scale(dpr, dpr);
  if (!video.videoWidth) return;
  const s = Math.min(w / video.videoWidth, h / video.videoHeight);
  const ox = (w - video.videoWidth * s) / 2, oy = (h - video.videoHeight * s) / 2;
  const css = getComputedStyle(document.documentElement);
  g.lineWidth = 3; g.lineCap = 'round'; g.font = '700 13px system-ui';
  for (const b of boxes) {
    if (!b.bbox) continue;
    const color = { ok: '#4ade80', bad: '#ff6b5e', warn: '#fbbf24' }[b.kind] || '#ffffff';
    const [bx, by, bw, bh] = b.bbox.map((n) => n * toVideo);
    const X = ox + bx * s, Y = oy + by * s, W = bw * s, H = bh * s, L = Math.min(W, H) * 0.22;
    g.strokeStyle = color; g.beginPath();
    for (const [px, py, dx, dy] of [[X, Y, 1, 1], [X + W, Y, -1, 1], [X, Y + H, 1, -1], [X + W, Y + H, -1, -1]]) { g.moveTo(px + dx * L, py); g.lineTo(px, py); g.lineTo(px, py + dy * L); }
    g.stroke();
    if (b.label) {
      const tw = g.measureText(b.label).width + 14;
      g.fillStyle = color; g.beginPath(); g.roundRect(X, Y + H + 6, tw, 22, 6); g.fill();
      g.fillStyle = '#04110a'; g.fillText(b.label, X + 7, Y + H + 21);
    }
  }
}
const kindOf = (decision) => ({ resident: 'ok', uncertain: 'warn' }[decision] || 'bad');
// A registered person who is DENIED entry is red, just like a stranger. `r` is a live scan result
// (access is an object), `e` is a saved log line (access is "granted" or "denied").
const resultKind = (r) => (r.decision === 'resident' ? (r.access && r.access.granted === false ? 'bad' : 'ok') : kindOf(r.decision));
const eventKind = (e) => (e.decision === 'resident' ? (e.access === 'denied' ? 'bad' : 'ok') : kindOf(e.decision));
const accessPill = (e) => (e.alert ? `<span class="pill bad">${esc(String(e.alert).toUpperCase())}</span> ` : '') + (e.access ? `<span class="pill ${e.access === 'granted' ? 'ok' : 'bad'}">${e.access === 'granted' ? 'Granted' : 'Denied'}</span>` : '<span class="faint">-</span>');

// =============================================================================== 3. login + shell
function showLogin() {
  cleanup(); cleanup = () => {}; camera.stop(); stopAlerts();
  $('#app').innerHTML = `
    <div class="login-wrap">
      <aside class="login-art">
        <div class="brand"><span class="logo">${icon('shield')}</span><div>Entry Guard<small>${esc(state.config?.customer || '')}</small></div></div>
        <div><h2>Know who is at the door, in real time.</h2><p>Face recognition for entrances: register people, scan live and keep a reviewable log of everyone seen.</p>
          <ul><li>${icon('scan')} Live scanning with instant verdicts</li><li>${icon('clipboard')} Searchable scan log with snapshots</li><li>${icon('lock')} Role-based access and a full audit trail</li></ul></div>
        <span style="opacity:.7;font-size:12px">Face data stays on this computer.</span>
      </aside>
      <section class="login-form"><form id="loginForm" novalidate>
        <div><h1>Sign in</h1><p class="muted" style="margin-top:4px">Use your Entry Guard account.</p></div>
        ${state.config?.needs_setup ? `<div class="banner">${icon('info')}<div>No users exist yet. On this computer run<br><code>python main.py create-user admin --role admin</code></div></div>` : ''}
        ${fieldHtml({ name: 'username', label: 'Username', extra: 'autocomplete="username" autofocus' })}
        ${fieldHtml({ name: 'password', label: 'Password', type: 'password', extra: 'autocomplete="current-password"' })}
        <button class="primary" style="padding:11px">Sign in</button>
        ${state.config?.face_login ? `<div class="or-line"><span>or</span></div><button type="button" id="faceSignIn" style="padding:11px">${icon('scan')}Sign in with face</button>` : ''}
        <div class="row"><button type="button" class="ghost sm" data-theme-toggle data-label="1"></button></div>
      </form></section>
    </div>`;
  renderThemeButtons();
  $('[data-theme-toggle]').onclick = toggleTheme;
  $('#loginForm').onsubmit = async (e) => {
    e.preventDefault();
    try { state.me = await api('/login', 'POST', { username: e.target.elements.username.value, password: e.target.elements.password.value }); start(); }
    catch (err) { setFieldError(e.target, 'password', err.message); }
  };
  const faceBtn = $('#faceSignIn');
  if (faceBtn) faceBtn.onclick = () => {
    const username = $('#loginForm').elements.username.value.trim();
    if (!username) return setFieldError($('#loginForm'), 'username', 'Enter your user name first, then choose face sign-in');
    faceSignInDialog(username);
  };
}

// Sign in with the face: look straight, then turn the head. The server checks it against the face this user enrolled.
async function faceSignInDialog(username) {
  const d = openDialog(`<div class="dlg-head"><h2>Sign in with your face</h2></div><div class="dlg-body" style="text-align:center">
    <p class="muted">${esc(username)}</p>${stageHtml({ guide: true })}<div class="hint-box" id="flHint" style="margin-top:6px">${icon('info')}<span>Starting camera...</span></div></div>
    <div class="dlg-foot"><button type="button" data-close>Cancel</button></div>`);
  let live = true; dialogCleanup = () => { live = false; camera.stop(); };
  const stage = $('.stage', d);
  const hint = (t, kind = '') => { const h = $('#flHint', d); if (!h) return; h.className = `hint-box ${kind}`; h.innerHTML = `${icon(kind === 'warn' ? 'alert' : kind === 'good' ? 'check' : 'info')}<span>${esc(t)}</span>`; };
  if (!(await startCamera(stage, null))) { hint('Camera not available. Use your password instead.', 'warn'); return; }
  while (live) {
    const photos = await captureLiveFace(stage, { headTurn: state.config.head_turn, setHint: (t) => hint(t), alive: () => live, qualityPath: '/login/face/quality' });
    if (!photos) return;
    hint('Checking...');
    try { state.me = await api('/login/face', 'POST', { username, images: photos }); closeDialog(); start(); return; }
    catch (e) { hint(e.message, 'warn'); if (e.code === 'ACCOUNT_LOCKED') return; await sleep(2200); }
  }
}

const STAFF = ['admin', 'viewer'], EVERYONE = ['admin', 'viewer', 'resident'];
const NAV = [
  { title: 'Monitor', items: [{ id: 'console', label: 'Security console', icon: 'scan', href: '/tf-check', roles: STAFF },
    { id: 'alerts', label: 'Alerts', icon: 'alert', roles: EVERYONE }] },
  { title: 'Manage', items: [
    { id: 'people', label: 'People', icon: 'users' },
    { id: 'register', label: 'Register', icon: 'userPlus', admin: true },
    { id: 'cameras', label: 'Cameras', icon: 'video' }] },
  { title: 'System', items: [{ id: 'settings', label: 'Settings', icon: 'lock' }, { id: 'users', label: 'Users', icon: 'users', admin: true }, { id: 'audit', label: 'Audit log', icon: 'clipboard', admin: true }] },
];
const canSee = (item) => (item.roles || STAFF).includes(state.me.role) && (!item.admin || state.me.role === 'admin');

function renderShell() {
  const admin = state.me.role === 'admin';
  $('#app').innerHTML = `
    <div class="shell">
      <aside class="sidebar">
        <div class="brand"><span class="logo">${icon('shield')}</span><div>Entry Guard<small>${esc(state.config.customer)}</small></div></div>
        <nav class="nav">${NAV.map((g) => ({ ...g, items: g.items.filter(canSee) })).filter((g) => g.items.length).map((g) => `<div class="nav-title">${g.title}</div>` + g.items.map((i) =>
          `<a href="${i.href || '#' + i.id}" data-nav="${i.id}">${icon(i.icon)}${i.label}<span class="tag badge-count" data-badge="${i.id}" hidden></span></a>`).join('')).join('')}</nav>
        <div class="foot">
          <div class="user"><span class="avatar">${esc(initials(state.me.username))}</span><div class="meta"><b>${esc(state.me.username)}</b><span>${esc(state.me.role)}</span></div></div>
          <div class="row"><button class="ghost sm grow" data-theme-toggle data-label="1"></button><button class="ghost sm" id="pwBtn" title="Change your password">${icon('lock')}</button><button class="ghost sm" id="logout" title="Sign out">${icon('logout')}</button></div>
        </div>
      </aside>
      <main class="content" id="page"></main>
    </div>`;
  renderThemeButtons();
  $('[data-theme-toggle]').onclick = toggleTheme;
  $('#pwBtn').onclick = changeOwnPassword;
  $('#logout').onclick = async () => { await api('/logout', 'POST'); state.me = null; showLogin(); };
}

const pageHead = (title, subtitle, actions = '') =>
  `<div class="page-head"><div><h1>${esc(title)}</h1>${subtitle ? `<p>${esc(subtitle)}</p>` : ''}</div><div class="actions">${actions}</div></div>`;

// =============================================================================== 4. pages
const pages = {
  people: { run: pagePeople }, register: { run: pageRegister, admin: true },
  cameras: { run: pageCameras }, users: { run: pageUsers, admin: true }, audit: { run: pageAudit, admin: true },
  alerts: { run: pageAlerts, roles: EVERYONE },
  settings: { run: pageSettings },
};

async function route() {
  cleanup(); cleanup = () => {}; camera.stop();
  const name = location.hash.slice(1) in pages ? location.hash.slice(1) : state.me.role === 'resident' ? 'alerts' : 'people';
  const page = pages[name];
  $$('.nav a').forEach((a) => a.classList.toggle('on', a.dataset.nav === name));
  const root = $('#page');
  if (!canSee(page)) { root.innerHTML = pageHead('Not allowed', 'This page is not available for your account.'); return; }
  root.innerHTML = '<p class="muted">Loading...</p>';
  try { await page.run(root); } catch (e) { if (!e.silent) root.innerHTML = `<div class="banner">${icon('alert')}<div>${esc(e.message)}</div></div>`; }
}

// ---------------------------------------------------------------- shared person form
// Name, phone, person type, unit, validity dates and notes are built in; the rest comes from
// `person_fields` in the customer config. The same form is used to register, edit and enrol from a scan.
const CORE_FIELDS = ['name', 'phone', 'person_type', 'unit', 'valid_from', 'valid_until', 'notes', 'consent', 'photos', 'watch_reason', 'watch_source', 'watch_reference', 'watch_review_by', 'watch_instructions'];
const formField = (field) => (CORE_FIELDS.includes(field) ? field : 'f_' + field);
const typeById = (id) => state.config.person_types.find((t) => t.id === id) || state.config.person_types[0];
const unitLabel = () => state.config.site.unit_label;
const dateStr = (ts) => { if (!ts) return ''; const d = new Date(ts * 1000); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; };
const addDays = (n) => dateStr(Date.now() / 1000 + n * 86400);

const STATUS = { active: ['ok', 'Active'], pending: ['info', 'Not valid yet'], expired: ['warn', 'Expired'], disabled: ['', 'Disabled'], blocked: ['bad', 'Blocked'] };
const statusPill = (label) => { const [kind, text] = STATUS[label] || ['', label]; return `<span class="pill ${kind}">${esc(text)}</span>`; };
const validityText = (p) => (p.valid_from || p.valid_until ? `${p.valid_from ? 'from ' + dateStr(p.valid_from) + ' ' : ''}${p.valid_until ? 'until ' + dateStr(p.valid_until) : ''}`.trim() : 'No time limit');

function profileFormHtml(p = {}, units = []) {
  const cfg = state.config, allUnits = [...new Set([...cfg.site.units.map(String), ...units])];
  return `
    <fieldset class="section"><legend>Identity</legend><div class="form-grid">
      ${fieldHtml({ name: 'name', label: 'Full name', value: p.name })}
      ${fieldHtml({ name: 'phone', label: 'Phone number', value: p.phone, type: 'tel', optional: !cfg.require_phone, placeholder: '+84 912 345 678' })}
      <label class="field">Person type<select name="person_type">${cfg.person_types.map((t) => `<option value="${esc(t.id)}" ${t.id === (p.person_type || 'resident') ? 'selected' : ''}>${esc(t.label)}</option>`).join('')}</select><span class="field-error" data-for="person_type"></span></label>
      <label class="field">${esc(unitLabel())} <span class="opt" id="unitReq"></span>
        <input name="unit" list="unitList" value="${esc(p.unit || '')}" autocomplete="off"><datalist id="unitList">${allUnits.map((u) => `<option value="${esc(u)}">`).join('')}</datalist><span class="field-error" data-for="unit"></span></label>
    </div><div class="faint" id="typeNote"></div></fieldset>
    <fieldset class="section" id="watchSection" hidden><legend>Watch-list details</legend><div class="form-grid">
      ${fieldHtml({ name: 'watch_reason', label: 'Reason (why this person is listed)', value: (p.watch || {}).reason, full: true })}
      ${fieldHtml({ name: 'watch_source', label: 'Source (who reported it)', value: (p.watch || {}).source, placeholder: 'City Police, security company...' })}
      ${fieldHtml({ name: 'watch_reference', label: 'Case / reference number', value: (p.watch || {}).reference, optional: true })}
      ${fieldHtml({ name: 'watch_review_by', label: 'Review this entry by', value: dateStr((p.watch || {}).review_by), type: 'date', optional: true })}
      <label class="field full">Instructions for staff <span class="opt">(optional)</span><textarea name="watch_instructions" rows="2" maxlength="300" placeholder="Do not approach. Call the police.">${esc((p.watch || {}).instructions || '')}</textarea><span class="field-error" data-for="watch_instructions"></span></label>
    </div><div class="faint">Every watch-list entry needs a reason and a source and should be reviewed regularly. Only record information you are authorised to hold. A match raises the highest alert, so use clear, front-facing photos.</div></fieldset>
    <fieldset class="section"><legend>Access period</legend><div class="form-grid">
      ${fieldHtml({ name: 'valid_from', label: 'Valid from', value: dateStr(p.valid_from), type: 'date', optional: true })}
      ${fieldHtml({ name: 'valid_until', label: 'Valid until', value: dateStr(p.valid_until), type: 'date', optional: true })}
    </div><div class="faint">Leave empty for no limit. Outside this period the person is still recognised, but access is denied.</div></fieldset>
    <fieldset class="section"><legend>More information</legend><div class="form-grid">
      ${cfg.fields.map((f) => fieldHtml({ name: 'f_' + f.key, label: f.label + (f.sensitive ? ' (sensitive)' : ''), value: (p.fields || {})[f.key] || '', optional: !f.required })).join('')}
      <label class="field full">Notes <span class="opt">(optional)</span><textarea name="notes" rows="2" maxlength="500">${esc(p.notes || '')}</textarea><span class="field-error" data-for="notes"></span></label>
    </div></fieldset>`;
}
function wireProfileForm(form) {
  const el = form.elements;
  const apply = (changed) => {
    const t = typeById(el.person_type.value);
    $('#unitReq', form).textContent = t.needs_unit ? '*' : '(optional)';
    $('#watchSection', form).hidden = !t.watchlist;
    const basis = $('#consentText', form); if (basis) basis.textContent = t.watchlist ? state.config.watchlist_basis_text : state.config.consent_text;
    $('#typeNote', form).textContent = t.watchlist ? (t.severity === 'critical'
        ? 'CRITICAL watch list: every confirmed detection raises the highest alert (siren, full screen, residents warned) and access is always denied.'
        : 'Banned: every detection raises a high alert and access is always denied.')
      : !t.can_enter ? 'This type is always denied, and every scan of them raises an alert.'
      : t.needs_expiry ? `${t.label} access needs a "valid until" date${t.default_days ? ` (suggested: ${t.default_days} day${t.default_days > 1 ? 's' : ''})` : ''}.` : '';
    if (changed && t.default_days && !el.valid_until.value) el.valid_until.value = addDays(t.default_days);
  };
  el.person_type.onchange = () => apply(true); apply(false);
}
function readProfile(form) {
  const el = form.elements, fields = {};
  state.config.fields.forEach((f) => { const v = el['f_' + f.key].value.trim(); if (v) fields[f.key] = v; });
  const watch = typeById(el.person_type.value).watchlist ? { reason: el.watch_reason.value.trim(), source: el.watch_source.value.trim(),
    reference: el.watch_reference.value.trim(), review_by: el.watch_review_by.value, instructions: el.watch_instructions.value.trim() } : {};
  return { name: el.name.value.trim(), phone: el.phone.value.trim(), person_type: el.person_type.value, unit: el.unit.value.trim(),
    valid_from: el.valid_from.value, valid_until: el.valid_until.value, notes: el.notes.value.trim(), watch, fields };
}
const showProfileError = (form, err) => { if (!setFieldError(form, formField(err.field), err.message)) toast(err.message, 'bad'); };
function fileToDataUrl(file, maxSide = 1280) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file), img = new Image();
    img.onload = () => {
      const k = Math.min(1, maxSide / Math.max(img.width, img.height)), c = document.createElement('canvas');
      c.width = Math.round(img.width * k); c.height = Math.round(img.height * k); c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
      URL.revokeObjectURL(url); resolve(c.toDataURL('image/jpeg', 0.92));
    };
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('not an image')); };
    img.src = url;
  });
}
const knownUnits = async () => { try { return [...new Set((await api('/people')).map((p) => p.unit).filter(Boolean))]; } catch { return []; } };

// ---------------------------------------------------------------- Update the photos of a registered person
// Replace every photo (for example after a wrong one was uploaded) or add more. Photos come from the camera or from files.
async function photosDialog(person, done) {
  const photos = []; let live = true, bad = -1, hold = 0;       // `hold`: keep an error message on screen for a few seconds
  const d = openDialog(`<div class="dlg-head"><h2>Update photos</h2><span class="grow"></span><b>${esc(person.name)}</b> <span class="mono faint">${esc(person.code)}</span></div>
    <div class="dlg-body">
      ${typeById(person.person_type).watchlist ? `<div class="banner" style="background:var(--bad-soft)">${icon('alert')}<div>This person is on the <b>watch list</b>. The photos decide who raises the alert, so use clear, front-facing photos of the right person.</div></div>` : ''}
      <div class="seg" id="phMode"><button type="button" data-v="replace" class="on">Replace all photos</button><button type="button" data-v="add">Add to current photos</button></div>
      <div class="faint" id="phModeNote"></div>
      ${stageHtml({ guide: true })}<div class="hint-box" id="phHint">${icon('info')}<span>Starting camera... you can also upload photo files.</span></div>
      <div class="row wrap"><div class="slots" id="phSlots"></div><span class="grow"></span>
        <input type="file" id="phFile" accept="image/*" multiple hidden><button type="button" id="phUpload">${icon('download')}Upload photos</button><button type="button" id="phShot">${icon('scan')}Capture now</button></div>
    </div>
    <div class="dlg-foot"><button type="button" data-close>Cancel</button><button class="primary" id="phSave" disabled>Save photos</button></div>`, false, true);
  dialogCleanup = () => { live = false; camera.stop(); };
  const stage = $('.stage', d), video = $('video', stage);
  const note = () => { $('#phModeNote', d).textContent = $('#phMode .on', d).dataset.v === 'replace' ? 'The photos you add now will replace ALL current photos of this person.' : 'The photos you add now will be added to the current photos.'; };
  $$('#phMode button', d).forEach((b) => { b.onclick = () => { $$('#phMode button', d).forEach((x) => x.classList.toggle('on', x === b)); note(); }; }); note();
  const drawSlots = () => {
    $('#phSlots', d).innerHTML = photos.length ? photos.map((ph, i) => `<div class="slot ${i === bad ? 'bad' : 'filled'}"><img src="${ph}" alt=""><button type="button" data-i="${i}" title="Remove">×</button></div>`).join('') : '<span class="faint">No new photos yet</span>';
    $('#phSave', d).disabled = !photos.length;
  };
  drawSlots();
  $('#phSlots', d).onclick = (e) => { const b = e.target.closest('button[data-i]'); if (b) { photos.splice(+b.dataset.i, 1); bad = -1; drawSlots(); } };
  $('#phUpload', d).onclick = () => $('#phFile', d).click();
  $('#phFile', d).onchange = async (e) => { for (const f of e.target.files) { try { photos.push(await fileToDataUrl(f)); } catch { toast(`${f.name} is not a readable image`, 'bad'); } } e.target.value = ''; bad = -1; drawSlots(); };
  $('#phShot', d).onclick = () => { if (!video.videoWidth) return toast('The camera is not ready', 'bad'); photos.push(camera.snapshot(video, 0, 0.92).data); bad = -1; drawSlots(); const f = $('.flash', stage); f.classList.remove('go'); void f.offsetWidth; f.classList.add('go'); };
  $('#phSave', d).onclick = async () => {
    $('#phSave', d).disabled = true;
    try {
      await api(`/people/${person.id}/photos`, 'POST', { images: photos, replace: $('#phMode .on', d).dataset.v === 'replace' });
      toast('Photos updated'); closeDialog(); done(); personDialog(person.id, done);
    } catch (err) {
      if (err.cancelled) { $('#phSave', d).disabled = false; return; }
      if (err.field?.startsWith('photos[')) { bad = +/\d+/.exec(err.field)[0] - 1; drawSlots(); }
      hold = Date.now() + 7000; $('#phHint', d).className = 'hint-box warn'; $('#phHint', d).innerHTML = `${icon('alert')}<span>${esc(err.message)}</span>`;
      $('#phSave', d).disabled = !photos.length;
    }
  };
  // live hints from the camera (no automatic capture: you press Capture now)
  startCamera(stage, null).then(async (ok) => {
    if (!ok) { $('#phHint', d).innerHTML = `${icon('info')}<span>No camera: upload photo files instead.</span>`; return; }
    while (live) {
      if (!video.videoWidth) { await sleep(300); continue; }
      try {
        const frame = camera.snapshot(video, 640, 0.8), q = await api('/quality', 'POST', { image: frame.data });
        if (!live) return;
        drawBoxes(stage, q.bbox ? [{ bbox: q.bbox, kind: q.ok ? 'ok' : 'warn' }] : [], 1 / frame.scale);
        $('.guide', stage)?.classList.toggle('good', q.ok);
        const h = $('#phHint', d); if (h && Date.now() > hold) { h.className = `hint-box ${q.ok ? 'good' : 'warn'}`; h.innerHTML = `${icon(q.ok ? 'check' : 'alert')}<span>${esc(q.ok ? 'Good. Press "Capture now"' : q.message)}</span>`; }
      } catch (e) { if (e.silent) return; }
      await sleep(450);
    }
  });
}

// ---------------------------------------------------------------- People
async function pagePeople(root) {
  const admin = state.me.role === 'admin';
  const people = await api('/people');
  const soon = (p) => p.valid_until && p.valid_until * 1000 > Date.now() && p.valid_until * 1000 - Date.now() < 7 * 86400e3;
  const n = (fn) => people.filter(fn).length;
  const rows = people.map((p) => `
    <tr class="click" data-id="${p.id}" data-q="${esc([p.name, p.code, p.phone, p.unit, p.person_type].join(' ').toLowerCase())}" data-status="${esc(p.status_label)}" data-type="${esc(p.person_type)}">
      <td><div class="row"><img class="avatar" src="/api/people/${p.id}/photo" alt="" data-initials="${esc(initials(p.name))}">
        <div><div class="name">${esc(p.name)} ${typeById(p.person_type).watchlist ? '<span class="pill bad plain">WATCH LIST</span>' : ''}</div><div class="sub"><span class="mono">${esc(p.code)}</span> · ${esc(p.type_label)}</div></div></div></td>
      <td>${esc(p.phone) || '<span class="faint">-</span>'}</td>
      <td>${esc(p.unit) || '<span class="faint">-</span>'}</td>
      <td>${statusPill(p.status_label)}<div class="sub">${esc(validityText(p))}</div></td>
      <td class="actions">${admin ? `<button class="sm" data-act="edit" data-id="${p.id}">${icon('edit')}Edit</button>
        <button class="sm" data-act="toggle" data-id="${p.id}">${p.status === 'active' ? 'Disable' : 'Enable'}</button>` : ''}</td>
    </tr>`).join('');
  root.innerHTML = pageHead('People', 'Everyone registered with the system and their access status.',
    admin ? `<a class="btn primary" href="#register">${icon('userPlus')}Register a person</a>` : '') + `
    <div class="kpis" style="margin-bottom:16px">
      <div class="kpi brand"><div class="label">Registered</div><div class="value">${people.length}</div></div>
      <div class="kpi ok"><div class="label">Active</div><div class="value">${n((p) => p.status_label === 'active')}</div></div>
      <div class="kpi warn"><div class="label">Expiring in 7 days</div><div class="value">${n(soon)}</div></div>
      <div class="kpi"><div class="label">Expired / disabled</div><div class="value">${n((p) => ['expired', 'disabled', 'pending'].includes(p.status_label))}</div></div>
      <div class="kpi bad"><div class="label">Watch list</div><div class="value">${n((p) => p.status_label === 'blocked')}</div></div>
    </div>
    <div class="card">
      <div class="toolbar"><input type="search" id="search" placeholder="Search name, ID, phone or ${esc(unitLabel().toLowerCase())}" style="width:300px">
        <select id="typeFilter"><option value="">All types</option>${state.config.person_types.map((t) => `<option value="${esc(t.id)}">${esc(t.label)}</option>`).join('')}</select>
        <select id="statusFilter"><option value="">All statuses</option>${Object.entries(STATUS).map(([k, [, t]]) => `<option value="${k}">${t}</option>`).join('')}</select>
        <span class="muted grow" style="text-align:right" id="count"></span></div>
      <div class="table-scroll"><table><thead><tr><th>Person</th><th>Phone</th><th>${esc(unitLabel())}</th><th>Access status</th><th></th></tr></thead>
        <tbody id="rows">${rows}</tbody></table></div>
      ${people.length ? '' : `<div class="empty">${icon('users')}<b>No one is registered yet</b><span>Register the first person to start recognizing faces.</span>${admin ? `<a class="btn primary" href="#register">Register a person</a>` : ''}</div>`}
    </div>`;
  const filter = () => {
    const q = $('#search').value.toLowerCase(), st = $('#statusFilter').value, ty = $('#typeFilter').value; let shown = 0;
    $$('#rows tr').forEach((tr) => { const ok = tr.dataset.q.includes(q) && (!st || tr.dataset.status === st) && (!ty || tr.dataset.type === ty); tr.hidden = !ok; shown += ok; });
    $('#count').textContent = `${shown} of ${people.length}`;
  };
  ['#search', '#statusFilter', '#typeFilter'].forEach((id) => { $(id).oninput = filter; $(id).onchange = filter; }); filter();
  $('#rows').onclick = async (e) => {
    const b = e.target.closest('button[data-act]'), tr = e.target.closest('tr[data-id]');
    if (!b) { if (tr) personDialog(+tr.dataset.id, () => pagePeople(root)); return; }
    const person = people.find((p) => p.id == b.dataset.id);
    if (b.dataset.act === 'edit') return editPerson(person, () => pagePeople(root));
    await api('/people/' + person.id, 'PATCH', { status: person.status === 'active' ? 'disabled' : 'active' });
    toast(`${person.name} ${person.status === 'active' ? 'disabled' : 'enabled'}`); pagePeople(root);
  };
}

async function personDialog(id, done) {
  const admin = state.me.role === 'admin';
  let p; try { p = await api('/people/' + id); } catch (e) { return toast(e.message, 'bad'); }
  const denied = !p.access.granted, w = p.watch || {};
  const watchHtml = w.reason ? `<div class="banner" style="background:var(--bad-soft)">${icon('alert')}<div><b>Watch-list entry</b> · ${esc(p.type_label)}<br>Reason: ${esc(w.reason)}${w.instructions ? `<br>Instructions: ${esc(w.instructions)}` : ''}
    <br><span class="faint">Source: ${esc(w.source)}${w.reference ? ' · Ref ' + esc(w.reference) : ''} · added by ${esc(w.added_by || '-')}${w.added_at ? ' on ' + esc(fmtDateTime(w.added_at)) : ''}${w.review_by ? ` · review by ${esc(dateStr(w.review_by))}${w.review_by * 1000 < Date.now() ? ' <b>(OVERDUE)</b>' : ''}` : ''}</span></div></div>` : '';
  const rows = [['ID', `<span class="mono">${esc(p.code)}</span>`], ['Type', esc(p.type_label)], ['Phone', esc(p.phone) || '-'], [unitLabel(), esc(p.unit) || '-'],
    ['Access period', esc(validityText(p))], ...state.config.fields.map((f) => [f.label, esc(p.fields[f.key]) || '-']),
    ['Notes', esc(p.notes) || '-'], ['Consent given', p.consent_at ? esc(fmtDateTime(p.consent_at)) : 'Not recorded'], ['Scans recorded', p.scans_total]];
  const d = openDialog(`<div class="dlg-head"><h2>${esc(p.name)}</h2>${statusPill(p.status_label)}<span class="grow"></span><span class="mono faint">${esc(p.code)}</span></div>
    <div class="dlg-body">
      ${watchHtml}
      <div class="verdict ${denied ? 'bad' : 'ok'}" style="padding:12px 16px"><span class="badge" style="width:40px;height:40px">${icon(denied ? 'x' : 'check')}</span>
        <div><div class="headline" style="font-size:17px">${denied ? 'Access denied now' : 'Access allowed now'}</div><div class="muted">${esc(p.access.reason) || 'All checks passed'}</div></div></div>
      <div class="detail"><img src="/api/people/${p.id}/photo" alt="" data-initials="${esc(initials(p.name))}">
        <dl style="margin:0;display:grid;grid-template-columns:auto 1fr;gap:7px 16px">${rows.map(([k, v]) => `<dt class="faint">${esc(k)}</dt><dd style="margin:0;word-break:break-word">${v}</dd>`).join('')}</dl></div>
      <div><b style="font-size:13px">Photos (${(p.photos || []).length})</b>
        <div class="photo-grid">${(p.photos || []).map((ph) => `<div class="ph"><img src="/api/people/${p.id}/photos/${ph.id}" alt="">${admin && (p.photos || []).length > 1 ? `<button type="button" data-rm-photo="${ph.id}" title="Remove this photo">×</button>` : ''}</div>`).join('')}</div>
        ${admin ? '<div class="faint" style="margin-top:6px">Uploaded the wrong photo? Use <b>Update photos</b> to replace it.</div>' : ''}</div>
      <div><b style="font-size:13px">Recent scans</b>${p.recent_events.length ? `<div class="table-scroll" style="margin-top:8px"><table><tbody>${p.recent_events.map((e) => `<tr><td class="muted">${esc(fmtDateTime(e.ts))}</td><td>${accessPill(e)}</td><td class="muted">${esc(e.reason)}</td></tr>`).join('')}</tbody></table></div>` : '<p class="faint" style="margin-top:6px">No scans yet.</p>'}</div>
    </div>
    <div class="dlg-foot"><button data-close>Close</button>
      ${admin ? `<button id="pEdit">${icon('edit')}Edit</button><button id="pPhotos">${icon('scan')}Update photos</button><button id="pToggle">${p.status === 'active' ? 'Disable' : 'Enable'}</button><button id="pDelete" class="danger">${icon('trash')}Delete</button>` : ''}</div>`, false, true);
  if (!admin) return;
  $('#pEdit', d).onclick = () => editPerson(p, done);
  $('#pPhotos', d).onclick = () => photosDialog(p, done);
  d.onclick = async (e) => {
    const b = e.target.closest('[data-rm-photo]'); if (!b) return;
    try { await api(`/people/${p.id}/photos/${b.dataset.rmPhoto}`, 'DELETE'); toast('Photo removed'); done(); personDialog(p.id, done); }
    catch (err) { if (!err.cancelled) toast(err.message, 'bad'); }
  };
  $('#pToggle', d).onclick = async () => { await api('/people/' + p.id, 'PATCH', { status: p.status === 'active' ? 'disabled' : 'active' }); closeDialog(); toast('Updated'); done(); };
  $('#pDelete', d).onclick = async () => {
    if (await confirmDialog({ title: `Delete ${p.name}?`, message: 'Their photos and face data are erased permanently. Past scan-log lines stay, without the name.', confirm: 'Delete permanently', danger: true })) {
      await api('/people/' + p.id, 'DELETE'); toast(`${p.name} deleted`); done();
    }
  };
}

async function editPerson(person, done) {
  const units = await knownUnits();
  const d = openDialog(`<form id="editForm" novalidate><div class="dlg-head"><h2>Edit ${esc(person.name)}</h2><span class="grow"></span><span class="mono faint">${esc(person.code)}</span></div>
    <div class="dlg-body">${profileFormHtml(person, units)}</div>
    <div class="dlg-foot"><button type="button" data-close>Cancel</button><button class="primary">Save changes</button></div></form>`, false, true);
  const form = $('#editForm', d); wireProfileForm(form);
  form.onsubmit = async (e) => {
    e.preventDefault();
    try { await api('/people/' + person.id, 'PATCH', readProfile(form)); closeDialog(); toast('Saved'); done(); } catch (err) { showProfileError(form, err); }
  };
}

// ---------------------------------------------------------------- Register (guided)
async function pageRegister(root) {
  const need = state.config.recommended_photos, units = await knownUnits();
  let photos = [], autoCapture = false, active = true, goodStreak = 0, badSlot = -1;
  root.innerHTML = pageHead('Register a person', `Capture ${need} clear photos, then fill in the details. An ID is generated automatically.`) + `
    <div class="live-grid">
      <section class="card"><header><h2>1. Capture photos</h2><span class="grow"></span><select id="camSelect" style="width:auto"></select></header>
        <div class="body stack">${stageHtml({ guide: true, hud: '<div class="hud tl"><span class="chip off" id="camChip">Camera</span></div>' })}
          <div class="hint-box" id="hint">${icon('info')}<span>Starting camera...</span></div>
          <div class="row wrap"><div class="slots" id="slots"></div><span class="grow"></span>
            <label class="row" style="gap:6px"><input type="checkbox" id="auto"> Auto-capture</label>
            <input type="file" id="upload" accept="image/*" multiple hidden><button id="uploadBtn">${icon('download')}Upload photos</button>
            <button id="snap">${icon('scan')}Capture now</button></div></div></section>
      <section class="card"><header><h2>2. Details</h2><span class="grow"></span><span class="pill plain info">ID is generated on save</span></header>
        <form class="body stack" id="regForm" novalidate>
          ${profileFormHtml({}, units)}
          <label class="row" style="align-items:flex-start;gap:10px"><input type="checkbox" name="consent" style="margin-top:3px"><span class="muted" style="font-size:13px" id="consentText">${esc(state.config.consent_text)}</span></label>
          <span class="field-error" data-for="consent"></span>
          <button class="primary" id="save" style="padding:11px">Register person</button></form></section>
    </div>`;
  const stage = $('.stage', root), video = $('video', stage), hint = $('#hint'), guide = $('.guide', stage), form = $('#regForm');
  wireProfileForm(form);

  const drawSlots = () => {
    const total = Math.max(need, photos.length), cells = [];
    for (let i = 0; i < total; i++) {
      cells.push(photos[i]
        ? `<div class="slot ${i === badSlot ? 'bad' : 'filled'}"><img src="${photos[i]}" alt=""><button data-i="${i}" title="Remove">×</button></div>`
        : `<div class="slot ${i === photos.length ? 'next' : ''}">${i + 1}</div>`);
    }
    $('#slots').innerHTML = cells.join('');
  };
  $('#slots').onclick = (e) => { const b = e.target.closest('button[data-i]'); if (b) { photos.splice(+b.dataset.i, 1); badSlot = -1; drawSlots(); } };
  const setHint = (kind, text, ic) => { hint.className = `hint-box ${kind}`; hint.innerHTML = `${icon(ic)}<span>${esc(text)}</span>`; };
  const capture = () => {
    if (!video.videoWidth) return false;
    photos.push(camera.snapshot(video, 0, 0.92).data); badSlot = -1; drawSlots();
    const flash = $('.flash', stage); flash.classList.remove('go'); void flash.offsetWidth; flash.classList.add('go');
    return true;
  };
  $('#snap').onclick = capture; $('#auto').onchange = (e) => { autoCapture = e.target.checked; };
  // Photos can also be uploaded as files (a photo supplied by the police, an ID photo...).
  $('#uploadBtn').onclick = () => $('#upload').click();
  $('#upload').onchange = async (e) => {
    for (const file of e.target.files) { try { photos.push(await fileToDataUrl(file)); } catch { toast(`${file.name} is not a readable image`, 'bad'); } }
    e.target.value = ''; badSlot = -1; drawSlots();
  };

  // Poll the server for live feedback about the picture; capture automatically when it is good.
  async function guideLoop() {
    while (active) {
      if (!video.videoWidth) { await sleep(300); continue; }
      try {
        const frame = camera.snapshot(video, 640, 0.8);
        const q = await api('/quality', 'POST', { image: frame.data });
        if (!active) return;
        guide.classList.toggle('good', q.ok);
        drawBoxes(stage, q.bbox ? [{ bbox: q.bbox, kind: q.ok ? 'ok' : 'warn' }] : [], 1 / frame.scale);
        if (photos.length >= need) setHint('good', `All ${need} photos captured. Fill in the details and register.`, 'check');
        else if (q.ok) setHint('good', `Good. Hold still... (photo ${photos.length + 1} of ${need})`, 'check');
        else setHint('warn', q.message, 'alert');
        goodStreak = q.ok ? goodStreak + 1 : 0;
        if (autoCapture && !typeById(form.elements.person_type.value).watchlist && goodStreak >= 3 && photos.length < need) { capture(); goodStreak = 0; await sleep(1400); }
      } catch (e) { if (e.silent) return; }
      await sleep(450);
    }
  }
  cleanup = () => { active = false; camera.stop(); };
  drawSlots();
  // The camera starts in the background: the form and the file upload work even without a camera
  // (for example when registering a watch-list person from a photo file).
  startCamera(stage, $('#camSelect')).then((ok) => {
    if (!active) return;
    $('#camChip').className = `chip ${ok ? 'live' : 'off'}`; $('#camChip').textContent = ok ? 'Camera live' : 'No camera';
    if (ok) guideLoop(); else setHint('warn', 'No camera: upload photos as files instead', 'alert');
  });

  form.onsubmit = async (e) => {
    e.preventDefault();
    if (!photos.length && !capture()) return toast('The camera is not ready yet', 'bad');
    $('#save').disabled = true;
    try {
      const person = await api('/people', 'POST', { ...readProfile(form), images: photos, consent: form.elements.consent.checked });
      toast(`${person.name} registered. ID ${person.code}`); location.hash = '#people';
    } catch (err) {
      if (err.field?.startsWith('photos[')) { badSlot = +/\d+/.exec(err.field)[0] - 1; drawSlots(); setHint('warn', err.message, 'alert'); toast(err.message, 'bad'); }
      else if (err.field === 'photos') { setHint('warn', err.message, 'alert'); toast(err.message, 'bad'); }
      else showProfileError(form, err);
    } finally { $('#save').disabled = false; }
  };
}

// ---------------------------------------------------------------- Cameras
async function pageCameras(root) {
  const admin = state.me.role === 'admin';
  const cams = await api('/cameras');
  const card = (c) => `
    <article class="card cam-card"><div class="top"><span class="ico">${icon(c.kind === 'browser' ? 'scan' : 'video')}</span>
      <div class="grow"><div class="name">${esc(c.name)} ${c.builtin ? '<span class="pill info plain">Default</span>' : ''}</div><div class="sub">${esc(c.location) || '&nbsp;'}</div></div>
      <span class="pill ${c.kind === 'browser' ? 'ok' : c.enabled ? 'info' : ''}">${c.kind === 'browser' ? 'Active' : c.enabled ? 'Registered' : 'Disabled'}</span></div>
      <dl><dt>Type</dt><dd>${c.kind === 'browser' ? 'Browser camera (this computer)' : 'IP camera (RTSP)'}</dd>
        ${c.kind === 'rtsp' ? `<dt>Address</dt><dd class="mono">${esc(c.url)}</dd><dt>Direction</dt><dd>${esc(c.direction)}</dd><dt>Transport</dt><dd>${esc(c.transport.toUpperCase())} · ${c.fps} fps</dd>` : '<dt>Used by</dt><dd>Security console and registration</dd>'}</dl>
      <div class="row wrap">${c.kind === 'rtsp' && c.enabled ? `<button class="sm primary" data-act="live" data-id="${c.id}">${icon('play')}Live view</button>` : ''}
        ${admin ? `${c.kind === 'rtsp' ? `<button class="sm" data-act="test" data-id="${c.id}">${icon('wifi')}Test</button>` : ''}
        <button class="sm" data-act="edit" data-id="${c.id}">${icon('edit')}Edit</button>
        ${c.kind === 'rtsp' ? `<button class="sm" data-act="toggle" data-id="${c.id}">${c.enabled ? 'Disable' : 'Enable'}</button>
        <button class="sm danger" data-act="delete" data-id="${c.id}">${icon('trash')}</button>` : ''}` : ''}</div></article>`;
  root.innerHTML = pageHead('Cameras', 'Where faces are scanned from.', admin ? `<button class="primary" id="addCam">${icon('plus')}Add IP camera</button>` : '') + `
    <div class="banner" style="margin-bottom:16px">${icon('info')}<div><b>The laptop camera is the default.</b> Add an IP camera (RTSP), press <b>Test</b> to check it, then <b>Live view</b> to watch the stream
      with face recognition. The security console can scan it too.</div></div>
    <div class="cam-grid">${cams.map(card).join('')}</div>`;
  if (admin) $('#addCam').onclick = () => cameraDialog(null, () => route());
  root.onclick = async (e) => {
    const b = e.target.closest('button[data-act]'); if (!b) return;
    const cam = cams.find((c) => c.id === b.dataset.id);
    if (b.dataset.act === 'live') return liveView(cam);
    if (b.dataset.act === 'edit') return cameraDialog(cam, () => route());
    if (b.dataset.act === 'toggle') { await api('/cameras/' + cam.id, 'PATCH', { enabled: !cam.enabled }); toast(`${cam.name} ${cam.enabled ? 'disabled' : 'enabled'}`); return route(); }
    if (b.dataset.act === 'test') return runTest(cam.id, null, cam.name);
    if (await confirmDialog({ title: `Delete ${cam.name}?`, message: 'The camera record is removed. Past scan-log lines stay.', confirm: 'Delete camera', danger: true })) {
      await api('/cameras/' + cam.id, 'DELETE'); toast('Camera deleted'); route();
    }
  };
}

// A live picture from an IP camera, streamed by the server (MJPEG) with face boxes drawn on it.
function liveView(cam) {
  const d = openDialog(`<div class="dlg-head"><h2>${esc(cam.name)}</h2><span class="pill plain" id="lvState">Connecting</span><span class="grow"></span><span class="faint mono" id="lvInfo"></span></div>
    <div class="dlg-body"><div class="stage"><img class="ipimg" alt="Live view of ${esc(cam.name)}" src="/api/cameras/${esc(cam.id)}/stream?ts=${Date.now()}"></div>
      <div id="lvNote" class="muted">Opening the camera stream. This can take a few seconds.</div></div>
    <div class="dlg-foot"><a class="btn" href="/tf-check?camera=${esc(cam.id)}">${icon('scan')}Open in security console</a><button data-close class="primary">Close</button></div>`, false, true);
  let open = true;
  dialogCleanup = () => { open = false; $('.ipimg', d)?.remove(); };   // drop the stream connection when the dialog closes
  (async function poll() {
    while (open) {
      try {
        const s = await api(`/cameras/${cam.id}/status`);
        if (!open) return;
        const pill = $('#lvState', d);
        pill.className = 'pill plain ' + (s.state === 'live' ? 'ok' : 'warn');
        pill.textContent = { live: 'Live', connecting: 'Connecting', reconnecting: 'Reconnecting' }[s.state] || s.state;
        $('#lvInfo', d).textContent = s.state === 'live' ? `${s.fps} fps${s.size ? ' · ' + s.size[0] + '×' + s.size[1] : ''}` : '';
        $('#lvNote', d).innerHTML = s.state !== 'live' ? esc(s.error || 'Opening the camera stream...')
          : s.results.some((r) => r.bbox) ? s.results.filter((r) => r.bbox).map((r) => `<span class="pill ${resultKind(r)}">${esc(r.person || r.decision)}</span>`).join(' ') : 'Streaming. No face in view.';
      } catch (e) { if (e.silent) return; }
      await sleep(700);
    }
  })();
}

function testResultHtml(r) {
  return `<div class="test-result"><div class="row"><span class="pill ${r.ok ? 'ok' : 'bad'}">${r.ok ? 'Connected' : 'Failed'}</span><span class="muted">${esc(r.message)}</span></div>
    ${r.ok ? `<div class="faint">${r.width}×${r.height} · first picture in ${r.latency_ms} ms</div><img class="preview" src="${r.preview}" alt="Camera preview">` : ''}</div>`;
}
async function runTest(id, body, name) {
  const d = openDialog(`<div class="dlg-head"><h2>Testing ${esc(name || 'camera')}</h2></div><div class="dlg-body" id="tr"><p class="muted">Connecting... this can take up to 10 seconds.</p></div>
    <div class="dlg-foot"><button data-close>Close</button></div>`, true);
  try { $('#tr', d).innerHTML = testResultHtml(await api('/cameras/test', 'POST', id ? { id } : body)); }
  catch (e) { $('#tr', d).innerHTML = `<div class="banner">${icon('alert')}<div>${esc(e.message)}</div></div>`; }
}

// ---- RTSP address helpers -------------------------------------------------------------------
const decode = (t) => { try { return decodeURIComponent(t || ''); } catch { return t || ''; } };
// rtsp://user:password@host:port/path?query  ->  fields (null when it is not an RTSP address)
function parseRtspUrl(text) {
  const m = /^rtsps?:\/\/(?:([^:@/]*)(?::([^@/]*))?@)?([^:/?#]+)(?::(\d+))?(.*)$/i.exec(text.trim());
  return m ? { username: decode(m[1]), password: decode(m[2]), host: m[3], port: m[4] || '554', path: m[5] || '' } : null;
}
// Catalog paths contain {ch} (channel 1, 2...) and {ch2} (01, 02...).
const expandPath = (path, channel) => path.replace('{ch2}', String(channel).padStart(2, '0')).replace('{ch}', String(channel));

// Add / edit a camera. The stream path is never fixed: pick a catalog entry, paste a full RTSP URL,
// type any custom path, reuse your own template, or let the server search for a working path.
async function cameraDialog(cam, done) {
  const edit = !!cam, ip = !cam?.builtin, v = (k, fallback = '') => esc(cam?.[k] ?? fallback);
  let presets = { brands: [], templates: [] };
  if (ip) { try { presets = await api('/camera-presets'); } catch (e) { if (e.silent) return; } }
  const brandOptions = presets.brands.map((b, i) => `<option value="b${i}">${esc(b.brand)}</option>`).join('');
  const templateOptions = presets.templates.map((t) => `<option value="t${t.id}">${esc(t.name)}</option>`).join('');
  const allPaths = [...new Set([...presets.brands.flatMap((b) => b.streams.map((s) => expandPath(s.path, 1))), ...presets.templates.map((t) => t.path)])];

  const d = openDialog(`<form id="camForm" novalidate>
    <div class="dlg-head"><h2>${edit ? 'Edit' : 'Add'} ${ip ? 'IP camera' : 'laptop camera'}</h2></div>
    <div class="dlg-body"><div class="form-grid">
      ${fieldHtml({ name: 'name', label: 'Camera name', value: cam?.name, placeholder: 'Main entrance' })}
      ${fieldHtml({ name: 'location', label: 'Location', value: cam?.location, optional: true, placeholder: 'Lobby, ground floor' })}
      ${ip ? `
      <div class="full" style="display:grid;gap:10px;padding:14px;border:1px solid var(--border);border-radius:var(--radius-sm);background:var(--surface-2)">
        <b style="font-size:13px">Stream address <span class="faint" style="font-weight:400">(pick any option: everything stays editable)</span></b>
        <label class="field">Paste a full RTSP address <span class="opt">(fills the fields below)</span>
          <input id="pasteUrl" placeholder="rtsp://user:password@192.168.1.10:554/stream1" autocomplete="off"><span class="faint" id="pasteNote" style="font-weight:400"></span></label>
        <div class="form-grid" style="grid-template-columns:1.4fr 1.4fr .6fr">
          <label class="field">Brand or template<select id="brand"><option value="">Choose...</option>${brandOptions}
            ${templateOptions ? `<optgroup label="My templates">${templateOptions}</optgroup>` : ''}<option value="custom">Custom / other</option></select></label>
          <label class="field">Stream<select id="stream" disabled><option>Choose a brand first</option></select></label>
          <label class="field">Channel<input id="channel" type="number" min="1" max="64" value="1"></label>
        </div>
        <div class="faint" id="brandNote"></div>
        <div class="row" id="tplActions" hidden><button type="button" class="sm danger" id="delTpl">${icon('trash')}Delete this template</button></div>
      </div>
      ${fieldHtml({ name: 'host', label: 'IP address or host name', value: cam?.host, placeholder: '192.168.1.210' })}
      ${fieldHtml({ name: 'port', label: 'Port', value: cam?.port ?? 554, type: 'number' })}
      <label class="field full">Stream path <span class="opt">(type any path; suggestions appear as you type)</span>
        <input name="path" list="pathlist" value="${v('path')}" placeholder="/stream1  or  /cam/realmonitor?channel=1&subtype=0" autocomplete="off">
        <datalist id="pathlist">${allPaths.map((p) => `<option value="${esc(p)}">`).join('')}</datalist><span class="field-error" data-for="path"></span></label>
      ${fieldHtml({ name: 'username', label: 'Camera username', value: cam?.username, optional: true })}
      ${fieldHtml({ name: 'password', label: 'Camera password', type: 'password', optional: true, placeholder: edit && cam.has_password ? 'Leave empty to keep the saved password' : '' })}
      <label class="field">Direction<select name="direction">${['in', 'out', 'both'].map((o) => `<option ${v('direction', 'in') === o ? 'selected' : ''}>${o}</option>`).join('')}</select><span class="field-error" data-for="direction"></span></label>
      <label class="field">Transport<select name="transport">${['tcp', 'udp'].map((o) => `<option ${v('transport', 'tcp') === o ? 'selected' : ''}>${o}</option>`).join('')}</select><span class="field-error" data-for="transport"></span></label>
      ${fieldHtml({ name: 'fps', label: 'Frames per second', value: cam?.fps ?? 10, type: 'number' })}
      <div class="full"><span class="faint">Address that will be used</span><div class="mono" id="preview" style="word-break:break-all"></div></div>` : ''}
    </div>
    ${ip ? `<div class="row wrap"><button type="button" id="testBtn">${icon('wifi')}Test connection</button>
        <button type="button" id="findBtn">${icon('search')}Find stream path automatically</button></div>
      <div id="testOut"></div>
      <label class="row" style="gap:8px"><input type="checkbox" id="saveTpl"> Save the path, port and transport as a template named
        <input id="tplName" placeholder="e.g. Warehouse cameras" style="width:220px" disabled></label>` : ''}</div>
    <div class="dlg-foot"><button type="button" data-close>Cancel</button><button class="primary">${edit ? 'Save changes' : 'Add camera'}</button></div></form>`);

  const form = $('#camForm', d), el = form.elements;
  const values = () => { const o = {}; $$('input[name], select[name]', form).forEach((x) => { o[x.name] = x.value; }); return o; };
  if (!ip) { form.onsubmit = submit; return; }

  // ---- live "address that will be used" line (password hidden)
  const preview = () => {
    const user = el.username.value ? encodeURIComponent(el.username.value) + (el.password.value || (edit && cam.has_password) ? ':***' : '') + '@' : '';
    $('#preview', d).textContent = `rtsp://${user}${el.host.value || '<address>'}:${el.port.value || 554}${el.path.value ? (el.path.value.startsWith('/') ? '' : '/') + el.path.value : ''}`;
  };
  ['host', 'port', 'path', 'username', 'password'].forEach((n) => el[n].addEventListener('input', preview));
  preview();

  // ---- brand / template -> stream -> path
  let chosen = null;      // the catalog stream or template currently selected
  const applyStream = () => {
    if (!chosen) return;
    el.path.value = expandPath(chosen.path, +$('#channel', d).value || 1);
    if (chosen.port) el.port.value = chosen.port;
    if (chosen.username && !el.username.value) el.username.value = chosen.username;
    if (chosen.transport) el.transport.value = chosen.transport;
    preview();
  };
  $('#brand', d).onchange = (e) => {
    const value = e.target.value, stream = $('#stream', d); chosen = null; $('#tplActions', d).hidden = true;
    $('#brandNote', d).textContent = '';
    if (value.startsWith('b')) {
      const brand = presets.brands[+value.slice(1)];
      stream.disabled = false; stream.innerHTML = '<option value="">Choose a stream...</option>' + brand.streams.map((s, i) => `<option value="${i}">${esc(s.label)}  ${esc(s.path)}</option>`).join('');
      stream.onchange = () => { chosen = stream.value === '' ? null : { ...brand.streams[+stream.value], port: brand.port, username: brand.username }; applyStream(); };
      $('#brandNote', d).textContent = brand.note || '';
      if (brand.streams.length === 1) { stream.value = '0'; stream.onchange(); }
    } else if (value.startsWith('t')) {
      const t = presets.templates.find((x) => 't' + x.id === value);
      stream.disabled = true; stream.innerHTML = `<option>${esc(t.path || '(no path)')}</option>`;
      chosen = t; applyStream(); $('#tplActions', d).hidden = false; $('#brandNote', d).textContent = t.note || '';
    } else {
      stream.disabled = true; stream.innerHTML = `<option>${value === 'custom' ? 'Type the path below' : 'Choose a brand first'}</option>`;
      if (value === 'custom') el.path.focus();
    }
  };
  $('#channel', d).oninput = applyStream;
  $('#delTpl', d).onclick = async () => {
    const id = +$('#brand', d).value.slice(1);
    await api('/camera-templates/' + id, 'DELETE'); toast('Template deleted');
    $(`#brand option[value="t${id}"]`, d).remove(); $('#brand', d).value = ''; $('#brand', d).onchange({ target: { value: '' } });
  };

  // ---- paste a full RTSP URL
  $('#pasteUrl', d).oninput = (e) => {
    const parsed = parseRtspUrl(e.target.value);
    $('#pasteNote', d).textContent = e.target.value && !parsed ? 'Not a valid rtsp:// address yet' : parsed ? 'Fields filled from the address' : '';
    if (!parsed) return;
    ['host', 'port', 'path', 'username'].forEach((n) => { el[n].value = parsed[n]; });
    if (parsed.password) el.password.value = parsed.password;
    $('#brand', d).value = 'custom'; $('#brand', d).onchange({ target: { value: 'custom' } }); preview();
  };

  // ---- test connection, auto-detect the path
  const note = (html) => { $('#testOut', d).innerHTML = html; };
  const problem = (e) => { if (!setFieldError(form, e.field, e.message)) note(`<div class="banner">${icon('alert')}<div>${esc(e.message)}</div></div>`); };
  $('#testBtn', d).onclick = async () => {
    note('<p class="muted">Connecting... up to 10 seconds.</p>');
    try { note(testResultHtml(await api('/cameras/test', 'POST', { ...values(), id: cam?.id }))); } catch (e) { note(''); problem(e); }
  };
  $('#findBtn', d).onclick = async () => {
    const button = $('#findBtn', d); button.disabled = true;
    note(`<p class="muted">Trying ${allPaths.length}+ common stream paths on ${esc(el.host.value || 'the camera')}... this can take up to 45 seconds.</p>`);
    try {
      const r = await api('/cameras/discover?channel=' + (+$('#channel', d).value || 1), 'POST', { ...values(), id: cam?.id });
      if (!r.reachable) note(`<div class="banner">${icon('alert')}<div>Cannot reach ${esc(el.host.value)}:${esc(el.port.value)}. Check the address and port, that the camera is on, and that it is on the same network as this computer.</div></div>`);
      else if (!r.found.length) note(`<div class="banner">${icon('info')}<div><b>No known path gave a picture</b> (${r.tried} tried). A wrong username or password makes every path fail, so check the login first. Otherwise look up the RTSP path in the camera manual and type it above.</div></div>`);
      else {
        note(`<div class="stack"><div class="row"><span class="pill ok">Found ${r.found.length}</span><span class="muted">Pick one to use it.</span></div>
          ${r.found.map((h) => `<div class="row"><span class="mono grow">${esc(h.path || '(no path)')}</span><span class="faint">${h.width}×${h.height}</span><button type="button" class="sm" data-use="${esc(h.path)}">Use this path</button></div>`).join('')}
          <div class="faint">Some cameras answer on several paths: usually the larger picture is the main stream, the smaller one the lighter sub stream.</div></div>`);
        $$('[data-use]', d).forEach((b) => { b.onclick = () => { el.path.value = b.dataset.use; preview(); toast('Path filled in'); }; });
      }
    } catch (e) { note(''); problem(e); } finally { button.disabled = false; }
  };
  $('#saveTpl', d).onchange = (e) => { $('#tplName', d).disabled = !e.target.checked; if (e.target.checked) $('#tplName', d).focus(); };

  form.onsubmit = submit;
  async function submit(e) {
    e.preventDefault();
    const body = values(); if (body.port === '') delete body.port;
    const template = ip && $('#saveTpl', d).checked ? $('#tplName', d).value.trim() : '';
    if (ip && $('#saveTpl', d).checked && !template) return setFieldError(form, 'tplName', '') || toast('Give the template a name', 'bad');
    try {
      const saved = await api(edit ? '/cameras/' + cam.id : '/cameras', edit ? 'PATCH' : 'POST', body);
      if (template) await api('/camera-templates', 'POST', { name: template, path: body.path || '', port: +body.port || 554, username: body.username || '', transport: body.transport || 'tcp' }).catch((err) => toast(err.message, 'bad'));
      closeDialog(); toast(edit ? 'Camera updated' : 'Camera added'); done();
      if (!edit) liveView(saved);   // show the stream straight away
    } catch (err) { if (!setFieldError(form, err.field, err.message)) toast(err.message, 'bad'); }
  }
}

// ---------------------------------------------------------------- Users (admin)
async function pageUsers(root) {
  const users = await api('/users'), minLen = state.config.min_password_length;
  root.innerHTML = pageHead('Users', 'Who can sign in. Passwords need at least ' + minLen + ' characters.', `<button class="primary" id="addUser">${icon('plus')}Add user</button>`) + `
    <div class="card"><div class="table-scroll"><table><thead><tr><th>User</th><th>Role</th><th>Status</th><th></th></tr></thead><tbody>
      ${users.map((u) => { const me = u.username === state.me.username; return `<tr>
        <td><div class="row"><span class="avatar">${esc(initials(u.username))}</span><div class="name">${esc(u.username)} ${me ? '<span class="pill plain info">you</span>' : ''}</div></div></td>
        <td><span class="pill ${u.role === 'admin' ? 'info' : ''} plain">${esc(u.role)}</span></td>
        <td><span class="pill ${u.active ? 'ok' : ''}">${u.active ? 'Active' : 'Disabled'}</span></td>
        <td class="actions"><button class="sm" data-act="pw" data-id="${u.id}">${icon('lock')}Reset password</button>
          ${me ? '' : `<select data-act="role" data-id="${u.id}" style="width:auto;padding:4px 8px">${['admin', 'viewer', 'resident'].map((r) => `<option ${r === u.role ? 'selected' : ''}>${r}</option>`).join('')}</select> <button class="sm" data-act="toggle" data-id="${u.id}">${u.active ? 'Disable' : 'Enable'}</button>`}</td></tr>`; }).join('')}
    </tbody></table></div></div>
    <p class="faint" style="margin-top:12px">Resetting a password, changing a role or disabling a user signs them out everywhere. <b>Admin</b> can change everything; <b>viewer</b> can watch the console and see masked personal data; <b>resident</b> sees only safety alerts (no names, no personal data).</p>`;
  $('#addUser').onclick = () => userDialog(() => pageUsers(root));
  root.onchange = async (e) => {
    const sel = e.target.closest('select[data-act=role]'); if (!sel) return;
    try { await api('/users/' + sel.dataset.id, 'PATCH', { role: sel.value }); toast('Role changed. They are signed out.'); } catch (err) { toast(err.message, 'bad'); pageUsers(root); }
  };
  root.onclick = async (e) => {
    const b = e.target.closest('button[data-act]'); if (!b) return;
    const u = users.find((x) => x.id == b.dataset.id);
    try {
      if (b.dataset.act === 'pw') return passwordDialog({ title: `Reset password for ${u.username}`, ask: ['password'], done: async (v) => { await api('/users/' + u.id, 'PATCH', { password: v.password }); toast('Password reset. They are signed out.'); } });
      if (b.dataset.act === 'role') await api('/users/' + u.id, 'PATCH', { role: u.role === 'admin' ? 'viewer' : 'admin' });
      if (b.dataset.act === 'toggle') await api('/users/' + u.id, 'PATCH', { active: !u.active });
      toast('Updated'); pageUsers(root);
    } catch (err) { toast(err.message, 'bad'); }
  };
}
function userDialog(done) {
  const d = openDialog(`<form id="userForm" novalidate><div class="dlg-head"><h2>Add user</h2></div><div class="dlg-body"><div class="form-grid">
    ${fieldHtml({ name: 'username', label: 'User name', placeholder: 'night.guard' })}
    <label class="field">Role<select name="role"><option value="viewer">Viewer (watch and review)</option><option value="admin">Admin (manage everything)</option><option value="resident">Resident (sees safety alerts only)</option></select><span class="field-error" data-for="role"></span></label>
    ${fieldHtml({ name: 'password', label: `Password (min ${state.config.min_password_length} characters)`, type: 'password', full: true })}</div></div>
    <div class="dlg-foot"><button type="button" data-close>Cancel</button><button class="primary">Create user</button></div></form>`, true);
  $('#userForm', d).onsubmit = async (e) => {
    e.preventDefault(); const el = e.target.elements;
    try { await api('/users', 'POST', { username: el.username.value, password: el.password.value, role: el.role.value }); closeDialog(); toast('User created'); done(); }
    catch (err) { if (!setFieldError(e.target, err.field, err.message)) toast(err.message, 'bad'); }
  };
}
// One dialog for "change my password" (asks the current one too) and "reset someone's password".
function passwordDialog({ title, ask, done }) {
  const d = openDialog(`<form id="pwForm" novalidate><div class="dlg-head"><h2>${esc(title)}</h2></div><div class="dlg-body">
    ${ask.includes('current') ? fieldHtml({ name: 'current', label: 'Current password', type: 'password' }) : ''}
    ${fieldHtml({ name: ask.includes('current') ? 'new' : 'password', label: `New password (min ${state.config.min_password_length} characters)`, type: 'password' })}</div>
    <div class="dlg-foot"><button type="button" data-close>Cancel</button><button class="primary">Save password</button></div></form>`, true);
  $('#pwForm', d).onsubmit = async (e) => {
    e.preventDefault(); const el = e.target.elements;
    try { await done({ current: el.current?.value, new: el.new?.value, password: el.password?.value }); closeDialog(); }
    catch (err) { if (!setFieldError(e.target, err.field, err.message)) toast(err.message, 'bad'); }
  };
}
const changeOwnPassword = () => passwordDialog({ title: 'Change your password', ask: ['current', 'new'],
  done: async (v) => { await api('/me/password', 'POST', { current: v.current, new: v.new }); toast('Password changed. Other devices are signed out.'); } });

// ---------------------------------------------------------------- Audit
async function pageAudit(root) {
  const entries = await api('/audit?limit=300');
  const kind = (a) => /failed|deleted|blocked/.test(a) ? 'bad' : /created|added|login$/.test(a) ? 'ok' : 'info';
  root.innerHTML = pageHead('Audit log', 'Who did what, and when. Newest first. Every line is chained to the one before it, so edits are detectable.',
    `<button id="verify">${icon('shield')}Verify integrity</button>`) + `<div id="verifyOut"></div><div class="card"><div class="table-scroll"><table>
    <thead><tr><th>Time</th><th>User</th><th>Action</th><th>Details</th></tr></thead><tbody>
    ${entries.map((a) => `<tr><td class="muted" style="white-space:nowrap">${esc(fmtDateTime(a.ts))}</td><td>${esc(a.username)}</td>
      <td><span class="pill ${kind(a.action)}">${esc(a.action.replace(/_/g, ' '))}</span></td>
      <td class="muted mono">${esc(JSON.stringify(a.detail) === '{}' ? '' : JSON.stringify(a.detail))}</td></tr>`).join('')}
    </tbody></table></div></div>`;
  $('#verify').onclick = async () => {
    const r = await api('/audit/verify');
    $('#verifyOut').innerHTML = r.ok
      ? `<div class="banner" style="margin-bottom:14px">${icon('check')}<div><b>Audit log is intact.</b> ${r.checked} chained line(s) verified${r.legacy ? `; ${r.legacy} older line(s) pre-date the chain and cannot be verified` : ''}.</div></div>`
      : `<div class="banner" style="margin-bottom:14px;background:var(--bad-soft)">${icon('alert')}<div><b>Audit log was changed.</b> The chain breaks at line #${r.broken_at}. Treat everything from that line on as untrusted.</div></div>`;
  };
}

// =============================================================================== 5. security console (/tf-check)
function beep() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)(), o = ctx.createOscillator(), g = ctx.createGain();
    o.type = 'square'; o.connect(g); g.connect(ctx.destination); g.gain.value = 0.06;
    o.frequency.setValueAtTime(880, ctx.currentTime); o.frequency.setValueAtTime(660, ctx.currentTime + 0.15);
    o.start(); o.stop(ctx.currentTime + 0.32); setTimeout(() => ctx.close(), 500);
  } catch { /* audio blocked */ }
}

async function renderConsole() {
  const admin = state.me.role === 'admin';
  const f = { decision: '', q: '', range: 'today', unreviewed: false, offset: 0, limit: 25 };
  let cams = []; try { cams = await api('/cameras'); } catch (e) { if (e.silent) return; }
  let scanning = false, sound = storage('sound') === '1', lastFace = 0, frames = 0, fpsStart = performance.now();

  $('#app').innerHTML = `
    <div class="console">
      <div class="console-bar">
        <a class="btn ghost sm" href="/#people" title="Back to admin">${icon('arrowLeft')}Admin</a>
        <div class="title">Security check console<small>${esc(state.config.customer)}</small></div>
        <span class="grow"></span>
        <select id="source" title="Camera source">${cams.filter((c) => c.enabled).map((c) => `<option value="${esc(c.id)}">${esc(c.name)}${c.kind === 'rtsp' ? ' (IP camera)' : ''}</option>`).join('')}</select>
        <select id="device" title="Which webcam"></select>
        <span class="clock" id="clock"></span>
        <button class="sm" id="soundBtn" title="Sound alert for unknown people"></button>
        <button class="sm" id="fsBtn" title="Full screen">${icon('expand')}</button>
        <button class="sm" data-theme-toggle title="Theme"></button>
        <button class="primary sm" id="scanBtn"></button>
      </div>
      <div class="console-main">
        <div class="kpis">
          <div class="kpi brand"><div class="label">Scanned today</div><div class="value" id="k-total">0</div></div>
          <div class="kpi ok"><div class="label">Access granted</div><div class="value" id="k-granted">0</div></div>
          <div class="kpi bad"><div class="label">Access denied</div><div class="value" id="k-denied">0</div></div>
          <div class="kpi warn"><div class="label">Unknown faces</div><div class="value" id="k-unknown">0</div></div>
          <div class="kpi"><div class="label">Needs review</div><div class="value" id="k-pending">0</div></div>
        </div>
        <div class="live-grid">
          <section class="stack">
            ${stageHtml({ hud: `<div class="hud tl"><span class="chip off" id="liveChip">Stopped</span></div><div class="hud tr"><span class="chip" id="perfChip">-</span></div>` })}
            <div class="verdict" id="verdict"><span class="badge">${icon('scan')}</span><div><div class="headline">Ready</div><div class="muted">Press Start scanning</div></div></div>
          </section>
          <section class="card"><header><h2>Recent detections</h2><span class="grow"></span><span class="faint" id="recentCount"></span></header>
            <div class="recent" id="recent"><div class="empty">${icon('users')}<span>No one scanned yet</span></div></div></section>
        </div>
        <section class="card"><header><h2>Scan log</h2><span class="grow"></span>${admin ? `<a class="btn sm" id="export" href="#">${icon('download')}Export CSV</a>` : ''}</header>
          <div class="toolbar">
            <div class="seg" id="decisionSeg">${[['', 'All'], ['granted', 'Granted'], ['denied', 'Denied'], ['unknown', 'Unknown']].map(([v, l]) => `<button data-v="${v}" class="${v === '' ? 'on' : ''}">${l}</button>`).join('')}</div>
            <select id="range"><option value="hour">Last hour</option><option value="today" selected>Today</option><option value="7d">Last 7 days</option><option value="all">All time</option></select>
            <input type="search" id="q" placeholder="Search name, ID, unit or phone">
            <label class="row" style="gap:6px"><input type="checkbox" id="unrev"> Unreviewed only</label>
          </div>
          <div class="table-scroll"><table><thead><tr><th>Time</th><th>Person</th><th>Result</th><th>Access</th><th>Score</th><th>Camera</th><th>Review</th></tr></thead><tbody id="log"></tbody></table></div>
          <div class="pager"><span id="pageInfo" class="grow"></span><button class="sm" id="prev">Previous</button><button class="sm" id="next">Next</button></div></section>
      </div>
    </div>`;
  renderThemeButtons();
  const wanted = new URLSearchParams(location.search).get('camera'); if (wanted && cams.some((c) => c.id === wanted && c.enabled)) $('#source').value = wanted;
  const stage = $('.stage'), video = $('video', stage);
  const sinceFor = () => { const n = new Date(); return { hour: Date.now() / 1000 - 3600, today: new Date(n.getFullYear(), n.getMonth(), n.getDate()).getTime() / 1000, '7d': Date.now() / 1000 - 7 * 86400, all: null }[f.range]; };
  const camName = (id) => cams.find((c) => c.id === id)?.name || id;

  // ---- top bar
  const tick = () => { const n = new Date(); $('#clock').textContent = `${n.toLocaleDateString([], { weekday: 'short', day: '2-digit', month: 'short' })}  ${pad(n.getHours())}:${pad(n.getMinutes())}:${pad(n.getSeconds())}`; };
  tick(); const clock = setInterval(tick, 1000);
  const drawSound = () => { $('#soundBtn').innerHTML = icon(sound ? 'volume' : 'volumeOff') + (sound ? 'Sound on' : 'Sound off'); };
  drawSound(); $('#soundBtn').onclick = () => { sound = !sound; storage('sound', sound ? '1' : '0'); drawSound(); if (sound) beep(); };
  $('#fsBtn').onclick = () => (document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen());
  $('[data-theme-toggle]').onclick = toggleTheme;
  const drawScanBtn = () => { $('#scanBtn').innerHTML = scanning ? icon('pause') + 'Stop scanning' : icon('play') + 'Start scanning'; $('#scanBtn').classList.toggle('danger', scanning); $('#scanBtn').classList.toggle('solid', scanning); };
  drawScanBtn();

  // ---- verdict banner
  let verdictHold = 0;
  function setVerdict(kind, headline, sub, ic) {
    const v = $('#verdict'); v.className = `verdict ${kind}`;
    v.innerHTML = `<span class="badge">${icon(ic)}</span><div><div class="headline">${esc(headline)}</div><div class="muted">${esc(sub)}</div></div>`;
  }
  function showVerdict(results) {
    const faces = results.filter((r) => r.bbox);
    if (!faces.length) { if (Date.now() - verdictHold > 1500) setVerdict('', scanning ? 'Scanning...' : 'Ready', scanning ? 'No face in view' : 'Press Start scanning', 'scan'); return; }
    verdictHold = Date.now();
    const main = faces.reduce((a, b) => (b.bbox[2] * b.bbox[3] > a.bbox[2] * a.bbox[3] ? b : a));
    const more = faces.length > 1 ? ` · +${faces.length - 1} other face${faces.length > 2 ? 's' : ''}` : '';
    const who = [main.code, main.unit ? `${unitLabel()} ${main.unit}` : '', typeById(main.person_type).label].filter(Boolean).join(' · ');
    if (main.decision === 'resident' && main.alert) {
      setVerdict('bad alarm', `${main.alert.level.toUpperCase()} ALERT: ${main.person}`, [typeById(main.person_type).label, main.watch?.reason, main.watch?.instructions,
        main.alert.confidence === 'possible' ? 'POSSIBLE match: verify identity first' : ''].filter(Boolean).join(' · ') + more, 'alert');
    } else if (main.decision === 'resident' && main.access.granted) setVerdict('ok', `Access granted: ${main.person}`, `${who} · match ${main.score}${more}`, 'check');
    else if (main.decision === 'resident') setVerdict('bad', `${main.access.alert ? 'ALERT, ' : ''}Access denied: ${main.person}`, `${main.access.reason} · ${who}${more}`, 'x');
    else if (main.decision === 'uncertain') setVerdict('warn', 'Uncertain match', `Verify identity manually · score ${main.score}${more}`, 'alert');
    else setVerdict('bad', 'Unknown person', `Not registered in the system · score ${main.score}${more}`, 'x');
  }

  // ---- recent detections (from live scan results)
  const recentItems = [];
  function addRecent(r) {
    recentItems.unshift({ ...r, at: Date.now() / 1000 }); recentItems.splice(12);
    $('#recent').innerHTML = recentItems.map((e, i) => {
      const granted = e.access?.granted;
      return `<div class="item ${i === 0 ? 'fresh' : ''}">
      ${!granted ? `<img class="snap" src="/api/events/${e.event_id}/snapshot" alt="" data-initials="${esc(initials(e.person || '?'))}">` : `<span class="avatar">${esc(initials(e.person))}</span>`}
      <div><div class="name">${esc(e.person || (e.decision === 'unknown' ? 'Unknown person' : 'Uncertain match'))}</div>
        <div class="sub">${esc([e.code, e.unit ? `${unitLabel()} ${e.unit}` : '', granted ? '' : e.access?.reason].filter(Boolean).join(' · ')) || 'Score ' + e.score}</div></div>
      <div class="when"><span class="pill ${resultKind(e)}">${granted ? 'Granted' : 'Denied'}</span><div>${esc(ago(e.at))}</div></div></div>`;
    }).join('');
    $('#recentCount').textContent = `${recentItems.length} latest`;
  }

  // ---- stats and log table
  async function loadStats() {
    try {
      const s = await api('/events/stats');
      ['total', 'granted', 'denied', 'unknown'].forEach((k) => { $('#k-' + k).textContent = s[k]; }); $('#k-pending').textContent = s.pending_review;
    } catch { /* ignore, next poll retries */ }
  }
  const queryString = () => {
    const p = new URLSearchParams(); const since = sinceFor();
    if (since) p.set('since', since); if (f.decision === 'unknown') p.set('decision', 'unknown'); if (f.decision === 'granted' || f.decision === 'denied') p.set('access_result', f.decision); if (f.q) p.set('q', f.q); if (f.unreviewed) p.set('reviewed', 'false');
    return p;
  };
  let freshId = 0;
  async function loadLog() {
    try {
      const p = queryString(); p.set('limit', f.limit); p.set('offset', f.offset);
      const { events, total } = await api('/events?' + p);
      $('#log').innerHTML = events.map((e) => `<tr class="click ${e.id === freshId ? 'fresh' : ''}" data-id="${e.id}">
        <td class="muted" style="white-space:nowrap">${esc(fmtDateTime(e.ts))}</td>
        <td><div class="row">${e.has_snapshot ? `<img class="snap" src="/api/events/${e.id}/snapshot" alt="" data-initials="${esc(initials(e.person || '?'))}">` : `<span class="avatar">${esc(initials(e.person || '?'))}</span>`}
          <div><div class="name">${esc(e.person || (e.decision === 'resident' ? 'Removed person' : 'Unknown'))}</div>
            <div class="sub">${esc([e.code, e.unit ? `${unitLabel()} ${e.unit}` : ''].filter(Boolean).join(' · ')) || '&nbsp;'}</div></div></div></td>
        <td><span class="pill ${kindOf(e.decision)}">${esc(e.decision)}</span></td>
        <td>${accessPill(e)}${e.reason ? `<div class="sub">${esc(e.reason)}</div>` : ''}</td>
        <td class="mono">${e.score}</td><td class="muted">${esc(camName(e.camera_id))}</td>
        <td>${e.decision === 'resident' && e.access !== 'denied' ? '<span class="faint">-</span>' : `<span class="pill ${e.reviewed ? 'ok' : 'warn'}">${e.reviewed ? 'Reviewed' : 'Pending'}</span>`}</td></tr>`).join('')
        || `<tr><td colspan="7"><div class="empty">${icon('clipboard')}<b>No scans match</b><span>Start scanning, or widen the filters.</span></div></td></tr>`;
      $('#pageInfo').textContent = total ? `${f.offset + 1}-${Math.min(f.offset + f.limit, total)} of ${total}` : '0 results';
      $('#prev').disabled = f.offset === 0; $('#next').disabled = f.offset + f.limit >= total;
      if (admin) $('#export').href = '/api/events/export.csv?' + queryString();
      return events;
    } catch { /* ignore */ }
  }
  const refresh = () => { loadStats(); return loadLog(); };

  $('#decisionSeg').onclick = (e) => { const b = e.target.closest('button'); if (!b) return; $$('#decisionSeg button').forEach((x) => x.classList.toggle('on', x === b)); f.decision = b.dataset.v; f.offset = 0; loadLog(); };
  $('#range').onchange = (e) => { f.range = e.target.value; f.offset = 0; loadLog(); };
  $('#unrev').onchange = (e) => { f.unreviewed = e.target.checked; f.offset = 0; loadLog(); };
  let typing; $('#q').oninput = (e) => { clearTimeout(typing); typing = setTimeout(() => { f.q = e.target.value.trim(); f.offset = 0; loadLog(); }, 250); };
  $('#prev').onclick = () => { f.offset = Math.max(0, f.offset - f.limit); loadLog(); };
  $('#next').onclick = () => { f.offset += f.limit; loadLog(); };
  $('#log').onclick = (e) => { const tr = e.target.closest('tr[data-id]'); if (tr) eventDialog(+tr.dataset.id); };

  async function eventDialog(id) {
    let e; try { e = await api('/events/' + id); } catch (err) { return toast(err.message, 'bad'); }
    const needsReview = e.decision !== 'resident' || e.access === 'denied';
    const row = (k, v) => `<dt class="faint">${esc(k)}</dt><dd style="margin:0">${v}</dd>`;
    const d = openDialog(`<div class="dlg-head"><h2>Scan #${e.id}</h2><span class="pill ${kindOf(e.decision)}">${esc(e.decision)}</span>${accessPill(e)}</div>
      <div class="dlg-body"><div class="detail">${e.has_snapshot ? `<img src="/api/events/${e.id}/snapshot" alt="Snapshot">` : `<div class="avatar" style="width:100%;height:auto;aspect-ratio:1;border-radius:12px;font-size:40px">${esc(initials(e.person || '?'))}</div>`}
        <dl style="margin:0;display:grid;grid-template-columns:auto 1fr;gap:8px 16px">
          ${row('Time', esc(new Date(e.ts * 1000).toLocaleString()))}
          ${row('Person', esc(e.person || (e.decision === 'resident' ? 'Removed person' : 'Unknown')))}
          ${e.code ? row('ID', `<span class="mono">${esc(e.code)}</span>`) : ''}${e.unit ? row(unitLabel(), esc(e.unit)) : ''}
          ${row('Access', e.access ? `${e.access === 'granted' ? 'Granted' : 'Denied'}${e.reason ? ': ' + esc(e.reason) : ''}` : '-')}
          ${row('Match score', `<span class="mono">${e.score}</span>`)}${row('Camera', esc(camName(e.camera_id)))}
          ${row('Review', needsReview ? (e.reviewed ? 'Reviewed' : 'Pending') : 'Not needed')}</dl></div></div>
      <div class="dlg-foot"><button data-close>Close</button>
        ${needsReview ? `<button id="rev">${e.reviewed ? 'Mark as pending' : 'Mark as reviewed'}</button>` : ''}
        ${admin && e.has_snapshot && e.decision !== 'resident' ? `<button class="primary" id="enroll">${icon('userPlus')}Register this person</button>` : ''}</div>`);
    if ($('#rev', d)) $('#rev', d).onclick = async () => { await api('/events/' + e.id, 'PATCH', { reviewed: !e.reviewed }); closeDialog(); toast('Updated'); refresh(); };
    if ($('#enroll', d)) $('#enroll', d).onclick = () => enrollDialog(e);
  }
  async function enrollDialog(e) {
    const units = await knownUnits();
    const d = openDialog(`<form id="enrollForm" novalidate><div class="dlg-head"><h2>Register this person</h2></div>
      <div class="dlg-body"><div class="detail"><img src="/api/events/${e.id}/snapshot" alt=""><div class="faint">The snapshot from this scan is used as their photo. Fill in the details below.</div></div>
        ${profileFormHtml({}, units)}
        <label class="row" style="align-items:flex-start;gap:10px"><input type="checkbox" name="consent" style="margin-top:3px"><span class="muted" style="font-size:13px" id="consentText">${esc(state.config.consent_text)}</span></label><span class="field-error" data-for="consent"></span></div>
      <div class="dlg-foot"><button type="button" data-close>Cancel</button><button class="primary">Register</button></div></form>`, false, true);
    const form = $('#enrollForm', d); wireProfileForm(form);
    form.onsubmit = async (ev) => {
      ev.preventDefault();
      try { const p = await api(`/events/${e.id}/enroll`, 'POST', { ...readProfile(form), consent: form.elements.consent.checked }); closeDialog(); toast(`${p.name} registered. ID ${p.code}`); refresh(); }
      catch (err) { showProfileError(form, err); }
    };
  }
  if (admin) $('#export').onclick = async (e) => { e.preventDefault(); try { await downloadCsv(queryString().toString()); } catch (err) { if (!err.cancelled) toast(err.message, 'bad'); } };

  // ---- the realtime loop: one camera picture -> /api/scan -> draw -> repeat
  const chip = (id, text, cls) => { const c = $(id); c.textContent = text; if (cls) c.className = 'chip ' + cls; };
  async function scanLoop() {
    while (scanning) {
      if (!video.videoWidth) { await sleep(250); continue; }
      const t0 = performance.now();
      try {
        const frame = camera.snapshot(video, state.config.scan_width, 0.8);
        const results = await api('/scan', 'POST', { image: frame.data, camera_id: $('#source').value });
        if (!scanning) break;
        drawBoxes(stage, results.filter((r) => r.bbox).map((r) => ({ bbox: r.bbox, kind: resultKind(r), label: r.person || r.decision })), 1 / frame.scale);
        showVerdict(results);
        const logged = results.filter((r) => r.event_id);
        if (logged.length) {
          logged.forEach(addRecent); freshId = Math.max(...logged.map((r) => r.event_id));
          if (sound && logged.some((r) => r.decision !== 'resident')) beep();
          if (f.offset === 0) refresh(); else loadStats();
        }
        frames++; const now = performance.now();
        if (now - fpsStart > 1000) { chip('#perfChip', `${(frames * 1000 / (now - fpsStart)).toFixed(1)} fps · ${Math.round(now - t0)} ms`); frames = 0; fpsStart = now; }
      } catch (err) { if (err.silent) return; chip('#perfChip', 'Connection problem'); await sleep(1000); }
      await sleep(Math.max(0, 120 - (performance.now() - t0)));
    }
  }
  // ---- IP camera: the server reads the RTSP stream and scans it; we show its picture and poll its results
  const selectedCam = () => cams.find((c) => c.id === $('#source').value);
  let ipSeq = 0;
  function showIpView(cam) {
    video.style.display = 'none'; $('canvas', stage).style.display = 'none'; $('#device').style.display = 'none'; $('.camera-error', stage)?.remove();
    $('.ipimg', stage)?.remove();
    const img = document.createElement('img'); img.className = 'ipimg'; img.alt = 'Live view'; img.src = `/api/cameras/${cam.id}/stream?ts=${Date.now()}`;
    stage.prepend(img);
  }
  function showBrowserView() {
    $('.ipimg', stage)?.remove(); video.style.display = ''; $('canvas', stage).style.display = ''; $('#device').style.display = '';
  }
  async function ipLoop(cam) {
    while (scanning) {
      try {
        const s = await api(`/cameras/${cam.id}/status?since=${ipSeq}`);
        if (!scanning) break;
        ipSeq = s.seq;
        const live = s.state === 'live';
        chip('#liveChip', live ? 'LIVE' : s.state === 'reconnecting' ? 'Reconnecting' : 'Connecting', live ? 'live' : 'off');
        chip('#perfChip', live ? `${s.fps} fps${s.size ? ' · ' + s.size[0] + '×' + s.size[1] : ''}` : s.error || '-');
        if (live) showVerdict(s.results);
        else setVerdict('warn', s.state === 'reconnecting' ? 'Reconnecting...' : 'Connecting...', s.error || 'Opening the camera stream', 'wifi');
        if (s.events.length) {
          s.events.forEach(addRecent); freshId = Math.max(...s.events.map((r) => r.event_id));
          if (sound && s.events.some((r) => r.decision !== 'resident')) beep();
          if (f.offset === 0) refresh(); else loadStats();
        }
      } catch (err) { if (err.silent) return; chip('#perfChip', 'Connection problem'); }
      await sleep(500);
    }
  }

  async function startScan() {
    if (scanning) return;
    const cam = selectedCam();
    if (cam?.kind === 'rtsp') { ipSeq = 0; scanning = true; showIpView(cam); drawScanBtn(); chip('#liveChip', 'Connecting', 'off'); ipLoop(cam); return; }
    showBrowserView();
    const ok = await startCamera(stage, $('#device'));
    if (!ok) return;
    scanning = true; drawScanBtn(); chip('#liveChip', 'LIVE', 'live'); scanLoop();
  }
  function stopScan() {
    scanning = false; camera.stop(); drawScanBtn(); chip('#liveChip', 'Stopped', 'off'); chip('#perfChip', '-');
    showBrowserView(); drawBoxes(stage, []); setVerdict('', 'Stopped', 'Press Start scanning', 'pause');
  }
  $('#scanBtn').onclick = () => (scanning ? stopScan() : startScan());
  $('#source').onchange = () => { if (scanning) stopScan(); startScan(); };

  const poll = setInterval(() => { if (!document.hidden) { loadStats(); if (f.offset === 0 && !$('#dialog').open) loadLog(); } }, 4000);
  cleanup = () => { scanning = false; clearInterval(clock); clearInterval(poll); camera.stop(); $('.ipimg')?.remove(); };
  await refresh();
  startScan();   // starts at once: with the laptop camera, or the camera chosen in the link (?camera=ID)
}

// =============================================================================== step-up confirmation (banking style)
// A risky request is answered with STEP_UP_REQUIRED. api() then opens "Confirm it's you" (face, PIN or password),
// gets a one-time token and repeats the request with it. Settings has the switches for face and PIN.
const METHOD_LABEL = { face: 'Face', pin: 'PIN', password: 'Password' };
const keypadHtml = () => `<div class="pinpad">${[1, 2, 3, 4, 5, 6, 7, 8, 9, '', 0, '⌫'].map((k) => (k === '' ? '<span></span>' : `<button type="button" data-k="${k}" aria-label="${k === '⌫' ? 'Delete' : k}">${k}</button>`)).join('')}</div>`;

// A PIN entry: dots + keypad (the number keys of the keyboard work too). Calls onComplete(pin) when full.
function pinWidget(root, length, onComplete) {
  let value = '', busy = false;
  const dots = $('.pin-dots', root);
  const draw = () => { dots.innerHTML = Array.from({ length }, (_, i) => `<span class="${i < value.length ? 'on' : ''}"></span>`).join(''); };
  const press = (k) => {
    if (busy) return;
    if (k === '⌫') value = value.slice(0, -1); else if (/^\d$/.test(k) && value.length < length) value += k;
    draw();
    if (value.length === length) { busy = true; onComplete(value); }
  };
  $('.pinpad', root).onclick = (e) => { const b = e.target.closest('button[data-k]'); if (b) press(b.dataset.k); };
  $('#dialog').onkeydown = (e) => { if (/^\d$/.test(e.key) || e.key === 'Backspace') { e.preventDefault(); press(e.key === 'Backspace' ? '⌫' : e.key); } };
  draw();
  return { reset() { value = ''; busy = false; draw(); }, shake() { dots.classList.remove('shake'); void dots.offsetWidth; dots.classList.add('shake'); setTimeout(() => this.reset(), 400); } };
}

// Live face check used by "confirm" and by enrolment. Phase 1: look straight. Phase 2 (optional): turn the head.
// Resolves with [straightPhoto, turnedPhoto?] (data URLs) or null when stopped.
async function captureLiveFace(stage, { headTurn, setHint, alive, qualityPath = '/quality' }) {
  const video = $('video', stage);
  const turnAt = (state.config.head_turn_min_yaw || 0.2) + 0.03;        // a small, natural turn is enough
  let phase = 1, streak = 0, straight = null;
  setHint('Look straight at the camera');
  while (alive()) {
    if (!video.videoWidth) { await sleep(250); continue; }
    const small = camera.snapshot(video, 640, 0.8);
    let q; try { q = await api(qualityPath, 'POST', { image: small.data }); } catch (e) { if (e.silent) return null; await sleep(500); continue; }
    if (!alive()) return null;
    drawBoxes(stage, q.bbox ? [{ bbox: q.bbox, kind: 'ok' }] : [], 1 / small.scale);
    $('.guide', stage)?.classList.toggle('good', phase === 1 ? q.ok && q.yaw <= 0.15 : !!q.bbox && q.yaw >= turnAt);
    if (phase === 1) {
      if (q.ok && q.yaw <= 0.15) {
        setHint('Hold still...');
        if (++streak >= 2) {
          straight = camera.snapshot(video, 800, 0.9).data;
          if (!headTurn) return [straight];
          phase = 2; streak = 0; showTurnCue(stage, true); setHint('Now turn your head a little to the LEFT or to the RIGHT. Either way works.'); await sleep(400);
        }
      } else { streak = 0; setHint(q.ok ? 'Look straight at the camera' : q.message); }
    } else if (q.bbox && q.yaw >= turnAt) {
      showTurnCue(stage, true, 1);
      if (++streak >= 2) { showTurnCue(stage, false); return [straight, camera.snapshot(video, 800, 0.9).data]; }
    } else {
      streak = 0;
      const progress = q.bbox ? Math.max(0, Math.min(1, q.yaw / turnAt)) : 0;
      showTurnCue(stage, true, progress);
      setHint(q.bbox ? (progress < 0.25 ? 'Slowly turn your head to the LEFT or the RIGHT (either way). Keep looking at the screen.' : `Good, keep turning (${Math.round(progress * 100)}%). Stop when the bar is full.`)
        : 'Your face left the picture. Turn back a little so the camera still sees your face.');
    }
    await sleep(300);
  }
  showTurnCue(stage, false);
  return null;
}

// The arrows and the progress bar that show the person how to turn their head.
function showTurnCue(stage, on, progress = 0) {
  const cue = $('.turn-cue', stage), meter = $('.turn-meter', stage);
  if (!cue || !meter) return;
  cue.hidden = meter.hidden = !on;
  if (on) $('.bar-fill', meter).style.width = Math.round(progress * 100) + '%';
}

// "Confirm it's you". Resolves with a one-time token, or null if the person cancels.
function confirmRisk(info) {
  return new Promise((resolve) => {
    const methods = info.methods;
    let method = methods.includes(info.preferred) ? info.preferred : methods[0], finished = false, stop = () => {};
    const end = (token) => { if (finished) return; finished = true; stop(); camera.stop(); closeDialog(); resolve(token); };
    const d = openDialog(`<div class="dlg-head"><h2>Confirm it's you</h2></div>
      <div class="dlg-body" style="justify-items:center;text-align:center"><div><div class="lock-badge">${icon('lock')}</div><p style="margin-top:10px;font-weight:600">${esc(info.label)}</p><p class="faint">This is a protected action.</p></div>
        ${methods.length > 1 ? `<div class="seg" id="methodSeg">${methods.map((m) => `<button type="button" data-m="${m}">${METHOD_LABEL[m]}</button>`).join('')}</div>` : ''}
        <div id="methodBody" style="width:100%"></div><div id="methodMsg" class="field-error" style="min-height:18px;font-size:13px"></div></div>
      <div class="dlg-foot"><button type="button" id="cancelConfirm">Cancel</button></div>`, true);
    dialogCleanup = () => { stop(); camera.stop(); $('#dialog').onkeydown = null; if (!finished) { finished = true; resolve(null); } };
    $('#cancelConfirm', d).onclick = () => closeDialog();
    const msg = (t) => { $('#methodMsg', d).textContent = t || ''; };
    const send = async (path, payload, onFail) => {
      try { end((await api(path, 'POST', { action: info.action, ...payload })).token); } catch (e) { msg(e.message); onFail?.(e); }
    };
    const bodies = {
      pin() {
        $('#methodBody', d).innerHTML = `<p class="muted">Enter your ${info.pin_length}-digit PIN</p><div class="pin-dots"></div>${keypadHtml()}`;
        const w = pinWidget(d, info.pin_length, (pin) => send('/step-up/pin', { pin }, () => w.shake()));
      },
      password() {
        $('#methodBody', d).innerHTML = `<form id="pwConfirm" novalidate>${fieldHtml({ name: 'password', label: 'Your password', type: 'password' })}<button class="primary" style="width:100%;margin-top:12px">Confirm</button></form>`;
        $('#pwConfirm input', d).focus();
        $('#pwConfirm', d).onsubmit = (e) => { e.preventDefault(); send('/step-up/password', { password: e.target.elements.password.value }); };
      },
      face() {
        $('#methodBody', d).innerHTML = `${stageHtml({ guide: true })}<div class="hint-box" id="faceHint" style="margin-top:10px">${icon('info')}<span>Starting camera...</span></div>`;
        const stage = $('.stage', d); let live = true; stop = () => { live = false; };
        const hint = (t, kind = '') => { $('#faceHint', d).className = `hint-box ${kind}`; $('#faceHint', d).innerHTML = `${icon(kind === 'warn' ? 'alert' : kind === 'good' ? 'check' : 'info')}<span>${esc(t)}</span>`; };
        (async () => {
          if (!(await startCamera(stage, null))) { hint('Camera not available. Use another method.', 'warn'); return; }
          while (live && !finished) {
            const photos = await captureLiveFace(stage, { headTurn: info.head_turn, setHint: (t) => hint(t), alive: () => live && !finished });
            if (!photos) return;
            hint('Checking...');
            try { end((await api('/step-up/face', 'POST', { action: info.action, images: photos })).token); return; }
            catch (e) { hint(e.message, 'warn'); await sleep(2000); }
          }
        })();
      },
    };
    const show = (m) => { method = m; stop(); camera.stop(); stop = () => {}; msg(''); $('#dialog').onkeydown = null; $$('#methodSeg button', d).forEach((b) => b.classList.toggle('on', b.dataset.m === m)); bodies[m](); };
    $$('#methodSeg button', d).forEach((b) => { b.onclick = () => show(b.dataset.m); });
    show(method);
  });
}

// ask for the account password (turning a security method off, changing a PIN...)
function askPassword(title, text) {
  return new Promise((resolve) => {
    let done = false;
    const d = openDialog(`<form id="askPw" novalidate><div class="dlg-head"><h2>${esc(title)}</h2></div><div class="dlg-body"><p class="muted">${esc(text)}</p>${fieldHtml({ name: 'password', label: 'Your password', type: 'password' })}</div>
      <div class="dlg-foot"><button type="button" data-close>Cancel</button><button class="primary">Continue</button></div></form>`, true);
    dialogCleanup = () => { if (!done) { done = true; resolve(null); } };
    $('input', d).focus();
    $('#askPw', d).onsubmit = (e) => { e.preventDefault(); done = true; const v = e.target.elements.password.value; closeDialog(); resolve(v); };
  });
}

// ---- PIN setup: new PIN, repeat it, then the password
function pinSetupDialog(length, done) {
  let first = '', stage = 'new';
  const d = openDialog(`<div class="dlg-head"><h2>Set up your PIN</h2></div><div class="dlg-body" style="justify-items:center;text-align:center">
    <div class="lock-badge">${icon('lock')}</div><p id="pinTitle" class="muted">Choose a ${length}-digit PIN</p><div class="pin-dots"></div>${keypadHtml()}<div id="pinMsg" class="field-error" style="min-height:18px"></div></div>
    <div class="dlg-foot"><button type="button" data-close>Cancel</button></div>`, true);
  dialogCleanup = () => { $('#dialog').onkeydown = null; };
  const w = pinWidget(d, length, async (pin) => {
    if (stage === 'new') { first = pin; stage = 'again'; $('#pinTitle', d).textContent = 'Enter the PIN again to confirm'; $('#pinMsg', d).textContent = ''; w.reset(); return; }
    if (pin !== first) { stage = 'new'; $('#pinTitle', d).textContent = `The PINs did not match. Choose a ${length}-digit PIN`; w.shake(); return; }
    const password = await askPassword('Confirm with your password', 'Setting a PIN needs your password.');
    if (password === null) return;
    try { await api('/me/security/pin', 'POST', { pin, current_password: password }); toast('PIN is on'); done(); }
    catch (e) { toast(e.message, 'bad'); if (e.code === 'WEAK_PIN') pinSetupDialog(length, done); }
  });
}

// ---- face setup: three good photos, then the password
async function faceEnrolDialog(done) {
  const photos = [];
  const d = openDialog(`<div class="dlg-head"><h2>Set up face authentication</h2></div><div class="dlg-body">
    ${stageHtml({ guide: true })}<div class="hint-box" id="enHint">${icon('info')}<span>Starting camera...</span></div><div class="slots" id="enSlots"></div>
    <div class="row wrap"><label class="row" style="gap:6px"><input type="checkbox" id="enAuto"> Auto-capture</label><span class="grow"></span><button type="button" id="enShot">${icon('scan')}Capture photo</button></div>
    <p class="faint">Take three photos looking at the camera, moving your head very slightly between them. Your face is stored only as numbers on this computer.</p>
    <p class="faint">Once on, you can sign in with your face from the login screen and confirm risky actions with it. Your password always still works. You can switch it off in Settings.</p></div>
    <div class="dlg-foot"><button type="button" data-close>Cancel</button><button class="primary" id="enSave" disabled>Turn on face authentication</button></div>`);
  let live = true; dialogCleanup = () => { live = false; camera.stop(); };
  const stage = $('.stage', d), video = $('video', stage);
  const drawSlots = () => { $('#enSlots', d).innerHTML = [0, 1, 2].map((i) => (photos[i] ? `<div class="slot filled"><img src="${photos[i]}" alt=""></div>` : `<div class="slot ${i === photos.length ? 'next' : ''}">${i + 1}</div>`)).join(''); };
  const hint = (t, kind = '') => { $('#enHint', d).className = `hint-box ${kind}`; $('#enHint', d).innerHTML = `${icon(kind === 'good' ? 'check' : kind === 'warn' ? 'alert' : 'info')}<span>${esc(t)}</span>`; };
  drawSlots();
  if (!(await startCamera(stage, null))) { hint('Camera not available', 'warn'); return; }
  let streak = 0, wantShot = false;
  $('#enShot', d).onclick = () => { wantShot = true; };
  const takePhoto = async () => { photos.push(camera.snapshot(video, 0, 0.92).data); drawSlots(); streak = 0; wantShot = false; const f = $('.flash', stage); f.classList.remove('go'); void f.offsetWidth; f.classList.add('go'); await sleep(900); };
  while (live && photos.length < 3) {
    if (!video.videoWidth) { await sleep(250); continue; }
    const small = camera.snapshot(video, 640, 0.8);
    let q; try { q = await api('/quality', 'POST', { image: small.data }); } catch (e) { if (e.silent) return; await sleep(500); continue; }
    if (!live) return;
    drawBoxes(stage, q.bbox ? [{ bbox: q.bbox, kind: q.ok ? 'ok' : 'warn' }] : [], 1 / small.scale);
    $('.guide', stage)?.classList.toggle('good', q.ok);
    const auto = $('#enAuto', d).checked;
    if (q.ok) {
      if (wantShot) await takePhoto();
      else if (auto) { hint(`Good. Hold still... (photo ${photos.length + 1} of 3)`, 'good'); if (++streak >= 3) await takePhoto(); }
      else hint(`Good. Press "Capture photo" (photo ${photos.length + 1} of 3)`, 'good');
    } else { streak = 0; if (wantShot) wantShot = false; hint(q.message, 'warn'); }
    await sleep(350);
  }
  if (!live) return;
  camera.stop(); hint('All three photos captured.', 'good'); $('#enSave', d).disabled = false;
  $('#enSave', d).onclick = async () => {
    const password = await askPassword('Confirm with your password', 'Turning on face authentication needs your password.');
    if (password === null) return;
    try {
      await api('/me/security/face', 'POST', { images: photos, current_password: password });
      toast('Face authentication is on: sign in and confirm risky actions with your face'); closeDialog(); done();
    }
    catch (e) { toast(e.message, 'bad'); }
  };
}

// ---- Settings page: banking-style switches
const switchHtml = (key, on, disabled = false) => `<label class="switch" title="${on ? 'On' : 'Off'}"><input type="checkbox" data-switch="${key}" ${on ? 'checked' : ''} ${disabled ? 'disabled' : ''}><span class="track"><span class="knob"></span></span></label>`;

async function pageSettings(root) {
  const s = await api('/me/security');
  const rows = [
    { key: 'face', icon: 'scan', title: 'Face authentication', on: s.face.enabled, ready: s.face.enrolled,
      text: s.face.enrolled ? 'Sign in and confirm risky actions with your face: look at the camera, then turn your head slightly.' : 'Not set up. Turn on to enrol your face.',
      links: s.face.enrolled ? [['reface', 'Retake face'], ['rmface', 'Remove face data']] : [] },
    { key: 'pin', icon: 'lock', title: `${s.pin_length}-digit PIN`, on: s.pin.enabled, ready: s.pin.set,
      text: s.pin.set ? 'Confirm risky actions with your PIN.' : 'Not set up. Turn on to choose a PIN.',
      links: s.pin.set ? [['chpin', 'Change PIN'], ['rmpin', 'Remove PIN']] : [] },
  ];
  root.innerHTML = pageHead('Settings', 'Your account and how you confirm risky actions.') + `
    <div class="cols"><div class="stack">
      <section class="card"><header><h2>Confirm risky actions</h2><span class="grow"></span>${s.enabled ? '<span class="pill ok">Protection on</span>' : '<span class="pill">Protection off</span>'}</header>
        ${rows.map((r) => `<div class="setting-row"><span class="ico-circle">${icon(r.icon)}</span>
          <div class="grow"><div class="name">${esc(r.title)}</div><div class="sub">${esc(r.text)}</div>
            ${r.links.length ? `<div class="row" style="margin-top:6px;gap:14px">${r.links.map(([id, t]) => `<a href="#settings" data-link="${id}" style="font-size:12.5px">${esc(t)}</a>`).join('')}</div>` : ''}</div>
          ${switchHtml(r.key, r.on, r.off)}</div>`).join('')}
        <div class="setting-row" style="border-bottom:0"><span class="ico-circle">${icon('shield')}</span><div class="grow"><div class="name">Password</div><div class="sub">Always available as a fallback. It is also needed to turn a method on or off.</div></div>
          <button class="sm" id="chPw">Change password</button></div></section>
      <div class="banner">${icon('info')}<div>When both are on, you choose at confirmation time; the one you used last is offered first. If none is on, you confirm with your password.</div></div>
    </div>
    <section class="card"><header><h2>Actions that need confirmation</h2></header><div class="body">
      ${Object.values(s.actions).map((label) => `<div class="row" style="padding:7px 0;border-bottom:1px solid var(--border)">${icon('lock')}<span>${esc(label)}</span></div>`).join('') || '<p class="faint">None. Confirmation is switched off in the configuration.</p>'}
      <p class="faint" style="margin-top:12px">Your customer's configuration decides this list. Face confirmation ${s.head_turn ? 'asks you to turn your head, so a photo of you cannot pass' : 'does not ask for a head turn'}.</p></div></section></div>`;

  $('#chPw').onclick = changeOwnPassword;
  const refresh = () => pageSettings(root);
  root.onchange = async (e) => {
    const sw = e.target.closest('input[data-switch]'); if (!sw) return;
    const key = sw.dataset.switch, row = rows.find((r) => r.key === key), turnOn = sw.checked;
    const field = key + '_enabled';
    const name = { face: 'Face authentication', pin: 'PIN' }[key];
    try {
      if (turnOn && !row.ready) { sw.checked = false; return key === 'pin' ? pinSetupDialog(s.pin_length, refresh) : faceEnrolDialog(refresh); }
      // turning a method OFF needs the password
      if (!turnOn) {
        const password = await askPassword(`Turn off ${name.toLowerCase()}?`, 'Weakening your security needs your password.');
        if (password === null) return refresh();
        await api('/me/security', 'PATCH', { [field]: false, current_password: password }); toast('Turned off'); return refresh();
      }
      await api('/me/security', 'PATCH', { [field]: true }); toast(`${name} is on`); return refresh();
    } catch (err) { toast(err.message, 'bad'); refresh(); }
  };
  root.onclick = async (e) => {
    const a = e.target.closest('a[data-link]'); if (!a) return; e.preventDefault();
    const id = a.dataset.link;
    if (id === 'reface') return faceEnrolDialog(refresh);
    if (id === 'chpin') return pinSetupDialog(s.pin_length, refresh);
    const password = await askPassword(id === 'rmface' ? 'Remove your face data?' : 'Remove your PIN?', 'This needs your password.');
    if (password === null) return;
    try { await api('/me/security/' + (id === 'rmface' ? 'face' : 'pin'), 'DELETE', { current_password: password }); toast('Removed'); refresh(); } catch (err) { toast(err.message, 'bad'); }
  };
}

// ---- export the scan log (a protected action, so it is fetched with the confirmation header)
async function downloadCsv(query) {
  const get = (extra) => fetch('/api/events/export.csv?' + query, { headers: { 'X-Requested-With': 'entryguard', ...extra } });
  let r = await get({});
  if (r.status === 403) {
    const data = await r.json().catch(() => ({}));
    if (data.error?.code !== 'STEP_UP_REQUIRED') throw new Error(data.error?.message || 'Not allowed');
    const token = await confirmRisk(data.error); if (!token) return;
    r = await get({ 'X-Step-Up': token });
  }
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error?.message || 'Export failed');
  const a = document.createElement('a'); a.href = URL.createObjectURL(await r.blob()); a.download = 'scan-log.csv'; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  toast('Export downloaded');
}

// =============================================================================== alerts (every signed-in user)
// A watch-list match opens an alert that stays open until staff acknowledge it. Staff get a full-screen
// siren overlay (critical) or a banner (high). Residents get a short warning with the face but no name or offence.
const alertState = { list: [], muted: 0, timer: null, siren: null, dismissed: new Set(), shown: null };
const isStaff = () => state.me && state.me.role !== 'resident';

function sirenSound() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)(), o = ctx.createOscillator(), g = ctx.createGain();
    o.type = 'sawtooth'; o.connect(g); g.connect(ctx.destination); g.gain.value = 0.12;
    for (let i = 0; i < 4; i++) { o.frequency.setValueAtTime(i % 2 ? 620 : 980, ctx.currentTime + i * 0.3); }
    o.start(); o.stop(ctx.currentTime + 1.2); setTimeout(() => ctx.close(), 1500);
  } catch { /* audio blocked until the person clicks once */ }
}

function startAlerts() { stopAlerts(); pollAlerts(); alertState.timer = setInterval(pollAlerts, 3000); }
function stopAlerts() {
  clearInterval(alertState.timer); clearInterval(alertState.siren); alertState.timer = alertState.siren = alertState.shown = null;
  const d = $('#alertDialog'); if (d?.open) d.close(); $('#alertBanner')?.remove(); document.body.classList.remove('has-banner');
}
async function pollAlerts() {
  if (!state.me) return;
  try { alertState.list = await api('/alerts?status=open'); } catch { return; }
  renderAlerts();
}

function renderAlerts() {
  const staff = isStaff(), open = alertState.list;
  $$('[data-badge="alerts"]').forEach((b) => { b.textContent = open.length || ''; b.hidden = !open.length; });
  const critical = open.filter((a) => a.level === 'critical' && (staff || !alertState.dismissed.has(a.id)));
  if (critical.length) showAlertOverlay(critical[0], critical.length); else hideAlertOverlay();

  // the siren repeats until the alert is acknowledged (or muted for a minute)
  if (critical.length && !alertState.siren) {
    if (Date.now() > alertState.muted) sirenSound();
    alertState.siren = setInterval(() => { if (Date.now() > alertState.muted) sirenSound(); }, 2500);
  } else if (!critical.length && alertState.siren) { clearInterval(alertState.siren); alertState.siren = null; }

  // high alerts: a flashing banner on every screen
  const high = staff ? open.filter((a) => a.level === 'high') : [];
  let banner = $('#alertBanner');
  if (!high.length) { banner?.remove(); document.body.classList.remove('has-banner'); return; }
  if (!banner) { banner = document.createElement('div'); banner.id = 'alertBanner'; banner.className = 'alert-banner'; document.body.prepend(banner); }
  document.body.classList.add('has-banner');
  const a = high[0];
  banner.innerHTML = `${icon('alert')}<span>HIGH ALERT: ${esc(a.person || 'watch-list person')} (${esc(typeById(a.person_type).label)}) at ${esc(a.camera)}, ${a.confidence === 'possible' ? 'possible match: verify identity' : 'confirmed match'}${high.length > 1 ? ` · +${high.length - 1} more` : ''}</span>
    <span class="grow"></span><button id="bannerReview" class="sm">Review and acknowledge</button>`;
  $('#bannerReview', banner).onclick = () => ackDialog(a);
}

function hideAlertOverlay() { const d = $('#alertDialog'); if (d?.open) d.close(); alertState.shown = null; }
function showAlertOverlay(a, total) {
  let d = $('#alertDialog');
  if (!d) {
    d = document.createElement('dialog'); d.id = 'alertDialog'; d.className = 'alert-dialog';
    d.addEventListener('cancel', (e) => e.preventDefault());       // Esc must not dismiss a critical alert
    document.body.append(d);
  }
  if (!d.open) d.showModal();
  if (alertState.shown === a.id) { const c = $('#alertCount', d); if (c) c.textContent = `seen ${a.count}×`; const t = $('#alertTotal', d); if (t) t.textContent = total > 1 ? `${total} open alerts` : ''; return; }
  alertState.shown = a.id;
  const staff = isStaff();
  d.innerHTML = `<div class="alert-card critical">
    <div class="alert-top">${icon('alert')}<span>CRITICAL SECURITY ALERT</span><span class="grow"></span><span id="alertTotal">${total > 1 ? total + ' open alerts' : ''}</span></div>
    <div class="alert-main">${a.has_snapshot ? `<img src="/api/alerts/${a.id}/snapshot?v=${a.count}" alt="Detected person">` : ''}
      <div>${staff
        ? `<h1>${esc(a.person || 'Watch-list person')} <span class="mono faint" style="font-size:16px">${esc(a.code || '')}</span></h1>
           <div class="alert-sub">${esc(typeById(a.person_type).label)}${a.unit ? ' · ' + esc(unitLabel()) + ' ' + esc(a.unit) : ''}</div>
           <div class="alert-reason"><b>Reason on file</b> ${esc(a.reason) || '-'}</div>
           ${a.instructions ? `<div class="alert-instr"><b>What to do</b> ${esc(a.instructions)}</div>` : ''}`
        : `<h1>Dangerous person detected at the entrance</h1><p style="font-size:18px">${esc(a.message)}</p>`}
        <div class="alert-meta">${esc(a.camera)} · ${esc(fmtTime(a.ts))} · <span id="alertCount">seen ${a.count}×</span> · ${a.confidence === 'confirmed' ? 'Confirmed match' : 'Possible match'}${staff ? ' · score ' + a.score : ''}</div>
        <div class="alert-verify">Verify identity before acting. Face recognition can be wrong.</div></div></div>
    <div class="alert-actions">
      ${staff ? `<textarea id="ackNote" rows="2" placeholder="What did you do? (for example: police called, person left the premises)"></textarea>
        <button class="primary big" id="ackBtn">Acknowledge alert</button>` : `<button class="primary big" id="dismissBtn">I understand</button>`}
      <button class="ghost" id="muteBtn">Mute siren for 60 seconds</button></div></div>`;
  $('#muteBtn', d).onclick = () => { alertState.muted = Date.now() + 60000; toast('Siren muted for 60 seconds. The alert stays open.'); };
  if (staff) $('#ackBtn', d).onclick = async () => {
    try { await api(`/alerts/${a.id}/ack`, 'POST', { note: $('#ackNote', d).value }); toast('Alert acknowledged'); alertState.shown = null; pollAlerts(); }
    catch (e) { toast(e.message, 'bad'); }
  };
  else $('#dismissBtn', d).onclick = () => { alertState.dismissed.add(a.id); renderAlerts(); };
}

// Review one alert and acknowledge it (used by the banner and the Alerts page).
function ackDialog(a) {
  const d = openDialog(`<div class="dlg-head"><h2>${esc(a.level.toUpperCase())} alert</h2><span class="pill bad">${esc(a.confidence)} match</span></div>
    <div class="dlg-body"><div class="detail">${a.has_snapshot ? `<img src="/api/alerts/${a.id}/snapshot" alt="">` : '<div></div>'}
      <div>${isStaff() ? `<h2 style="margin:0">${esc(a.person || '-')} <span class="mono faint">${esc(a.code || '')}</span></h2><p class="muted">${esc(typeById(a.person_type).label)}</p>
        <p><b>Reason</b> ${esc(a.reason) || '-'}</p>${a.instructions ? `<p><b>What to do</b> ${esc(a.instructions)}</p>` : ''}` : `<p>${esc(a.message)}</p>`}
        <p class="faint">${esc(a.camera)} · ${esc(fmtDateTime(a.ts))} · seen ${a.count}×${isStaff() ? ' · score ' + a.score : ''}</p>
        <p class="faint">Verify identity before acting. Face recognition can be wrong.</p></div></div>
      ${a.status === 'open' && isStaff() ? `<label class="field">Note <span class="opt">(what was done)</span><textarea id="ackNote2" rows="2"></textarea></label>` : ''}</div>
    <div class="dlg-foot"><button data-close>Close</button>${a.status === 'open' && isStaff() ? '<button class="primary" id="ackNow">Acknowledge</button>' : ''}</div>`, false, true);
  const b = $('#ackNow', d);
  if (b) b.onclick = async () => { try { await api(`/alerts/${a.id}/ack`, 'POST', { note: $('#ackNote2', d).value }); closeDialog(); toast('Alert acknowledged'); pollAlerts(); if (location.hash === '#alerts') route(); } catch (e) { toast(e.message, 'bad'); } };
}

async function pageAlerts(root) {
  const staff = isStaff(), list = await api('/alerts?limit=100');
  const open = list.filter((a) => a.status === 'open');
  root.innerHTML = pageHead('Alerts', staff ? 'Watch-list detections. Open alerts stay on every screen until someone acknowledges them.' : 'Security warnings for the building.') +
    (open.length ? '' : `<div class="banner" style="margin-bottom:16px">${icon('check')}<div><b>No open alerts.</b> The system is watching the entrance.</div></div>`) +
    `<div class="stack">${list.map((a) => `
      <article class="card" style="padding:16px;border-left:5px solid ${a.status === 'open' ? 'var(--bad)' : 'var(--border-strong)'}">
        <div class="row" style="align-items:flex-start;gap:16px">
          ${a.has_snapshot ? `<img class="snap" style="width:84px;height:84px;border-radius:10px" src="/api/alerts/${a.id}/snapshot" alt="">` : ''}
          <div class="grow"><div class="row wrap"><span class="pill ${a.level === 'critical' ? 'bad' : 'warn'}">${esc(a.level.toUpperCase())}</span>
              <span class="pill plain ${a.status === 'open' ? 'bad' : 'ok'}">${a.status === 'open' ? 'OPEN' : 'Acknowledged'}</span><span class="faint">${esc(fmtDateTime(a.ts))} · ${esc(a.camera)} · seen ${a.count}×</span></div>
            ${staff ? `<div class="name" style="margin-top:6px">${esc(a.person || 'Removed person')} <span class="mono faint">${esc(a.code || '')}</span> · ${esc(typeById(a.person_type).label)}</div>
              <div class="muted">${esc(a.reason)}</div>${a.instructions ? `<div class="muted"><b>Do:</b> ${esc(a.instructions)}</div>` : ''}`
              : `<div style="margin-top:6px">${esc(a.message)}</div>`}
            ${a.status === 'acknowledged' ? `<div class="faint" style="margin-top:6px">Acknowledged by ${esc(a.ack_by)} ${a.ack_at ? esc(fmtDateTime(a.ack_at)) : ''}${a.ack_note ? ': ' + esc(a.ack_note) : ''}</div>` : ''}</div>
          ${a.status === 'open' && staff ? `<button class="primary" data-ack="${a.id}">Review and acknowledge</button>` : ''}</div></article>`).join('')}</div>`;
  root.onclick = (e) => { const b = e.target.closest('[data-ack]'); if (b) ackDialog(list.find((a) => a.id == b.dataset.ack)); };
}

// =============================================================================== 6. start-up
// Cancelling a confirmation is a normal choice, not an error: do not report it as an unhandled rejection.
window.addEventListener('unhandledrejection', (e) => { if (e.reason?.cancelled) e.preventDefault(); });
// A person without a photo (or a snapshot that was deleted) shows initials instead of a broken image.
document.addEventListener('error', (e) => {
  const img = e.target;
  if (img.tagName === 'IMG' && (img.classList.contains('avatar') || img.classList.contains('snap'))) {
    const span = document.createElement('span'); span.className = img.classList.contains('avatar') ? 'avatar' : 'snap';
    span.textContent = img.dataset.initials || '?'; img.replaceWith(span);
  }
}, true);

function start() {
  startAlerts();
  if (location.pathname === '/tf-check') { if (state.me.role === 'resident') { location.replace('/#alerts'); return; } return renderConsole(); }
  renderShell(); route();
}
window.addEventListener('hashchange', () => { if (state.me && location.pathname !== '/tf-check') route(); });

(async () => {
  applyTheme();
  state.config = await api('/config');
  try { state.me = await api('/me'); start(); } catch { /* showLogin() already ran */ }
})();
