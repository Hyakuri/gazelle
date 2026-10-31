// Offline browser-logic checks; no server, network or external media.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const html=fs.readFileSync(path.join(__dirname,'../tools/validation/annotation_page.html'),'utf8');
assert.match(html, /id="webcamImage"[^>]*aspect-ratio:16\/9/, 'W placeholder retains aspect ratio before pixels arrive');
const script=html.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/start\(\)\.catch\(e=>error\(e.message\)\);\s*$/,'');
class Element {
  constructor(tagName='DIV',type=''){this.tagName=tagName.toUpperCase();this.type=type;this.children=[];this.style={setProperty(){}};this.value='';this.attrs={};}
  focus(){document.activeElement=this;}
  blur(){if(document.activeElement===this)document.activeElement=document.body;}
  closest(selector){return selector.split(',').some(s=>s===this.tagName.toLowerCase()||(s==='input[type="range"]'&&this.tagName==='INPUT'&&this.type==='range'))?this:null;}
  setAttribute(name,value){this.attrs[name]=value;}
  getBoundingClientRect(){return {left:0,top:0,width:1920,height:720};}
  set src(value){this._src=value;if(!this.delayLoad)this.onload?.();}
  get src(){return this._src;}
  append(...children){this.children.push(...children);}
  replaceChildren(...children){this.children=children;}
  click(){if(!this.disabled)this.onclick?.();}
}
const elements=new Map(),events={},windowEvents={};
let clock=0,nextTimer=0;const timers=new Map();
const document={body:new Element('BODY'),getElementById(id){if(!elements.has(id)){
                  const tag=html.match(new RegExp('<(\\w+)\\b[^>]*\\bid="'+id+'"[^>]*>'));
                  elements.set(id,new Element(tag?.[1],tag?.[0].match(/type="([^"]+)"/)?.[1]));
                }return elements.get(id);},
                createElement(tag){return new Element(tag);},createElementNS(){return new Element();},addEventListener(name,callback){events[name]=callback;}};
const context=vm.createContext({document,window:{addEventListener(name,callback){windowEvents[name]=callback;}},console,performance:{now:()=>clock},
  requestAnimationFrame(fn){fn();},setInterval(){},setTimeout(fn,delay){const id=++nextTimer;timers.set(id,{fn,due:clock+delay});return id;},clearTimeout(id){timers.delete(id);},fetch(){throw new Error('Unexpected network boundary');}});
vm.runInContext(script,context);
const run=s=>vm.runInContext(s,context);
const plain=s=>JSON.parse(JSON.stringify(run(s)));
run("const actualSave=save,actualQueueViewed=queueViewedSave;state={segments:[{segment_id:'s',step_count:50,step_hz:5,start_wall_time:100,pilot:true}],classes:{classes:[{key:1,label:'target',color:'#123456',name_zh:'Target'},{key:2,label:'hands_object',color:'#f1c40f',name_zh:'Hands'},{key:3,label:'cell_other',color:'#9b59b6',name_zh:'Other'},{key:4,label:'away',color:'#c0392b',name_zh:'Away'},{key:0,label:'unknown',color:'#cccccc',name_zh:'Unknown'}]}};segmentId='s';documentData={revision:0,segments:[{segment_id:'s',labels:[{start_step:0,end_step_exclusive:50,label:null}],points:[],point_skips:[],viewed_ranges:[],finished_at:null,other_people:[],note:''}]};save=()=>{viewDirty=false;};queueViewedSave=()=>{};");
run("go(0);assign('target');");
assert.equal(run("byId('webcamPanel').hidden"),true,'three-camera recordings keep the existing page');
run("meta().has_webcam=true;meta().webcam_uncertain_steps=[1];step=1;showWebcam();");
assert.equal(run("byId('webcamPanel').hidden"),false);
assert.equal(run("byId('webcamImage').src"),'/webcam/s/1');
assert.match(run("byId('webcamStatus').textContent"),/不确定/);
assert.equal(run("byId('webcamImage').onclick"),undefined,'W reference never accepts gaze points');
assert.equal(run("byId('webcamImage').style.visibility"),'visible');
assert.ok(html.indexOf('id="webcamPanel"')>html.indexOf('id="classes"'),'W follows timeline and class buttons');
assert.match(html,/#webcamImage\{display:block;visibility:hidden\}/,'W reserves image layout while loading');
run("byId('webcamImage').delayLoad=true;step=2;showWebcam();");
assert.equal(run("byId('webcamImage').style.visibility"),'hidden','old W image disappears immediately');
assert.notEqual(run("byId('webcamImage').hidden"),true,'loading does not collapse the image');
run("byId('image').delayLoad=true;step=3;showFrame();showWebcam();byId('webcamImage').onload();");
assert.equal(run('displayReady'),false,'W load cannot make the montage ready');
assert.equal(run('viewed(record(),3)'),false,'W load cannot mark a step viewed');
run("byId('image').onload();byId('webcamImage').onerror();assign('target');");
assert.equal(run('displayReady'),true,'W failure leaves montage labelling available');
assert.equal(run('runAt(record(),3).label'),'target');
assert.equal(run("byId('webcamImage').style.visibility"),'hidden');
assert.match(run("byId('webcamStatus').textContent"),/加载失败/);
run("byId('image').delayLoad=false;byId('webcamImage').delayLoad=false;record().viewed_ranges=[{start_step:0,end_step_exclusive:1}];");
run("meta().has_webcam=false;step=0;showWebcam();");
assert.equal(run("byId('webcamPanel').hidden"),true);
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
assert.equal(run("byId('finish').disabled"),true,'eligible run also needs a point or skip');
assert.match(run("byId('pointStatus').textContent"),/缺注视点/);
run("addPoint({clientX:1280,clientY:360});go(25);addPoint({clientX:1280,clientY:360});go(0);");
assert.equal(run("byId('finish').disabled"),false,'all seen, labelled and point-covered can be confirmed');
run("record().finished_at='confirmed';assign('unknown');");
assert.equal(run('record().finished_at'),null,'a changed judgment requires another confirmation');
run('undo();');
assert.equal(run('record().finished_at'),null,'undo never restores a completion receipt');
run("state.segments.push({segment_id:'s2',step_count:50,step_hz:5,start_wall_time:200,pilot:false});documentData.segments.push({segment_id:'s2',labels:[{start_step:0,end_step_exclusive:50,label:null}],points:[],point_skips:[],other_people:[],note:''});otherFrom=25;switchSegment('s2');");
assert.equal(run('changing'),false,'unfinished people start must not begin a segment switch');
assert.equal(run('segmentId'),'s','unfinished people start stays on its original segment');
assert.match(run("byId('error').textContent"),/结束或取消/);
console.log('PASS: label boundaries, explicit unknown, deletion/undo, people intervals, keyboard event');

for(const scale of [1,.25]){
  context.box={left:20,top:30,width:1920*scale,height:720*scale};
  context.event={clientX:20+1280*scale,clientY:30+360*scale};
  assert.deepEqual(plain('overviewCoordinates(event,box)'),{x:.5,y:.5});
}
assert.equal(run('overviewCoordinates({clientX:100,clientY:30},{left:0,top:0,width:1920,height:720})'),null);
assert.deepEqual(plain('overviewCoordinates({clientX:1280,clientY:500},{left:0,top:0,width:1920,height:1000})'),{x:.5,y:.5},'letterboxing keeps overview coordinates');
run("otherFrom=null;go(0);record().labels=[{start_step:0,end_step_exclusive:50,label:'hands_object'}];record().points=[];record().point_skips=[];render();byId('frameSurface').onclick({clientX:1280,clientY:360});");
assert.deepEqual(plain('record().points'),[{step:0,x:.5,y:.5}]);
run('addPoint({clientX:1600,clientY:180})');
assert.deepEqual(plain('record().points'),[{step:0,x:.75,y:.25}],'same step replaces the point');
run('go(4);addPoint({clientX:1280,clientY:360});');
assert.equal(run('record().points.length'),1,'extra points cannot be closer than five steps');
run('go(5);addPoint({clientX:1280,clientY:360});');
assert.equal(run('record().points.length'),2);
assert.equal(run("byId('pointOverlay').children.length"),2,'current and other points in this run are drawn');
assert.match(run("byId('timeline').children[5].title"),/注视点/);
events.keydown({key:'x',target:{tagName:'BODY'},preventDefault(){}});
assert.equal(run('record().points.length'),1,'X deletes only the current point');
run('go(0);byId("deletePoint").click();byId("skipPoint").click();');
assert.deepEqual(plain('record().point_skips'),[{step:0,reason:'unsure'}]);
assert.equal(run("byId('finish').disabled"),false,'explicit skip covers the eligible run');
events.keydown({key:'o',target:{tagName:'BODY'},preventDefault(){}});
assert.deepEqual(plain('record().point_skips'),[{step:0,reason:'out_of_view'}]);
run("addPoint({clientX:1280,clientY:360});assign('away');");
assert.deepEqual(plain('[record().points,record().point_skips]'),[[],[]]);
assert.match(run("byId('pointNotice').textContent"),/清除/);
run('undo();');
assert.equal(run('record().points.length'),0,'clicking a marked run cannot add a point');
assert.equal(run('record().point_skips[0].reason'),'out_of_view','undo restores out-of-view mark');
run("assign('target');");
assert.deepEqual(plain('record().point_skips'),[],'out-of-view cannot remain on a target region');
assert.equal(run("byId('outOfView').disabled"),true);
console.log('PASS: scaled overview points, replacement, spacing, deletion, skips/out-of-view, cleanup/undo, completion');

run("record().labels=[{start_step:0,end_step_exclusive:5,label:'target'},{start_step:5,end_step_exclusive:50,label:'hands_object'}];record().points=[{step:4,x:.1,y:.1},{step:5,x:.2,y:.2}];record().point_skips=[];go(5);byId('deleteChange').click();");
assert.deepEqual(plain('record().points'),[{step:4,x:.1,y:.1}],'merging runs enforces the same five-step spacing');
assert.deepEqual(plain('record().point_skips'),[],'a removed run start cannot retain its skip');
assert.match(run("byId('pointNotice').textContent"),/清除/);
run('undo();');
assert.equal(run('record().points.length'),2,'undo restores both pre-merge points');
const key=(key,extra={})=>{let prevented=false;events.keydown({key,target:{tagName:'BODY'},preventDefault(){prevented=true;},...extra});return prevented;};
run("record().points=[{step:0,x:.1,y:.1},{step:5,x:.2,y:.2}];go(5);");
key('Delete');
assert.equal(run('record().labels.length'),1,'Delete really removes a label change');
assert.equal(run('record().points.length'),2,'Delete preserves valid attention points');

run("record().labels=[{start_step:0,end_step_exclusive:5,label:'hands_object'},{start_step:5,end_step_exclusive:50,label:'target'}];record().points=[{step:5,x:.2,y:.2},{step:10,x:.3,y:.3}];record().point_skips=[{step:0,reason:'out_of_view'}];go(5);assign('hands_object');");
assert.equal(run('record().points.length'),2,'merge keeps points');
assert.deepEqual(plain('record().point_skips'),[],'merge removes the conflicting skip at the surviving start');
assert.match(run("byId('pointNotice').textContent"),/1 个标记/);
run('undo();');
assert.deepEqual(plain('record().point_skips'),[{step:0,reason:'out_of_view'}]);
assert.equal(run('record().labels.length'),2);

run("record().labels=[{start_step:0,end_step_exclusive:50,label:'hands_object'}];record().point_skips=[];go(7);");
for(const [shortcut,reason] of [['s','unsure'],['o','out_of_view']]){
  key(shortcut);
  assert.deepEqual(plain('record().point_skips'),[{step:0,reason}],'middle-of-run shortcut uses its start');
  assert.deepEqual(plain('record().points'),[],'skip removes all points in the run');
  assert.match(run("byId('pointNotice').textContent"),/2 个/);
  run('addPoint({clientX:1280,clientY:360});');
  assert.deepEqual(plain('record().points'),[],'marked run rejects a click');
  assert.match(run("byId('pointNotice').textContent"),/先按 [SO].*取消/);
  key(shortcut);
  assert.deepEqual(plain('[record().points,record().point_skips]'),[[],[]],'same shortcut cancels the mark without inventing points');
  key('z',{ctrlKey:true});
  assert.deepEqual(plain('record().point_skips'),[{step:0,reason}],'undo restores the cancelled mark');
  key('z',{ctrlKey:true});
  assert.equal(run('record().points.length'),2,'undo restores both points');
  assert.deepEqual(plain('record().point_skips'),[],'undo restores absence of skip');
}
for(const modifier of ['ctrlKey','metaKey','altKey'])for(const shortcut of ['s','o','x','Delete','1',' ','ArrowLeft','ArrowRight']){
  const before=plain('[record(),step,playing,undoStack.length]');
  assert.equal(key(shortcut,{[modifier]:true}),false,'browser modifier shortcut keeps its default');
  assert.deepEqual(plain('[record(),step,playing,undoStack.length]'),before,'modifier shortcut cannot edit or navigate');
}
for(const shortcut of ['s','o','x','Delete','1',' ']){
  const before=plain('[record(),step,playing,undoStack.length]');
  assert.equal(key(shortcut,{repeat:true}),true,'ignored shortcut repeats must prevent native browser actions');
  assert.deepEqual(plain('[record(),step,playing,undoStack.length]'),before,'repeated shortcut is ignored');
}
for(const modifier of ['ctrlKey','metaKey']){
  for(const extra of [{shiftKey:true},{altKey:true},{repeat:true}]){
    const before=plain('[record(),step,playing,undoStack.length]');
    assert.equal(key('z',{[modifier]:true,...extra}),Boolean(extra.repeat),'only plain undo consumes its repeat');
    assert.deepEqual(plain('[record(),step,playing,undoStack.length]'),before,'modified or repeated undo does not change the record');
  }
}
for(const tagName of ['INPUT','TEXTAREA','SELECT'])for(const shortcut of ['s','o','x','Delete','1',' ','ArrowLeft','ArrowRight','z']){
  for(const repeat of [false,true]){
    const before=plain('[record(),step,playing,undoStack.length]');
    assert.equal(key(shortcut,{target:{tagName},repeat,ctrlKey:shortcut==='z'}),false,'editing fields retain their keyboard behavior');
    assert.deepEqual(plain('[record(),step,playing,undoStack.length]'),before,'focused editing fields do not annotate or undo');
  }
}
// Each held shortcut has exactly its first effect, including undo on either platform.
const baseline=plain('record()');
for(const shortcut of ['s','o','x','Delete','1',' ','z'])for(const modifier of (shortcut==='z'?['ctrlKey','metaKey']:[null])){
  context.baseline=structuredClone(baseline);
  run("pause();Object.assign(record(),baseline);undoStack=[];go(5);change(row=>row.note='undo me');");
  if(shortcut==='Delete')run('go(0);');
  const extra=modifier?{[modifier]:true}:{};
  const before=plain('[record(),step,playing,undoStack.length]');
  assert.equal(key(shortcut,extra),true);
  const once=plain('[record(),step,playing,undoStack.length]');
  assert.notDeepEqual(once,before,'initial shortcut has an observable effect');
  for(let i=0;i<3;i++){
    assert.equal(key(shortcut,{...extra,repeat:true}),true);
    assert.deepEqual(plain('[record(),step,playing,undoStack.length]'),once,'holding a key acts only once');
  }
}
context.baseline=baseline;
run('pause();Object.assign(record(),baseline);go(7);');
key('ArrowRight',{repeat:true});assert.equal(run('step'),8,'arrows still repeat');
key('o');assert.equal(run("byId('finish').disabled"),false,'out-of-view alone can cover the complete run');
run('addPoint({clientX:100,clientY:100});');
assert.match(run("byId('pointNotice').textContent"),/请在全局画面上点/);

const advance=time=>{clock=time;for(const [id,t] of [...timers])if(t.due<=clock){timers.delete(id);t.fn();}};
timers.clear();
run("byId('speed').value='1';byId('image').delayLoad=true;go(0);togglePlay();");
advance(200);assert.equal(run('step'),0);
clock=1000;run("byId('image').onload();");
advance(1025);assert.equal(run('step'),0,'slow frame must dwell for a full step after loading');
advance(1199);assert.equal(run('step'),0);
advance(1200);assert.equal(run('step'),1);
run("pause();byId('image').delayLoad=false;");timers.clear();clock=0;
console.log('PASS: mutually exclusive points/skips, merge and undo, modifier/repeat guards, slow-frame dwell');

const emit=(name,target,extra={})=>events[name]?.({target,button:0,pointerType:'mouse',detail:1,...extra});
const mouseStart=control=>{emit('pointerdown',control);control.focus();};
for(const id of ['scrub','speed','segments']){
  const control=document.getElementById(id);
  mouseStart(control);emit('change',control);
  assert.equal(document.activeElement,document.body,id+' releases mouse focus after change');
  const before=run('playing');
  key(' ',{target:document.activeElement});
  assert.equal(run('playing'),!before,'space works immediately after mouse change');run('pause();');
  const stepBefore=run('step'),segmentBefore=run('segmentId'),speedBefore=run("byId('speed').value");
  key('ArrowRight',{target:document.activeElement});
  assert.equal(run('step'),stepBefore+1,'arrow advances one step after mouse change');
  assert.equal(run('segmentId'),segmentBefore,'arrow does not switch segment');
  assert.equal(run("byId('speed').value"),speedBefore,'arrow does not change speed');
  key('1',{target:document.activeElement});
  assert.equal(run('expand(record().labels,50)[step]'),'target','digit annotates after mouse change');
  run('undo();');
  control.focus();key('Tab',{target:control});emit('change',control);
  assert.equal(document.activeElement,control,id+' retains keyboard focus');
  assert.equal(key(' ',{target:control}),false,'keyboard-focused input retains shortcut isolation');
  mouseStart(control);key('ArrowRight',{target:control});emit('change',control);
  assert.equal(document.activeElement,control,'switching from mouse to keyboard retains control focus');
}
const slider=document.getElementById('scrub');
mouseStart(slider);emit('pointerup',slider);
assert.equal(document.activeElement,document.body,'clicking an unchanged slider releases focus');
mouseStart(slider);emit('pointerup',document.body);
assert.equal(document.activeElement,document.body,'dragging beyond slider still releases focus');
for(const button of [document.getElementById('undo'),document.createElement('button')]){
  mouseStart(button);emit('pointerup',button);emit('click',button);
  assert.equal(document.activeElement,document.body,'mouse clicks release static and dynamic buttons');
  button.focus();key('Tab',{target:button});emit('click',button,{detail:0});
  assert.equal(document.activeElement,button,'keyboard activation keeps button focus');
}
const note=document.getElementById('note');
mouseStart(note);emit('change',note);emit('pointerup',note);emit('click',note);
assert.equal(document.activeElement,note,'notes keep mouse focus');
mouseStart(slider);emit('pointercancel',slider);emit('change',slider);
assert.equal(document.activeElement,slider,'cancelled pointer gesture does not affect a later change');
document.activeElement=document.body;
console.log('PASS: mouse focus release, keyboard focus retention, notes and cancelled gestures');

(async()=>{
  const writes=[];let serverRevision=0,staleRequests=0;
  context.fetch=async(url,options)=>{
    const payload=JSON.parse(options.body);writes.push({clock,payload,keepalive:options.keepalive});
    assert.ok(Array.isArray(payload.points),'save includes points');
    assert.ok(Array.isArray(payload.point_skips),'save includes point_skips');
    if(payload.revision!==serverRevision){staleRequests++;return {ok:false,json:async()=>({error:'Stale annotation revision'})};}
    const result=plain('documentData');result.revision=++serverRevision;
    const row=result.segments.find(r=>r.segment_id===payload.segment_id);
    Object.assign(row,payload,{started_at:'saved',active_seconds:0,annotator:'test',finished_at:null});
    return {ok:true,json:async()=>result};
  };
  run("save=actualSave;queueViewedSave=actualQueueViewed;otherFrom=null;step=0;requestedKey='s/0';displayKey='s/0';displayReady=true;record().viewed_ranges=[];documentData.segments[1].viewed_ranges=[];viewDirty=false;lastSavedAt=-Infinity;pending=0;");
  const add=index=>run(`record().viewed_ranges=mergePeople(record().viewed_ranges,{start_step:${index},end_step_exclusive:${index+1}});queueViewedSave();`);
  add(0);await run('saveQueue');assert.equal(writes.length,1);
  for(let i=1;i<5;i++){clock=i*200;add(i);}
  await run('saveQueue');assert.equal(writes.length,1,'view-only changes are coalesced inside one second');
  clock=1000;
  for(const [id,timer] of [...timers])if(timer.due<=clock){timers.delete(id);timer.fn();}
  await run('saveQueue');assert.equal(writes.length,2);
  assert.deepEqual(writes[1].payload.viewed_ranges,[{start_step:0,end_step_exclusive:5}]);
  clock=1200;add(5);run('playing=true;pause()');await run('saveQueue');assert.equal(writes.length,3,'pausing playback flushes immediately');
  clock=1400;add(6);await run("switchSegment('s2')");await run('saveQueue');
  assert.equal(writes.length,4,'switch flushes old segment immediately');
  assert.equal(writes[3].payload.segment_id,'s');
  assert.deepEqual(writes[3].payload.viewed_ranges,[{start_step:0,end_step_exclusive:7}]);
  clock=1450;run("change(row=>row.note='immediate')");await run('saveQueue');
  assert.equal(writes.at(-1).payload.note,'immediate','notes are never throttled');
  clock=1500;add(1);document.visibilityState='hidden';events.visibilitychange();await run('saveQueue');
  assert.equal(writes.at(-1).clock,1500,'hidden page flushes immediately');
  assert.equal(writes.at(-1).keepalive,false,'visibility hiding uses the normal queue');
  clock=1550;add(2);windowEvents.beforeunload({preventDefault(){}});await run('saveQueue');
  assert.equal(writes.at(-1).keepalive,true,'closing starts a keepalive flush');
  document.visibilityState='visible';timers.clear();writes.length=0;
  run("segmentId='s';step=0;requestedKey=null;record().viewed_ranges=[];viewDirty=false;lastSavedAt=-Infinity;playing=false;go(0);");
  await run('saveQueue');
  const begin=clock;
  for(let i=1;i<=20;i++){
    clock=begin+i*100;
    for(const [id,timer] of [...timers])if(timer.due<=clock){timers.delete(id);timer.fn();}
    events.keydown({key:'ArrowRight',repeat:true,target:{tagName:'BODY'},preventDefault(){}});
    await run('saveQueue');
  }
  assert.ok(writes.length<=3,`unplayed 10Hz stepping wrote ${writes.length} times in two seconds`);
  assert.ok(writes.length>=2,'manual progression is actually persisted');
  for(let i=1;i<writes.length;i++)assert.ok(writes[i].clock-writes[i-1].clock>=1000);
  await run("switchSegment('s2')");
  assert.equal(writes.at(-1).payload.viewed_ranges[0].end_step_exclusive,21,'switch keeps final unplayed viewed step');

  const originalFetch=context.fetch;
  let resolveBusy;
  let hold=true;
  context.fetch=(url,options)=>{
    if(options.keepalive||!hold)return originalFetch(url,options);
    hold=false;
    return new Promise(resolve=>{resolveBusy=()=>originalFetch(url,options).then(resolve);});
  };
  run("save();");await Promise.resolve();await Promise.resolve();
  assert.equal(typeof resolveBusy,'function');
  add(3);const before=writes.length;
  document.visibilityState='hidden';events.visibilitychange();
  assert.equal(writes.length,before,'hidden-page save waits for the in-flight save');
  resolveBusy();await run('saveQueue');
  assert.equal(run('failed'),false,'hiding while saving does not fail');
  assert.equal(staleRequests,0,'queued writes use the returned server revision');
  assert.deepEqual(writes.at(-1).payload.viewed_ranges,[{start_step:0,end_step_exclusive:4}]);
  for(const event of ['pagehide','beforeunload']){
    run('failed=false;pending=0;');context.currentRevision=serverRevision;run('documentData.revision=currentRevision;');
    hold=true;run('save();');await Promise.resolve();await Promise.resolve();
    clock+=100;add(event==='pagehide'?4:5);const count=writes.length;
    windowEvents[event]({preventDefault(){}});
    assert.equal(writes.length,count+1,`${event} dispatches keepalive without waiting for an in-flight save`);
    assert.equal(writes.at(-1).keepalive,true);
    resolveBusy();await run('saveQueue');
    assert.equal(run('failed'),true,'real close races remain protected by server revisions');
  }
  assert.equal(staleRequests,2,'only the deliberately raced closing requests conflict');
  console.log('PASS: fake-clock save coalescing, pause/switch/hide/close flush, immediate edits');
})().catch(error=>{console.error(error);process.exitCode=1;});
