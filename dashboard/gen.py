"""Generate English + Chinese dashboards from skill_index.json."""

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

root = Path(__file__).resolve().parent.parent
data = json.load(open(root / "skill_index.json", encoding="utf-8"))

# Stats
total = len(data)
sources = Counter(s["registry"] for s in data)
domains = Counter(s.get("domain", "") or "none" for s in data)
modes = Counter(s.get("mode", "") for s in data)
fmts = Counter()
for s in data:
    for f in s.get("output_formats", []) or []:
        fmts[f] += 1
num_sources = len(sources)
num_domains = len([d for d in domains if d != "none"])
num_formats = len(fmts)
updated = datetime.now().strftime("%Y-%m-%d")

# Skill data for JS
skills = []
for d in data:
    skills.append({
        "name": d["name"],
        "registry": d["registry"],
        "description": (d.get("description", "") or "")[:200],
        "mode": d.get("mode", "on_demand"),
        "domain": d.get("domain", "") or "none",
        "phase": d.get("phase", "execute") or "execute",
        "execution_mode": d.get("execution_mode", "independent") or "independent",
        "output_formats": d.get("output_formats", []),
        "triggers": d.get("triggers", []),
    })
js_data = json.dumps(skills, ensure_ascii=False)

# ─── CSS (shared) ───
CSS = """
  :root {
    --bg: #06060b; --card: #0e0e18; --card-hover: #161625; --border: #1a1a2e;
    --text: #e8e8f0; --text-dim: #7878a0; --accent: #7c6cf0; --accent2: #00d4cf;
    --accent3: #ff6b9d; --accent4: #f0c040; --accent5: #40e0a0;
    --global: #ff5c5c; --compose: #ffc93c; --on_demand: #7c6cf0;
    --glow: rgba(124,108,240,0.15);
  }
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family:'Inter','SF Pro Display','PingFang SC','Microsoft YaHei','Segoe UI',system-ui,sans-serif; background:var(--bg); color:var(--text); line-height:1.6; overflow-x:hidden; }

  /* ── Hero ── */
  .hero { padding:100px 40px 50px; text-align:center; position:relative; overflow:hidden; background:linear-gradient(180deg,#0c0c1a 0%,#0a0a14 100%); }
  .hero::before { content:''; position:absolute; inset:0; background:radial-gradient(ellipse 80% 50% at 50% 0%,rgba(124,108,240,0.12) 0%,transparent 60%),radial-gradient(ellipse 60% 40% at 20% 80%,rgba(0,212,207,0.06) 0%,transparent 50%),radial-gradient(ellipse 60% 40% at 80% 80%,rgba(255,107,157,0.05) 0%,transparent 50%); pointer-events:none; }
  .hero::after { content:''; position:absolute; inset:0; background:url("data:image/svg+xml,%3Csvg width='60' height='60' xmlns='http://www.w3.org/2000/svg'%3E%3Cdefs%3E%3Cpattern id='g' width='60' height='60' patternUnits='userSpaceOnUse'%3E%3Cpath d='M60 0H0v60' fill='none' stroke='%23ffffff' stroke-width='0.3' opacity='0.03'/%3E%3C/pattern%3E%3C/defs%3E%3Crect fill='url(%23g)' width='60' height='60'/%3E%3C/svg%3E"); pointer-events:none; opacity:0.5; }
  .hero-content { position:relative; z-index:1; }
  .hero h1 { font-size:3.2rem; font-weight:800; letter-spacing:-0.02em; background:linear-gradient(135deg,#a78bfa 0%,#7c6cf0 30%,#00d4cf 70%,#40e0a0 100%); background-size:200% 200%; -webkit-background-clip:text; -webkit-text-fill-color:transparent; animation:gradient-shift 8s ease infinite; margin-bottom:12px; }
  @keyframes gradient-shift { 0%,100%{background-position:0% 50%} 50%{background-position:100% 50%} }
  .hero p { color:var(--text-dim); font-size:1.15rem; max-width:600px; margin:0 auto; }
  .hero .updated { color:var(--text-dim); font-size:0.75rem; margin-top:10px; opacity:0.5; }
  .hero-links { display:flex; gap:12px; justify-content:center; margin-top:24px; position:relative; z-index:1; }
  .hero-btn { display:inline-flex; align-items:center; gap:8px; padding:10px 24px; border-radius:10px; font-size:0.9rem; font-weight:600; text-decoration:none; transition:all 0.25s; cursor:pointer; border:none; }
  .hero-btn-primary { background:linear-gradient(135deg,#7c6cf0,#6c5ce7); color:#fff; box-shadow:0 4px 20px rgba(124,108,240,0.3); }
  .hero-btn-primary:hover { transform:translateY(-2px); box-shadow:0 6px 28px rgba(124,108,240,0.45); }
  .hero-btn-ghost { background:rgba(255,255,255,0.05); color:var(--text-dim); border:1px solid var(--border); backdrop-filter:blur(8px); }
  .hero-btn-ghost:hover { background:rgba(255,255,255,0.1); color:var(--text); border-color:var(--accent); }
  .hero-btn svg { width:18px; height:18px; fill:currentColor; }

  /* ── Stats ── */
  .stats { display:flex; justify-content:center; gap:48px; padding:36px 40px; position:relative; }
  .stats::before { content:''; position:absolute; top:0; left:50%; transform:translateX(-50%); width:80%; height:1px; background:linear-gradient(90deg,transparent,var(--border),transparent); }
  .stat { text-align:center; position:relative; }
  .stat-num { font-size:2.4rem; font-weight:800; background:linear-gradient(135deg,var(--accent),var(--accent2)); -webkit-background-clip:text; -webkit-text-fill-color:transparent; line-height:1.1; }
  .stat-label { font-size:0.75rem; color:var(--text-dim); letter-spacing:1.5px; text-transform:uppercase; margin-top:4px; }

  /* ── Container & Sections ── */
  .container { max-width:1440px; margin:0 auto; padding:0 48px 80px; }
  .section { margin-bottom:56px; }
  .section-title { font-size:1.3rem; font-weight:700; margin-bottom:20px; padding-left:14px; border-left:3px solid var(--accent); display:flex; align-items:center; gap:12px; letter-spacing:-0.01em; }

  /* ── Charts ── */
  .charts-row { display:grid; grid-template-columns:1fr 1fr 1fr; gap:20px; margin-bottom:24px; }
  .chart-card { background:var(--card); border:1px solid var(--border); border-radius:14px; padding:24px; position:relative; overflow:hidden; transition:border-color 0.3s; }
  .chart-card:hover { border-color:rgba(124,108,240,0.3); }
  .chart-card::before { content:''; position:absolute; top:0; left:0; right:0; height:1px; background:linear-gradient(90deg,transparent,rgba(124,108,240,0.2),transparent); }
  .chart-card h3 { font-size:0.85rem; color:var(--text-dim); margin-bottom:16px; font-weight:600; letter-spacing:0.5px; text-transform:uppercase; }
  .chart-container { position:relative; height:220px; }

  /* ── Filters ── */
  .filter-bar { display:flex; gap:8px; flex-wrap:wrap; margin-bottom:24px; }
  .filter-btn { padding:6px 14px; border:1px solid var(--border); border-radius:8px; background:transparent; color:var(--text-dim); font-size:0.8rem; cursor:pointer; transition:all 0.2s; font-weight:500; }
  .filter-btn:hover { border-color:var(--accent); color:var(--accent); background:var(--glow); }
  .filter-btn.active { border-color:var(--accent); color:var(--accent); background:rgba(124,108,240,0.15); box-shadow:0 0 12px rgba(124,108,240,0.1); }

  /* ── Search ── */
  .search-row { display:flex; gap:12px; align-items:center; margin-bottom:20px; flex-wrap:wrap; }
  .search-box { flex:1; min-width:200px; max-width:420px; padding:10px 16px 10px 40px; border:1px solid var(--border); border-radius:10px; background:var(--card) url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%237878a0' stroke-width='2' stroke-linecap='round'%3E%3Ccircle cx='11' cy='11' r='8'/%3E%3Cline x1='21' y1='21' x2='16.65' y2='16.65'/%3E%3C/svg%3E") 14px center no-repeat; color:var(--text); font-size:0.9rem; outline:none; transition:all 0.2s; }
  .search-box:focus { border-color:var(--accent); box-shadow:0 0 0 3px rgba(124,108,240,0.1); }
  .search-box::placeholder { color:var(--text-dim); opacity:0.6; }
  .sort-select { padding:8px 12px; border:1px solid var(--border); border-radius:10px; background:var(--card); color:var(--text-dim); font-size:0.8rem; outline:none; cursor:pointer; transition:border-color 0.2s; }
  .sort-select:focus { border-color:var(--accent); }

  /* ── Skill Grid ── */
  .skill-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(330px,1fr)); gap:14px; }
  .skill-card { background:var(--card); border:1px solid var(--border); border-radius:12px; padding:18px; transition:all 0.25s; cursor:default; position:relative; }
  .skill-card:hover { background:var(--card-hover); border-color:rgba(124,108,240,0.4); transform:translateY(-3px); box-shadow:0 8px 32px rgba(0,0,0,0.3),0 0 0 1px rgba(124,108,240,0.1); }
  .skill-header { display:flex; align-items:center; gap:8px; margin-bottom:8px; }
  .skill-name { font-weight:700; font-size:0.95rem; letter-spacing:-0.01em; }
  .skill-mode { font-size:0.65rem; padding:2px 8px; border-radius:6px; font-weight:600; letter-spacing:0.5px; text-transform:uppercase; }
  .mode-global { background:rgba(255,92,92,0.12); color:var(--global); }
  .mode-compose { background:rgba(255,201,60,0.12); color:var(--compose); }
  .mode-on_demand { background:rgba(124,108,240,0.1); color:var(--on_demand); }
  .skill-source { font-size:0.72rem; color:var(--text-dim); margin-bottom:6px; opacity:0.7; }
  .skill-desc { font-size:0.82rem; color:var(--text-dim); line-height:1.55; display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden; }
  .skill-tags { display:flex; gap:5px; flex-wrap:wrap; margin-top:10px; }
  .skill-tag { font-size:0.68rem; padding:2px 8px; border-radius:6px; background:rgba(0,212,207,0.08); color:var(--accent2); font-weight:500; }
  .skill-domain { font-size:0.68rem; padding:2px 8px; border-radius:6px; background:rgba(240,192,64,0.08); color:var(--accent4); font-weight:500; }
  .skill-phase { font-size:0.68rem; padding:2px 8px; border-radius:6px; background:rgba(124,108,240,0.08); color:var(--accent); font-weight:500; }
  .skill-exec { font-size:0.68rem; padding:2px 8px; border-radius:6px; font-weight:500; }
  .exec-serial { background:rgba(0,212,207,0.08); color:var(--accent2); }
  .exec-parallel { background:rgba(64,224,160,0.08); color:var(--accent5); }
  .exec-independent { background:rgba(120,120,160,0.08); color:var(--text-dim); }
  .count-badge { font-size:0.75rem; color:var(--text-dim); margin-left:auto; font-weight:400; }

  /* ── Footer ── */
  .footer { text-align:center; padding:48px 40px; color:var(--text-dim); font-size:0.8rem; border-top:1px solid var(--border); margin-top:40px; }
  .footer a { color:var(--accent); text-decoration:none; transition:color 0.2s; }
  .footer a:hover { color:var(--accent2); }

  /* ── Responsive ── */
  @media (max-width:960px) {
    .charts-row { grid-template-columns:1fr 1fr; }
    .hero h1 { font-size:2.2rem; } .hero { padding:60px 24px 36px; }
    .stats { gap:24px; flex-wrap:wrap; } .stat-num { font-size:1.8rem; }
    .skill-grid { grid-template-columns:1fr; } .container { padding:0 24px 50px; }
    .search-row { flex-direction:column; } .search-box { max-width:100%; }
  }
  @media (max-width:600px) {
    .charts-row { grid-template-columns:1fr; }
    .hero h1 { font-size:1.8rem; } .hero-links { flex-direction:column; align-items:center; }
  }
"""

# ─── JS (shared logic, parameterized) ───
def make_js(js_data, domain_map, mode_map, phase_map, exec_map, labels):
    domain_js = json.dumps(domain_map, ensure_ascii=False)
    mode_js = json.dumps(mode_map, ensure_ascii=False)
    phase_js = json.dumps(phase_map, ensure_ascii=False)
    exec_js = json.dumps(exec_map, ensure_ascii=False)
    return f"""
const SKILLS = {js_data};
const domainMap = {domain_js};
const modeMap = {mode_js};
const phaseMap = {phase_js};
const execMap = {exec_js};
const chartColors = ['#6c5ce7','#00cec9','#fd79a8','#fdcb6e','#55efc4','#a29bfe','#fab1a0','#81ecec','#ffeaa7','#dfe6e9','#636e72'];

function makeChart(id, labels, data, type='doughnut') {{
  new Chart(document.getElementById(id), {{
    type,
    data: {{ labels, datasets: [{{ data, backgroundColor: chartColors.slice(0,data.length), borderWidth:0, hoverBorderWidth:2, hoverBorderColor:'#fff' }}] }},
    options: {{ responsive:true, maintainAspectRatio:false, plugins: {{ legend: {{ position:'right', labels: {{ color:'#8888a0', font:{{size:11}}, padding:8, boxWidth:12 }} }} }} }}
  }});
}}

// Charts
const sourceMap = {{}};
SKILLS.forEach(s => {{ sourceMap[s.registry] = (sourceMap[s.registry]||0)+1; }});
makeChart('chartSource', Object.keys(sourceMap).map(r => r.split('/').pop()), Object.values(sourceMap));

const domMap = {{}};
SKILLS.forEach(s => {{ const d = domainMap[s.domain]||s.domain; domMap[d] = (domMap[d]||0)+1; }});
makeChart('chartDomain', Object.keys(domMap), Object.values(domMap));

const fmtMap = {{}};
SKILLS.forEach(s => (s.output_formats||[]).forEach(f => {{ fmtMap[f] = (fmtMap[f]||0)+1; }}));
const fmtSorted = Object.entries(fmtMap).sort((a,b) => b[1]-a[1]);
makeChart('chartFormat', fmtSorted.map(e=>e[0]), fmtSorted.map(e=>e[1]), 'bar');

const phaseMap2 = {{}};
SKILLS.forEach(s => {{ const p = phaseMap[s.phase]||s.phase; phaseMap2[p] = (phaseMap2[p]||0)+1; }});
makeChart('chartPhase', Object.keys(phaseMap2), Object.values(phaseMap2));

const execMap2 = {{}};
SKILLS.forEach(s => {{ const e = execMap[s.execution_mode]||s.execution_mode; execMap2[e] = (execMap2[e]||0)+1; }});
makeChart('chartExec', Object.keys(execMap2), Object.values(execMap2));

// Filter & render
const filterBar = document.getElementById('filterBar');
const grid = document.getElementById('skillGrid');
const searchInput = document.getElementById('searchInput');
const countBadge = document.getElementById('skillCount');
const sortSelect = document.getElementById('sortSelect');
const domains = [...new Set(SKILLS.map(s => s.domain||'none'))].sort();
const sourceKeys = [...new Set(SKILLS.map(s => s.registry))].sort();
const modeKeys = [...new Set(SKILLS.map(s => s.mode))].sort();
const phaseKeys = [...new Set(SKILLS.map(s => s.phase||'execute'))].sort();
const execKeys = [...new Set(SKILLS.map(s => s.execution_mode||'independent'))].sort();
let activeFilter = {{ type:'domain', value:null }};
let searchQuery = '';

function createFilterGroup(title, items, type) {{
  const allBtn = document.createElement('button');
  allBtn.className = 'filter-btn' + (activeFilter.type===type && !activeFilter.value ? ' active' : '');
  allBtn.textContent = '{labels["all"]}' + title;
  allBtn.onclick = () => {{ activeFilter = {{type, value:null}}; render(); }};
  filterBar.appendChild(allBtn);
  items.forEach(item => {{
    const btn = document.createElement('button');
    let label = item;
    if (type==='source') label = item.split('/').pop();
    if (type==='domain') label = domainMap[item]||item;
    if (type==='mode') label = modeMap[item]||item;
    const count = SKILLS.filter(s => {{
      if (type==='domain') return (s.domain||'none')===item;
      if (type==='source') return s.registry===item;
      if (type==='mode') return s.mode===item;
      if (type==='phase') return (s.phase||'execute')===item;
      if (type==='exec') return (s.execution_mode||'independent')===item;
    }}).length;
    btn.className = 'filter-btn' + (activeFilter.type===type && activeFilter.value===item ? ' active' : '');
    btn.textContent = label + ' (' + count + ')';
    btn.onclick = () => {{ activeFilter = {{type, value:item}}; render(); }};
    filterBar.appendChild(btn);
  }});
}}

function render() {{
  let filtered = SKILLS;
  if (activeFilter.value) {{
    filtered = filtered.filter(s => {{
      if (activeFilter.type==='domain') return (s.domain||'none')===activeFilter.value;
      if (activeFilter.type==='source') return s.registry===activeFilter.value;
      if (activeFilter.type==='mode') return s.mode===activeFilter.value;
      if (activeFilter.type==='phase') return (s.phase||'execute')===activeFilter.value;
      if (activeFilter.type==='exec') return (s.execution_mode||'independent')===activeFilter.value;
    }});
  }}
  if (searchQuery) {{
    const q = searchQuery.toLowerCase();
    filtered = filtered.filter(s =>
      s.name.toLowerCase().includes(q) ||
      (s.description||'').toLowerCase().includes(q) ||
      (s.triggers||[]).some(t => t.toLowerCase().includes(q))
    );
  }}
  // Sort
  const sortBy = sortSelect ? sortSelect.value : 'name';
  if (sortBy === 'name') filtered.sort((a,b) => a.name.localeCompare(b.name));
  else if (sortBy === 'source') filtered.sort((a,b) => a.registry.localeCompare(b.registry));
  else if (sortBy === 'domain') filtered.sort((a,b) => (a.domain||'zzz').localeCompare(b.domain||'zzz'));

  countBadge.textContent = filtered.length + ' / ' + SKILLS.length;
  filterBar.innerHTML = '';
  createFilterGroup('{labels["domains"]}', domains, 'domain');
  createFilterGroup('{labels["sources"]}', sourceKeys, 'source');
  createFilterGroup('{labels["modes"]}', modeKeys, 'mode');
  createFilterGroup('{labels["phases"]}', phaseKeys, 'phase');
  createFilterGroup('{labels["execs"]}', execKeys, 'exec');
  grid.innerHTML = filtered.map(s => {{
    const modeClass = 'mode-' + s.mode;
    const modeLabel = modeMap[s.mode] || s.mode;
    const phaseLabel = phaseMap[s.phase] || s.phase || '';
    const execLabel = execMap[s.execution_mode] || s.execution_mode || '';
    const execClass = 'exec-' + (s.execution_mode||'independent');
    const src = s.registry.split('/').pop();
    const tags = (s.output_formats||[]).slice(0,4).map(f => '<span class="skill-tag">' + f + '</span>').join('');
    const dTag = s.domain ? '<span class="skill-domain">' + (domainMap[s.domain]||s.domain) + '</span>' : '';
    const pTag = phaseLabel ? '<span class="skill-phase">' + phaseLabel + '</span>' : '';
    const eTag = execLabel ? '<span class="skill-exec ' + execClass + '">' + execLabel + '</span>' : '';
    const desc = (s.description||'').slice(0,150);
    return '<div class="skill-card"><div class="skill-header"><span class="skill-name">' + s.name + '</span><span class="skill-mode ' + modeClass + '">' + modeLabel + '</span></div><div class="skill-source">' + src + '</div><div class="skill-desc">' + desc + '</div><div class="skill-tags">' + dTag + pTag + eTag + tags + '</div></div>';
  }}).join('');
}}

searchInput.addEventListener('input', e => {{ searchQuery = e.target.value; render(); }});
if (sortSelect) sortSelect.addEventListener('change', () => render());
render();
"""


# ─── English ───
en_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Skill Hub — Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
<style>{CSS}</style>
</head>
<body>

<div class="hero">
  <div class="hero-content">
    <h1>Skill Hub</h1>
    <p>{total} skills across {num_sources} sources — index first, load on demand</p>
    <div class="updated">Last updated: {updated}</div>
    <div class="hero-links">
      <a class="hero-btn hero-btn-primary" href="https://github.com/rhwkafn/skill-hub" target="_blank">
        <svg viewBox="0 0 16 16"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>
        GitHub
      </a>
      <a class="hero-btn hero-btn-ghost" href="https://github.com/rhwkafn/skill-hub/releases" target="_blank">
        <svg viewBox="0 0 16 16"><path d="M1 7.775V2.75C1 1.784 1.784 1 2.75 1h5.025c.464 0 .91.184 1.238.513l6.25 6.25a1.75 1.75 0 010 2.474l-5.026 5.026a1.75 1.75 0 01-2.474 0l-6.25-6.25A1.752 1.752 0 011 7.775zM6 5a1 1 0 100 2 1 1 0 000-2z"/></svg>
        Releases
      </a>
    </div>
  </div>
</div>

<div class="stats">
  <div class="stat"><div class="stat-num">{total}</div><div class="stat-label">Total Skills</div></div>
  <div class="stat"><div class="stat-num">{num_sources}</div><div class="stat-label">Sources</div></div>
  <div class="stat"><div class="stat-num">{num_domains}</div><div class="stat-label">Domains</div></div>
  <div class="stat"><div class="stat-num">{num_formats}</div><div class="stat-label">Output Formats</div></div>
</div>

<div class="container">
  <div class="charts-row">
    <div class="chart-card"><h3>By Source</h3><div class="chart-container"><canvas id="chartSource"></canvas></div></div>
    <div class="chart-card"><h3>By Domain</h3><div class="chart-container"><canvas id="chartDomain"></canvas></div></div>
    <div class="chart-card"><h3>By Phase</h3><div class="chart-container"><canvas id="chartPhase"></canvas></div></div>
  </div>
  <div class="charts-row">
    <div class="chart-card"><h3>By Output Format</h3><div class="chart-container"><canvas id="chartFormat"></canvas></div></div>
    <div class="chart-card"><h3>By Execution Mode</h3><div class="chart-container"><canvas id="chartExec"></canvas></div></div>
    <div class="chart-card"></div>
  </div>
  <div class="section">
    <div class="section-title">All Skills <span class="count-badge" id="skillCount"></span></div>
    <div class="search-row">
      <input type="text" class="search-box" id="searchInput" placeholder="Search skills by name, description, or triggers...">
      <select class="sort-select" id="sortSelect">
        <option value="name">Sort by Name</option>
        <option value="source">Sort by Source</option>
        <option value="domain">Sort by Domain</option>
      </select>
    </div>
    <div class="filter-bar" id="filterBar"></div>
    <div class="skill-grid" id="skillGrid"></div>
  </div>
</div>

<div class="footer">
  <a href="https://github.com/rhwkafn/skill-hub">skill-hub</a> &mdash; Skills-as-RAG agent skill registry
</div>

<script>
{make_js(js_data, {
    "biology": "Biology", "science": "Science", "engineering": "Engineering",
    "data-science": "Data Science", "writing": "Writing", "marketing": "Marketing", "chemistry": "Chemistry", "none": "General",
}, {
    "global": "global", "on_demand": "on-demand", "compose": "compose",
}, {
    "define": "Define", "plan": "Plan", "build": "Build",
    "verify": "Verify", "review": "Review", "ship": "Ship", "execute": "Execute",
}, {
    "serial": "Serial", "parallel": "Parallel", "independent": "Independent",
}, {
    "all": "All ", "domains": "Domains", "sources": "Sources", "modes": "Modes",
    "phases": "Phases", "execs": "Exec Mode",
})}
</script>
</body>
</html>"""


# ─── Chinese ───
zh_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Skill Hub — 技能面板</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
<style>{CSS}</style>
</head>
<body>

<div class="hero">
  <div class="hero-content">
    <h1>Skill Hub</h1>
    <p>{total} 个技能，覆盖 {num_sources} 个来源 — 先索引，按需加载</p>
    <div class="updated">最后更新：{updated}</div>
    <div class="hero-links">
      <a class="hero-btn hero-btn-primary" href="https://github.com/rhwkafn/skill-hub" target="_blank">
        <svg viewBox="0 0 16 16"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>
        GitHub
      </a>
      <a class="hero-btn hero-btn-ghost" href="https://github.com/rhwkafn/skill-hub/releases" target="_blank">
        <svg viewBox="0 0 16 16"><path d="M1 7.775V2.75C1 1.784 1.784 1 2.75 1h5.025c.464 0 .91.184 1.238.513l6.25 6.25a1.75 1.75 0 010 2.474l-5.026 5.026a1.75 1.75 0 01-2.474 0l-6.25-6.25A1.752 1.752 0 011 7.775zM6 5a1 1 0 100 2 1 1 0 000-2z"/></svg>
        Releases
      </a>
    </div>
  </div>
</div>

<div class="stats">
  <div class="stat"><div class="stat-num">{total}</div><div class="stat-label">技能总数</div></div>
  <div class="stat"><div class="stat-num">{num_sources}</div><div class="stat-label">来源</div></div>
  <div class="stat"><div class="stat-num">{num_domains}</div><div class="stat-label">领域</div></div>
  <div class="stat"><div class="stat-num">{num_formats}</div><div class="stat-label">输出格式</div></div>
</div>

<div class="container">
  <div class="charts-row">
    <div class="chart-card"><h3>按来源分布</h3><div class="chart-container"><canvas id="chartSource"></canvas></div></div>
    <div class="chart-card"><h3>按领域分布</h3><div class="chart-container"><canvas id="chartDomain"></canvas></div></div>
    <div class="chart-card"><h3>按阶段分布</h3><div class="chart-container"><canvas id="chartPhase"></canvas></div></div>
  </div>
  <div class="charts-row">
    <div class="chart-card"><h3>按输出格式分布</h3><div class="chart-container"><canvas id="chartFormat"></canvas></div></div>
    <div class="chart-card"><h3>按执行模式分布</h3><div class="chart-container"><canvas id="chartExec"></canvas></div></div>
    <div class="chart-card"></div>
  </div>
  <div class="section">
    <div class="section-title">全部技能 <span class="count-badge" id="skillCount"></span></div>
    <div class="search-row">
      <input type="text" class="search-box" id="searchInput" placeholder="搜索技能名称、描述、触发词...">
      <select class="sort-select" id="sortSelect">
        <option value="name">按名称排序</option>
        <option value="source">按来源排序</option>
        <option value="domain">按领域排序</option>
      </select>
    </div>
    <div class="filter-bar" id="filterBar"></div>
    <div class="skill-grid" id="skillGrid"></div>
  </div>
</div>

<div class="footer">
  <a href="https://github.com/rhwkafn/skill-hub">skill-hub</a> &mdash; Skills-as-RAG 智能体技能注册中心
</div>

<script>
{make_js(js_data, {
    "biology": "生物学", "science": "科学", "engineering": "工程",
    "data-science": "数据科学", "writing": "写作", "marketing": "营销", "chemistry": "化学", "none": "通用",
}, {
    "global": "全局", "on_demand": "按需", "compose": "组合",
}, {
    "define": "定义", "plan": "规划", "build": "构建",
    "verify": "验证", "review": "审查", "ship": "交付", "execute": "执行",
}, {
    "serial": "串行", "parallel": "并行", "independent": "独立",
}, {
    "all": "全部", "domains": "领域", "sources": "来源", "modes": "模式",
    "phases": "阶段", "execs": "执行模式",
})}
</script>
</body>
</html>"""


# Write
out_dir = Path(__file__).resolve().parent
(out_dir / "index.html").write_text(en_html, encoding="utf-8")
(out_dir / "index_zh.html").write_text(zh_html, encoding="utf-8")
print(f"English:  {out_dir / 'index.html'} ({len(en_html):,} bytes)")
print(f"Chinese:  {out_dir / 'index_zh.html'} ({len(zh_html):,} bytes)")
print(f"Skills:   {total} from {num_sources} sources")
