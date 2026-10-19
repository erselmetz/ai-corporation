const inlineTokens = /(`[^`\n]+`|\*\*[^*\n]+\*\*)/g;

function appendInline(parent, text, documentRef) {
  for (const part of String(text).split(inlineTokens)) {
    if (!part) continue;
    if (part.startsWith("**") && part.endsWith("**")) {
      const strong = documentRef.createElement("strong");
      strong.textContent = part.slice(2, -2);
      parent.append(strong);
    } else if (part.startsWith("`") && part.endsWith("`")) {
      const code = documentRef.createElement("code");
      code.textContent = part.slice(1, -1);
      parent.append(code);
    } else {
      parent.append(documentRef.createTextNode(part));
    }
  }
}

export function renderSafeMarkdown(value, {
  documentRef = document,
  navigatorRef = globalThis.navigator,
} = {}) {
  const root = documentRef.createElement("div");
  root.className = "chat-markdown";
  const source = String(value ?? "").slice(0, 32768);
  const lines = source.split(/\r?\n/);
  let paragraph = [];
  let list = null;
  let codeLines = null;
  const flushParagraph = () => {
    if (!paragraph.length) return;
    const p = documentRef.createElement("p");
    appendInline(p, paragraph.join(" "), documentRef);
    root.append(p);
    paragraph = [];
  };
  const flushList = () => { if (list) { root.append(list); list = null; } };
  for (const line of lines) {
    if (line.startsWith("```")) {
      flushParagraph(); flushList();
      if (codeLines) {
        const block = documentRef.createElement("div"); block.className = "chat-code-block";
        const pre = documentRef.createElement("pre"); const code = documentRef.createElement("code");
        code.textContent = codeLines.join("\n"); pre.append(code);
        const copy = documentRef.createElement("button"); copy.type = "button"; copy.className = "chat-code-copy";
        copy.textContent = "Copy"; copy.setAttribute("aria-label", "Copy code block");
        copy.addEventListener("click", async () => {
          try { await navigatorRef?.clipboard?.writeText?.(code.textContent); copy.textContent = "Copied"; }
          catch { copy.textContent = "Copy unavailable"; }
        });
        block.append(pre, copy); root.append(block); codeLines = null;
      } else codeLines = [];
      continue;
    }
    if (codeLines) { codeLines.push(line); continue; }
    const heading = /^(#{1,3})\s+(.+)$/.exec(line);
    const unordered = /^\s*[-*+]\s+(.+)$/.exec(line);
    const ordered = /^\s*\d+[.)]\s+(.+)$/.exec(line);
    if (!line.trim()) { flushParagraph(); flushList(); continue; }
    if (heading) {
      flushParagraph(); flushList();
      const node = documentRef.createElement(`h${heading[1].length}`); appendInline(node, heading[2], documentRef); root.append(node); continue;
    }
    if (unordered || ordered) {
      flushParagraph();
      const type = unordered ? "ul" : "ol";
      if (!list || list.tagName?.toLowerCase() !== type) { flushList(); list = documentRef.createElement(type); }
      const item = documentRef.createElement("li"); appendInline(item, (unordered || ordered)[1], documentRef); list.append(item); continue;
    }
    flushList(); paragraph.push(line);
  }
  flushParagraph(); flushList();
  if (codeLines) {
    const pre = documentRef.createElement("pre"); const code = documentRef.createElement("code");
    code.textContent = codeLines.join("\n"); pre.append(code); root.append(pre);
  }
  return root;
}
