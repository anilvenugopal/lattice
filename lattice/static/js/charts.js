// Alpine component for components/chart.html. Server config comes from
// lattice/components/chart/render.py build_chart(); the data from
// GET /_chart/{key}/data (lattice/components/chart/engine.py).
// See lattice/help/developer/building-apps/charts.md.
//
// Chart.js and its plugins (static/js/vendor/chart/) load on first use, so
// pages without a chart never download them. Colours come from the --chart-*
// tokens and are re-read when the theme changes.

(function () {
document.addEventListener('alpine:init', () => Alpine.data('ltChart', ltChart));

const VENDOR = '/static/js/vendor/chart/';
const BASE = ['chart.min.js', 'adapter-date-fns.min.js', 'hammer.min.js', 'zoom.min.js', 'annotation.min.js'];
const PLUGINS = { calendar: 'matrix.min.js', treemap: 'treemap.min.js', sankey: 'sankey.min.js', choropleth: 'geo.min.js' };
const loaded = {};
let world = null;

function script(name) {
  if (!loaded[name]) {
    loaded[name] = new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = VENDOR + name;
      s.onload = resolve;
      s.onerror = () => reject(new Error('Could not load the chart library.'));
      document.head.appendChild(s);
    });
  }
  return loaded[name];
}

async function libraries(kind) {
  for (const name of BASE) await script(name);
  if (PLUGINS[kind]) await script(PLUGINS[kind]);
}

async function worldMap() {
  if (!world) {
    world = fetch('/static/maps/countries-110m.json').then(r => r.json()).then(topo =>
      ChartGeo.topojson.feature(topo, topo.objects.countries).features);
  }
  return world;
}

// ── Theme ──────────────────────────────────────────────────────────────────
function token(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}
function alpha(color, a) {
  const m = /^#([0-9a-f]{6})$/i.exec(color);
  if (!m) return color;
  const n = parseInt(m[1], 16);
  return `rgba(${n >> 16}, ${(n >> 8) & 255}, ${n & 255}, ${a})`;
}
function theme() {
  return {
    series: [1, 2, 3, 4, 5, 6, 7, 8].map(i => token(`--chart-${i}`)),
    tone: t => token(`--chart-${t}`),
    text: token('--text-2'),
    muted: token('--text-3'),
    grid: token('--chart-grid'),
    panel: token('--surface-panel'),
    font: token('--font-ui'),
  };
}

function formatter(format, compact = false) {
  const num = new Intl.NumberFormat(undefined, compact
    ? { notation: 'compact', maximumFractionDigits: 1 } : { maximumFractionDigits: 1 });
  if (format === 'money') return v => '$' + (compact ? num.format(v) : Math.round(v).toLocaleString());
  if (format === 'percent') return v => num.format(v) + '%';
  return v => num.format(v);
}

// ── Chart.js configuration per kind ────────────────────────────────────────
function seriesColor(t, s, i) { return s.tone ? t.tone(s.tone) : t.series[i % t.series.length]; }
function categoryColor(t, d, key, i) {
  if (key === '__other__') return t.tone('neutral');
  return d.xTones[key] ? t.tone(d.xTones[key]) : t.series[i % t.series.length];
}
function lookup(d) {
  const m = new Map();
  d.points.forEach(([x, s, v]) => m.set(x + '\u0000' + s, v));
  return (x, s) => m.get(x + '\u0000' + s);
}

function cartesian(d, t, fmt) {
  const time = d.x.type === 'time';
  const get = lookup(d);
  const area = d.kind === 'area';
  const single = d.series.length === 1 && !d.series[0].key;
  const datasets = d.series.map((s, i) => {
    const color = seriesColor(t, s, i);
    const data = time
      ? d.points.filter(p => p[1] === s.key).map(([x, , v]) => ({ x, y: v }))
      : d.categories.map(x => get(x, s.key) ?? 0);
    const perCategory = single && !time && d.kind === 'bar';
    return {
      label: s.label, data,
      backgroundColor: perCategory ? d.categories.map(x => (x === '__other__' || d.xTones[x] ? categoryColor(t, d, x, 0) : color))
        : (d.kind === 'bar' ? color : alpha(color, area ? 0.25 : 1)),
      borderColor: color, borderWidth: d.kind === 'bar' ? 0 : 2,
      fill: area ? (d.stacked ? (i ? '-1' : 'origin') : 'origin') : false,
      tension: 0.25, pointRadius: time && data.length > 60 ? 0 : 2, borderRadius: d.kind === 'bar' ? 3 : 0,
    };
  });
  const value = { beginAtZero: true, stacked: d.stacked, grid: { color: t.grid }, ticks: { color: t.muted, callback: formatter(d.format, true) } };
  const index = time
    ? { type: 'time', time: { unit: d.x.unit === 'quarter' ? 'quarter' : d.x.unit }, stacked: d.stacked, grid: { display: false }, ticks: { color: t.muted } }
    : { type: 'category', stacked: d.stacked, grid: { display: false }, ticks: { color: t.muted } };
  const horizontal = d.kind === 'bar' && d.horizontal;
  const annotations = {};
  d.thresholds.forEach((th, i) => {
    annotations['t' + i] = {
      type: 'line', scaleID: horizontal ? 'x' : 'y', value: th.value, borderColor: t.tone(th.tone),
      borderWidth: 1.5, borderDash: [5, 4],
      label: { display: !!th.label, content: th.label, position: 'end', backgroundColor: t.tone(th.tone), color: t.panel, font: { size: 11 } },
    };
  });
  return {
    type: d.kind === 'bar' ? 'bar' : 'line',
    data: { labels: time ? undefined : d.categories.map(x => d.xLabels[x] ?? x), datasets },
    options: {
      indexAxis: horizontal ? 'y' : 'x',
      scales: horizontal ? { x: value, y: index } : { x: index, y: value },
      plugins: {
        legend: { display: !single },
        annotation: { annotations },
        zoom: time ? {
          zoom: { wheel: { enabled: true, modifierKey: 'ctrl' }, drag: { enabled: true, backgroundColor: alpha(t.series[0], 0.12) }, mode: 'x' },
          pan: { enabled: true, mode: 'x', modifierKey: 'shift' },
        } : undefined,
      },
    },
  };
}

function pie(d, t) {
  const get = lookup(d);
  return {
    type: d.kind,
    data: {
      labels: d.categories.map(x => d.xLabels[x] ?? x),
      datasets: [{
        label: d.measure, data: d.categories.map(x => get(x, '') ?? 0),
        backgroundColor: d.categories.map((x, i) => categoryColor(t, d, x, i)),
        borderColor: t.panel, borderWidth: 2,
      }],
    },
    options: { plugins: { legend: { position: 'right' } } },
  };
}

// The months that have data, and the one with the busiest day (where a calendar opens).
function calendarMonths(d) {
  const months = [...new Set(d.points.map(p => p[0].slice(0, 7)))].sort();
  let peak = months[months.length - 1] || '';
  let best = -Infinity;
  for (const [x, , v] of d.points) if (v > best) { best = v; peak = x.slice(0, 7); }
  return { months, peak };
}

// One month as a calendar: weekdays across, weeks down, each day shaded by its value.
function calendar(d, t, fmt, month) {
  const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  const values = new Map(d.points.map(([x, , v]) => [x.slice(0, 10), v]));
  const max = Math.max(1, ...values.values());
  const first = new Date(month + '-01T00:00:00Z');
  const lead = (first.getUTCDay() + 6) % 7;                       // days before the 1st, from Monday
  const days = new Date(Date.UTC(first.getUTCFullYear(), first.getUTCMonth() + 1, 0)).getUTCDate();
  const weeks = Math.ceil((lead + days) / 7);
  const cells = [];
  for (let day = 1; day <= days; day++) {
    const i = lead + day - 1;
    const iso = `${month}-${String(day).padStart(2, '0')}`;
    cells.push({ x: DAYS[i % 7], y: Math.floor(i / 7), v: values.get(iso) || 0, date: iso, day });
  }
  const base = t.series[0];
  const shade = v => (v ? alpha(base, 0.15 + 0.85 * v / max) : t.grid);
  return {
    type: 'matrix',
    data: {
      datasets: [{
        label: d.measure, data: cells, borderWidth: 0,
        backgroundColor: c => shade(c.raw ? c.raw.v : 0),
        width: ({ chart }) => ((chart.chartArea || {}).width || 0) / 7 - 4,
        height: ({ chart }) => ((chart.chartArea || {}).height || 0) / weeks - 4,
      }],
    },
    options: {
      scales: {
        x: { type: 'category', labels: DAYS, position: 'top', offset: true, grid: { display: false }, ticks: { color: t.muted } },
        y: { type: 'linear', min: -0.5, max: weeks - 0.5, reverse: true, offset: false, display: false },
      },
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { title: items => new Date(items[0].raw.date + 'T00:00:00Z').toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric', timeZone: 'UTC' }),
                                label: item => `${d.measure}: ${fmt(item.raw.v)}` } },
      },
    },
    plugins: [{
      id: 'calendarDays',
      afterDatasetsDraw(chart) {
        const ctx = chart.ctx;
        ctx.save();
        ctx.font = `11px ${t.font}`;
        ctx.textAlign = 'left';
        ctx.textBaseline = 'top';
        chart.getDatasetMeta(0).data.forEach((el, i) => {
          const c = cells[i];
          const strong = c.v / max > 0.55;
          ctx.fillStyle = strong ? t.panel : t.muted;
          const { x, y, width, height } = el.getProps(['x', 'y', 'width', 'height'], true);
          ctx.fillText(String(c.day), x + 5, y + 4);
          if (c.v && height > 34) {
            ctx.font = `600 12px ${t.font}`;
            ctx.fillStyle = strong ? t.panel : t.text;
            ctx.fillText(fmt(c.v), x + 5, y + height - 18);
            ctx.font = `11px ${t.font}`;
          }
          void width;
        });
        ctx.restore();
      },
    }],
  };
}

// How many rows fall in each range: touching bars, labelled with their ranges.
function histogram(d, t) {
  const short = formatter(d.format, true);
  return {
    type: 'bar',
    data: {
      labels: d.points.map(([lo, hi]) => `${short(lo)}–${short(hi)}`),
      datasets: [{ label: d.measure, data: d.points.map(p => p[2]), backgroundColor: t.series[0],
                   barPercentage: 1, categoryPercentage: 0.96, borderRadius: 2 }],
    },
    options: {
      scales: {
        x: { grid: { display: false }, ticks: { color: t.muted, maxRotation: 45, autoSkip: true } },
        y: { beginAtZero: true, grid: { color: t.grid }, ticks: { color: t.muted, precision: 0 } },
      },
      plugins: { legend: { display: false } },
    },
  };
}

// The chance a value is exceeded: amount across, probability up. Thresholds mark probabilities.
function exceedance(d, t) {
  const short = formatter(d.format, true);
  const fmt = formatter(d.format);
  const annotations = {};
  d.thresholds.forEach((th, i) => {
    annotations['t' + i] = {
      type: 'line', scaleID: 'y', value: th.value, borderColor: t.tone(th.tone), borderWidth: 1.5, borderDash: [5, 4],
      label: { display: !!th.label, content: th.label, position: i % 2 ? 'start' : 'end', backgroundColor: t.tone(th.tone), color: t.panel, font: { size: 11 } },
    };
  });
  return {
    type: 'line',
    data: { datasets: [{ label: 'Chance of exceeding', data: d.points.map(([v, , p]) => ({ x: v, y: p })),
                         borderColor: t.series[0], backgroundColor: alpha(t.series[0], 0.12), fill: 'origin',
                         pointRadius: 0, borderWidth: 2, tension: 0.2 }] },
    options: {
      scales: {
        x: { type: 'linear', grid: { color: t.grid }, ticks: { color: t.muted, callback: short } },
        y: { min: 0, max: 100, grid: { color: t.grid }, ticks: { color: t.muted, callback: v => v + '%' } },
      },
      plugins: {
        legend: { display: false },
        annotation: { annotations },
        tooltip: { callbacks: { title: () => '', label: item => `${item.parsed.y.toFixed(1)}% chance of more than ${fmt(item.parsed.x)}` } },
      },
    },
  };
}

function treemap(d, t) {
  const short = formatter(d.format, true);
  const seriesLabel = k => (d.series.find(e => e.key === k) || {}).label || k;
  const tree = d.points.map(([x, s, v]) => ({ x: x === '__other__' ? 'Other' : (d.xLabels[x] ?? x), s: seriesLabel(s), v }));
  const grouped = d.series.length > 1;
  const colorOf = new Map(d.series.map((s, i) => [s.label, seriesColor(t, s, i)]));
  return {
    type: 'treemap',
    data: {
      datasets: [{
        label: d.measure, tree, key: 'v', groups: grouped ? ['s', 'x'] : ['x'], spacing: 1, borderWidth: 0,
        backgroundColor: c => {
          if (c.type !== 'data') return 'transparent';
          // A group box carries its group in `g`; a leaf only through its source rows.
          const raw = c.raw;
          const top = raw.l === 0 ? raw.g : ((raw._data.children || [])[0] || raw._data).s;
          const color = grouped ? (colorOf.get(top) || t.series[0]) : t.series[c.dataIndex % t.series.length];
          return alpha(color, grouped && c.raw.l === 0 ? 0.25 : 0.9);
        },
        labels: { display: true, overflow: 'hidden', color: t.panel, font: { size: 11 },
                  formatter: c => [c.raw.g, short(c.raw.v)] },
        captions: { display: grouped, color: t.text, font: { weight: '600' } },
      }],
    },
    options: { plugins: { legend: { display: false } } },
  };
}

function sankey(d, t) {
  const labels = {};
  const colors = {};
  d.categories.forEach((x, i) => { labels['f:' + x] = d.xLabels[x] ?? x; colors['f:' + x] = categoryColor(t, d, x, i); });
  d.series.forEach((s, i) => { labels['t:' + s.key] = s.label; colors['t:' + s.key] = seriesColor(t, s, i + 3); });
  return {
    type: 'sankey',
    data: {
      datasets: [{
        label: d.measure, labels,
        data: d.points.map(([x, s, v]) => ({ from: 'f:' + x, to: 't:' + s, flow: v })),
        colorFrom: c => colors[c.dataset.data[c.dataIndex].from],
        colorTo: c => colors[c.dataset.data[c.dataIndex].to],
        colorMode: 'gradient', alpha: 0.6, color: t.text, borderWidth: 0, nodeWidth: 12,
      }],
    },
    options: { plugins: { legend: { display: false } } },
  };
}

async function choropleth(d, t) {
  const countries = await worldMap();
  const values = new Map();
  d.points.forEach(([x, , v]) => values.set(String(x).toLowerCase(), v));
  const pick = f => values.get(String(f.properties.name).toLowerCase()) ?? values.get(String(Number(f.id)))
    ?? values.get(String(f.id));
  const base = t.series[0];
  return {
    type: 'choropleth',
    data: {
      labels: countries.map(f => f.properties.name),
      datasets: [{
        label: d.measure, outline: countries, borderColor: t.panel, borderWidth: 0.5,
        data: countries.map(f => ({ feature: f, value: pick(f) ?? 0 })),
      }],
    },
    options: {
      showOutline: true, showGraticule: false,
      scales: {
        projection: { axis: 'x', projection: 'equalEarth' },
        color: { axis: 'x', interpolate: v => v ? alpha(base, 0.12 + 0.88 * v) : t.grid, legend: { position: 'bottom-left', align: 'right' }, ticks: { color: t.muted } },
      },
      plugins: { legend: { display: false } },
    },
  };
}

async function configFor(d, month) {
  const t = theme();
  const fmt = formatter(d.format);
  let cfg;
  if (['bar', 'line', 'area'].includes(d.kind)) cfg = cartesian(d, t, fmt);
  else if (['pie', 'doughnut'].includes(d.kind)) cfg = pie(d, t);
  else if (d.kind === 'calendar') cfg = calendar(d, t, fmt, month);
  else if (d.kind === 'histogram') cfg = histogram(d, t);
  else if (d.kind === 'exceedance') cfg = exceedance(d, t);
  else if (d.kind === 'treemap') cfg = treemap(d, t);
  else if (d.kind === 'sankey') cfg = sankey(d, t);
  else cfg = await choropleth(d, t);
  const o = cfg.options;
  o.responsive = true;
  o.maintainAspectRatio = false;
  o.animation = { duration: 250 };
  o.plugins.legend = Object.assign({ labels: { color: t.text, boxWidth: 12, font: { family: t.font } } }, o.plugins.legend);
  o.plugins.tooltip = Object.assign({
    callbacks: { label: item => `${item.dataset.label}: ${fmt(item.parsed && typeof item.parsed === 'object' ? (item.parsed.y ?? item.parsed.x ?? item.raw.value) : item.raw)}` },
  }, o.plugins.tooltip);
  if (['pie', 'doughnut'].includes(d.kind)) {
    o.plugins.tooltip.callbacks = { label: item => `${item.label}: ${fmt(item.raw)}` };
  }
  if (d.kind === 'choropleth') {
    o.plugins.tooltip.callbacks = { label: item => `${item.raw.feature.properties.name}: ${fmt(item.raw.value)}` };
  }
  if (['calendar', 'exceedance'].includes(d.kind)) o.plugins.tooltip = cfg.options.plugins.tooltip;
  if (d.kind === 'treemap') o.plugins.tooltip.callbacks = { title: items => items[0].raw.g, label: item => fmt(item.raw.v) };
  if (d.kind === 'sankey') o.plugins.tooltip.callbacks = { label: item => { const p = item.raw; return `${item.dataset.labels[p.from]} → ${item.dataset.labels[p.to]}: ${fmt(p.flow)}`; } };
  return cfg;
}

function ltChart(config) {
  let chart = null;               // kept outside Alpine's reactivity: Chart.js mutates it
  return {
    loading: true,
    empty: false,
    error: '',
    zoomable: false,
    params: config.params,
    data: null,
    months: [],               // calendar: the months with data, and the one shown
    month: '',

    init() {
      this.$refs.box.style.height = this.$el.dataset.height + 'px';
      this.onGrid = e => {
        if (config.grid && e.detail.key === config.grid) {
          this.params = [e.detail.params, config.fixed].filter(Boolean).join('&');
          this.load();
        }
      };
      window.addEventListener('gridstate', this.onGrid);
      this.observer = new MutationObserver(() => this.draw());
      this.observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-mode'] });
      this.load();
    },
    destroy() {
      window.removeEventListener('gridstate', this.onGrid);
      this.observer.disconnect();
      if (chart) chart.destroy();
    },

    async load() {
      this.loading = true;
      try {
        const res = await fetch(`${config.endpoint}?${this.params}`, { headers: { Accept: 'application/json' } });
        const body = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(body.detail || `Could not load the chart (${res.status}).`);
        this.data = body;
        this.error = '';
        if (body.kind === 'calendar') {
          const { months, peak } = calendarMonths(body);
          this.months = months;
          if (!months.includes(this.month)) this.month = peak;
        }
        await this.draw();
      } catch (err) {
        this.error = err.message;
      }
      this.loading = false;
    },

    async draw() {
      const d = this.data;
      if (!d) return;
      this.empty = !d.points.length;
      if (chart) { chart.destroy(); chart = null; }
      if (this.empty) return;
      await libraries(d.kind);
      Chart.defaults.font.family = token('--font-ui');
      Chart.defaults.color = token('--text-2');
      chart = new Chart(this.$refs.canvas, await configFor(d, this.month));
      this.zoomable = d.x.type === 'time' && ['bar', 'line', 'area'].includes(d.kind);
    },

    resetZoom() { if (chart) chart.resetZoom(); },

    // Calendar: step to the previous (-1) or next (1) month that has data.
    stepMonth(step) {
      const i = this.months.indexOf(this.month) + step;
      if (i >= 0 && i < this.months.length) { this.month = this.months[i]; this.draw(); }
    },
    monthLabel() {
      return this.month ? new Date(this.month + '-01T00:00:00Z').toLocaleDateString(undefined, { month: 'long', year: 'numeric', timeZone: 'UTC' }) : '';
    },
  };
}
})();
