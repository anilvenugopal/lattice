<svelte:options customElement={{ tag: 'lt-graph', props: { spec: { type: 'String' } } }} />

<!--
  <lt-graph spec='{…}'>: a DAG laid out with dagre and drawn with Svelte Flow.
  The spec comes from lattice/components/flows.py build_graph(). Colours are Lattice's
  CSS tokens, which reach into the shadow root, so light and dark mode just work.
  Click or Enter selects a node and shows its actions; double-click opens its record.
-->
<script>
  import dagre from '@dagrejs/dagre';
  import { Background, Controls, MiniMap, SvelteFlow } from '@xyflow/svelte';
  import xyCss from '@xyflow/svelte/dist/style.css?inline';
  import ownCss from './graph.css?inline';
  import LtNode from './LtNode.svelte';

  let { spec = '{}' } = $props();
  const host = $host();
  const W = 190, H = 58;

  let data = $derived(JSON.parse(spec || '{}'));
  let nodes = $state.raw([]);
  let edges = $state.raw([]);
  let selected = $state(null);
  let confirming = $state(null);
  let busy = $state(false);

  $effect(() => {
    const d = data;
    const horizontal = (d.direction || 'LR') === 'LR';
    const g = new dagre.graphlib.Graph();
    g.setGraph({ rankdir: d.direction || 'LR', nodesep: 24, ranksep: 56, marginx: 8, marginy: 8 });
    g.setDefaultEdgeLabel(() => ({}));
    (d.nodes || []).forEach(n => g.setNode(n.id, { width: W, height: H }));
    (d.edges || []).forEach(e => g.setEdge(e.source, e.target));
    dagre.layout(g);
    nodes = (d.nodes || []).map(n => {
      const p = g.node(n.id);
      return { id: n.id, type: 'lt', data: { ...n, horizontal }, position: { x: p.x - W / 2, y: p.y - H / 2 } };
    });
    edges = (d.edges || []).map((e, i) => ({
      id: `e${i}`, source: e.source, target: e.target, label: e.label || undefined,
      animated: !!e.animated, type: 'smoothstep',
    }));
    selected = null;
  });

  const height = host?.dataset?.height || 480;
  const nodeTypes = { lt: LtNode };

  function select(node) { selected = node ? node.data : null; confirming = null; }
  function open(node) { if (node?.data?.href) window.location = node.data.href; }

  async function run(key) {
    const action = data.actions[key];
    if (action.confirm && confirming !== key) { confirming = key; return; }
    busy = true;
    try {
      const res = await window.app.post(`${data.endpoint}/action/${key}`, { ids: [selected.id], values: {} });
      const event = new CustomEvent('lt-graph-action', { bubbles: true, composed: true, cancelable: true,
                                                         detail: { action: key, id: selected.id, result: res } });
      if (res.redirect) { window.location = res.redirect; return; }
      if (host.dispatchEvent(event)) window.app.toastAfterReload(res.message, res.tone);
      else window.app.toast(res.message, res.tone);
    } catch (err) {
      window.app.toast(err.message, 'danger');
    }
    busy = false;
    confirming = null;
  }
</script>

{@html `<style>${xyCss}${ownCss}</style>`}
<div class="lt-graph" style:height="{height}px">
  <SvelteFlow bind:nodes bind:edges {nodeTypes} fitView fitViewOptions={{ maxZoom: 1 }} minZoom={0.1} nodesDraggable={false}
              nodesConnectable={false} elementsSelectable={true} proOptions={{ hideAttribution: true }}
              onnodeclick={({ node }) => select(node)} onpaneclick={() => select(null)}
              onselectionchange={({ nodes: chosen }) => select(chosen[0])}>
    <Background gap={18} />
    <Controls showLock={false} />
    {#if nodes.length > 30}<MiniMap pannable zoomable />{/if}
  </SvelteFlow>

  {#if selected}
  <div class="lt-graph__panel" role="dialog" aria-label={selected.label}>
    <div class="lt-graph__title">{selected.label}</div>
    {#if selected.note}<div class="lt-graph__note">{selected.note}</div>{/if}
    <div class="lt-graph__actions">
      {#if selected.href}<a class="lt-btn" href={selected.href}>Open</a>{/if}
      {#each selected.actions as key}
        {#if confirming === key}
          <span class="lt-graph__confirm">{data.actions[key].confirm}</span>
          <button class="lt-btn lt-btn--{data.actions[key].tone}" disabled={busy} onclick={() => run(key)}>Yes, {data.actions[key].label.toLowerCase()}</button>
          <button class="lt-btn" onclick={() => (confirming = null)}>Cancel</button>
        {:else}
          <button class="lt-btn lt-btn--{data.actions[key].tone}" disabled={busy} onclick={() => run(key)}>{data.actions[key].label}</button>
        {/if}
      {/each}
    </div>
  </div>
  {/if}
</div>
<svelte:window ondblclick={(e) => {
  const el = e.composedPath().find(t => t?.dataset?.id && t.classList?.contains('svelte-flow__node'));
  if (el) open(nodes.find(n => n.id === el.dataset.id));
}} onkeydown={(e) => {
  if (e.key === 'Enter' && selected?.href && e.composedPath()[0]?.classList?.contains('svelte-flow__node')) {
    window.location = selected.href;
  }
}} />
