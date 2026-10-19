<!-- One node: label, note and a tone stripe; handles on the sides the layout uses. -->
<script>
  import { Handle, Position } from '@xyflow/svelte';
  let { data, selected = false } = $props();
</script>

<div class="lt-node tone-{data.tone}" class:is-selected={selected}>
  <Handle type="target" position={data.horizontal ? Position.Left : Position.Top} />
  <div class="lt-node__label">{data.label}</div>
  {#if data.note}<div class="lt-node__note">{data.note}</div>{/if}
  <Handle type="source" position={data.horizontal ? Position.Right : Position.Bottom} />
</div>
