// Alpine component for the folder_picker macro (components/macros.html, ADR 0017): browse a
// mounted share one folder at a time through GET /attachments/folders/{store}?path=, create a
// folder, and choose one. The value is "{store}:{path}".

(function () {
document.addEventListener('alpine:init', () => Alpine.data('ltFolder', ltFolder));

async function getJson(url) {
  const res = await fetch(url, { headers: { Accept: 'application/json' } });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `Could not open the folder (${res.status}).`);
  return body;
}

function ltFolder(config) {
  return {
    value: config.value, text: config.text,
    open: false, loading: false, error: '', newName: '',
    stores: [], store: '', path: '', crumbs: [], folders: [],

    async browse() {
      this.open = true;
      this.error = '';
      try {
        if (!this.stores.length) this.stores = (await getJson('/attachments/folders')).stores;
        if (!this.stores.length) { this.error = 'No shared folders are set up on this site.'; return; }
        const [key, ...rest] = (this.value || '').split(':');
        const known = this.stores.some(s => s.key === key);
        await this.go(known ? key : this.stores[0].key, known ? rest.join(':') : '');
      } catch (err) { this.error = err.message; }
    },
    async go(store, path) {
      this.loading = true;
      this.error = '';
      try {
        const here = await getJson(`/attachments/folders/${encodeURIComponent(store)}?path=${encodeURIComponent(path)}`);
        Object.assign(this, { store: here.store, path: here.path, crumbs: here.crumbs, folders: here.folders });
      } catch (err) {
        this.error = err.message;
        if (path) await this.go(store, '');          // a folder that is gone: start at the top
      }
      this.loading = false;
    },
    async create() {
      try {
        const made = await app.post(`/attachments/folders/${encodeURIComponent(this.store)}/new`,
                                    { path: this.path, name: this.newName.trim() });
        this.newName = '';
        await this.go(this.store, made.path);
      } catch (err) { this.error = err.message; }
    },
    choose() {
      this.value = `${this.store}:${this.path}`;
      this.text = this.crumbs.map(c => c.name).join(' / ');
      this.open = false;
      this.$nextTick(() => this.$el.dispatchEvent(new Event('change', { bubbles: true })));
    },
    clear() {
      this.value = '';
      this.text = '';
      this.$nextTick(() => this.$el.dispatchEvent(new Event('change', { bubbles: true })));
    },
  };
}
})();
