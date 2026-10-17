// Alpine component for components/grid.html. Server config comes from
// app/grid/render.py build_grid() (`config`). See docs/GRID.md.
//
// State that survives body reloads lives here: selection, cursor, panel,
// dialogs. The table body is re-rendered by the server on every change.

(function () {
document.addEventListener('alpine:init', () => Alpine.data('dataGrid', dataGrid));

function dataGrid(config) {
  return {
    config,
    view: config.view,
    total: config.total,
    pageIds: [],
    pageNo: 1,
    pages: 1,
    selected: {},          // id -> row attrs used by Action.when
    allMatching: false,    // "select all N matching" across pages
    anchor: null,
    cursor: null,
    panelOpen: false,
    panelId: null,
    loading: false,
    dirty: false,
    rowMenu: { open: false, x: 0, y: 0, id: null, attrs: {} },
    dialog: { open: false, title: '', text: '', fields: [], values: {}, submit: '', tone: '', action: '', ids: null, busy: false },

    init() {
      this.updateFilterState();
      if (config.poll) {
        this.timer = setInterval(() => {
          if (!document.hidden && !this.dialog.open && !this.rowMenu.open && !this.loading) this.reload({ quiet: true });
        }, config.poll * 1000);
      }
    },
    destroy() { clearInterval(this.timer); },

    get count() { return Object.keys(this.selected).length; },

    // Called by grid_body.html after each render.
    syncPage(ids, total, page, pages) {
      this.pageIds = ids.map(String);
      this.total = total;
      this.pageNo = page;
      this.pages = pages;
      this.$refs.page.value = page;
      if (this.cursor && !this.pageIds.includes(this.cursor)) this.cursor = null;
    },

    // ── Loading ────────────────────────────────────────────────────────────
    paramString() {
      const out = new URLSearchParams();
      for (const [k, v] of new FormData(this.$refs.state)) {
        if (v === '') continue;
        if (k === 'page' && v === '1') continue;
        if (k === 'size' && v === String(config.defaultSize)) continue;
        if (k === 'view' && (v === config.defaultView || config.viewsInNav && !v)) continue;
        out.append(k, v);
      }
      // Sidebar-driven views keep the view in the URL even when it is the default.
      if (config.viewsInNav && this.view && !out.has('view')) out.set('view', this.view);
      return out.toString();
    },

    reload(opts = {}) {
      if (opts.reset) this.clearSelection();
      if ('page' in opts) this.$refs.page.value = opts.page;
      const qs = this.paramString();
      const scroller = this.$refs.body.querySelector('.dg__scroll');
      const top = scroller ? scroller.scrollTop : 0;
      if (!opts.quiet) this.loading = true;
      const url = `${config.endpoint}/rows?${qs}${config.viewsInNav ? '&_nav=1' : ''}`;
      if (config.syncUrl && !opts.quiet) history.replaceState(null, '', config.path + (qs ? '?' + qs : ''));
      this.updateFilterState();
      return htmx.ajax('GET', url, { target: this.$refs.body, swap: 'innerHTML' }).then(() => {
        this.loading = false;
        if (opts.quiet) {
          const s = this.$refs.body.querySelector('.dg__scroll');
          if (s) s.scrollTop = top;
        }
      }, () => { this.loading = false; });
    },

    sortBy(key) {
      const cur = this.$refs.sort.value || config.sort;
      const next = cur === key ? '-' + key : key;
      this.$refs.sort.value = next;
      config.sort = next;
      this.reload({ page: 1 });
    },
    goPage(n) { this.reload({ page: n }); },
    setSize(n) { this.$refs.size.value = n; this.reload({ page: 1 }); },
    setView(v) {
      this.view = v;
      this.closePanel();
      this.$nextTick(() => this.reload({ page: 1, reset: true }));
    },

    filterInputs(name) {
      return [...this.$refs.state.querySelectorAll(name ? `input[name="${name}"]` : 'input[name^="f_"]')];
    },
    clearFilter(name) {
      this.filterInputs(name).forEach(i => (i.checked = false));
      this.reload({ page: 1, reset: true });
    },
    clearAll() {
      this.$refs.search.value = '';
      this.filterInputs().forEach(i => (i.checked = false));
      this.reload({ page: 1, reset: true });
    },
    updateFilterState() {
      let any = !!this.$refs.search.value;
      this.$refs.state.querySelectorAll('[data-filter]').forEach(chip => {
        const n = this.filterInputs(chip.dataset.filter).filter(i => i.checked).length;
        chip.classList.toggle('is-on', n > 0);
        chip.querySelector('[data-filter-count]').textContent = n || '';
        any = any || n > 0;
      });
      this.dirty = any;
    },

    exportUrl() { return `${config.endpoint}/export.csv?${this.paramString()}`; },

    async toggleColumn(key, visible) {
      const hidden = new Set(config.hidden);
      visible ? hidden.delete(key) : hidden.add(key);
      config.hidden = [...hidden];
      try {
        await app.post(`${config.endpoint}/columns`, { hidden: config.hidden });
        this.reload({ quiet: true });
      } catch (err) { app.toast(err.message, 'danger'); }
    },

    onRefreshEvent(e) {
      if (!e.detail || !e.detail.key || e.detail.key === config.key) this.reload({ quiet: true });
    },

    // ── Selection ──────────────────────────────────────────────────────────
    rows() { return [...this.$refs.body.querySelectorAll('tbody tr[data-id]')]; },
    rowEl(id) { return this.$refs.body.querySelector(`tbody tr[data-id="${CSS.escape(id)}"]`); },
    attrs(tr) { try { return JSON.parse(tr.dataset.w || '{}'); } catch (_) { return {}; } },

    isSel(id) { return this.allMatching || id in this.selected; },
    rowClass(id) {
      return {
        'is-selected': this.isSel(id),
        'is-cursor': this.cursor === id,
        'is-open': this.panelId === id && (this.panelOpen || config.layout === 'split'),
      };
    },
    select(tr, on) {
      const id = tr.dataset.id;
      if (on) this.selected[id] = this.attrs(tr); else delete this.selected[id];
    },
    toggleRow(tr, e) {
      const id = tr.dataset.id;
      if (config.selection === 'none') return;
      if (this.allMatching) { this.allMatching = false; this.togglePage(true); }
      if (config.selection === 'single') {
        const on = !(id in this.selected);
        this.selected = {};
        if (on) this.select(tr, true);
      } else if (e && e.shiftKey && this.anchor && this.pageIds.includes(this.anchor)) {
        this.selectRange(this.anchor, id);
      } else {
        this.select(tr, !(id in this.selected));
        this.anchor = id;
      }
      this.cursor = id;
    },
    selectRange(fromId, toId) {
      const a = this.pageIds.indexOf(fromId);
      const b = this.pageIds.indexOf(toId);
      const [lo, hi] = a < b ? [a, b] : [b, a];
      this.pageIds.slice(lo, hi + 1).forEach(id => { const tr = this.rowEl(id); if (tr) this.select(tr, true); });
    },
    togglePage(on) {
      this.allMatching = false;
      this.rows().forEach(tr => this.select(tr, on));
    },
    allOnPage() { return this.pageIds.length > 0 && this.pageIds.every(id => this.isSel(id)); },
    someOnPage() { return !this.allOnPage() && this.pageIds.some(id => this.isSel(id)); },
    clearSelection() { this.selected = {}; this.allMatching = false; this.anchor = null; },

    rowClick(e) {
      if (e.target.closest('a, button, input, select, label')) return;
      const tr = e.currentTarget;
      const id = tr.dataset.id;
      this.$root.focus({ preventScroll: true });
      if (config.selection === 'multi' && (e.shiftKey || e.ctrlKey || e.metaKey)) {
        this.toggleRow(tr, e);
        return;
      }
      this.cursor = id;
      if (config.selection !== 'none') {
        this.selected = {};
        this.allMatching = false;
        this.select(tr, true);
        this.anchor = id;
      }
      if (config.hasPanel) this.openPanel(id);
    },
    rowOpen(id) {
      if (config.rowHref) window.location = config.rowHref.replace(/\{id\}/g, encodeURIComponent(id));
      else this.openPanel(id);
    },

    // ── Panel ──────────────────────────────────────────────────────────────
    // htmx handles HX-Redirect (expired session), HX-Trigger gridrefresh (reaches
    // @gridrefresh.window) and error toasts. hx-sync on the panel element lets a
    // later click replace a request still in flight.
    async openPanel(id) {
      this.panelId = id;
      this.panelOpen = true;
      this.showPlaceholder();
      await htmx.ajax('GET', `${config.endpoint}/panel/${encodeURIComponent(id)}`,
        { target: this.$refs.panel, swap: 'innerHTML' });
      if (this.panelId === id && !this.$refs.panel.querySelector('.panel')) this.closePanel();
    },
    closePanel() {
      this.panelOpen = false;
      this.panelId = null;
      this.showPlaceholder();
    },
    showPlaceholder() {
      this.$refs.panel.replaceChildren(this.$refs.placeholder.content.cloneNode(true));
    },

    // ── Keyboard ───────────────────────────────────────────────────────────
    onKey(e) {
      if (this.dialog.open) return;
      if (app.isTyping(e)) return;
      const k = e.key;
      if ((e.ctrlKey || e.metaKey) && k !== 'a') return;
      if (k === '/') { e.preventDefault(); this.$refs.search.focus(); return; }
      if (k === 'ArrowDown' || k === 'j') { e.preventDefault(); this.moveCursor(1, e.shiftKey); }
      else if (k === 'ArrowUp' || k === 'k') { e.preventDefault(); this.moveCursor(-1, e.shiftKey); }
      else if ((k === ' ' || k === 'x') && this.cursor) {
        e.preventDefault();
        const tr = this.rowEl(this.cursor);
        if (tr) this.toggleRow(tr);
      } else if (k === 'Enter' && this.cursor) {
        e.preventDefault();
        this.rowOpen(this.cursor);
      } else if (k === 'Escape') {
        if (this.rowMenu.open) this.rowMenu.open = false;
        else if (this.panelOpen && config.layout !== 'split') this.closePanel();
        else this.clearSelection();
      } else if ((e.ctrlKey || e.metaKey) && k === 'a' && config.selection === 'multi') {
        e.preventDefault();
        this.togglePage(true);
      }
    },
    moveCursor(step, extend) {
      if (!this.pageIds.length) return;
      let i = this.pageIds.indexOf(this.cursor);
      i = i === -1 ? (step > 0 ? 0 : this.pageIds.length - 1) : Math.min(this.pageIds.length - 1, Math.max(0, i + step));
      this.cursor = this.pageIds[i];
      const tr = this.rowEl(this.cursor);
      if (!tr) return;
      tr.scrollIntoView({ block: 'nearest' });
      if (extend && config.selection === 'multi') this.select(tr, true);
      if (this.panelOpen || config.layout === 'split') this.openPanel(this.cursor);
    },

    // ── Actions ────────────────────────────────────────────────────────────
    matches(a, attrs) {
      return Object.entries(a.when || {}).every(([k, allowed]) => allowed.includes(attrs[k]));
    },
    canRun(key) {
      const a = config.actions[key];
      if (!a) return false;
      if (a.scope === 'none') return true;
      if (this.allMatching) return a.scope === 'multi';
      const n = this.count;
      if (a.scope === 'single' && n !== 1) return false;
      if (n < 1) return false;
      // Enabled when at least one selected row qualifies; the server skips the rest.
      return Object.values(this.selected).some(attrs => this.matches(a, attrs));
    },
    reason(key) {
      if (this.canRun(key)) return '';
      const a = config.actions[key];
      if (a.scope === 'single' && this.count !== 1) return 'Select exactly one row';
      if (this.allMatching) return 'Not available for all matching rows';
      return 'None of the selected rows qualify';
    },
    run(key, ids = null) {
      const a = config.actions[key];
      if (!a) return;
      const all = !ids && this.allMatching;
      ids = ids || Object.keys(this.selected);
      if (a.href) {
        window.location = a.href.replace(/\{id\}/g, encodeURIComponent(ids[0] || ''));
        return;
      }
      const count = all ? this.total : ids.length;
      if (a.fields.length || a.confirm) {
        const values = {};
        a.fields.forEach(f => (values[f.name] = f.default || ''));
        this.dialog = {
          open: true, title: a.label + (a.scope !== 'none' && count > 1 ? ` (${count})` : ''),
          text: (a.confirm || '').replace('{count}', count.toLocaleString()), fields: a.fields, values,
          submit: a.label, tone: a.tone, action: key, ids, all, busy: false,
        };
        this.$nextTick(() => {
          const first = this.$root.querySelector('.dialog .input');
          (first || this.$refs.dialogSubmit).focus();
        });
        return;
      }
      this.execute(key, ids, all, {});
    },
    async execute(key, ids, all, values) {
      try {
        const res = await app.post(`${config.endpoint}/action/${key}`, {
          ids, all, params: this.paramString(), values });
        app.toast(res.message, res.tone);
        if (res.redirect) { window.location = res.redirect; return true; }
        if (res.clear) this.clearSelection();
        if (res.refresh) {
          await this.reload({ quiet: true });
          if (this.panelOpen && this.panelId) this.openPanel(this.panelId);
        }
        return true;
      } catch (err) {
        app.toast(err.message, 'danger');
        return false;
      }
    },
    async submitDialog() {
      const d = this.dialog;
      const missing = d.fields.filter(f => f.required && !d.values[f.name]).map(f => f.label);
      if (missing.length) { app.toast('Required: ' + missing.join(', '), 'warning'); return; }
      d.busy = true;
      const ok = await this.execute(d.action, d.ids, d.all, d.values);
      d.busy = false;
      if (ok) d.open = false;
    },

    runForRow(key, tr) {
      const a = config.actions[key];
      if (!a) return;
      if (!this.matches(a, this.attrs(tr))) { app.toast(`${a.label} does not apply to this row.`, 'warning'); return; }
      this.run(key, [tr.dataset.id]);
    },
    openRowMenu(e, tr) {
      const r = e.currentTarget.getBoundingClientRect();
      const menuW = 220;
      this.rowMenu = {
        open: true, id: tr.dataset.id, attrs: this.attrs(tr),
        x: Math.max(8, Math.min(window.innerWidth - menuW - 8, r.right - menuW)),
        y: Math.min(window.innerHeight - 260, r.bottom + 4),
      };
    },
    rowEligible(key) {
      const a = config.actions[key];
      return a && a.scope !== 'none' && this.matches(a, this.rowMenu.attrs);
    },
    runFromMenu(key) {
      this.rowMenu.open = false;
      this.run(key, [this.rowMenu.id]);
    },
    runForPanel(key, el) {
      const root = el.closest('[data-row-id]');
      this.run(key, [root.dataset.rowId]);
    },
  };
}
})();
