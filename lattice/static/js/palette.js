// Ctrl+J palette (base/shell.html, components/palette_body.html, lattice/components/search/providers.py).
// The component sits inside the shell component, so it uses the shell's
// closePalette(), setTheme() and shortcutsOpen.

(function () {
document.addEventListener('alpine:init', () => Alpine.data('palette', () => ({
  provider: '',
  index: 0,
  previewTimer: null,

  init() {
    window.addEventListener('palette-open', () => this.reset());
  },
  reset() {
    this.provider = '';
    this.$refs.input.value = '';
    this.$refs.input.focus();
    this.search();
  },

  async search() {
    const params = new URLSearchParams({ q: this.$refs.input.value, provider: this.provider });
    await htmx.ajax('GET', `/_search?${params}`, { target: this.$refs.body, swap: 'innerHTML' });
    this.highlight(0);
  },
  setProvider(key) {
    this.provider = key;
    this.$refs.input.focus();
    this.search();
  },
  cycleProvider(step) {
    const keys = [...this.$refs.body.querySelectorAll('[data-provider]')].map(b => b.dataset.provider);
    if (!keys.length) return;
    this.setProvider(keys[(keys.indexOf(this.provider) + step + keys.length) % keys.length]);
  },

  items() { return [...this.$refs.body.querySelectorAll('[data-palette-item]')]; },
  highlight(i) {
    const items = this.items();
    clearTimeout(this.previewTimer);
    if (!items.length) { this.index = 0; this.showPreview(null); return; }
    this.index = (i + items.length) % items.length;
    items.forEach((el, n) => el.classList.toggle('is-active', n === this.index));
    items[this.index].scrollIntoView({ block: 'nearest' });
    // Short delay so holding an arrow key does not request every preview.
    this.previewTimer = setTimeout(() => this.showPreview(items[this.index]), 120);
  },
  hover(el) {
    const i = this.items().indexOf(el);
    if (i !== this.index) this.highlight(i);
  },
  showPreview(item) {
    if (!item) {
      this.$refs.preview.replaceChildren(this.$refs.previewEmpty.content.cloneNode(true));
      return;
    }
    htmx.ajax('GET', item.dataset.preview, { target: this.$refs.preview, swap: 'innerHTML' });
  },

  open(item) {
    if (item.dataset.command) this.runCommand(item.dataset.command);
    else window.location = item.getAttribute('href');
  },
  // One branch per key in lattice/components/search/providers.py COMMANDS.
  runCommand(key) {
    this.closePalette();
    const theme = key.match(/^theme-(\w+)$/);
    if (theme) this.setTheme(theme[1]);
    else if (key === 'preferences') window.location = '/account/preferences';
    else if (key === 'shortcuts') this.shortcutsOpen = true;
    else if (key === 'signout') app.signOut();
  },

  onKey(e) {
    if (e.key === 'ArrowDown') { e.preventDefault(); this.highlight(this.index + 1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); this.highlight(this.index - 1); }
    else if (e.key === 'Tab') { e.preventDefault(); this.cycleProvider(e.shiftKey ? -1 : 1); }
    else if (e.key === 'Escape') { e.preventDefault(); this.closePalette(); }
    else if (e.key === 'Enter') {
      const item = this.items()[this.index];
      if (item) { e.preventDefault(); this.open(item); }
    }
  },
})));
})();
