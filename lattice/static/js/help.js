// Mermaid diagrams on help pages, drawn with the theme's colours and redrawn
// when the theme changes. Loaded only on topics that contain a diagram.
(function () {
  const sources = new Map();

  function token(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function draw() {
    const blocks = [...document.querySelectorAll('pre.mermaid')];
    blocks.forEach(el => {
      if (!sources.has(el)) sources.set(el, el.textContent);
      el.removeAttribute('data-processed');
      el.textContent = sources.get(el);
    });
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: 'strict',
      theme: 'base',
      fontFamily: token('--font-ui'),
      themeVariables: {
        darkMode: document.documentElement.dataset.mode === 'dark',
        background: token('--surface-panel'),
        primaryColor: token('--surface-selected'),
        primaryBorderColor: token('--brand'),
        primaryTextColor: token('--text'),
        secondaryColor: token('--surface-recessed'),
        tertiaryColor: token('--surface-panel'),
        lineColor: token('--text-3'),
        textColor: token('--text'),
        noteBkgColor: token('--tone-warning-bg'),
        noteTextColor: token('--tone-warning-fg'),
      },
    });
    mermaid.run({ nodes: blocks });
  }

  document.addEventListener('DOMContentLoaded', draw);
  new MutationObserver(draw).observe(document.documentElement,
    { attributes: true, attributeFilter: ['data-mode'] });
})();
