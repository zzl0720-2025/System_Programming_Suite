const escape = value => String(value ?? '—').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pretty = value => JSON.stringify(value, null, 2);
const names = {cpu:'CPU scheduling',disk:'Disk scheduling',linker:'Two-pass linking',compiler:'Compilation',vm:'Address spaces'};
const aliases = {link:'linker',code:'compiler'};
const policies = {cpu:['fcfs','lcfs','srtf','rr','prio','preprio'],disk:['fifo','sstf','look','clook','flook'],vm:['fifo','random','clock','nru','aging','working-set']};
const lessons = {
  cpu:{title:'One CPU. Several things to do.',intro:'A process is a running program. Only one process can use this simulated CPU at a time. A scheduler decides who gets the next turn.',read:'P0 arrives first and needs 5 units of CPU time, then 3 units of I/O, then 2 more CPU units. P1 and P2 arrive later. A blocked process is waiting for I/O and cannot use the CPU.',observe:'Watch the timeline. Each tile is one unit of time. Round Robin (RR) gives a process at most 2 units before another ready process gets a turn. The table shows state after that unit.',question:'P1 arrives at time 1. Does it immediately interrupt P0 under Round Robin?',choices:['Yes','No'],answer:'No',why:'P0 still has one unit left in its time slice. P1 waits; it starts at time 2. Arrival alone does not cause RR preemption.',before:1,after:2,compare:'Try SRTF: it can interrupt a long job when a shorter one arrives. Compare response time (first start minus arrival) with waiting time (all time spent ready).',challenge:'Try a quantum of 1, then 4. Which helps P1 respond sooner? Add I/O bursts and see why a blocked process leaves the ready queue.',fields:'arrival is the first ready time. bursts alternates CPU, I/O, CPU and must end with CPU. priority is 0–31; larger numbers have higher priority. All times are simulated units.'},
  disk:{title:'The order changes the journey.',intro:'A moving-head disk must move to the track holding each request. Scheduling changes the order of those trips. This lesson models seek distance, not SSD performance.',read:'The head starts at track 50. Requests for tracks 10, 90, and 55 are already waiting. Two more requests arrive later. Request IDs follow their order in the input.',observe:'One step serves one request. The line shows the path so far; the horizontal axis is track number. Distance is the absolute difference between the start and destination tracks.',question:'Under FIFO, which track will the head visit first?',choices:['10','55','90'],answer:'10',why:'FIFO follows arrival order, breaking ties by input order. Track 55 is nearer, but request 0 for track 10 came first in this workload.',before:0,after:1,compare:'SSTF chooses the nearest waiting request. LOOK moves in one direction before turning. FLOOK freezes a batch while new requests wait for the next batch.',challenge:'Make new requests arrive near the current head. Compare SSTF with FLOOK: reducing distance and keeping old requests waiting less are different goals.',fields:'head and track are integers from 0 to 9999. arrival is measured in simulated time. Moving one track costs one time unit. A request at the current head costs zero.'},
  linker:{title:'Give every name an address.',intro:'Source files can refer to names defined elsewhere. A linker lays out their object modules, collects definitions, then fills in references using final addresses.',read:'The main module has 3 instructions, so math starts at address 3. math defines add at offset 0. An offset is a position inside one module; an address is a position in the combined program.',observe:'Pass 1 builds the symbol table. Pass 2 visits every instruction and resolves its operand. The teaching opcodes are opaque numbers; this module does not execute instructions.',question:'main references add with addend 0. What final address should it receive?',choices:['0','3','4'],answer:'3',why:'math starts at 3 and defines add at local offset 0. Its final address is 3 + 0. A forward reference works because definitions are collected before relocation.',before:3,after:4,compare:'Compare the five modes in the instruction table: I keeps a literal; A checks an absolute address; R adds the current module base; E finds a symbol; M finds a named module.',challenge:'Rename add in its definition but keep the reference. Inspect the undefined-symbol diagnostic. Then restore it and move math before main to see relocation change.',fields:'modules are laid out in input order. definitions maps names to local offsets. code entries contain mode, opcode and value; E and M also need target. memory_limit bounds addresses.'},
  compiler:{title:'From an expression to a machine.',intro:'A compiler translates source into instructions. Here an OCaml front end reads a small language, and a code generator produces real RISC-V machine code.',read:'add(8, 6) produces 14. The let expression names that value total. An if expression selects one branch. In this language every expression produces a signed 32-bit integer.',observe:'Step through tokens, the syntax tree, name checks, reference evaluation, assembly emission and machine execution. The tree preserves the structure of the program.',question:'What should both the reference interpreter and the RISC-V program return?',choices:['14','42','0'],answer:'42',why:'total is 14, which is greater than 10. The then branch computes 14 × 3. QEMU runs the generated ELF and its output is compared with the interpreter.',before:3,after:6,compare:'A matching result is a concrete check for this input. Try several inputs and inspect how arithmetic, branches and function calls appear in the assembly.',challenge:'Write a recursive factorial function. Then try a missing variable or the wrong number of arguments to see which front-end check catches it.',fields:'Define functions with fn f(x) = expression; and finish with an expression. Use let x = value in body, if c then a else b, arithmetic and comparisons. Up to four arguments; # starts a comment.'},
  vm:{title:'Same address. Different memory.',intro:'Each process sees its own virtual address space. A page table tells the system which physical frame holds a virtual page. Two processes can use the same virtual address without sharing a frame.',read:'There are two physical frames and 4096 bytes per page. P0 uses anonymous pages; P1 uses file-backed pages. P0 page 3 is read-only. Areas use an exclusive end: [0, 3) includes pages 0, 1 and 2.',observe:'Split an address into page number and offset. Look up the page in that process’s table, then keep the offset when forming the physical address. A missing valid page needs a page fault.',question:'P1 reads virtual address 16 after P0 used frame 0. P1 page 0 gets frame 1. What physical address is used?',choices:['16','4096','4112'],answer:'4112',why:'The page offset is 16. Frame 1 begins at byte 4096, so the physical address is 1 × 4096 + 16. P0 and P1 have separate page tables.',before:1,after:2,compare:'With only two frames, pages must leave. Dirty anonymous pages go to swap; dirty file-backed pages go back to their file. Compare the six replacement rules on the same instruction stream.',challenge:'Add a third frame. Then change a virtual address to an unmapped page or write to a read-only page. Compare a normal page fault with an invalid or protected access.',fields:'processes declares pid and non-overlapping page areas. instructions uses switch, read, write or exit plus pid; reads and writes need a byte address. R means referenced; D means modified.'}
};
const stages = ['Meet the idea','Watch it happen','Make a prediction','Compare and explain','Try your own'];
const sessions = new Map();
let examples, selected, refresh = () => {}, switchMode = () => {}, playback;
const keyFor = (id,mode) => `${aliases[id] || id}:${mode}`;
const sessionFor = (id,mode) => {
  const key=keyFor(id,mode);
  if(!sessions.has(key)) sessions.set(key,{module:aliases[id]||id,mode,config:null,result:null,cursor:0,stage:0,answer:null,revealed:false,rows:null,busy:false,error:'',draft:null,complete:false});
  const s=sessions.get(key);
  if(!s.complete) {try{s.complete=localStorage.getItem(`suite.${s.module}.completed.v1`)==='true';}catch{}}
  return s;
};
const display = value => typeof value==='object' ? JSON.stringify(value) : typeof value==='number' && !Number.isInteger(value) ? value.toFixed(3) : value;
function table(rows, keys = rows[0] ? Object.keys(rows[0]) : []) {
  return `<div class="table-scroll"><table><thead><tr>${keys.map(k=>`<th>${escape(k.replaceAll('_',' '))}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${keys.map(k=>`<td>${escape(display(r[k]))}</td>`).join('')}</tr>`).join('') || `<tr><td colspan="${keys.length || 1}">No entries yet.</td></tr>`}</tbody></table></div>`;
}
async function api(path,config) {
  const response=await fetch(path,config?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(config)}:{});
  const data=await response.json();
  if(!response.ok) throw new Error(data.error || 'The experiment could not run.');
  return data;
}
async function run(s,config) {
  stopPlayback();s.busy=true;s.error='';refresh();
  try {const result=await api('/api/run',config);s.config=result.config;s.result=result;s.cursor=0;s.rows=null;s.draft=null;s.answer=null;s.revealed=false;}
  catch(error) {s.error=error instanceof TypeError?'Could not reach the local server. Check that it is running.':error.message;}
  finally {s.busy=false;refresh();}
}
export function stopPlayback() {clearInterval(playback);playback=null;}
export async function openModule(id,mode) {
  stopPlayback();selected=sessionFor(id,mode);
  if(selected.result || selected.busy) return;
  const s=selected;s.busy=true;refresh();
  try {examples ||= await api('/api/examples');await run(s,structuredClone(examples[s.module]));}
  catch(error) {s.error=error.message;s.busy=false;refresh();}
}
function guide(s) {
  const l=lessons[s.module];
  const content=[`<h2>Start with one idea.</h2><p>${l.intro}</p><div class="hint">${l.read}</div>`,`<h2>Take the first few steps.</h2><p>${l.observe}</p><div class="hint">Use Next event and Back. The highlighted state always belongs to the selected event.</div>`,`<h2>Pause and predict.</h2><p>${l.question}</p><div class="answer-options">${l.choices.map(choice=>`<button class="secondary ${s.answer===choice?'chosen':''}" data-exp="answer" data-value="${choice}">${choice}</button>`).join('')}</div>${s.answer?`<p class="hint">${s.answer===l.answer?'That is right.':'Try following the rule once more.'} ${l.why}</p><button class="primary full" data-exp="reveal">Show the result</button>`:'<p class="small muted">A guess is enough. You can change your answer.</p>'}`,`<h2>One input, different decisions.</h2><p>${l.compare}</p>${policies[s.module]?'<button class="primary full" data-exp="compare">Compare all policies</button>':'<button class="secondary full" data-exp="finish">Inspect the completed trace</button>'}`,`<h2>Make it your experiment.</h2><p>${l.challenge}</p><div class="hint">${l.fields}</div><button class="primary full" data-exp="lab">Open this module in Lab</button>`];
  return `<section class="lesson-card module-guide"><span class="section-kicker">STEP ${s.stage+1} OF 5</span>${content[s.stage]}<details class="module-details"><summary>Inspect the example input</summary><pre>${escape(pretty(s.config || {}))}</pre></details><div class="guide-bottom"><button class="secondary" data-exp="stage" data-value="${Math.max(0,s.stage-1)}" ${s.stage===0?'disabled':''}>Previous</button><button class="primary" data-exp="stage" data-value="${Math.min(4,s.stage+1)}">${s.stage===4?'Mark complete':'Continue'}</button></div>${s.complete?'<p class="hint">Lesson complete. Every module remains open to explore.</p>':''}</section>`;
}
function editor(s) {
  const c=s.config || examples?.[s.module];
  if(!c) return '<section class="lesson-card">Loading example…</section>';
  const options=policies[s.module];
  return `<section class="lesson-card module-editor"><span class="section-kicker">EXPERIMENT INPUT</span><h2>Change one thing.</h2><p>${lessons[s.module].fields}</p><form id="module-form">
    ${options?`<label for="module-policy">Policy</label><select id="module-policy" name="algorithm">${options.map(p=>`<option ${p===(s.draft?.algorithm||c.algorithm)?'selected':''}>${p}</option>`).join('')}</select>`:''}
    ${s.module==='compiler'?`<label for="module-source">Source program</label><textarea id="module-source" name="source" spellcheck="false" rows="12">${escape(s.draft?.text??c.source)}</textarea><label class="check-label"><input name="verify" type="checkbox" ${(s.draft?.verify??c.verify)?'checked':''}> Execute with QEMU</label>`:`<label for="module-input">Workload JSON</label><textarea id="module-input" name="input" spellcheck="false" rows="16">${escape(s.draft?.text??pretty(Object.fromEntries(Object.entries(c).filter(([k])=>!['schema_version','module','algorithm'].includes(k)))))}</textarea>`}
    <p id="module-draft" class="small muted">${s.draft?'Unapplied edits. The trace uses your last applied inputs.':'Edit the workload, then apply to build a new trace.'}</p><button class="primary full" ${s.busy?'disabled':''}>${s.busy?'Running…':'Apply and run'}</button></form>
    <div class="file-actions"><button class="text-button" data-exp="example">Reset example</button><button class="text-button" data-exp="import">Import JSON</button><button class="text-button" data-exp="export">Export config</button></div><input id="module-import" type="file" accept=".json,application/json" hidden>
    <details class="cli-details"><summary>Use the interactive CLI</summary><code>python3 suite.py shell --module ${s.module}</code><p>Use step, back, goto, config, set, save, export and help. Load the exported configuration with:</p><code>python3 suite.py shell experiment.json</code></details></section>`;
}
function explanation(s,e) {
  if(!e) return 'The input is ready. Take one step to see the first decision.';
  if(s.module==='cpu') return e.running<0?`Time ${e.time}–${e.end}: the CPU is idle because no process is ready.`:`Time ${e.time}–${e.end}: P${e.running} uses the CPU. ${e.outcome==='complete'?'It finishes its final CPU burst.':e.outcome==='block'?'It now waits for I/O.':e.outcome==='quantum-expired'?'Its time slice ends; it returns to a ready queue.':e.preempted>=0?`P${e.preempted} was preempted by this policy.`:'The process table shows the state at the end of this interval.'}`;
  if(s.module==='disk') return e.request<0?`No requests are ready. Time advances from ${e.time} to ${e.end}.`:`Request ${e.request}: move from track ${e.from} to ${e.to}, a distance of ${e.distance}. It waited ${e.waiting} time units before service began. Waiting queues are shown at dispatch.`;
  if(s.module==='linker') return e.pass===1?`Pass 1: ${e.module_name} starts at ${e.base} and occupies ${e.size} instruction addresses. Add its definitions to the symbol table.`:`Pass 2: instruction ${e.address} in ${e.module_name} uses mode ${e.mode}${e.target?` with target ${e.target}`:''}. Its operand changes from ${e.original} to ${e.resolved}.`;
  if(s.module==='compiler') return e.description;
  return `P${e.pid} · ${e.operation}: ${e.outcome.replaceAll('-',' ')}. ${e.actions.join(' → ')}.${e.physical>=0?` Physical address: ${e.physical}.`:''}`;
}
function cpuView(s,e) {
  const visited=s.result.events.slice(0,s.cursor);
  return `<div class="section-kicker">CPU TIMELINE · ONE TILE PER TIME UNIT</div><div class="cpu-timeline">${visited.map(x=>`<button data-exp="goto" data-value="${x.index+1}" style="--process-color:var(--process-${x.running<0?'idle':x.running%5})" class="time-tile ${x.index===s.cursor-1?'selected':''}" title="Time ${x.time} to ${x.end}: ${x.running<0?'idle':'P'+x.running}"><small>${x.time}</small>${x.running<0?'—':'P'+x.running}</button>`).join('')||'<p class="muted">The timeline starts empty.</p>'}</div><h3>Process state</h3>${table(e?.processes || s.config.processes.map((p,id)=>({id,state:'new',remaining:p.bursts.filter((_,i)=>i%2===0).reduce((a,b)=>a+b,0),priority:p.priority,waiting:0})),['id','state','remaining','priority','waiting'])}<p class="small muted">remaining counts CPU work only. Waiting counts time ready but not running.</p>`;
}
function diskView(s,e) {
  const visits=s.result.events.slice(0,s.cursor).filter(x=>x.request>=0);
  const maximum=Math.max(100,s.config.head,...s.config.requests.map(r=>r.track));
  const x=t=>40+520*t/maximum, y=i=>30+i*26;
  const points=[s.config.head,...visits.map(v=>v.to)];const height=Math.max(140,y(points.length)+25);
  return `<div class="section-kicker">HEAD PATH · TRACK 0 TO ${maximum}</div><div class="disk-path"><svg viewBox="0 0 600 ${height}" role="img" aria-label="Disk head moves through tracks ${points.join(', ')}"><line x1="40" y1="16" x2="560" y2="16" stroke="#b8c5c0"/><text x="40" y="12">0</text><text x="540" y="12">${maximum}</text><polyline points="${points.map((t,i)=>`${x(t)},${y(i)}`).join(' ')}" fill="none" stroke="#25816d" stroke-width="3"/>${points.map((t,i)=>`<circle cx="${x(t)}" cy="${y(i)}" r="5" fill="#25816d"/><text x="${x(t)+9}" y="${y(i)+4}">${t}${i?' · R'+visits[i-1].request:' · start'}</text>`).join('')}</svg></div><p><strong>Head:</strong> ${e?.to??s.config.head} · <strong>Distance so far:</strong> ${e?.movement||0}</p>${table(s.config.requests.map((r,id)=>({id,...r,state:visits.some(v=>v.request===id)?'served':r.arrival<=(e?.end||0)?'waiting':'not arrived'})),['id','arrival','track','state'])}${s.config.algorithm==='flook'?`<p class="small muted">Frozen queue at last dispatch: ${escape(e?.queue || [])} · Incoming: ${escape(e?.incoming || [])}</p>`:''}`;
}
function linkerView(s,e) {
  const seen=s.result.events.slice(0,s.cursor),symbols=[...seen].reverse().find(x=>x.symbols)?.symbols||[];
  return `<div class="link-passes"><span class="${e?.pass===1?'active':''}">1 · Collect definitions</span><span class="${e?.pass===2?'active':''}">2 · Resolve operands</span></div><h3>Symbol table</h3>${table(symbols,['name','module','address'])}<h3>Resolved instructions</h3>${table(seen.filter(x=>x.pass===2),['address','module_name','mode','target','original','resolved'])}<details class="module-details"><summary>Addressing mode reference</summary><p>I = immediate literal · A = absolute address · R = current module base + offset · E = symbol address + addend · M = named module base + offset.</p></details>${s.cursor===s.result.events.length?`<h3>Diagnostics</h3>${table(s.result.diagnostics,['level','code','module','address','message'])}`:''}`;
}
function tree(value) {
  if(value===null || typeof value!=='object') return `<span>${escape(value)}</span>`;
  if(Array.isArray(value)) return `<ul>${value.map(v=>`<li>${tree(v)}</li>`).join('')}</ul>`;
  return `<ul>${Object.entries(value).map(([k,v])=>`<li><strong>${escape(k)}</strong> ${typeof v==='object'?tree(v):`<span>${escape(v)}</span>`}</li>`).join('')}</ul>`;
}
function compilerView(s,e) {
  const r=s.result;
  return `<div class="compiler-stages">${r.events.map((v,i)=>`<button class="${i===s.cursor-1?'active':''}" data-exp="goto" data-value="${i+1}">${i+1}. ${v.stage}</button>`).join('')}</div>${!e?`<h3>Your program</h3><pre>${escape(s.config.source)}</pre>`:e.stage==='lex'?`<h3>Tokens</h3><div class="tokens">${r.tokens.map(t=>`<span title="Line ${t.line}, column ${t.column}">${escape(t.text)}</span>`).join('')}</div>`:e.stage==='parse'?`<h3>Syntax tree</h3><div class="syntax-tree">${tree(r.ast)}</div>`:e.stage==='check'?'<h3>Names and calls checked</h3><p>Every variable is bound, every called function exists, and argument counts match. A failed check stops compilation with a diagnostic.</p>':e.stage==='interpret'?`<div class="result-number">${r.reference_result}</div><p>Reference result from the OCaml interpreter. Arithmetic uses signed 32-bit values with wraparound.</p>`:e.stage==='emit'?`<h3>Generated RV64IM assembly</h3><pre class="assembly">${escape(r.assembly)}</pre>`:`<div class="verification ${r.verification.status==='passed'?'passed':''}"><strong>QEMU: ${escape(r.verification.status)}</strong><p>Reference: ${r.reference_result} · Machine result: ${r.verification.result??'unavailable'}</p>${r.verification.message?`<p>${escape(r.verification.message)}</p>`:''}</div><p>This ELF runs on QEMU’s RISC-V virt machine with a small bare-metal entry point. It uses UART output, not the Linux syscall ABI.</p><div class="file-actions"><a class="secondary" href="/api/artifacts/${r.artifact_id}/program.s" download>Download assembly</a><a class="secondary" href="/api/artifacts/${r.artifact_id}/program.elf" download>Download ELF</a></div>`}`;
}
function vmView(s,e) {
  const frames=e?.frames||Array.from({length:s.config.frames},(_,slot)=>({slot,pid:-1,page:-1,referenced:false,dirty:false}));
  return `${e && ['read','write'].includes(e.operation)?`<div class="address-equation"><span>Virtual ${e.address}<small>page ${e.page} · offset ${e.offset}</small></span><b>→</b><span>${e.physical>=0?`Physical ${e.physical}`:'Access rejected'}<small>${e.physical>=0?`frame ${Math.floor(e.physical/s.config.page_size)} × ${s.config.page_size} + ${e.offset}`:e.outcome}</small></span></div>`:'<p>Each process translates its own virtual addresses.</p>'}<div class="vm-frames">${frames.map(f=>`<div class="vm-frame ${f.pid<0?'empty':''}"><small>FRAME ${f.slot}</small><strong>${f.pid<0?'Free':`P${f.pid} / page ${f.page}`}</strong><span>R ${+f.referenced} · D ${+f.dirty}</span></div>`).join('')}</div><h3>Page tables · touched pages only</h3>${(e?.page_tables||s.config.processes.map(p=>({pid:p.pid,alive:true,pages:[]}))).map(p=>`<h4>Process ${p.pid} ${p.alive?'':'· exited'}</h4>${table(p.pages,['page','present','frame','dirty','swapped','read_only','file_mapped'])}`).join('')}<p class="small muted">Frame numbers start at 0. A protected write can be translated but is rejected before modifying the page. Swap and file actions are simulated; page contents are not stored.</p>`;
}
const views={cpu:cpuView,disk:diskView,linker:linkerView,compiler:compilerView,vm:vmView};
export function moduleMarkup(id,mode) {
  const s=sessionFor(id,mode),l=lessons[s.module],e=s.result?.events[s.cursor-1];
  return `<div class="hero"><div><div class="eyebrow">${escape(names[s.module])} / ${mode==='learn'?'GUIDED EXPLORATION':'EXPERIMENT WORKSPACE'}</div><h1>${l.title}</h1><p>${mode==='learn'?'Understand the idea, watch a decision, then try your own input.':'Change the workload. Inspect the decisions. Export a reproducible experiment.'}</p></div><div class="mode-toggle"><button data-action="mode" data-value="learn" aria-pressed="${mode==='learn'}" class="${mode==='learn'?'active':''}">Learn</button><button data-action="mode" data-value="lab" aria-pressed="${mode==='lab'}" class="${mode==='lab'?'active':''}">Lab</button></div></div>
    ${s.error?`<div class="error" role="alert">${escape(s.error)} <button data-exp="retry" class="secondary">Retry applied input</button></div>`:''}
    ${mode==='learn'?`<div class="lesson-rail">${stages.map((t,i)=>`<button class="lesson-stop ${i===s.stage?'current':''}" data-exp="stage" data-value="${i}"><span class="step-number">${i+1}</span>${t}</button>`).join('')}</div>`:''}
    <div class="experiment-layout module-layout">${mode==='learn'?guide(s):editor(s)}<section class="simulation module-simulation"><div class="simulation-heading"><strong>${escape(names[s.module])}</strong><span class="algorithm-badge">${escape(s.config?.algorithm?.toUpperCase() || 'TRACE')}</span></div>${s.busy?'<p role="status">Running the experiment…</p>':''}${s.result?views[s.module](s,e):'<p>Your example will appear here.</p>'}<div class="event-explanation"><span class="event-symbol">↳</span><div><strong>${s.cursor?`Event ${s.cursor} of ${s.result?.events.length}`:'Ready when you are.'}</strong><p>${escape(explanation(s,e))}</p></div></div><div class="transport"><div class="transport-buttons"><button class="secondary" data-exp="reset">Reset</button><button class="secondary" data-exp="back" ${s.cursor===0?'disabled':''}>Back</button><button class="primary" data-exp="step" ${!s.result || s.busy || s.cursor===s.result.events.length?'disabled':''}>Next event →</button><button class="secondary" data-exp="play" ${!s.result || s.busy || s.cursor===s.result.events.length?'disabled':''}>${playback && selected===s?'Pause':'Play'}</button></div></div></section></div>
    ${s.result && (mode==='lab' || s.stage>=3)?`<section class="comparison module-summary"><div><span class="section-kicker">FULL-RUN RESULTS · INDEPENDENT OF PLAYBACK</span><h3>What happened across the whole workload?</h3></div><div class="summary-grid">${Object.entries(s.result.summary).map(([k,v])=>`<div><strong>${escape(display(v))}</strong><span>${escape(k.replaceAll('_',' '))}</span></div>`).join('')}</div><div class="file-actions">${policies[s.module]?'<button class="secondary" data-exp="compare">Compare all policies</button>':''}<button class="text-button" data-exp="trace">Export full trace</button></div>${s.rows?table(s.rows):''}</section><details class="module-details raw-event"><summary>Inspect the current event data</summary><pre>${escape(pretty(e||{}))}</pre></details>`:''}`;
}
function download(value,name) {
  const url=URL.createObjectURL(new Blob([pretty(value)+'\n'],{type:'application/json'}));
  const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function navigate(s,cursor) {s.cursor=Math.max(0,Math.min(s.result?.events.length||0,cursor));refresh();document.querySelector('#announcer').textContent=explanation(s,s.result?.events[s.cursor-1]);}
export function bindModules(redraw,onMode) {
  refresh=redraw;switchMode=onMode;
  document.addEventListener('click',async event=>{
    const b=event.target.closest('[data-exp]');if(!b || b.disabled || !selected) return;
    const s=selected,action=b.dataset.exp;if(s.busy) return;
    if(action!=='play') stopPlayback();
    if(action==='step') navigate(s,s.cursor+1);
    if(action==='back') navigate(s,s.cursor-1);
    if(action==='reset') navigate(s,0);
    if(action==='goto') navigate(s,Number(b.dataset.value));
    if(action==='finish') navigate(s,s.result.events.length);
    if(action==='play') {if(playback){stopPlayback();refresh();}else{playback=setInterval(()=>{if(selected!==s || s.cursor>=s.result.events.length){stopPlayback();refresh();return;}navigate(s,s.cursor+1);},900);refresh();}}
    if(action==='stage') {const n=Number(b.dataset.value);if(s.stage===4 && n===4){s.complete=true;try{localStorage.setItem(`suite.${s.module}.completed.v1`,'true');}catch{}}s.stage=n;s.answer=null;s.revealed=false;navigate(s,n===0?0:n===1?1:n===2?lessons[s.module].before:s.cursor);}
    if(action==='answer') {s.answer=b.dataset.value;refresh();}
    if(action==='reveal') {s.revealed=true;navigate(s,lessons[s.module].after);}
    if(action==='lab') await switchMode('lab');
    if(action==='example') await run(s,structuredClone(examples[s.module]));
    if(action==='retry') {if(s.config) await run(s,s.config);else await openModule(s.module,s.mode);}
    if(action==='compare') {s.busy=true;s.error='';refresh();try{s.rows=await api('/api/compare',s.config);}catch(error){s.error=error.message;}finally{s.busy=false;refresh();}}
    if(action==='export') download(s.config,'experiment.json');
    if(action==='trace') download(s.result,`${s.module}-trace.json`);
    if(action==='import') document.querySelector('#module-import').click();
  });
  document.addEventListener('input',event=>{
    if(!event.target.closest('#module-form') || !selected)return;
    stopPlayback();
    const form=new FormData(document.querySelector('#module-form'));
    selected.draft={text:form.get('source')??form.get('input'),algorithm:form.get('algorithm'),verify:form.has('verify')};
    document.querySelector('#module-draft').textContent='Unapplied edits. The trace uses your last applied inputs.';
  });
  document.addEventListener('submit',async event=>{
    if(event.target.id!=='module-form')return;event.preventDefault();
    const s=selected;if(s.busy)return;const form=new FormData(event.target);
    try {const config=s.module==='compiler'?{source:form.get('source'),verify:form.has('verify')}:JSON.parse(form.get('input'));
      if(!config || Array.isArray(config) || typeof config!=='object')throw new Error('The workload must be a JSON object.');
      if(policies[s.module])config.algorithm=form.get('algorithm');
      await run(s,{...config,schema_version:1,module:s.module});
    }catch(error){s.error=error.message;refresh();}
  });
  document.addEventListener('change',async event=>{
    if(event.target.id!=='module-import' || !event.target.files[0])return;
    const s=selected;
    try {const file=event.target.files[0];if(file.size>65536)throw new Error('Choose a configuration under 64 KB.');const config=JSON.parse(await file.text());if(config.module!==s.module)throw new Error('Select the matching module before importing this file.');await run(s,config);}catch(error){s.error=error.message;refresh();}
  });
}

export function moduleNotes(id) {
  const module=aliases[id]||id;
  const entries={
    cpu:[['Ready','The process can run but is waiting for a CPU turn.'],['Blocked','The process is waiting for I/O; it cannot use the CPU yet.'],['Quantum','The maximum length of one time slice in RR and priority scheduling.'],['Preemption','The scheduler interrupts a running process and returns it to a ready queue.'],['Response time','Time from arrival until the first CPU instruction.'],['Turnaround time','Time from arrival to completion, including CPU work, I/O and ready waiting.'],['Dynamic priority','A priority that falls when a time slice expires. I/O completion restores the static priority.']],
    disk:[['Track','A numbered location the simulated disk head can visit.'],['Seek distance','The absolute difference between the starting track and the destination.'],['Waiting time','Time from a request’s arrival until service starts.'],['LOOK','Serve in one direction and reverse when no waiting request remains in that direction.'],['CLOOK','Serve upward; wrap to the lowest waiting track when needed. The wrap costs distance too.'],['FLOOK','Serve a frozen batch with LOOK while new arrivals collect in a separate queue.']],
    linker:[['Object module','A named block of instructions and local symbol definitions.'],['Base address','Where a module begins in the combined address space.'],['Offset','A position measured from the beginning of a module.'],['Symbol','A name bound to an address, such as a function entry.'],['Relocation','Computing a final operand from a local offset, symbol, or module reference.'],['Diagnostic','An error or warning with a code and location. The linker continues with a documented fallback so you can inspect other instructions.']],
    compiler:[['Token','A small meaningful piece of source, such as a name, number or operator.'],['Syntax tree','A tree of expressions that records grouping and precedence.'],['Semantic check','Validation of names, bindings, function definitions and argument counts.'],['Reference interpreter','An OCaml evaluator that computes the expected result from the syntax tree.'],['RISC-V','The instruction set used by the generated machine code. This compiler targets RV64IM.'],['ELF','The executable file container holding the generated instructions.'],['QEMU','An emulator that executes those instructions. Passed means its output matched the reference for this program.']],
    vm:[['Virtual address','A byte address interpreted within one process’s address space.'],['Page table','A per-process mapping from virtual pages to physical frames.'],['Offset','The byte position within a page. It stays unchanged during translation.'],['Protection fault','An attempted write to a read-only page. The page may be loaded, but the write is rejected.'],['Segmentation fault','An access outside the process’s declared areas. No page is allocated.'],['Swap','Simulated storage for anonymous pages removed from physical memory.'],['File-backed page','A page loaded from a file. A dirty eviction or process exit causes a simulated file-out.']]
  };
  return `<h2 id="notes-title">${escape(names[module])} field notes.</h2><p>Use these definitions alongside the current experiment.</p><dl>${entries[module].map(([term,definition])=>`<dt>${term}</dt><dd>${definition}</dd>`).join('')}</dl><div class="hint">${lessons[module].fields}</div>`;
}
