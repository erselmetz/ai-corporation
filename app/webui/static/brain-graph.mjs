const MAX_RENDER_NODES = 320;
const MAX_RENDER_EDGES = 480;
const RETRIEVAL_SESSION_KEY = "ersel-brain-retrieval-v1";

export function layoutBrainGraph(graph) {
  const nodes = Array.isArray(graph?.nodes) ? graph.nodes : [];
  const clusters = [...new Set(nodes.map(node => String(node.cluster || "note")))].sort();
  const clusterPositions = new Map(clusters.map((cluster, index) => {
    const angle = clusters.length ? (Math.PI * 2 * index) / clusters.length : 0;
    return [cluster, { x: Math.cos(angle) * 2.2, y: Math.sin(angle) * 1.35, z: Math.sin(angle * 2) * 0.65 }];
  }));
  const groupCounts = new Map();
  const positioned = nodes.map(node => {
    const cluster = String(node.cluster || "note");
    const center = clusterPositions.get(cluster) || { x: 0, y: 0, z: 0 };
    const index = groupCounts.get(cluster) || 0;
    groupCounts.set(cluster, index + 1);
    const angle = index * Math.PI * (3 - Math.sqrt(5));
    const spread = 0.18 + 0.1 * Math.sqrt(index);
    return { ...node, x: center.x + Math.cos(angle) * spread,
      y: center.y + Math.sin(angle) * spread, z: center.z + ((index % 5) - 2) * 0.11 };
  });
  const rendered = positioned.slice(0, MAX_RENDER_NODES);
  const renderedIds = new Set(rendered.map(node => node.id));
  const edges = (Array.isArray(graph?.edges) ? graph.edges : [])
    .filter(edge => edge.kind === "same-source" && renderedIds.has(edge.from) && renderedIds.has(edge.to))
    .slice(0, MAX_RENDER_EDGES);
  return { nodes: rendered, allNodes: positioned, edges,
    omitted: Math.max(0, positioned.length - rendered.length), basis: graph?.basis || "Derived file-type/note groups" };
}

export function readLastBrainRetrieval(storage) {
  if (!storage) return { retrieved: [], cited: [] };
  try {
    const raw = storage.getItem(RETRIEVAL_SESSION_KEY);
    storage.removeItem(RETRIEVAL_SESSION_KEY);
    const event = JSON.parse(raw || "{}");
    const normalize = values => Array.isArray(values)
      ? values.filter(value => typeof value === "string" && value.length <= 300).slice(0, 5) : [];
    return { retrieved: normalize(event.retrieved), cited: normalize(event.cited) };
  } catch { return { retrieved: [], cited: [] }; }
}

export function recordLastBrainRetrieval(storage, trace) {
  if (!storage) return false;
  const sources = Array.isArray(trace?.sources) ? trace.sources
    : Array.isArray(trace?.retrieval?.returned_chunks) ? trace.retrieval.returned_chunks : [];
  const references = sources.map(source => source?.chunk_reference)
    .filter(reference => typeof reference === "string" && reference.length <= 280).slice(0, 5);
  try {
    if (!references.length) { storage.removeItem(RETRIEVAL_SESSION_KEY); return false; }
    storage.setItem(RETRIEVAL_SESSION_KEY, JSON.stringify({ retrieved: references, cited: references }));
    return true;
  } catch { return false; }
}

export const MAX_BRAIN_RENDER_NODES = MAX_RENDER_NODES;
