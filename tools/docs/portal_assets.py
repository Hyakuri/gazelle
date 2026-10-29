"""Static CSS and JavaScript for the generated project overview page."""

MERMAID_URL = "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js"
FONTS_URL = ("https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500"
             "&family=IBM+Plex+Sans+Condensed:wght@500;600&family=Noto+Sans+SC:wght@400;500;700&display=swap")

CSS = r"""
:root {
  /* Layout: sticky top bar with a heat-ramp rule, an index rail on wide screens, one column below 960px.
     Palette: cool drafting-film neutrals, a teal accent for the gaze ray, the heatmap ramp as the one flourish. */
  --bg: #eef2f1;
  --surface: #ffffff;
  --surface-2: #e5ebe9;
  --ink: #14201c;
  --ink-2: #4b5a54;
  --line: #cfd9d5;
  --accent: #0a6c64;
  --accent-soft: #d3ece8;
  --done: #1d7148;
  --done-bg: #ddf1e5;
  --active: #1b5ca3;
  --active-bg: #e0ebf8;
  --attention: #8f5300;
  --attention-bg: #f9ecd2;
  --fix: #ad2a20;
  --fix-bg: #f9e1de;
  --muted: #69766f;
  --muted-bg: #e8ecea;
  --heat-1: #2c4f9c;
  --heat-2: #24a29b;
  --heat-3: #e2bb32;
  --heat-4: #d4522a;
  --font-display: "IBM Plex Sans Condensed", "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
  --font-body: "Noto Sans SC", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
  --font-mono: "IBM Plex Mono", ui-monospace, "Cascadia Mono", Consolas, monospace;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #0d1513; --surface: #141e1b; --surface-2: #1b2723; --ink: #e2ebe7; --ink-2: #9db0a8; --line: #2b3934;
    --accent: #3ccdb9; --accent-soft: #163a35; --done: #6fd39b; --done-bg: #173226; --active: #8db8f0; --active-bg: #1a2a40;
    --attention: #f0b35a; --attention-bg: #3a2a12; --fix: #f08a80; --fix-bg: #3d1b18; --muted: #8a9893; --muted-bg: #1f2a26;
    color-scheme: dark;
  }
}
:root[data-theme="dark"] {
  --bg: #0d1513; --surface: #141e1b; --surface-2: #1b2723; --ink: #e2ebe7; --ink-2: #9db0a8; --line: #2b3934;
  --accent: #3ccdb9; --accent-soft: #163a35; --done: #6fd39b; --done-bg: #173226; --active: #8db8f0; --active-bg: #1a2a40;
  --attention: #f0b35a; --attention-bg: #3a2a12; --fix: #f08a80; --fix-bg: #3d1b18; --muted: #8a9893; --muted-bg: #1f2a26;
  color-scheme: dark;
}
* { box-sizing: border-box; }
html { scroll-padding-top: 72px; }
body { margin: 0; background: var(--bg); color: var(--ink); font-family: var(--font-body); font-size: 15px; line-height: 1.7; }
a { color: var(--accent); text-underline-offset: 2px; }
a:focus-visible, button:focus-visible, summary:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
code, .mono { font-family: var(--font-mono); font-size: 0.88em; }
code { background: var(--surface-2); padding: 0 0.3em; border-radius: 3px; overflow-wrap: anywhere; }
.topbar { position: sticky; top: env(safe-area-inset-top, 0px); z-index: 10; background: var(--surface); border-bottom: 1px solid var(--line);
  display: flex; align-items: center; gap: 16px; flex-wrap: wrap; padding-block: 10px;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); }
.brand { display: flex; align-items: baseline; gap: 10px; margin-right: auto; }
.brand .mark { font-family: var(--font-display); font-weight: 600; font-size: 22px; letter-spacing: 0.02em; }
.brand .sub { color: var(--ink-2); font-size: 14px; }
.osd { font-family: var(--font-mono); font-size: 13px; color: var(--ink-2); letter-spacing: 0.04em; font-variant-numeric: tabular-nums; }
.heatbar { height: 3px; background: linear-gradient(90deg, var(--heat-1), var(--heat-2), var(--heat-3), var(--heat-4)); }
.theme-btn { font: inherit; font-size: 13px; color: var(--ink); background: var(--surface-2); border: 1px solid var(--line); border-radius: 6px; padding: 4px 10px; cursor: pointer; white-space: nowrap; flex-shrink: 0; }
.layout { display: grid; grid-template-columns: 200px minmax(0, 1fr); gap: 32px; max-width: 1480px; margin: 0 auto;
  padding-block: 24px 48px; padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); }
.rail { position: sticky; top: 72px; align-self: start; display: flex; flex-direction: column; gap: 2px; font-size: 14px; }
.rail a { color: var(--ink-2); text-decoration: none; padding: 6px 10px; border-left: 2px solid transparent; }
.rail a:hover, .rail a.current { color: var(--ink); border-left-color: var(--accent); background: var(--surface); }
main { min-width: 0; display: flex; flex-direction: column; gap: 40px; }
section > h2 { font-family: var(--font-display); font-weight: 600; font-size: 24px; margin: 0 0 4px; text-wrap: balance; }
section > .lede { color: var(--ink-2); margin: 0 0 16px; max-width: 70ch; }
h3 { font-family: var(--font-display); font-weight: 600; font-size: 18px; margin: 24px 0 8px; }
.panel { background: var(--surface); border: 1px solid var(--line); border-radius: 8px; padding: 16px 20px; min-width: 0; }
.grid-2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(300px, 100%), 1fr)); gap: 16px; }
.readouts { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1px; background: var(--line); border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }
.readout { background: var(--surface); padding: 12px 16px; min-width: 0; }
.readout .label { font-size: 12px; color: var(--ink-2); letter-spacing: 0.06em; }
.readout .value { font-size: 15px; overflow-wrap: anywhere; }
.banner { border: 1px solid var(--attention); background: var(--attention-bg); color: var(--ink); border-radius: 8px; padding: 14px 18px; }
.banner strong { color: var(--attention); }
.todo { list-style: none; margin: 8px 0 0; padding: 0; display: flex; flex-direction: column; gap: 10px; }
.todo li { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 10px; align-items: start; }
.chip { display: inline-block; font-size: 12px; line-height: 1.4; padding: 2px 8px; border-radius: 999px; white-space: nowrap; font-weight: 500; }
.chip.done { color: var(--done); background: var(--done-bg); }
.chip.active { color: var(--active); background: var(--active-bg); }
.chip.attention { color: var(--attention); background: var(--attention-bg); }
.chip.fix { color: var(--fix); background: var(--fix-bg); }
.chip.ready { color: var(--accent); background: var(--accent-soft); }
.chip.paused, .chip.planned, .chip.blocked, .chip.other { color: var(--muted); background: var(--muted-bg); }
.chip.muted { color: var(--muted); background: var(--muted-bg); text-decoration: line-through; }
.stages { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }
.stages li { background: var(--surface); border: 1px solid var(--line); border-top: 4px solid var(--line); border-radius: 0 0 8px 8px; padding: 10px 12px; min-width: 0; }
.stages li.done { border-top-color: var(--done); }
.stages li.active { border-top-color: var(--active); }
.stages li.attention { border-top-color: var(--attention); }
.stages .num { font-family: var(--font-mono); font-size: 12px; color: var(--ink-2); }
.stages .goal { font-size: 14px; margin: 4px 0 6px; }
.table-wrap { overflow-x: auto; border: 1px solid var(--line); border-radius: 8px; background: var(--surface); }
/* Column roles: identifiers stay on one line, prose keeps a readable minimum width, paths break after separators. */
th.c-narrow, td.c-narrow { white-space: nowrap; }
th.c-status, td.c-status { min-width: 8.5em; }
details.cell-more { background: transparent; border: 0; border-radius: 0; }
details.cell-more > summary { display: block; padding: 0; cursor: pointer; list-style: none; }
details.cell-more > summary::-webkit-details-marker { display: none; }
details.cell-more[open] > summary { border-bottom: 0; }
details.cell-more .toggle::after { content: "展开全文"; margin-left: 6px; font-size: 12px; color: var(--accent); white-space: nowrap; }
details.cell-more[open] .toggle::after { content: "收起"; }
details.cell-more[open] .preview { display: none; }
td.c-status .small { margin-top: 4px; max-width: 26em; }
th.c-mid, td.c-mid { min-width: 8em; }
th.c-text, td.c-text { min-width: 14em; }
th.c-long, td.c-long { min-width: 20em; }
.prose th.c-status, .prose td.c-status { min-width: 10em; }
th.c-path, td.c-path { min-width: 10em; max-width: 24em; overflow-wrap: anywhere; }
th.c-wide, td.c-wide { max-width: 32em; }
td.c-path code { white-space: normal; }
.prose td:first-child { white-space: nowrap; }
table { border-collapse: collapse; width: 100%; font-size: 14px; }
th, td { text-align: left; vertical-align: top; padding: 8px 12px; border-bottom: 1px solid var(--line); }
th { font-weight: 500; color: var(--ink-2); background: var(--surface-2); white-space: nowrap; }
tr:last-child td { border-bottom: 0; }
td p { margin: 0; }
td.id.c-narrow { font-family: var(--font-mono); }
.diagram { overflow-x: auto; background: var(--surface); border: 1px solid var(--line); border-radius: 8px; padding: 12px; }
pre.mermaid { margin: 0; font-family: var(--font-mono); font-size: 12px; white-space: pre; color: var(--ink-2); }
pre.mermaid[data-processed] { color: inherit; white-space: normal; text-align: center; }
pre.mermaid svg { min-width: min(560px, 160vw); height: auto; }
.filters { display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 12px; }
.filters button { font: inherit; font-size: 13px; color: var(--ink); background: var(--surface); border: 1px solid var(--line); border-radius: 999px; padding: 4px 12px; cursor: pointer; }
.filters button[aria-pressed="true"] { background: var(--accent); border-color: var(--accent); color: var(--surface); }
.prose { max-width: 78ch; }
.prose > :first-child { margin-top: 0; }
.prose table { margin: 8px 0; }
.prose pre:not(.mermaid) { background: var(--surface-2); padding: 10px 12px; border-radius: 6px; overflow-x: auto; }
details.doc, details.history { background: var(--surface); border: 1px solid var(--line); border-radius: 8px; }
details.doc + details.doc, details.history + details.history { margin-top: 8px; }
details > summary { cursor: pointer; padding: 10px 16px; display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
details > summary .title { font-weight: 500; }
details > summary .small, details > summary .title { overflow-wrap: anywhere; min-width: 0; }
details[open] > summary { border-bottom: 1px solid var(--line); }
details .inner { padding: 16px 20px; overflow-x: auto; }
details .inner .table-wrap, details .inner table { font-size: 13px; }
.meta { font-size: 13px; color: var(--ink-2); }
.small { font-size: 13px; color: var(--ink-2); }
footer { border-top: 1px solid var(--line); color: var(--ink-2); font-size: 13px; padding-block: 16px 32px;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); }
footer .inner { max-width: 1480px; margin: 0 auto; }
@media (max-width: 960px) {
  .layout { grid-template-columns: minmax(0, 1fr); }
  .rail { position: static; flex-direction: row; flex-wrap: wrap; gap: 4px; }
  .rail a { border-left: 0; border-bottom: 2px solid transparent; padding: 4px 8px; }
  .rail a:hover, .rail a.current { border-bottom-color: var(--accent); background: transparent; }
}
@media (max-width: 600px) {
  .topbar { flex-wrap: nowrap; gap: 10px; padding-block: 8px; }
  .brand .sub { display: none; }
  .brand .mark { font-size: 19px; }
  .osd { font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0; }
  section > h2 { font-size: 21px; }
}
tr:target { outline: 2px solid var(--accent); outline-offset: -2px; }
@media (prefers-reduced-motion: no-preference) { html { scroll-behavior: smooth; } }
"""

JS = r"""
(function () {
  var root = document.documentElement;
  var KEY = "gazelle-portal-theme";
  function isDark() {
    var chosen = root.getAttribute("data-theme");
    if (chosen) { return chosen === "dark"; }
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  }
  function label(button) { if (button) { button.textContent = isDark() ? "浅色" : "深色"; } }
  try {
    var saved = window.localStorage.getItem(KEY);
    if (saved === "light" || saved === "dark") { root.setAttribute("data-theme", saved); }
  } catch (error) { /* storage unavailable */ }
  var themeButton = document.getElementById("theme-toggle");
  label(themeButton);
  if (themeButton) {
    themeButton.addEventListener("click", function () {
      var next = isDark() ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try { window.localStorage.setItem(KEY, next); } catch (error) { /* storage unavailable */ }
      label(themeButton);
    });
  }
  document.querySelectorAll("[data-filter-group]").forEach(function (group) {
    var targets = document.querySelectorAll(group.getAttribute("data-filter-group"));
    var buttons = group.querySelectorAll("button[data-filter]");
    buttons.forEach(function (button) {
      button.addEventListener("click", function () {
        var wanted = button.getAttribute("data-filter");
        buttons.forEach(function (other) { other.setAttribute("aria-pressed", other === button ? "true" : "false"); });
        targets.forEach(function (row) {
          var tags = (row.getAttribute("data-tags") || "").split(" ");
          row.hidden = !(wanted === "all" || tags.indexOf(wanted) >= 0);
        });
      });
    });
  });
  var links = Array.prototype.slice.call(document.querySelectorAll(".rail a"));
  if ("IntersectionObserver" in window && links.length) {
    var byId = {};
    links.forEach(function (link) { byId[link.getAttribute("href").slice(1)] = link; });
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting && byId[entry.target.id]) {
          links.forEach(function (link) { link.classList.remove("current"); });
          byId[entry.target.id].classList.add("current");
        }
      });
    }, { rootMargin: "-20% 0px -70% 0px" });
    document.querySelectorAll("main > section[id]").forEach(function (section) { observer.observe(section); });
  }
  function renderDiagrams(nodes) {
    if (!window.mermaid || !nodes.length) { return; }
    try { window.mermaid.run({ nodes: nodes }); } catch (error) { /* the source text stays visible */ }
  }
  if (window.mermaid) {
    try {
      window.mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: isDark() ? "dark" : "neutral",
        fontFamily: "Noto Sans SC, PingFang SC, Microsoft YaHei, sans-serif" });
    } catch (error) { /* ignore */ }
    renderDiagrams(Array.prototype.filter.call(document.querySelectorAll("pre.mermaid"), function (node) {
      return !node.closest("details");
    }));
    document.querySelectorAll("details").forEach(function (details) {
      details.addEventListener("toggle", function () {
        if (details.open) { renderDiagrams(Array.prototype.slice.call(details.querySelectorAll("pre.mermaid:not([data-processed])"))); }
      });
    });
  }
})();
"""
