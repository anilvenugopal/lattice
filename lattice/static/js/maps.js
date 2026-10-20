// Alpine component for components/map.html. Server config comes from
// lattice/components/map/render.py build_map(); the layers from GET /_map/{key}/data
// (lattice/components/map/engine.py). See lattice/help/developer/building-apps/maps.md.
//
// MapLibre and its helpers (static/js/vendor/map/) load on first use. With the self-hosted
// basemap (`make maps`) the background is a Protomaps map in the theme's flavour; without
// it, US states and counties drawn from static/maps/ in the --map-* tokens. Data colours
// come from the --chart-* tokens, and the map is redrawn when the theme changes.

(function () {
document.addEventListener('alpine:init', () => Alpine.data('ltMap', ltMap));

const VENDOR = '/static/js/vendor/map/';
const scripts = {};
let library = null;
const boundaries = {};
const US = [[-125, 24], [-66.5, 49.5]];

function script(name) {
  if (!scripts[name]) {
    scripts[name] = new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = VENDOR + name;
      s.onload = resolve;
      s.onerror = () => reject(new Error('Could not load the map library.'));
      document.head.appendChild(s);
    });
  }
  return scripts[name];
}

async function load(withBasemap) {
  if (!library) {
    const css = document.createElement('link');
    css.rel = 'stylesheet';
    css.href = VENDOR + 'maplibre-gl.css';
    document.head.appendChild(css);
    library = Promise.all([import(VENDOR + 'maplibre-gl.mjs'), script('h3.js'), script('topojson.js')])
      .then(([maplibre]) => maplibre);
  }
  const maplibre = await library;
  if (withBasemap) {
    await script('pmtiles.js');
    await script('basemaps.js');
    if (!load.protocol) {
      load.protocol = new pmtiles.Protocol();
      maplibre.addProtocol('pmtiles', load.protocol.tile);
    }
  }
  return maplibre;
}

async function boundary(name) {
  if (!boundaries[name]) {
    const file = name === 'us-counties' ? 'counties-10m.json' : 'states-10m.json';
    const object = name === 'us-counties' ? 'counties' : 'states';
    boundaries[name] = fetch('/static/maps/' + file).then(r => r.json())
      .then(topo => topojson.feature(topo, topo.objects[object]));
  }
  return boundaries[name];
}

// ── Theme ──────────────────────────────────────────────────────────────────
function token(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
function dark() { return document.documentElement.dataset.mode === 'dark'; }
function palette() { return [1, 2, 3, 4, 5, 6, 7, 8].map(i => token(`--chart-${i}`)); }
function toneColor(t) { return token(`--chart-${t}`) || token('--chart-1'); }
function format(kind) {
  const n = new Intl.NumberFormat(undefined, { notation: 'compact', maximumFractionDigits: 1 });
  if (kind === 'money') return v => '$' + n.format(v);
  if (kind === 'percent') return v => n.format(v) + '%';
  return v => n.format(v);
}

function style(basemap) {
  if (basemap) {
    const flavor = dark() ? 'dark' : 'light';
    return {
      version: 8,
      glyphs: '/static/maps/basemap/fonts/{fontstack}/{range}.pbf',
      sprite: `${location.origin}/static/maps/basemap/sprites/v4/${flavor}`,
      sources: { protomaps: { type: 'vector', url: `pmtiles://${location.origin}${basemap}`,
                              attribution: '© <a href="https://openstreetmap.org">OpenStreetMap</a> contributors' } },
      layers: basemaps.layers('protomaps', basemaps.namedFlavor(flavor), { lang: 'en' }),
    };
  }
  return { version: 8, sources: {}, layers: [{ id: 'water', type: 'background', paint: { 'background-color': token('--map-water') } }] };
}

// A ramp from faint to strong in one colour, over the layer's values.
function ramp(values, color) {
  const max = Math.max(1, ...values);
  return ['interpolate', ['linear'], ['coalesce', ['get', 'v'], 0],
          0, 'rgba(0,0,0,0)', max * 0.0001, colorAlpha(color, 0.12), max, colorAlpha(color, 0.85)];
}
function colorAlpha(hex, a) {
  const m = /^#([0-9a-f]{6})$/i.exec(hex);
  if (!m) return hex;
  const n = parseInt(m[1], 16);
  return `rgba(${n >> 16}, ${(n >> 8) & 255}, ${n & 255}, ${a})`;
}

function ltMap(config) {
  let map = null;                 // outside Alpine's reactivity: MapLibre mutates it
  let popup = null;
  let draw = null;                // Terra Draw, made on the first drawing
  return {
    config, loading: true, error: '', note: '', legend: [],
    params: config.params, data: null, mode: '', shaped: new URLSearchParams(config.params).has('shape'),

    init() {
      this.$refs.canvas.style.height = this.$el.dataset.height + 'px';
      this.onGrid = e => {
        if (config.grid && e.detail.key === config.grid) {
          this.params = [e.detail.params, config.fixed].filter(Boolean).join('&');
          this.shaped = new URLSearchParams(this.params).has('shape');
          if (!this.shaped && draw) draw.clear();          // cleared from the grid's chip
          if (!this.shaped && map && map.getLayer('lt-shape')) { map.removeLayer('lt-shape'); map.removeSource('lt-shape'); }
          this.fetchData();
        }
      };
      window.addEventListener('gridstate', this.onGrid);
      this.observer = new MutationObserver(() => this.redraw(true));
      this.observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-mode'] });
      this.fetchData();
    },
    destroy() {
      window.removeEventListener('gridstate', this.onGrid);
      this.observer.disconnect();
      if (map) map.remove();
    },

    async fetchData() {
      this.loading = true;
      try {
        const res = await fetch(`${config.endpoint}?${this.params}`, { headers: { Accept: 'application/json' } });
        const body = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(body.detail || `Could not load the map (${res.status}).`);
        this.data = body;
        this.error = '';
        await this.redraw(false);
      } catch (err) {
        this.error = err.message;
      }
      this.loading = false;
    },

    // Build the map once (again after a theme change), then (re)fill its layers.
    async redraw(rebuild) {
      if (!this.data) return;
      const maplibre = await load(!!config.basemap);
      if (map && rebuild) { if (draw) { draw.stop(); draw = null; } map.remove(); map = null; }
      if (!map) {
        map = new maplibre.Map({ container: this.$refs.canvas, style: style(config.basemap), bounds: US,
                                 attributionControl: config.basemap ? { compact: true } : false });
        map.addControl(new maplibre.NavigationControl({ showCompass: false }), 'top-right');
        popup = new maplibre.Popup({ closeButton: false, maxWidth: '280px' });
        await new Promise(resolve => map.once('load', resolve));
        if (!config.basemap) await this.outlines();
        this.fitted = false;
      }
      await this.fill(maplibre);
      this.showShape();
    },

    // ── Drawing a shape to filter the linked grid ───────────────────────────
    async drawMode(mode) {
      const maplibre = await load(!!config.basemap);
      await script('terra-draw.js');
      await script('terra-draw-maplibre.js');
      if (!draw) {
        const color = token('--accent');
        const styles = { fillColor: color, outlineColor: color, fillOpacity: 0.15, outlineWidth: 2 };
        draw = new terraDraw.TerraDraw({
          adapter: new terraDrawMaplibreGlAdapter.TerraDrawMapLibreGLAdapter({ map, lib: maplibre }),
          modes: [new terraDraw.TerraDrawPolygonMode({ styles }), new terraDraw.TerraDrawRectangleMode({ styles }),
                  new terraDraw.TerraDrawCircleMode({ styles })],
        });
        draw.start();
        draw.on('finish', id => {
          const shape = draw.getSnapshot().find(f => f.id === id);
          for (const f of draw.getSnapshot()) if (f.id !== id) draw.removeFeatures([f.id]);
          this.mode = '';
          draw.setMode('static');
          window.dispatchEvent(new CustomEvent('mapshape', { detail: { key: config.grid, shape: shape.geometry } }));
        });
      }
      if (map.getLayer('lt-shape')) { map.removeLayer('lt-shape'); map.removeSource('lt-shape'); }
      this.mode = this.mode === mode ? '' : mode;
      draw.setMode(this.mode || 'static');
    },
    clearShape() {
      if (draw) draw.clear();
      if (map && map.getLayer('lt-shape')) { map.removeLayer('lt-shape'); map.removeSource('lt-shape'); }
      window.dispatchEvent(new CustomEvent('mapshape', { detail: { key: config.grid, shape: null } }));
    },
    // A shape already in the page address (a saved view, a shared link): outline it.
    showShape() {
      const raw = new URLSearchParams(this.params).get('shape');
      if (!raw || (draw && draw.getSnapshot().length) || map.getLayer('lt-shape')) return;
      map.addSource('lt-shape', { type: 'geojson', data: { type: 'Feature', properties: {}, geometry: JSON.parse(raw) } });
      map.addLayer({ id: 'lt-shape', type: 'line', source: 'lt-shape', paint: { 'line-color': token('--accent'), 'line-width': 2, 'line-dasharray': [2, 2] } });
    },

    async outlines() {
      const states = await boundary('us-states');
      map.addSource('lt-states', { type: 'geojson', data: states });
      map.addLayer({ id: 'lt-land', type: 'fill', source: 'lt-states', paint: { 'fill-color': token('--map-land') } });
      map.addLayer({ id: 'lt-state-lines', type: 'line', source: 'lt-states', paint: { 'line-color': token('--map-line'), 'line-width': 1 } });
    },

    async fill(maplibre) {
      const fmt = format(this.data.format);
      const colors = palette();
      const bounds = new maplibre.LngLatBounds();
      for (const layer of map.getStyle().layers.filter(l => l.id.startsWith('lt-d-'))) map.removeLayer(layer.id);
      for (const id of Object.keys(map.getStyle().sources).filter(s => s.startsWith('lt-d-'))) map.removeSource(id);
      this.legend = [];
      this.note = '';
      for (const [i, layer] of this.data.layers.entries()) {
        const id = `lt-d-${layer.id}`;
        const color = layer.kind === 'areas' ? toneColor(layer.tone) : colors[i % colors.length];
        let features = [];
        if (layer.kind === 'points') {
          const tones = layer.tones || {};
          const keys = [...new Set(layer.rows.map(r => r[2]))];
          const pick = k => (tones[k] ? toneColor(tones[k]) : colors[keys.indexOf(k) % colors.length]);
          features = layer.rows.map(([lon, lat, c, label]) => ({
            type: 'Feature', geometry: { type: 'Point', coordinates: [lon, lat] },
            properties: { c, color: pick(c), label: layer.labels[c] ? `${label} · ${layer.labels[c]}` : label } }));
          map.addSource(id, { type: 'geojson', data: { type: 'FeatureCollection', features } });
          map.addLayer({ id, type: 'circle', source: id, paint: {
            'circle-color': ['get', 'color'], 'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, 2, 10, 5],
            'circle-stroke-width': 0.5, 'circle-stroke-color': token('--surface-panel') } });
          if (layer.truncated) this.note = `Showing the first ${layer.rows.length.toLocaleString()} locations.`;
        } else if (layer.kind === 'hexagons') {
          features = Object.entries(layer.values).map(([cell, v]) => ({
            type: 'Feature', properties: { v, label: `${layer.measure}: ${fmt(v)}` },
            geometry: { type: 'Polygon', coordinates: [h3.cellToBoundary(cell, true)] } }));
          map.addSource(id, { type: 'geojson', data: { type: 'FeatureCollection', features } });
          map.addLayer({ id, type: 'fill', source: id, paint: { 'fill-color': ramp(features.map(f => f.properties.v), color), 'fill-outline-color': colorAlpha(color, 0.5) } });
        } else if (layer.kind === 'regions') {
          const shapes = await boundary(layer.map);
          features = shapes.features.filter(f => f.id in layer.values).map(f => ({
            ...f, properties: { v: layer.values[f.id], label: `${f.properties.name}: ${fmt(layer.values[f.id])}` } }));
          map.addSource(id, { type: 'geojson', data: { type: 'FeatureCollection', features } });
          map.addLayer({ id, type: 'fill', source: id, paint: { 'fill-color': ramp(features.map(f => f.properties.v), color) } });
          map.addLayer({ id: id + '-line', type: 'line', source: id, paint: { 'line-color': token('--map-line'), 'line-width': 0.5 } });
        } else if (layer.kind === 'areas') {
          features = (layer.geojson.features || []).map(f => ({ ...f, properties: { ...(f.properties || {}), label: (f.properties || {}).name || layer.title } }));
          map.addSource(id, { type: 'geojson', data: { type: 'FeatureCollection', features } });
          map.addLayer({ id, type: 'fill', source: id, paint: { 'fill-color': colorAlpha(color, 0.12) } });
          map.addLayer({ id: id + '-line', type: 'line', source: id, paint: { 'line-color': color, 'line-width': 2, 'line-dasharray': [3, 2] } });
        }
        this.legend.push({ id, title: layer.title || layer.measure || 'Layer', color, visible: true });
        map.on('mousemove', id, e => {
          map.getCanvas().style.cursor = 'pointer';
          popup.setLngLat(e.lngLat).setText(e.features[0].properties.label).addTo(map);
        });
        map.on('mouseleave', id, () => { map.getCanvas().style.cursor = ''; popup.remove(); });
        for (const f of features) extend(bounds, f.geometry);
      }
      if (!this.fitted && !bounds.isEmpty()) {
        map.fitBounds(bounds, { padding: 32, maxZoom: 11, duration: 0 });
        this.fitted = true;
      }
    },

    toggle(id, visible) {
      const value = visible ? 'visible' : 'none';
      for (const layerId of [id, id + '-line']) if (map.getLayer(layerId)) map.setLayoutProperty(layerId, 'visibility', value);
      this.legend.find(l => l.id === id).visible = visible;
    },
  };
}

function extend(bounds, geometry) {
  const walk = c => (typeof c[0] === 'number' ? bounds.extend(c) : c.forEach(walk));
  if (geometry) walk(geometry.coordinates);
}
})();
