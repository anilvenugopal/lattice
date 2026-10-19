// Alpine component for components/record_page.html. Server config comes from
// lattice/components/record.py render_record_page(). Actions run through the
// record's grid action endpoint, exactly as from the grid; after one, the page's
// #record section is fetched again so the header, details and history update.

(function () {
document.addEventListener('alpine:init', () => Alpine.data('recordPage', recordPage));

function recordPage(config) {
  return {
    dialog: { open: false, title: '', text: '', fields: [], values: {}, submit: '', tone: '', action: '', busy: false },

    run(key) {
      const a = config.actions[key];
      if (a.href) { window.location = a.href.replace(/\{id\}/g, encodeURIComponent(config.id)); return; }
      if (a.fields.length || a.confirm) {
        const values = {};
        a.fields.forEach(f => (values[f.name] = f.default || ''));
        this.dialog = { open: true, title: a.label, text: (a.confirm || '').replace('{count}', '1'),
                        fields: a.fields, values, submit: a.label, tone: a.tone, action: key, busy: false };
        this.$nextTick(() => {
          const first = this.$root.querySelector('.dialog .input');
          (first || this.$refs.dialogSubmit).focus();
        });
        return;
      }
      this.execute(key, {});
    },
    async execute(key, values) {
      try {
        const res = await app.post(`${config.endpoint}/action/${key}`, { ids: [config.id], values });
        app.toast(res.message, res.tone);
        if (res.redirect) { window.location = res.redirect; return true; }
        await this.refresh();
        return true;
      } catch (err) {
        app.toast(err.message, 'danger');
        return false;
      }
    },
    // Fetch the page again and swap in its #record. A record the action removed from the
    // grid's query (deleted, or moved out of the user's rows) answers 404: back to the list.
    async refresh() {
      const res = await fetch(window.location.href, { credentials: 'same-origin' });
      if (res.status === 404) { window.location = config.back; return; }
      const fresh = new DOMParser().parseFromString(await res.text(), 'text/html').getElementById('record');
      if (!fresh) { window.location.reload(); return; }
      this.$root.replaceWith(fresh);
      htmx.process(fresh);
    },
    async submitDialog() {
      const d = this.dialog;
      const missing = d.fields.filter(f => f.required && !d.values[f.name]).map(f => f.label);
      if (missing.length) { app.toast('Required: ' + missing.join(', '), 'warning'); return; }
      d.busy = true;
      const ok = await this.execute(d.action, d.values);
      d.busy = false;
      if (ok) d.open = false;
    },
  };
}
})();
