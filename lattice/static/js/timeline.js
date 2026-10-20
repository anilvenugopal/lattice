// Alpine component for components/timeline.html (ADR 0014). Server config comes from
// lattice/components/timeline/render.py build_timeline(); the data from
// GET /_timeline/{key}/data (lattice/components/timeline/engine.py).
// See lattice/help/developer/building-apps/timelines.md.
//
// Bars are buttons positioned by percentage on their lane: Tab reaches them, arrows move
// between them, Enter opens one. Times arrive as UTC ISO strings and show in the browser's
// time zone. Dragging across a lane zooms to that window, which the server narrows to.

(function () {
document.addEventListener('alpine:init', () => Alpine.data('ltTimeline', ltTimeline));

const MIN = 60e3, HOUR = 60 * MIN, DAY = 24 * HOUR;
const ROW = 22, MAX_ROWS = 8;      // a lane's bars stack in rows where they overlap
const STEPS = [MIN, 5 * MIN, 15 * MIN, 30 * MIN, HOUR, 3 * HOUR, 6 * HOUR, 12 * HOUR, DAY,
  2 * DAY, 7 * DAY, 14 * DAY, 30 * DAY, 91 * DAY, 182 * DAY, 365 * DAY];
const time = new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' });
const day = new Intl.DateTimeFormat(undefined, { day: 'numeric', month: 'short' });
const dateOnly = new Intl.DateTimeFormat(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
const full = new Intl.DateTimeFormat(undefined, { day: 'numeric', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit' });

function duration(ms) {
  if (ms < HOUR) return Math.max(1, Math.round(ms / MIN)) + 'm';
  if (ms < 2 * DAY) return (ms / HOUR).toFixed(ms < 10 * HOUR ? 1 : 0) + 'h';
  return Math.round(ms / DAY) + 'd';
}

function ltTimeline(config) {
  return {
    loading: true,
    error: '',
    data: null,
    params: config.params,
    win: null,                // [from, to] in ms when zoomed in, else null (the whole extent)
    drag: null,               // the window being dragged out: {x0, left, width, track}
    now: Date.now(),

    get zoomed() { return this.win !== null; },

    init() {
      this.onGrid = e => {
        if (config.grid && e.detail.key === config.grid) {
          this.params = [e.detail.params, config.fixed].filter(Boolean).join('&');
          this.load();
        }
      };
      window.addEventListener('gridstate', this.onGrid);
      this.onMove = e => this.dragMove(e);
      this.onUp = e => this.dragEnd(e);
      if (config.poll) this.timer = setInterval(() => { if (!document.hidden) this.load(); }, config.poll * 1000);
      this.clock = setInterval(() => { this.now = Date.now(); }, 30e3);
      this.load();
    },
    destroy() {
      window.removeEventListener('gridstate', this.onGrid);
      clearInterval(this.timer);
      clearInterval(this.clock);
    },

    async load() {
      this.loading = true;
      const q = new URLSearchParams(this.params);
      if (this.win) {
        q.set('from', new Date(this.win[0]).toISOString());
        q.set('to', new Date(this.win[1]).toISOString());
      }
      try {
        const res = await fetch(`${config.endpoint}?${q}`, { headers: { Accept: 'application/json' } });
        const body = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(body.detail || `Could not load the timeline (${res.status}).`);
        this.data = body;
        this.now = Date.parse(body.now);
        this.error = '';
      } catch (err) {
        this.error = err.message;
      }
      this.loading = false;
    },

    // ── Geometry ───────────────────────────────────────────────────────────
    range() {
      if (this.win) return this.win;
      const d = this.data;
      if (!d || !d.extent.from) return [this.now - DAY, this.now];
      let [lo, hi] = [Date.parse(d.extent.from), Date.parse(d.extent.to)];
      if (hi - lo < MIN) hi = lo + HOUR;
      const pad = (hi - lo) * 0.02;
      return [lo - pad, hi + pad];
    },
    pct(t) { const [lo, hi] = this.range(); return ((t - lo) / (hi - lo)) * 100; },

    lanes() {
      const d = this.data;
      if (!d) return [];
      const [lo, hi] = this.range();
      const byLane = new Map(d.lanes.map(l => [l.key, { ...l, bars: [] }]));
      for (const b of d.bars) {
        const start = Date.parse(b.start);
        const end = b.marker ? start : b.end ? Date.parse(b.end) : this.now;
        const left = Math.max(0, this.pct(start));
        const right = Math.min(100, this.pct(Math.max(end, start)));
        const span = b.marker ? `at ${full.format(start)}`
          : `${full.format(start)} – ${b.end ? full.format(end) : 'now'} (${duration(end - start)})`;
        byLane.get(b.lane).bars.push({
          ...b, from: start, to: b.marker ? start : end,
          cls: [b.tone && 'tone-' + b.tone, b.marker && 'is-marker', !b.end && !b.marker && 'is-open'].filter(Boolean).join(' '),
          style: b.marker ? `left:${this.pct(start)}%` : `left:${left}%;width:${Math.max(0, right - left)}%`,
          tip: `${b.label} · ${span}`,
          hidden: end < lo || start > hi,
        });
      }
      return [...byLane.values()].map(l => {
        // Greedy packing: each bar takes the first row free at its start.
        const ends = [];
        const bars = l.bars.filter(b => !b.hidden).sort((a, b) => a.from - b.from).map(b => {
          let row = ends.findIndex(e => e <= b.from);
          if (row < 0) row = ends.length < MAX_ROWS ? ends.length : MAX_ROWS - 1;
          ends[row] = Math.max(ends[row] || 0, b.to);
          return { ...b, style: `${b.style};top:${4 + row * ROW + (b.marker ? 2 : 0)}px` };
        });
        return { ...l, bars, height: Math.max(1, ends.length) * ROW + 8 };
      });
    },

    ticks() {
      const [lo, hi] = this.range();
      const step = STEPS.find(s => (hi - lo) / s <= 8) || STEPS[STEPS.length - 1];
      const offset = new Date(lo).getTimezoneOffset() * MIN;   // ticks on local boundaries
      const out = [];
      for (let t = Math.ceil((lo - offset) / step) * step + offset; t <= hi; t += step) {
        out.push({ at: t, left: this.pct(t), label: step < DAY ? time.format(t) : day.format(t) });
      }
      return out;
    },
    nowLeft() {
      const p = this.pct(this.now);
      return p >= 0 && p <= 100 ? p : null;
    },
    rangeLabel() {
      const [lo, hi] = this.range();
      if (!this.data) return '';
      const f = hi - lo > 2 * DAY ? dateOnly : full;
      return `${f.format(lo)} – ${f.format(hi)}`;
    },

    // ── Zoom: drag across a track ──────────────────────────────────────────
    dragStart(e) {
      if (e.button !== 0 || e.target.closest('.tl__bar')) return;
      const track = e.currentTarget.getBoundingClientRect();
      this.drag = { x0: e.clientX, track, left: 0, width: 0 };
      window.addEventListener('mousemove', this.onMove);
      window.addEventListener('mouseup', this.onUp, { once: true });
    },
    dragMove(e) {
      if (!this.drag) return;
      const { track, x0 } = this.drag;
      const a = Math.min(x0, e.clientX), b = Math.max(x0, e.clientX);
      this.drag.left = Math.max(0, (a - track.left) / track.width * 100);
      this.drag.width = Math.min(100 - this.drag.left, (b - a) / track.width * 100);
    },
    dragEnd() {
      window.removeEventListener('mousemove', this.onMove);
      const d = this.drag;
      this.drag = null;
      if (!d || d.width < 1) return;
      const [lo, hi] = this.range();
      const span = hi - lo;
      this.win = [lo + span * d.left / 100, lo + span * (d.left + d.width) / 100];
      this.load();
    },
    resetZoom() { this.win = null; this.load(); },

    // ── Open and keyboard ──────────────────────────────────────────────────
    open(b) {
      if (b.href) window.location = b.href;
      else if (config.grid) window.dispatchEvent(new CustomEvent('gridpanel', { detail: { key: config.grid, id: b.id } }));
    },
    onKey(e) {
      const bar = e.target.closest('.tl__bar');
      if (!bar || !['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(e.key)) return;
      e.preventDefault();
      const all = [...this.$root.querySelectorAll('.tl__bar')];
      const lane = bar.dataset.lane;
      if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
        const same = all.filter(b => b.dataset.lane === lane);
        const next = same[same.indexOf(bar) + (e.key === 'ArrowRight' ? 1 : -1)];
        if (next) next.focus();
        return;
      }
      const lanes = [...new Set(all.map(b => b.dataset.lane))];
      const target = lanes[lanes.indexOf(lane) + (e.key === 'ArrowDown' ? 1 : -1)];
      if (target === undefined) return;
      const x = bar.getBoundingClientRect().left;
      const near = all.filter(b => b.dataset.lane === target)
        .sort((p, q) => Math.abs(p.getBoundingClientRect().left - x) - Math.abs(q.getBoundingClientRect().left - x))[0];
      if (near) near.focus();
    },
  };
}
})();
