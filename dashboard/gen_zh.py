"""Generate Chinese dashboard from skill_index.json."""

import json
from pathlib import Path

root = Path(__file__).resolve().parent.parent
data = json.load(open(root / "skill_index.json", encoding="utf-8"))

skills = []
for d in data:
    skills.append({
        "name": d["name"],
        "registry": d["registry"],
        "description": (d.get("description", "") or "")[:200],
        "mode": d.get("mode", "on_demand"),
        "domain": d.get("domain", "") or "none",
        "output_formats": d.get("output_formats", []),
        "triggers": d.get("triggers", []),
    })

domain_cn = {
    "biology": "生物学", "science": "科学", "engineering": "工程",
    "data-science": "数据科学", "writing": "写作", "none": "通用",
}
mode_cn = {"global": "全局", "on_demand": "按需", "compose": "组合"}

js_data = json.dumps(skills, ensure_ascii=False)
domain_cn_js = json.dumps(domain_cn, ensure_ascii=False)
mode_cn_js = json.dumps(mode_cn, ensure_ascii=False)

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Skill Hub — 技能面板</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #0a0a0f; --card: #12121a; --card-hover: #1a1a28; --border: #1e1e30;
    --text: #e0e0e8; --text-dim: #8888a0; --accent: #6c5ce7; --accent2: #00cec9;
    --accent3: #fd79a8; --accent4: #fdcb6e; --accent5: #55efc4;
    --global: #ff6b6b; --compose: #ffd93d; --on_demand: #6c5ce7;
  }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family: -apple-system,'PingFang SC','Microsoft YaHei','Segoe UI',sans-serif; background:var(--bg); color:var(--text); line-height:1.6; overflow-x:hidden; }}
  .hero {{ padding:80px 40px 40px; text-align:center; background:linear-gradient(135deg,#0a0a1a 0%,#1a0a2e 50%,#0a1a2e 100%); position:relative; overflow:hidden; }}
  .hero::before {{ content:''; position:absolute; top:-50%; left:-50%; width:200%; height:200%; background:radial-gradient(circle at 30% 50%,rgba(108,92,231,0.08) 0%,transparent 50%),radial-gradient(circle at 70% 50%,rgba(0,206,201,0.06) 0%,transparent 50%); animation:drift 20s ease-in-out infinite; }}
  @keyframes drift {{ 0%,100%{{transform:translate(0,0)}} 50%{{transform:translate(-20px,10px)}} }}
  .hero h1 {{ font-size:3rem; font-weight:700; background:linear-gradient(135deg,#6c5ce7,#00cec9); -webkit-background-clip:text; -webkit-text-fill-color:transparent; position:relative; margin-bottom:8px; }}
  .hero p {{ color:var(--text-dim); font-size:1.1rem; position:relative; }}
  .stats {{ display:flex; justify-content:center; gap:40px; padding:30px 40px; }}
  .stat {{ text-align:center; }}
  .stat-num {{ font-size:2.2rem; font-weight:700; background:linear-gradient(135deg,var(--accent),var(--accent2)); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }}
  .stat-label {{ font-size:0.8rem; color:var(--text-dim); letter-spacing:1px; }}
  .container {{ max-width:1400px; margin:0 auto; padding:0 40px 60px; }}
  .section {{ margin-bottom:50px; }}
  .section-title {{ font-size:1.4rem; font-weight:600; margin-bottom:20px; padding-left:12px; border-left:3px solid var(--accent); }}
  .charts-row {{ display:grid; grid-template-columns:1fr 1fr 1fr; gap:20px; margin-bottom:40px; }}
  .chart-card {{ background:var(--card); border:1px solid var(--border); border-radius:12px; padding:24px; }}
  .chart-card h3 {{ font-size:0.9rem; color:var(--text-dim); margin-bottom:16px; }}
  .chart-container {{ position:relative; height:220px; }}
  .filter-bar {{ display:flex; gap:10px; flex-wrap:wrap; margin-bottom:24px; }}
  .filter-btn {{ padding:6px 16px; border:1px solid var(--border); border-radius:20px; background:transparent; color:var(--text-dim); font-size:0.85rem; cursor:pointer; transition:all 0.2s; }}
  .filter-btn:hover,.filter-btn.active {{ border-color:var(--accent); color:var(--accent); background:rgba(108,92,231,0.1); }}
  .filter-btn.active {{ background:rgba(108,92,231,0.2); }}
  .search-box {{ width:100%; max-width:400px; padding:10px 16px; border:1px solid var(--border); border-radius:8px; background:var(--card); color:var(--text); font-size:0.95rem; outline:none; margin-bottom:20px; transition:border-color 0.2s; }}
  .search-box:focus {{ border-color:var(--accent); }}
  .search-box::placeholder {{ color:var(--text-dim); }}
  .skill-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(320px,1fr)); gap:14px; }}
  .skill-card {{ background:var(--card); border:1px solid var(--border); border-radius:10px; padding:16px; transition:all 0.2s; }}
  .skill-card:hover {{ background:var(--card-hover); border-color:var(--accent); transform:translateY(-2px); }}
  .skill-header {{ display:flex; align-items:center; gap:8px; margin-bottom:8px; }}
  .skill-name {{ font-weight:600; font-size:0.95rem; }}
  .skill-mode {{ font-size:0.7rem; padding:2px 8px; border-radius:10px; font-weight:500; }}
  .mode-global {{ background:rgba(255,107,107,0.15); color:var(--global); }}
  .mode-compose {{ background:rgba(255,217,61,0.15); color:var(--compose); }}
  .mode-on_demand {{ background:rgba(108,92,231,0.12); color:var(--on_demand); }}
  .skill-source {{ font-size:0.75rem; color:var(--text-dim); margin-bottom:6px; }}
  .skill-desc {{ font-size:0.82rem; color:var(--text-dim); line-height:1.5; display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden; }}
  .skill-tags {{ display:flex; gap:6px; flex-wrap:wrap; margin-top:8px; }}
  .skill-tag {{ font-size:0.7rem; padding:2px 8px; border-radius:6px; background:rgba(0,206,201,0.1); color:var(--accent2); }}
  .skill-domain {{ font-size:0.7rem; padding:2px 8px; border-radius:6px; background:rgba(253,203,110,0.1); color:var(--accent4); }}
  .count-badge {{ font-size:0.75rem; color:var(--text-dim); margin-left:auto; }}
  @media (max-width:900px) {{
    .charts-row {{ grid-template-columns:1fr; }} .hero h1 {{ font-size:2rem; }}
    .stats {{ gap:20px; }} .stat-num {{ font-size:1.6rem; }}
    .skill-grid {{ grid-template-columns:1fr; }} .container {{ padding:0 20px 40px; }}
  }}
</style>
</head>
<body>

<div class="hero">
  <h1>Skill Hub</h1>
  <p>255 个技能，覆盖 7 个来源 — 先索引，按需加载</p>
</div>

<div class="stats">
  <div class="stat"><div class="stat-num">255</div><div class="stat-label">技能总数</div></div>
  <div class="stat"><div class="stat-num">7</div><div class="stat-label">来源</div></div>
  <div class="stat"><div class="stat-num">6</div><div class="stat-label">领域</div></div>
  <div class="stat"><div class="stat-num">11</div><div class="stat-label">输出格式</div></div>
</div>

<div class="container">
  <div class="charts-row">
    <div class="chart-card"><h3>按来源分布</h3><div class="chart-container"><canvas id="chartSource"></canvas></div></div>
    <div class="chart-card"><h3>按领域分布</h3><div class="chart-container"><canvas id="chartDomain"></canvas></div></div>
    <div class="chart-card"><h3>按输出格式分布</h3><div class="chart-container"><canvas id="chartFormat"></canvas></div></div>
  </div>
  <div class="section">
    <div class="section-title">全部技能<span class="count-badge" id="skillCount"></span></div>
    <input type="text" class="search-box" id="searchInput" placeholder="搜索技能名称、描述、触发词...">
    <div class="filter-bar" id="filterBar"></div>
    <div class="skill-grid" id="skillGrid"></div>
  </div>
</div>

<script>
const SKILLS = {js_data};
const domainCN = {domain_cn_js};
const modeCN = {mode_cn_js};
const chartColors = ['#6c5ce7','#00cec9','#fd79a8','#fdcb6e','#55efc4','#a29bfe','#fab1a0','#81ecec','#ffeaa7','#dfe6e9','#636e72'];

function makeChart(id, labels, data, type='doughnut') {{
  new Chart(document.getElementById(id), {{
    type,
    data: {{ labels, datasets: [{{ data, backgroundColor: chartColors.slice(0,data.length), borderWidth:0, hoverBorderWidth:2, hoverBorderColor:'#fff' }}] }},
    options: {{ responsive:true, maintainAspectRatio:false, plugins: {{ legend: {{ position:'right', labels: {{ color:'#8888a0', font:{{size:11}}, padding:8, boxWidth:12 }} }} }} }}
  }});
}}

const sourceMap = {{}};
SKILLS.forEach(s => {{ sourceMap[s.registry] = (sourceMap[s.registry]||0)+1; }});
makeChart('chartSource', Object.keys(sourceMap).map(r => r.split('/').pop()), Object.values(sourceMap));

const domainMap = {{}};
SKILLS.forEach(s => {{ const d = domainCN[s.domain]||s.domain; domainMap[d] = (domainMap[d]||0)+1; }});
makeChart('chartDomain', Object.keys(domainMap), Object.values(domainMap));

const fmtMap = {{}};
SKILLS.forEach(s => (s.output_formats||[]).forEach(f => {{ fmtMap[f] = (fmtMap[f]||0)+1; }}));
const fmtSorted = Object.entries(fmtMap).sort((a,b) => b[1]-a[1]);
makeChart('chartFormat', fmtSorted.map(e=>e[0]), fmtSorted.map(e=>e[1]), 'bar');

const filterBar = document.getElementById('filterBar');
const grid = document.getElementById('skillGrid');
const searchInput = document.getElementById('searchInput');
const countBadge = document.getElementById('skillCount');
const domains = [...new Set(SKILLS.map(s => s.domain||'none'))].sort();
const sources = [...new Set(SKILLS.map(s => s.registry))].sort();
const modes = [...new Set(SKILLS.map(s => s.mode))].sort();
let activeFilter = {{ type:'domain', value:null }};
let searchQuery = '';

function createFilterGroup(title, items, type) {{
  const allBtn = document.createElement('button');
  allBtn.className = 'filter-btn' + (activeFilter.type===type && !activeFilter.value ? ' active' : '');
  allBtn.textContent = '全部' + title;
  allBtn.onclick = () => {{ activeFilter = {{type, value:null}}; render(); }};
  filterBar.appendChild(allBtn);
  items.forEach(item => {{
    const btn = document.createElement('button');
    let label = item;
    if (type==='source') label = item.split('/').pop();
    if (type==='domain') label = domainCN[item]||item;
    if (type==='mode') label = modeCN[item]||item;
    const count = SKILLS.filter(s => {{
      if (type==='domain') return (s.domain||'none')===item;
      if (type==='source') return s.registry===item;
      if (type==='mode') return s.mode===item;
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
    }});
  }}
  if (searchQuery) {{
    const q = searchQuery.toLowerCase();
    filtered = filtered.filter(s => s.name.toLowerCase().includes(q) || (s.description||'').toLowerCase().includes(q) || (s.triggers||[]).some(t => t.toLowerCase().includes(q)));
  }}
  countBadge.textContent = filtered.length + ' / ' + SKILLS.length;
  filterBar.innerHTML = '';
  createFilterGroup('领域', domains, 'domain');
  createFilterGroup('来源', sources, 'source');
  createFilterGroup('模式', modes, 'mode');
  grid.innerHTML = filtered.map(s => {{
    const modeClass = 'mode-' + s.mode;
    const modeLabel = modeCN[s.mode] || s.mode;
    const source = s.registry.split('/').pop();
    const tags = (s.output_formats||[]).slice(0,4).map(f => '<span class="skill-tag">' + f + '</span>').join('');
    const domainTag = s.domain ? '<span class="skill-domain">' + (domainCN[s.domain]||s.domain) + '</span>' : '';
    const desc = (s.description||'').slice(0,150);
    return '<div class="skill-card"><div class="skill-header"><span class="skill-name">' + s.name + '</span><span class="skill-mode ' + modeClass + '">' + modeLabel + '</span></div><div class="skill-source">' + source + '</div><div class="skill-desc">' + desc + '</div><div class="skill-tags">' + domainTag + tags + '</div></div>';
  }}).join('');
}}

searchInput.addEventListener('input', e => {{ searchQuery = e.target.value; render(); }});
render();
</script>
</body>
</html>'''

out = Path(__file__).resolve().parent / "index_zh.html"
out.write_text(html, encoding="utf-8")
print(f"Chinese dashboard: {out} ({len(html)} bytes)")
