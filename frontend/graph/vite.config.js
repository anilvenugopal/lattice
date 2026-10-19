import { svelte } from '@sveltejs/vite-plugin-svelte';
import { defineConfig } from 'vite';

// One ES module, CSS included, written straight into Lattice's static files.
export default defineConfig({
  plugins: [svelte({ compilerOptions: { customElement: true } })],
  // Library mode leaves process.env in dependencies; the browser has no `process`.
  define: { 'process.env.NODE_ENV': JSON.stringify('production') },
  build: {
    outDir: '../../lattice/static/js/vendor/graph',
    emptyOutDir: true,
    lib: { entry: 'src/main.js', formats: ['es'], fileName: () => 'lt-graph.js' },
    cssCodeSplit: false,
    minify: true,
    // Library builds keep whitespace by default; this file is only ever served, so minify it fully.
    rolldownOptions: { output: { minify: true } },
  },
});
