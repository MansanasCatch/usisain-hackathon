/*
 * UsisAIn cross-browser namespace shim.
 *
 * Chromium exposes `chrome.*`; Firefox and Safari expose `browser.*` (and an
 * alias `chrome.*`). This shim picks whichever is available and offers a tiny
 * feature check so callers never touch an API that the host browser lacks.
 */
(function (g) {
  "use strict";

  const api =
    typeof g.browser !== "undefined" && g.browser && g.browser.runtime
      ? g.browser
      : typeof g.chrome !== "undefined"
        ? g.chrome
        : undefined;

  /**
   * Returns true when a dotted API path (e.g. "tabs.captureVisibleTab")
   * exists on the active extension namespace.
   * @param {string} path
   * @returns {boolean}
   */
  function has(path) {
    if (!api) return false;
    let node = api;
    for (const part of path.split(".")) {
      if (node == null || !(part in node)) return false;
      node = node[part];
    }
    return node != null;
  }

  g.usisainExt = Object.freeze({
    api,
    has,
    menus: api ? api.contextMenus || api.menus : undefined,
  });
})(globalThis);
