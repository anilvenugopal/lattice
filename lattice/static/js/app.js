// Shell behaviour: CSRF-aware requests, toasts, local time display, theme and
// global shortcuts. The Ctrl+J palette is palette.js; the grid is grid.js.
//
// Everything public lives on window.app (created in base/head.html, which also
// defines app.applyTheme before first paint). Alpine components are registered
// with Alpine.data, so nothing else is global.

Object.assign(window.app, (function () {
  function csrf() {
    const m = document.cookie.match(/(?:^|;\s*)lattice_csrf=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }

  async function request(method, url, body) {
    const headers = { 'X-CSRF-Token': csrf(), 'Accept': 'application/json' };
    let payload = body;
    if (body && !(body instanceof FormData) && !(body instanceof URLSearchParams)) {
      headers['Content-Type'] = 'application/json';
      payload = JSON.stringify(body);
    }
    const res = await fetch(url, { method, headers, body: payload, credentials: 'same-origin' });
    if (res.redirected && res.url.includes('/auth/login')) {
      window.location = res.url;
      throw new Error('Your session has ended.');
    }
    let data = {};
    try { data = await res.json(); } catch (_) { /* empty or non-JSON body */ }
    if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
    return data;
  }

  function toast(message, tone = 'success') {
    if (window.Alpine) Alpine.store('toasts').push(message, tone);
  }

  // ── Time display ────────────────────────────────────────────────────────
  const dateFmt = new Intl.DateTimeFormat(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
  const dateTimeFmt = new Intl.DateTimeFormat(undefined, {
    day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });

  function relative(d) {
    const s = (Date.now() - d.getTime()) / 1000;
    const future = s < 0;
    const a = Math.abs(s);
    let text;
    if (a < 45) return 'just now';
    if (a < 3600) text = Math.round(a / 60) + 'm';
    else if (a < 86400) text = Math.round(a / 3600) + 'h';
    else if (a < 86400 * 7) text = Math.round(a / 86400) + 'd';
    else return dateFmt.format(d);
    return future ? 'in ' + text : text + ' ago';
  }

  function formatTimes(root) {
    const pref = document.documentElement.dataset.time || 'relative';
    (root || document).querySelectorAll('time[data-fmt]').forEach(el => {
      const d = new Date(el.getAttribute('datetime'));
      if (isNaN(d)) return;
      let mode = el.dataset.fmt;
      if (mode === 'auto') mode = pref === 'absolute' ? 'datetime' : 'relative';
      el.textContent = mode === 'date' ? dateFmt.format(d)
        : mode === 'datetime' ? dateTimeFmt.format(d) : relative(d);
      el.title = dateTimeFmt.format(d);
    });
  }

  // The observer formats every <time data-fmt> as it is added (initial parse, HTMX swaps,
  // Alpine renders); the interval keeps relative times current.
  setInterval(() => formatTimes(), 60000);
  new MutationObserver(muts => muts.forEach(m => m.addedNodes.forEach(n => {
    if (n.nodeType === 1) formatTimes(n);
  }))).observe(document.documentElement, { childList: true, subtree: true });

  // ── HTMX integration ───────────────────────────────────────────────────
  document.addEventListener('htmx:configRequest', e => {
    e.detail.headers['X-CSRF-Token'] = csrf();
  });
  document.addEventListener('toast', e => toast(e.detail.message, e.detail.tone));
  document.addEventListener('htmx:responseError', e => {
    let msg = `Request failed (${e.detail.xhr.status})`;
    try { msg = JSON.parse(e.detail.xhr.responseText).detail || msg; } catch (_) { /* HTML error page */ }
    toast(msg, 'danger');
  });
  document.addEventListener('htmx:sendError', () => toast('Network error. Check your connection.', 'danger'));

  function isTyping(e) {
    const t = e.target;
    return t && (t.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(t.tagName));
  }

  // Submits the page's sign-out form (components/macros.html signout_button).
  function signOut() {
    const form = document.querySelector('form[data-signout]');
    if (form) form.submit();
  }

  return { csrf, post: (url, body) => request('POST', url, body), toast, isTyping, signOut };
})());

document.addEventListener('alpine:init', () => {
  Alpine.store('toasts', {
    items: [],
    seq: 0,
    push(message, tone = 'success') {
      if (!message) return;
      const id = ++this.seq;
      this.items.push({ id, message, tone });
      setTimeout(() => this.dismiss(id), tone === 'success' ? 4000 : 9000);
    },
    dismiss(id) { this.items = this.items.filter(t => t.id !== id); },
  });
});

(function () {
// Alpine component on .shell (base/shell.html). opts.themes is the server's theme list.
function shell(opts) {
  return {
    theme: opts.theme,
    themes: opts.themes,
    paletteOpen: false,
    shortcutsOpen: false,

    onKey(e) {
      if ((e.ctrlKey || e.metaKey) && (e.key === 'j' || e.key === 'J' || e.key === 'k' || e.key === 'K')) {
        e.preventDefault();
        this.paletteOpen ? this.closePalette() : this.openPalette();
      } else if (e.key === '?' && !app.isTyping(e)) {
        this.shortcutsOpen = !this.shortcutsOpen;
      }
    },

    // The palette component (static/js/palette.js) listens for this event to reset and focus.
    openPalette() {
      this.paletteOpen = true;
      this.$nextTick(() => window.dispatchEvent(new CustomEvent('palette-open')));
    },
    closePalette() { this.paletteOpen = false; },

    cycleTheme() {
      this.setTheme(this.themes[(this.themes.indexOf(this.theme) + 1) % this.themes.length]);
    },
    setTheme(theme) {
      this.theme = theme;
      app.applyTheme(theme);
      this.paletteOpen = false;
      app.post('/account/preferences', new URLSearchParams({ theme })).catch(() => {});
    },
  };
}


document.addEventListener('alpine:init', () => Alpine.data('shell', shell));
})();
