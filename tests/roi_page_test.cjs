// Offline event regression harness; no browser, network, media, or third-party packages.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const html = fs.readFileSync(path.join(__dirname, '../tools/validation/roi_page.html'), 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/init\(\)\.then\([^\n]+\);\s*$/, '');
class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.attrs = {}; this.events = {}; this.style = {}; this.classList = {toggle() {}}; }
  setAttribute(k, v) { this.attrs[k] = v; }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  addEventListener(name, callback) { this.events[name] = callback; }
  getScreenCTM() { return {inverse() {return {};}}; }
  setPointerCapture() {}
}
const elements = new Map();
const document = {getElementById(id) {if (!elements.has(id)) elements.set(id, new Element(id)); return elements.get(id);},
  createElementNS(ns, tag) {return new Element(tag);}, createElement(tag) {return new Element(tag);},
  querySelectorAll() {return [];}, addEventListener() {}};
const context = vm.createContext({document, window: {addEventListener() {}}, console,
  DOMPoint: class {constructor(x,y){this.x=x;this.y=y;} matrixTransform(){return this;}},
  fetch: async () => ({ok: true, json: async () => ({})})});
vm.runInContext(script, context);
const run = source => vm.runInContext(source, context);
const defaults = JSON.parse(fs.readFileSync(path.join(__dirname, '../tools/validation/default_regions.json')));
context.settings = defaults;
run("data={candidates:[{id:'one',session:'test',container_time_ms:0}],defaults:settings.regions,custom_colors:settings.custom_colors,reserved_keys:settings.fixed_classes.map(r=>r.label),token:'test'}; reference='one'; save=()=>{};");
run("regions=[{...settings.regions[0],polygon:[[.2,.2],[.6,.2],[.6,.6],[.2,.6]]},{...settings.regions[3],polygon:[[0,0],[1,0],[1,1],[0,1]]}]; selected=0; renderCanvas();");
const shapes = elements.get('canvas').children;
assert.equal(shapes.find(n => n.tag === 'polygon').attrs.stroke, defaults.regions[3].color, 'cell must be drawn first');
assert.equal(shapes.at(-1).tag, 'circle', 'selected vertices must be above all polygons');
const event = (x,y,detail=1) => ({clientX:x*1920,clientY:y*1080,detail,pointerId:1,preventDefault(){},stopPropagation(){}});
const fire = (name,e) => elements.get('canvas').events[name]?.(e);
fire('pointerdown', event(.3,.3,0)); fire('click', event(.3,.3));
assert.equal(run('selected'), 0, 'canvas chooses the smallest containing region');
const dot = elements.get('canvas').children.find(n => n.tag === 'circle');
dot.events.pointerdown(event(.2,.2)); fire('pointermove', event(.25,.25)); fire('pointerup', event(.25,.25));
fire('click', event(.25,.25));
assert.equal(run('regions[0].polygon[0][0]'), .25, 'inner target vertex remains draggable');
assert.equal(run('vertex'), 0, 'pointer-captured click preserves vertex selection');
run("$('deleteVertex').onclick();");
assert.equal(run('regions[0].polygon.length'), 3, 'selected vertex can be deleted');
run("regions=[]; begin(settings.regions[0]);");
for (const e of [event(.2,.2),event(.6,.2),event(.4,.6),event(.4,.6,2)]) {
  fire('pointerdown',{...e,detail:0}); fire('pointerup',e); fire('click',e);
}
fire('dblclick',event(.4,.6,2));
assert.equal(run('regions.length'),1,'double click closes exactly one polygon');
assert.equal(run('regions[0].polygon.length'),3,'double click never duplicates the final vertex');
assert.equal(run('draft.region'),null);
run("regions=[]; $('customKey').value='rack'; $('customName').value='Rack'; $('custom').onclick();");
assert(!defaults.fixed_classes.some(row => row.color === run('draft.region.color')), 'custom color must avoid fixed classes');
console.log('PASS: cell order, topmost vertices, smallest hit, drag, double-click, custom color');
run('updateCompletion({complete:true,has_export:true});');
assert.equal(run("$('completion').textContent"),'已导出、未修改');
run('updateCompletion({complete:false,has_export:true});');
assert.match(run("$('completion').textContent"),/需要重新导出/);
