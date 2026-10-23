// Plain text only. Callers assign the result through textContent, never HTML.
export function formatDetails(value) {
  const label = key => {
    const words = String(key).replaceAll("_", " ");
    return words.charAt(0).toUpperCase() + words.slice(1);
  };
  const scalar = item => item === null ? "Not recorded"
    : item === true ? "Yes" : item === false ? "No" : String(item);
  function lines(item, indent = "") {
    if (Array.isArray(item)) {
      if (!item.length) return [`${indent}None`];
      return item.flatMap(entry => typeof entry === "object" && entry !== null
        ? [`${indent}-`, ...lines(entry, indent + "  ")]
        : [`${indent}- ${scalar(entry)}`]);
    }
    if (item !== null && typeof item === "object") {
      return Object.entries(item).flatMap(([key, entry]) => typeof entry === "object" && entry !== null
        ? [`${indent}${label(key)}:`, ...lines(entry, indent + "  ")]
        : [`${indent}${label(key)}: ${scalar(entry)}`]);
    }
    return [`${indent}${scalar(item)}`];
  }
  return lines(value).join("\n");
}
