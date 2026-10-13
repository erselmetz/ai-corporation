"use strict";

function createDisplayMediaRequestHandler({ getSources, chooseSource, isTrusted }) {
  if (typeof getSources !== "function" || typeof chooseSource !== "function"
      || typeof isTrusted !== "function") {
    throw new TypeError("Screen capture handlers require source, chooser, and trust functions");
  }
  return async (request, callback) => {
    let responded = false;
    const finish = (result) => {
      if (responded) return;
      responded = true;
      callback(result);
    };
    try {
      if (!isTrusted(request)) return finish(null);
      const sources = await getSources();
      if (!Array.isArray(sources) || sources.length === 0
          || sources.some((source) => typeof source?.id !== "string" || !source.id)) {
        return finish(null);
      }
      const selected = await chooseSource(sources, request);
      if (!selected || !sources.some((source) => source.id === selected.id)) {
        return finish(null);
      }
      return finish({ video: selected });
    } catch {
      return finish(null);
    }
  };
}

module.exports = { createDisplayMediaRequestHandler };
