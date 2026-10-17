// Offline browser-logic checks; no server, network or external media.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const html=fs.readFileSync(path.join(__dirname,'../tools/validation/annotation_page.html'),'utf8');
const script=html.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/start\(\)\.catch\(e=>error\(e.message\)\);\s*$/,'');
class Element {
  constructor(){this.children=[];this.style={setProperty(){}};this.value='';}
  set src(value){this._src=value;if(!this.delayLoad)this.onload?.();}
  get src(){return this._src;}
  append(...children){this.children.push(...children);}
  replaceChildren(...children){this.children=children;}
  click(){if(!this.disabled)this.onclick?.();}
}
const elements=new Map(),events={};
const document={getElementById(id){if(!elements.has(id))elements.set(id,new Element());return elements.get(id);},
                createElement(){return new Element();},addEventListener(name,callback){events[name]=callback;}};
const context=vm.createContext({document,window:{addEventListener(){}},console,performance:{now:()=>0},
  requestAnimationFrame(fn){fn();},setInterval(){},setTimeout(){},clearTimeout(){},fetch(){throw new Error('Unexpected network boundary');}});
vm.runInContext(script,context);
const run=s=>vm.runInContext(s,context);
const plain=s=>JSON.parse(JSON.stringify(run(s)));
run("state={segments:[{segment_id:'s',step_count:50,step_hz:5,start_wall_time:100,pilot:true}],classes:{classes:[{key:1,label:'target',color:'#123456',name_zh:'Target'},{key:0,label:'unknown',color:'#cccccc',name_zh:'Unknown'}]}};segmentId='s';documentData={revision:0,segments:[{segment_id:'s',labels:[{start_step:0,end_step_exclusive:50,label:null}],viewed_ranges:[],finished_at:null,other_people:[],note:''}]};save=()=>{};");
run("go(0);assign('target');");
assert.equal(run("byId('finish').disabled"),true,'one key cannot finish unseen content');
assert.equal(run('viewed(record(),1)'),false);
assert.match(run("byId('timeline').children[1].style.backgroundImage"),/gradient/,'labelled unseen steps retain texture');
run("record().labels=[{start_step:0,end_step_exclusive:50,label:null}];");
run("go(20);assign('unknown');go(10);assign('target');");
assert.deepEqual(plain('record().labels'),[
  {start_step:0,end_step_exclusive:10,label:null},{start_step:10,end_step_exclusive:20,label:'target'},
  {start_step:20,end_step_exclusive:50,label:'unknown'}],'new label stops at the next existing change');
run("byId('deleteChange').click();");
assert.deepEqual(plain('record().labels'),[
  {start_step:0,end_step_exclusive:20,label:null},{start_step:20,end_step_exclusive:50,label:'unknown'}]);
run('undo();');
assert.equal(run('record().labels.length'),3,'undo restores the deleted change');
run('go(0);');
events.keydown({key:'0',target:{tagName:'BODY'},preventDefault(){}});
assert.equal(run('expand(record().labels,50)[0]'),'unknown','key zero is intentional unknown, not unlabelled');
run("go(5);byId('otherStart').click();go(10);byId('otherEnd').click();go(9);byId('otherStart').click();go(14);byId('otherEnd').click();");
assert.deepEqual(plain('record().other_people'),[{start_step:5,end_step_exclusive:15}],'overlapping people ranges merge');
run('undo();');
assert.deepEqual(plain('record().other_people'),[{start_step:5,end_step_exclusive:11}]);
run("byId('note').oninput({target:{value:'autosaved note'}});");
assert.equal(run('record().note'),'autosaved note','notes save on input without requiring blur');
run('undo();');
assert.equal(run('record().note'),'');
run("byId('image').delayLoad=true;go(25);assign('target');");
assert.equal(run('viewed(record(),25)'),false,'loading is not viewing');
assert.equal(run('expand(record().labels,50)[25]'),'unknown','unloaded frame cannot receive a judgment');
run("byId('image').onload();assign('target');");
assert.equal(run('expand(record().labels,50)[25]'),'target','loaded frame accepts annotation');
run("byId('otherCancel').click();byId('image').delayLoad=false;for(let i=0;i<50;i++)go(i);go(0);assign('target');");
assert.deepEqual(plain('record().viewed_ranges'),[{start_step:0,end_step_exclusive:50}]);
assert.equal(run("byId('finish').disabled"),false,'all seen and labelled can be confirmed');
run("record().finished_at='confirmed';assign('unknown');");
assert.equal(run('record().finished_at'),null,'a changed judgment requires another confirmation');
run('undo();');
assert.equal(run('record().finished_at'),null,'undo never restores a completion receipt');
run("state.segments.push({segment_id:'s2',step_count:50,step_hz:5,start_wall_time:200,pilot:false});documentData.segments.push({segment_id:'s2',labels:[{start_step:0,end_step_exclusive:50,label:null}],other_people:[],note:''});otherFrom=25;switchSegment('s2');");
assert.equal(run('changing'),false,'unfinished people start must not begin a segment switch');
assert.equal(run('segmentId'),'s','unfinished people start stays on its original segment');
assert.match(run("byId('error').textContent"),/结束或取消/);
console.log('PASS: label boundaries, explicit unknown, deletion/undo, people intervals, keyboard event');
