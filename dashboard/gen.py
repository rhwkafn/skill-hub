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
    --bg: #0a0a0f; --card: #12121a; --card-hover: #1a1a28; --border: #1e1e30;
    --text: #e0e0e8; --text-dim: #8888a0; --accent: #6c5ce7; --accent2: #00cec9;
    --accent3: #fd79a8; --accent4: #fdcb6e; --accent5: #55efc4;
    --global: #ff6b6b; --compose: #ffd93d; --on_demand: #6c5ce7;
  }
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family: -apple-system,'SF Pro Display','PingFang SC','Microsoft YaHei','Segoe UI',sans-serif; background:var(--bg); color:var(--text); line-height:1.6; overflow-x:hidden; }
  .hero { padding:80px 40px 40px; text-align:center; background:linear-gradient(135deg,#0a0a1a 0%,#1a0a2e 50%,#0a1a2e 100%); position:relative; overflow:hidden; }
  .hero::before { content:''; position:absolute; top:-50%; left:-50%; width:200%; height:200%; background:radial-gradient(circle at 30% 50%,rgba(108,92,231,0.08) 0%,transparent 50%),radial-gradient(circle at 70% 50%,rgba(0,206,201,0.06) 0%,transparent 50%); animation:drift 20s ease-in-out infinite; }
  @keyframes drift { 0%,100%{transform:translate(0,0)} 50%{transform:translate(-20px,10px)} }
  .hero h1 { font-size:3rem; font-weight:700; background:linear-gradient(135deg,#6c5ce7,#00cec9); -webkit-background-clip:text; -webkit-text-fill-color:transparent; position:relative; margin-bottom:8px; }
  .hero p { color:var(--text-dim); font-size:1.1rem; position:relative; }
  .hero .updated { color:var(--text-dim); font-size:0.75rem; margin-top:8px; position:relative; opacity:0.6; }
  .stats { display:flex; justify-content:center; gap:40px; padding:30px 40px; }
  .stat { text-align:center; }
  .stat-num { font-size:2.2rem; font-weight:700; background:linear-gradient(135deg,var(--accent),var(--accent2)); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
  .stat-label { font-size:0.8rem; color:var(--text-dim); letter-spacing:1px; }
  .container { max-width:1400px; margin:0 auto; padding:0 40px 60px; }
  .section { margin-bottom:50px; }
  .section-title { font-size:1.4rem; font-weight:600; margin-bottom:20px; padding-left:12px; border-left:3px solid var(--accent); display:flex; align-items:center; gap:12px; }
  .charts-row { display:grid; grid-template-columns:1fr 1fr 1fr; gap:20px; margin-bottom:40px; }
  .chart-card { background:var(--card); border:1px solid var(--border); border-radius:12px; padding:24px; }
  .chart-card h3 { font-size:0.9rem; color:var(--text-dim); margin-bottom:16px; }
  .chart-container { position:relative; height:220px; }
  .filter-bar { display:flex; gap:10px; flex-wrap:wrap; margin-bottom:24px; }
  .filter-btn { padding:6px 16px; border:1px solid var(--border); border-radius:20px; background:transparent; color:var(--text-dim); font-size:0.85rem; cursor:pointer; transition:all 0.2s; }
  .filter-btn:hover,.filter-btn.active { border-color:var(--accent); color:var(--accent); background:rgba(108,92,231,0.1); }
  .filter-btn.active { background:rgba(108,92,231,0.2); }
  .search-row { display:flex; gap:12px; align-items:center; margin-bottom:20px; flex-wrap:wrap; }
  .search-box { flex:1; min-width:200px; max-width:400px; padding:10px 16px; border:1px solid var(--border); border-radius:8px; background:var(--card); color:var(--text); font-size:0.95rem; outline:none; transition:border-color 0.2s; }
  .search-box:focus { border-color:var(--accent); }
  .search-box::placeholder { color:var(--text-dim); }
  .sort-select { padding:8px 12px; border:1px solid var(--border); border-radius:8px; background:var(--card); color:var(--text); font-size:0.85rem; outline:none; cursor:pointer; }
  .skill-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(320px,1fr)); gap:14px; }
  .skill-card { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:16px; transition:all 0.2s; cursor:default; }
  .skill-card:hover { background:var(--card-hover); border-color:var(--accent); transform:translateY(-2px); }
  .skill-header { display:flex; align-items:center; gap:8px; margin-bottom:8px; }
  .skill-name { font-weight:600; font-size:0.95rem; }
  .skill-mode { font-size:0.7rem; padding:2px 8px; border-radius:10px; font-weight:500; }
  .mode-global { background:rgba(255,107,107,0.15); color:var(--global); }
  .mode-compose { background:rgba(255,217,61,0.15); color:var(--compose); }
  .mode-on_demand { background:rgba(108,92,231,0.12); color:var(--on_demand); }
  .skill-source { font-size:0.75rem; color:var(--text-dim); margin-bottom:6px; }
  .skill-desc { font-size:0.82rem; color:var(--text-dim); line-height:1.5; display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden; }
  .skill-tags { display:flex; gap:6px; flex-wrap:wrap; margin-top:8px; }
  .skill-tag { font-size:0.7rem; padding:2px 8px; border-radius:6px; background:rgba(0,206,201,0.1); color:var(--accent2); }
  .skill-domain { font-size:0.7rem; padding:2px 8px; border-radius:6px; background:rgba(253,203,110,0.1); color:var(--accent4); }
  .skill-phase { font-size:0.7rem; padding:2px 8px; border-radius:6px; background:rgba(108,92,231,0.1); color:var(--accent); }
  .skill-exec { font-size:0.7rem; padding:2px 8px; border-radius:6px; }
  .exec-serial { background:rgba(0,206,201,0.1); color:var(--accent2); }
  .exec-parallel { background:rgba(85,239,196,0.1); color:var(--accent5); }
  .exec-independent { background:rgba(136,136,160,0.1); color:var(--text-dim); }
  .count-badge { font-size:0.75rem; color:var(--text-dim); margin-left:auto; font-weight:400; }
  .footer { text-align:center; padding:40px; color:var(--text-dim); font-size:0.8rem; border-top:1px solid var(--border); margin-top:40px; }
  .footer a { color:var(--accent); text-decoration:none; }
  @media (max-width:900px) {
    .charts-row { grid-template-columns:1fr; } .hero h1 { font-size:2rem; }
    .stats { gap:20px; flex-wrap:wrap; } .stat-num { font-size:1.6rem; }
    .skill-grid { grid-template-columns:1fr; } .container { padding:0 20px 40px; }
    .search-row { flex-direction:column; } .search-box { max-width:100%; }
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
  <h1>Skill Hub</h1>
  <p>{total} skills across {num_sources} sources — index first, load on demand</p>
  <div class="updated">Last updated: {updated}</div>
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
  <a href="https://github.com/Jinze-Lee/codex-skills-workbench">skill-hub</a> &mdash; Skills-as-RAG agent skill registry
</div>

<script>
{make_js(js_data, {
    "biology": "Biology", "science": "Science", "engineering": "Engineering",
    "data-science": "Data Science", "writing": "Writing", "none": "General",
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
  <h1>Skill Hub</h1>
  <p>{total} 个技能，覆盖 {num_sources} 个来源 — 先索引，按需加载</p>
  <div class="updated">最后更新：{updated}</div>
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
  <a href="https://github.com/Jinze-Lee/codex-skills-workbench">skill-hub</a> &mdash; Skills-as-RAG 智能体技能注册中心
</div>

<script>
{make_js(js_data, {
    "biology": "生物学", "science": "科学", "engineering": "工程",
    "data-science": "数据科学", "writing": "写作", "none": "通用",
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
