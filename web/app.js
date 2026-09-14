import {moduleMarkup, openModule, bindModules, stopPlayback, moduleNotes} from './modules.js';
const icons = {
  memory: '<rect x="5" y="5" width="14" height="14" rx="3"/><path d="M9 1v4m6-4v4M9 19v4m6-4v4M1 9h4m-4 6h4m14-6h4m-4 6h4"/><path d="M9 9h6v6H9z"/>',
  cpu: '<path d="M3 17h3V7h4v10h4V4h4v13h3"/>',
  disk: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3"/><path d="m14 10 5-5"/>',
  link: '<path d="m10 14 4-4m-6 6-1 1a4 4 0 0 1-6-6l4-4a4 4 0 0 1 6 0m2 10a4 4 0 0 0 6 0l4-4a4 4 0 0 0-6-6l-1 1"/>',
  code: '<path d="m8 6-6 6 6 6m8-12 6 6-6 6m-3-15-2 18"/>',
  book: '<path d="M12 5v16M2 3c4-1 7 0 10 2 3-2 6-3 10-2v16c-4-1-7 0-10 2-3-2-6-3-10-2z"/>',
  lab: '<path d="M8 2h8m-6 0v7L3 20q-1 2 2 2h14q3 0 2-2L14 9V2M7 15h10"/>',
  arrow: '<path d="M5 12h14m-5-5 5 5-5 5"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  play: '<path d="m8 4 12 8-12 8z"/>',
  reset: '<path d="M3 10a9 9 0 1 1 1 7M3 3v7h7"/>',
  terminal: '<path d="m4 6 6 6-6 6m9 0h7"/>',
  spark: '<path d="m12 2 3 7 7 3-7 3-3 7-3-7-7-3 7-3z"/>',
  download: '<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',
};
const icon = (name, cls = '') => `<svg class="icon ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name] || icons.memory}</svg>`;
const escape = value => String(value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const defaults = {schema_version: 1, module: 'memory', algorithm: 'fifo', frames: 3, references: [1,2,3,1,4,2,5,2,3,4,5,1]};
const policies = {fifo:'FIFO', random:'Random', clock:'Clock', nru:'NRU', aging:'Aging', 'working-set':'Working Set'};
const policyRules = {
  fifo:'FIFO removes the resident page loaded earliest. Hits do not change arrival order.',
  random:'Random selects a frame using the configured seed. Repeating the inputs and seed repeats the result.',
  clock:'Clock clears marked reference bits while scanning, then replaces the first unmarked page.',
  nru:'NRU prefers the lowest reference/dirty class: 00, 01, 10, then 11. Reference bits reset periodically.',
  aging:'Aging samples reference bits into 32-bit counters at each reset interval and replaces the smallest counter.',
  'working-set':'Working Set scans from the hand, refreshes marked pages, and chooses an unmarked page older than the window. It falls back to the oldest sampled page.'
};
const anomaly = [1,2,3,4,1,2,5,1,2,3,4,5];
const titles = ['Meet the pages', 'Fill the frames', 'Make a prediction', 'Change the policy', 'Check your intuition'];
const modules = [
  {id:'memory', icon:'memory', title:'Virtual memory', sub:'Make room for one more', question:'How can a program use more memory than fits in RAM?', concepts:['Pages and physical frames', 'Page hits, faults, and replacement', 'FIFO and Clock policies']},
  {id:'vm', icon:'memory', title:'Address spaces', sub:'Translate each process address'},
  {id:'cpu', icon:'cpu', title:'CPU scheduling', sub:'Decide who runs next', question:'When several programs need the CPU, who should go first?', concepts:['Ready, running, and blocked states', 'Time slices and preemption', 'Response time versus throughput'], example:'Imagine a short keyboard task arriving while a long calculation is running. Letting the calculation finish is simple, but a time slice can help the keyboard task respond sooner.', experiment:'Predict the next process, move through a scheduling timeline, then compare six policies on the same workload.'},
  {id:'disk', icon:'disk', title:'Disk scheduling', sub:'Find a shorter path', question:'Can changing request order reduce the distance a disk head travels?', concepts:['Requests, tracks, and head position', 'Seek distance and waiting time', 'FIFO, SSTF, LOOK, CLOOK, and FLOOK'], example:'A head at track 50 receives requests for tracks 10, 90, and 55. The first request is not the nearest request. Which order would you try?', experiment:'Choose the next request, watch the head move, then compare distance and waiting time. This models a moving-head disk, not an SSD.'},
  {id:'link', icon:'link', title:'Linking', sub:'Connect the missing pieces', question:'How does a call to a function in another file get an address?', concepts:['Object modules and symbol definitions', 'Symbol resolution across two passes', 'Five teaching addressing modes'], example:'One module calls a function named add. Another defines add at a local offset. The linker needs the module location and the definition before it can fill in the call target.', experiment:'Build a symbol table, resolve a reference, and inspect each relocation. The teaching object format is separate from real ELF linking.'},
  {id:'code', icon:'code', title:'Compilation', sub:'Follow a program into assembly', question:'How does a line of source code become instructions a machine can execute?', concepts:['Tokens, syntax trees, and semantic checks', 'An OCaml compiler front end', 'RISC-V output and reference execution'], example:'For the expression 2 + 3 * 4, the syntax tree must preserve multiplication before addition. A reference interpreter and generated code should both produce 14.', experiment:'Inspect tokens and a syntax tree, fix a semantic error, and compare interpreted results with RISC-V execution under QEMU.'},
];
let completed = false;
try { completed = localStorage.getItem('suite.memory.completed.v1') === 'true'; } catch {}
const state = {module:'memory', mode:'learn', lesson:0, cursor:0, config:structuredClone(defaults), runs:{}, prediction:null, quiz:null, completed, playing:false, busy:true, error:'', toast:'', lab:null, draft:null, glossary:false};
let timer;
let requestId = 0;
const app = document.querySelector('#app');
const current = () => state.runs[state.config.algorithm];
const event = () => current()?.events[state.cursor - 1];
const announce = message => { document.querySelector('#announcer').textContent = message; };

async function calculate(config = state.config, reset = true) {
  pause();
  const id = ++requestId;
  state.busy = true;
  state.error = '';
  render();
  try {
    if (!config || !Object.hasOwn(policies,config.algorithm)) throw new Error('Choose a supported replacement policy.');
    if (!Array.isArray(config.references) || config.references.length > 128 || config.frames > 8) throw new Error('The visual lab supports up to 8 frames and 128 accesses. Use the CLI for larger workloads (64 frames and 4096 accesses).');
    const results = await Promise.all(Object.keys(policies).map(async algorithm => {
      const response = await fetch('/api/run', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({...config, algorithm})});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'The experiment could not run.');
      return [algorithm, data];
    }));
    if (id !== requestId) return;
    state.config = structuredClone(config);
    state.draft = null;
    state.runs = Object.fromEntries(results);
    state.cursor = reset ? 0 : Math.min(state.cursor, config.references.length);
  } catch (error) {
    if (id === requestId) state.error = error instanceof TypeError ? 'Could not reach the local server. Start it with python3 suite.py serve.' : error.message;
  } finally {
    if (id === requestId) { state.busy = false; render(); }
  }
}

function pause() { clearInterval(timer); state.playing = false; }
function limit() {
  if (state.mode === 'learn' && state.lesson === 1) return 4;
  if (state.mode === 'learn' && state.lesson === 2) return 5;
  return state.config.references.length;
}
function step(delta = 1) {
  if (state.busy || !current()) return;
  state.cursor = Math.max(0, Math.min(limit(), state.cursor + delta));
  if (state.cursor >= limit()) pause();
  render();
  announce(describe(event()).text);
}
function describeBase(e) {
  if (!e) return {kind:'ready', title:'Your memory starts empty.', text:`The program will ask for page ${state.config.references[0]}. Take one step to see where it goes.`};
  if (e.hit) return {kind:'hit', title:`Page ${e.page} is already here.`, text:`This is a page hit. Frame ${e.slot + 1} already holds page ${e.page}, so nothing needs to be loaded or replaced.${state.config.algorithm === 'fifo' ? ' FIFO keeps the original arrival order, even after a hit.' : ' Its reference bit is set to 1.'}`};
  if (e.victim < 0) return {kind:'fault', title:`Page ${e.page} gets an empty frame.`, text:`This is a page fault: the requested page is not in RAM yet. Load it into empty frame ${e.slot + 1}. A fault is part of normal operation here; it is not a program crash.`};
  return {kind:'replace', title:`Page ${e.page} takes page ${e.victim}’s place.`, text:state.config.algorithm === 'fifo'
    ? `All frames are full. FIFO removes page ${e.victim}, the page loaded earliest among those still here. Page ${e.page} is loaded into frame ${e.slot + 1}.`
    : state.config.algorithm === 'clock' ? `Clock ${e.cleared.length ? `clears ${e.cleared.length} reference bit${e.cleared.length === 1 ? '' : 's'} while scanning, then ` : ''}chooses page ${e.victim}, whose reference bit is 0. Page ${e.page} is loaded into frame ${e.slot + 1}.`
    : `${policyRules[state.config.algorithm]} Page ${e.victim} leaves frame ${e.slot + 1}.`};
}

function describe(e) {
  const explanation = describeBase(e);
  if(e?.writeback) explanation.text += ' The removed page was dirty, so it required a simulated writeback.';
  if(e?.write) explanation.text += ' This access writes to the page, setting its dirty bit.';
  return explanation;
}

function frameDetails(frame) {
  if(frame.page < 0) return 'Available';
  if(state.mode === 'learn') return state.config.algorithm === 'clock' ? `Reference bit: ${frame.referenced ? '1 · recent' : '0 · eligible'}` : 'In memory';
  const bits = `R ${Number(frame.referenced)} · D ${Number(frame.dirty)}`;
  if(state.config.algorithm === 'aging') return `Age ${frame.age.toString(16).padStart(8,'0')} · ${bits}`;
  if(state.config.algorithm === 'working-set') return `Seen at ${frame.last_seen} · ${bits}`;
  return bits;
}

function sidebar() {
  return `<aside class="sidebar">
    <a class="brand" href="#" data-action="home"><span class="brand-mark">${icon('memory')}</span><span>systems<span class="brand-small">PROGRAMMING SUITE</span></span></a>
    <div class="sidebar-label">YOUR WORKSPACE</div>
    <button class="workspace-link ${state.mode === 'learn' ? 'selected' : ''}" data-action="mode" data-value="learn">${icon('book')} Learning path</button>
    <button class="workspace-link ${state.mode === 'lab' ? 'selected' : ''}" data-action="mode" data-value="lab">${icon('lab')} Experiment lab</button>
    <div class="sidebar-label module-label">EXPLORE SYSTEMS <span>06</span></div>
    <nav aria-label="Systems modules">${modules.map((m,i) => `<button class="module-link ${state.module === m.id ? 'active' : ''}" data-action="module" data-value="${m.id}" ${state.module === m.id ? 'aria-current="page"' : ''}>${icon(m.icon)}<span>${m.title}<small>Learn + Lab</small></span>${state.module === m.id ? '<span class="active-dot"></span>' : ''}</button>`).join('')}</nav>
    <div class="sidebar-note"><span class="tiny-tag">SMALL STEPS. REAL SYSTEMS.</span><p>You do not need to know the answer before you begin.</p><span class="note-line"></span><span class="muted">Learn it. Try it. Make it yours.</span></div>
    <div class="local-status"><span></span> Runs on your computer</div>
  </aside>`;
}

function header() {
  const m = modules.find(m => m.id === state.module);
  return `<header class="topbar"><div class="breadcrumb">Workspace <span>/</span> <strong>${m.title}</strong></div>
    <div class="topbar-right"><span class="preview-badge">LOCAL SUITE</span><button class="text-button" data-action="glossary">${icon('book')} Field notes</button><span class="avatar" title="Local workspace">S</span></div></header>`;
}

function hero() {
  return `<div class="hero"><div><div class="eyebrow"><span class="green-line"></span> MEMORY / ${state.mode === 'learn' ? 'GUIDED EXPLORATION' : 'EXPERIMENT WORKSPACE'}</div>
    <h1>${state.mode === 'learn' ? 'A little memory. A lot to discover.' : 'Your workload. Your experiment.'}</h1>
    <p>${state.mode === 'learn' ? 'See how a computer makes room when memory fills up. One page at a time.' : 'Change the inputs, inspect every access, and compare replacement policies.'}</p></div>
    <div class="mode-toggle" aria-label="Workspace mode"><button data-action="mode" data-value="learn" aria-pressed="${state.mode === 'learn'}" class="${state.mode === 'learn' ? 'active' : ''}">${icon('book')} Learn</button><button data-action="mode" data-value="lab" aria-pressed="${state.mode === 'lab'}" class="${state.mode === 'lab' ? 'active' : ''}">${icon('lab')} Lab</button></div></div>`;
}

function lessonRail() {
  return `<div class="lesson-rail" aria-label="Lesson sections">${titles.map((name,i) => `<button data-action="lesson" data-value="${i}" class="lesson-stop ${state.lesson === i ? 'current' : ''}" ${state.lesson === i ? 'aria-current="step"' : ''}><span class="step-number">${i+1}</span><span>${name}</span></button>`).join('')}</div>`;
}

function lessonText() {
  const bodies = [
    `<h2>Think of RAM as a small desk.</h2><p>A program keeps its information in pieces called <button class="term" data-action="glossary">pages</button>. RAM has a limited number of spaces, called <button class="term" data-action="glossary">frames</button>, where those pages can fit.</p><p>Our desk has <strong>three frames</strong>. The program will ask for more than three different pages. Let’s find out what happens.</p><div class="learning-goal">${icon('spark')}<div><strong>Your goal</strong><span>Explain a page hit, a page fault, and why a page gets replaced.</span></div></div>`,
    `<h2>Give each page a place.</h2><p>Press <strong>Next access</strong> four times. Watch pages 1, 2, and 3 fill the frames. Then the program asks for page 1 again.</p><p>Does page 1 need to be loaded a second time? The explanation beside the frames changes with each access.</p><div class="hint"><strong>Notice the fourth access.</strong><br>A page can be used again without moving it or making a new copy.</div>`,
    `<h2>One more page. No more room.</h2><p>The next request is for <strong>page 4</strong>. All three frames are occupied. We are using <strong>FIFO</strong>: first in, first out.</p><p>Which page do you think will leave?</p><div class="prediction" role="group" aria-label="Choose the page FIFO will replace">${[1,2,3].map(page => `<button data-action="predict" data-value="${page}" aria-pressed="${state.prediction === page}" class="${state.prediction === page ? 'chosen' : ''}">Page ${page}</button>`).join('')}</div>
    ${state.prediction !== null ? `<div class="feedback ${state.prediction === 1 ? 'correct' : ''}">${state.prediction === 1 ? 'That’s the FIFO rule: page 1 arrived first. Its recent hit does not change its place in line.' : `A useful guess. Page ${state.prediction} arrived after page 1. FIFO tracks arrival order, not how recently a page was used. Try again or reveal the result.`}</div>` : '<p class="small muted">Make a guess. You can change your answer, or reveal the result.</p>'}
    <button class="secondary" data-action="reveal" ${state.busy ? 'disabled' : ''}>${state.cursor >= 5 ? 'Result shown in the frames' : 'Reveal the next access'} ${icon('arrow')}</button>`,
    `<h2>Give a recently used page a chance.</h2><p><strong>Clock</strong> adds a reference bit: a small “used recently” marker. A moving hand clears marked frames and replaces the first unmarked page it finds.</p><p>Switch policies below, then move through the remaining accesses. On access 7, look at whether page 2 survives.</p><div class="policy-picker">${['fifo','clock'].map(a => `<button data-action="algorithm" data-value="${a}" aria-pressed="${state.config.algorithm === a}" class="${state.config.algorithm === a ? 'chosen' : ''}">${a === 'fifo' ? 'FIFO · arrival order' : 'Clock · second chance'}</button>`).join('')}</div><div class="hint">Neither policy wins on every workload. Use the same inputs to make a fair comparison.</div>`,
    `<h2>Test an intuition, not your memory.</h2><p>If we give FIFO one more frame, will the number of page faults <em>always</em> stay the same or decrease?</p><div class="quiz-options">${[['yes','Yes, more space always helps'],['no','No, the request order can matter']].map(([v,label])=>`<button data-action="quiz" data-value="${v}" class="${state.quiz === v ? 'chosen' : ''}" aria-pressed="${state.quiz === v}">${label}</button>`).join('')}</div>
    ${state.quiz ? `<div class="feedback ${state.quiz === 'no' ? 'correct' : ''}">${state.quiz === 'no' ? 'Exactly. FIFO can have more faults with more frames. This is called Belady’s anomaly. Open the challenge in Lab and compare 3 frames with 4.' : 'That is a reasonable intuition, but FIFO has counterexamples. Replacements change the future arrival order. Try the other answer, then explore the challenge.'}</div>` : ''}
    <button class="secondary" data-action="challenge">Try the counterexample in Lab ${icon('arrow')}</button>`,
  ];
  return `<section class="lesson-copy"><div class="section-kicker">STEP ${String(state.lesson + 1).padStart(2,'0')} <span>/ 05</span></div>${bodies[state.lesson]}</section>`;
}

function labConfig() {
  const draft = state.draft || {algorithm:state.config.algorithm, frames:state.config.frames, references:state.config.references.map((page,i)=>(state.config.writes?.includes(i)?'w':'')+page).join(', '), seed:state.config.seed??1, reset_interval:state.config.reset_interval??4, window:state.config.window??4};
  return `<section class="lab-config"><div class="section-kicker">EXPERIMENT CONFIGURATION</div><h2>Set up your run.</h2><p class="muted small">All six policies run against these exact inputs. Apply changes to begin a new trace.</p>
    <form id="config-form"><label for="algorithm">Replacement policy</label><select id="algorithm" name="algorithm">${Object.entries(policies).map(([key,name])=>`<option value="${key}" ${draft.algorithm===key?'selected':''}>${name}</option>`).join('')}</select>
    <label for="frames">Physical frames <span>1–8</span></label><input id="frames" name="frames" type="number" min="1" max="8" step="1" required value="${escape(draft.frames)}">
    <label for="references">Page reference sequence</label><textarea id="references" name="references" rows="3" required aria-describedby="refs-help">${escape(draft.references)}</textarea><p id="refs-help" class="field-help">Use 7 or r7 to read, w7 to write. Page numbers 0–999, separated by commas or spaces. Up to 128 accesses.</p>
    <details class="policy-settings"><summary>Policy parameters</summary><label for="seed">Random seed</label><input id="seed" name="seed" type="number" min="0" max="4294967295" step="1" required value="${escape(draft.seed)}"><label for="reset-interval">NRU / Aging reset interval</label><input id="reset-interval" name="reset_interval" type="number" min="1" max="4096" step="1" required value="${escape(draft.reset_interval)}"><label for="window">Working Set window</label><input id="window" name="window" type="number" min="1" max="4096" step="1" required value="${escape(draft.window)}"><p class="field-help">Intervals count accesses. Sampling occurs before the next access after each interval.</p></details>
    <button class="primary full" type="submit" ${state.busy ? 'disabled' : ''}>${icon('play')} Apply & reset</button><p id="draft-status" class="field-help" role="status">${state.draft ? 'Unapplied edits. The trace still uses your last applied inputs.' : 'The trace and JSON export use the applied inputs.'}</p></form>
    <label for="preset">Try a workload</label><select id="preset"><option value="">Choose a preset…</option><option value="guided">Guided example</option><option value="locality">A small working set</option><option value="anomaly">Belady’s anomaly</option></select>
    <div class="file-actions"><button class="text-button" data-action="import">Import JSON</button><button class="text-button" data-action="export">Export JSON ${icon('download')}</button></div><input type="file" id="import-file" accept="application/json,.json" hidden>
    ${state.lab ? '<button class="secondary full" data-action="restore-lab">Restore previous Lab experiment</button>' : ''}
    <details class="cli-details"><summary>${icon('terminal')} Run this from your terminal</summary><p>Export the configuration as <code>experiment.json</code>, then start an interactive session:</p><code>python3 suite.py shell experiment.json</code><p>Try step, state, set policy clock, compare, or help. For a batch comparison:</p><code>python3 suite.py compare experiment.json --format table</code></details>
    <p class="model-note">Current model: one process, read/write page requests, equal-sized frames. Dirty evictions count as writebacks. The CLI supports larger workloads. Open Address spaces for process page tables, translation, protection, and swap.</p></section>`;
}

function simulator() {
  const e = event();
  const explanation = describe(e);
  const frames = e?.frames || Array.from({length:state.config.frames},()=>({page:-1,referenced:false}));
  const faults = e?.faults || 0;
  const refs = state.config.references;
  return `<section class="simulation" aria-label="Memory simulator">
    <div class="simulation-heading"><div><span class="live-dot"></span><strong>The memory desk</strong><span class="simulation-sub">A real page-replacement experiment</span></div><span class="algorithm-badge">${state.config.algorithm.toUpperCase()}</span></div>
    <div class="request-label"><span>THE PROGRAM ASKS FOR</span><span>ACCESS ${state.cursor} OF ${refs.length}</span></div>
    <div class="reference-strip" aria-label="Page reference sequence">${refs.map((page,i)=>`<span class="reference ${i === state.cursor ? 'next' : ''} ${i < state.cursor ? 'visited' : ''} ${i === state.cursor-1 ? 'just-used' : ''}" title="Access ${i+1}: ${state.config.writes?.includes(i)?'write':'read'} page ${page}${i===state.cursor?', next':''}">${state.config.writes?.includes(i)?'w':''}${page}${i===state.cursor?'<span class="next-label">NEXT</span>':''}</span>`).join('')}</div>
    <div class="memory-divider"><span></span><span>PHYSICAL MEMORY · ${state.config.frames} FRAMES</span><span></span></div>
    <div class="frames" style="--frame-count:${Math.min(state.config.frames,4)}">${frames.map((f,i)=>`<div class="frame ${f.page < 0 ? 'empty' : 'occupied'} ${e?.slot===i ? `touched ${e.hit ? 'touched-hit' : ''}` : ''}"><div class="frame-label">FRAME ${i+1}${state.config.algorithm!=='random' && (e?.hand || 0)===i ? '<span class="hand" title="The next replacement scan starts here">↓ hand</span>' : ''}</div><div class="page-tile">${f.page < 0 ? '<span class="empty-plus">+</span><span class="empty-caption">Waiting for a page</span>' : `<span class="page-caption">PAGE</span><strong>${f.page}</strong>`}</div><div class="frame-footer">${frameDetails(f)}</div></div>`).join('')}</div>
    <div class="event-explanation ${explanation.kind}" aria-live="polite"><span class="event-symbol">${e ? e.hit ? '✓' : '↳' : 'i'}</span><div><strong>${explanation.title}</strong><p>${explanation.text}</p></div></div>
    <div class="transport"><div class="transport-buttons"><button class="icon-button" data-action="reset" aria-label="Reset playback" title="Reset playback" ${state.busy?'disabled':''}>${icon('reset')}</button><button class="icon-button" data-action="back" aria-label="Previous access" title="Previous access" ${state.cursor===0 || state.busy?'disabled':''}>←</button><button class="primary" data-action="step" ${state.cursor>=limit() || state.busy?'disabled':''}>${state.busy ? 'Loading…' : state.cursor>=limit() ? 'Section complete' : 'Next access'} ${icon('arrow')}</button><button class="secondary play-button" data-action="play" ${state.cursor>=limit() || state.busy?'disabled':''}>${state.playing ? 'Pause' : 'Play'}</button></div><span class="keyboard-hint">← → to step</span></div>
    <div class="metrics"><div><strong>${state.cursor}</strong><span>Accesses so far</span></div><div><strong>${faults}</strong><span>Page faults <button class="info" data-action="glossary" aria-label="Explain page faults">?</button></span></div><div><strong>${state.cursor-faults}</strong><span>Page hits</span></div><div><strong>${state.cursor ? Math.round((state.cursor-faults)/state.cursor*100) : 0}<small>%</small></strong><span>Hit rate</span></div></div>
  </section>`;
}

function comparison() {
  if (!current()) return '';
  return `<section class="comparison"><div class="comparison-title"><div class="section-kicker">SAME WORKLOAD, ${state.mode==='learn'?'TWO':'SIX'} POLICIES</div><h3>What changes when the rule changes?</h3><p>Full-run results · ${state.config.references.length} accesses · ${state.config.frames} frames</p></div><div class="comparison-bars">${(state.mode==='learn'?['fifo','clock']:Object.keys(policies)).map(a=>{const r=state.runs[a];return `<button class="comparison-row ${state.config.algorithm===a?'selected':''}" data-action="algorithm" data-value="${a}" aria-label="Inspect ${a.toUpperCase()} trace with ${r.summary.faults} page faults"><strong>${a.toUpperCase()}</strong><span class="bar-track"><span style="width:${r.summary.faults/r.summary.accesses*100}%"></span></span><span>${r.summary.faults} faults${state.mode==='lab'?` · ${r.summary.writebacks} WB`:''}</span></button>`;}).join('')}<p class="small muted">Fewer faults means fewer page loads. WB counts dirty-page writebacks on eviction. These are simulated counts, not measured execution times.</p></div></section>`;
}

function trace() {
  return `<details class="trace"><summary>Inspect the event log <span>${state.cursor} recorded accesses</span></summary><div class="table-scroll"><table><thead><tr><th>Access</th><th>Op</th><th>Page</th><th>Outcome</th><th>Frame</th><th>Replaced</th><th>Total faults</th><th>Writebacks</th></tr></thead><tbody>${(current()?.events.slice(0,state.cursor)||[]).map(e=>`<tr><td>${e.index+1}</td><td>${e.write?'Write':'Read'}</td><td>${e.page}</td><td><span class="outcome ${e.hit?'hit':''}">${e.hit?'Hit':e.victim<0?'Load':'Replace'}</span></td><td>${e.slot+1}</td><td>${e.victim<0?'—':e.victim}</td><td>${e.faults}</td><td>${e.writebacks}</td></tr>`).join('') || '<tr><td colspan="8">Take the first step to record an access.</td></tr>'}</tbody></table></div></details>`;
}

function learningFooter() {
  const blocked = state.busy || (state.lesson===1 && state.cursor<4) || (state.lesson===2 && state.cursor<5) || (state.lesson===4 && !state.completed && state.quiz!=='no');
  const note = state.lesson===1 && state.cursor<4 ? 'Explore the first four accesses to continue.' : state.lesson===2 && state.cursor<5 ? 'Reveal the next access to continue.' : state.lesson===4 ? state.completed ? 'Lesson complete. Your progress is saved on this browser.' : 'Answer the question to complete this lesson.' : 'Go at your own pace. You can revisit any step.';
  return `<div class="lesson-footer"><div><span class="progress-label">${state.completed?'LESSON COMPLETE':`YOUR PROGRESS · STEP ${state.lesson+1} OF 5`}</span><div class="progress-track"><span style="width:${state.completed?100:state.lesson*20}%"></span></div><p>${note}</p>${state.completed ? '<button class="text-button" data-action="restart-lesson">Restart lesson</button>' : ''}</div><button class="primary" data-action="continue" ${blocked?'disabled':''}>${state.lesson===0 ? 'Start guided experiment' : state.lesson===4 ? state.completed ? 'Continue in Lab' : 'Complete lesson' : 'Continue'} ${icon('arrow')}</button></div>`;
}


function glossary() {
  if (!state.glossary) return '';
  if(state.module!=='memory') return `<div class="drawer-scrim" data-action="close-glossary"></div><section class="glossary" role="dialog" aria-modal="true" aria-labelledby="notes-title"><div class="drawer-heading"><span class="eyebrow">KEEP THESE HANDY</span><button class="icon-button" data-action="close-glossary" aria-label="Close field notes">×</button></div>${moduleNotes(state.module)}</section>`;
  return `<div class="drawer-scrim" data-action="close-glossary"></div><section class="glossary" role="dialog" aria-modal="true" aria-labelledby="notes-title"><div class="drawer-heading"><span class="eyebrow">KEEP THESE HANDY</span><button class="icon-button" data-action="close-glossary" aria-label="Close field notes">×</button></div><h2 id="notes-title">A few field notes.</h2><p>You do not need to memorize these. Come back whenever a word feels unfamiliar.</p><dl><dt>Page</dt><dd>A fixed-size piece of a program’s virtual memory. This first lesson represents each page with a number.</dd><dt>Frame</dt><dd>A page-sized space in physical memory (RAM). One frame holds one page at a time.</dd><dt>Page hit</dt><dd>The requested page is already in a frame. No page needs to be loaded.</dd><dt>Page fault</dt><dd>The requested page is not in RAM. In this lesson, all requests are valid, so the system loads the page. Real systems can also fault on invalid accesses.</dd><dt>Replacement policy</dt><dd>The rule used to choose which page leaves when all frames are full.</dd><dt>FIFO</dt><dd>First in, first out. Replace the resident page loaded earliest. A hit does not change its position.</dd><dt>Clock</dt><dd>Scan frames with a rotating hand. Clear reference bits that are 1; replace the first frame with a bit of 0. Each access sets the page’s bit to 1.</dd><dt>Dirty bit (D)</dt><dd>A marker that the resident page has been written. It stays set until the page is evicted.</dd><dt>Reference bit (R)</dt><dd>A marker set by each access. Clock, NRU, Aging, and Working Set clear it according to their sampling rules.</dd><dt>Writeback (WB)</dt><dd>A simulated write needed when a dirty page is evicted. Dirty pages still resident at the end are not flushed in this model.</dd><dt>Workload</dt><dd>The sequence of requests given to a simulator. Keep it fixed when comparing policies.</dd></dl><div class="hint">The guided example uses read-only requests. Lab also supports writes. Both model one process, without address translation, page contents, or protection faults.</div></section>`;
}

function render() {
  const openDetails = [...app.querySelectorAll('details[open]')].map(detail => detail.className);
  const focus = document.activeElement;
  const focusKind = focus?.dataset.action ? 'action' : focus?.dataset.exp ? 'exp' : null;
  const focusKey = focus?.dataset[focusKind];
  const focusValue = focus?.dataset.value;
  app.innerHTML = `${sidebar()}<div class="workspace">${header()}<main id="main" tabindex="-1">${state.module==='memory' ? `${hero()}${state.error?`<div class="error" role="alert">${escape(state.error)}</div>`:''}${state.toast?`<div class="toast" role="status">${escape(state.toast)}<button data-action="dismiss" aria-label="Dismiss message">×</button></div>`:''}${state.mode==='learn'?lessonRail():''}<div class="experiment-layout">${state.mode==='learn'?lessonText():labConfig()}${simulator()}</div>${state.mode==='lab' || state.lesson>=3 ? comparison()+trace() : '<div class="below-note">'+icon('check')+' No setup. No prior operating systems course. Just curiosity.<span>01 / Virtual memory</span></div>'}${state.mode==='learn'?learningFooter():''}` : moduleMarkup(state.module,state.mode)}<footer class="site-footer"><span>Systems Programming Suite</span><span>Understand the mechanism. Explore the trade-offs.</span></footer></main></div>${glossary()}`;
  if (state.glossary) {
    app.querySelector('.sidebar').inert = true;
    app.querySelector('.workspace').inert = true;
  }
  app.querySelectorAll('details').forEach(detail => { detail.open = openDetails.includes(detail.className); });
  if (focusKey) {
    const match = [...app.querySelectorAll('[data-action], [data-exp]')].find(el=>el.dataset[focusKind]===focusKey && el.dataset.value===focusValue && !el.disabled);
    match?.focus({preventScroll:true});
  }
}

async function chooseLesson(index) {
  if(state.busy) return;
  pause();
  state.lesson=index;
  state.prediction=null;
  state.quiz=null;
  state.toast='';
  const needsReset=JSON.stringify(state.config)!==JSON.stringify(defaults);
  if(needsReset) await calculate(defaults);
  state.cursor=index===2?4:index>=3?5:0;
  render();
  window.scrollTo({top:0,behavior:'instant'});
}

async function setMode(mode) {
  if(state.busy) return;
  pause();
  stopPlayback();
  if(state.module!=='memory') {state.mode=mode;render();await openModule(state.module,mode);return;}
  if(state.mode===mode) return;
  if(mode==='lab') {
    state.mode='lab';
    state.toast='Your current experiment is ready to explore. Change any input and apply it to start a new trace.';
  } else {
    state.lab={config:structuredClone(state.config),cursor:state.cursor,draft:state.draft};
    state.draft=null;
    state.mode='learn';
    await chooseLesson(0);
    state.toast='The guided lesson uses a small fixed example. Your previous Lab experiment is saved for this session.';
  }
  render();
}

app.addEventListener('click', async e=>{
  const button=e.target.closest('[data-action]');
  if(!button || button.disabled) return;
  const {action,value}=button.dataset;
  if(button.tagName==='A') e.preventDefault();
  if(action==='glossary') { state.glossary=true; pause(); stopPlayback(); render(); app.querySelector('[data-action="close-glossary"].icon-button')?.focus(); return; }
  if(action==='close-glossary') {state.glossary=false;render();app.querySelector('[data-action="glossary"]')?.focus();return;}
  if(state.busy && !['dismiss'].includes(action)) return;
  if(action==='home') {stopPlayback();state.module='memory';await setMode('learn');return;}
  if(action==='module') {pause();stopPlayback();state.module=value;render();if(value!=='memory') await openModule(value,state.mode);return;}
  if(action==='mode') {await setMode(value);return;}
  if(action==='lesson') {await chooseLesson(Number(value));return;}
  if(action==='step') {pause();step();return;}
  if(action==='back') {pause();step(-1);return;}
  if(action==='reset') {pause();state.cursor=state.mode==='learn' && state.lesson===2?4:0;render();return;}
  if(action==='play') {if(state.playing) {pause();render();} else {state.playing=true;render();timer=setInterval(()=>step(),1100);}return;}
  if(action==='predict') {state.prediction=Number(value);render();return;}
  if(action==='reveal') {pause();state.cursor=5;render();announce(describe(event()).text);return;}
  if(action==='algorithm') {pause();state.config.algorithm=value;render();return;}
  if(action==='quiz') {state.quiz=value;render();return;}
  if(action==='restart-lesson') {state.completed=false;try{localStorage.removeItem('suite.memory.completed.v1');}catch{}await chooseLesson(0);return;}
  if(action==='challenge') {state.mode='lab';await calculate({...defaults,references:anomaly});state.toast='Challenge: run FIFO with 3 frames, then 4. Compare the full-run fault counts: more frames can produce more faults.';render();return;}
  if(action==='continue') {
    if(state.lesson<4) await chooseLesson(state.lesson+1);
    else if(!state.completed) {state.completed=true;try{localStorage.setItem('suite.memory.completed.v1','true');}catch{}state.toast='Lesson complete. You can now explain hits, faults, and replacement. Try your own workload in Lab.';render();announce(state.toast);}
    else await setMode('lab');
    return;
  }
  if(action==='dismiss') {state.toast='';render();return;}
  if(action==='import') {app.querySelector('#import-file').click();return;}
  if(action==='restore-lab' && state.lab) {
    const saved=state.lab;
    await calculate(saved.config);
    if(!state.error) {state.cursor=saved.cursor;state.draft=saved.draft;state.lab=null;state.toast='Your previous Lab experiment and playback position are restored.';render();}
    return;
  }
  if(action==='export') {
    const blob=new Blob([JSON.stringify(state.config,null,2)+'\n'],{type:'application/json'});
    const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download='experiment.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);return;
  }
});

app.addEventListener('input', e=>{
  if(e.target.closest('#config-form')) {
    const form=new FormData(app.querySelector('#config-form'));
    state.draft=Object.fromEntries(form);
    app.querySelector('#draft-status').textContent='Unapplied edits. The trace still uses your last applied inputs.';
  }
});

app.addEventListener('submit',async e=>{
  if(e.target.id!=='config-form') return;
  e.preventDefault();
  const form=new FormData(e.target);
  const raw=String(form.get('references')).trim();
  const tokens=raw.split(/[\s,]+/).filter(Boolean);
  if(!tokens.length || tokens.some(t=>!/^[rw]?\d+$/i.test(t))) {state.error='Use page numbers, r7 for a read, or w7 for a write; separate accesses with commas or spaces.';render();return;}
  await calculate({...defaults,algorithm:form.get('algorithm'),frames:Number(form.get('frames')),references:tokens.map(token=>Number(token.replace(/^[rw]/i,''))),writes:tokens.flatMap((token,index)=>/^w/i.test(token)?[index]:[]),seed:Number(form.get('seed')),reset_interval:Number(form.get('reset_interval')),window:Number(form.get('window'))});
});

app.addEventListener('change',async e=>{
  if(e.target.id==='preset') {
    const presets={guided:defaults.references,locality:[1,2,1,2,1,2,3,1,2,3,1,2],anomaly};
    if(presets[e.target.value]) await calculate({...defaults,references:presets[e.target.value]});
  }
  if(e.target.id==='import-file' && e.target.files[0]) {
    try {
      const file=e.target.files[0];
      if(file.size>16384) throw new Error('Choose a JSON configuration smaller than 16 KB.');
      const config=JSON.parse(await file.text());
      await calculate(config);
    } catch(error) {state.error=`Could not import the experiment. ${error.message}`;render();}
  }
});

document.addEventListener('keydown',e=>{
  if(state.glossary) {
    if(e.key==='Escape') {state.glossary=false;render();app.querySelector('[data-action="glossary"]')?.focus();}
    if(e.key==='Tab') {e.preventDefault();app.querySelector('.glossary button')?.focus();}
    return;
  }
  if(['INPUT','TEXTAREA','SELECT','SUMMARY'].includes(document.activeElement?.tagName)) return;
  if(state.module!=='memory') return;
  if(e.key==='ArrowRight'||e.key==='ArrowLeft') {e.preventDefault();pause();step(e.key==='ArrowRight'?1:-1);}
});

bindModules(render,setMode);
render();
calculate();
