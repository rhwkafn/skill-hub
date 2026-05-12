"""Generate skill usage analytics dashboard from skill_index.json + skill_usage.json."""

import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

root = Path(__file__).resolve().parent.parent
index_path = root / "skill_index.json"
usage_path = root / "skill_usage.json"

# Load data
if index_path.exists():
    with open(index_path, encoding="utf-8") as f:
        skills = json.load(f)
else:
    skills = []

if usage_path.exists():
    with open(usage_path, encoding="utf-8") as f:
        usage = json.load(f)
else:
    usage = {}

total_skills = len(skills)
used_skills = len(usage)
unused_skills = total_skills - used_skills
total_calls = sum(u.get("total", 0) for u in usage.values())

# Monthly stats (last 6 months)
now = datetime.now()
months = []
for i in range(5, -1, -1):
    d = now - timedelta(days=i * 30)
    months.append(d.strftime("%Y-%m"))

monthly_counts = {}
for m in months:
    monthly_counts[m] = sum(u.get("months", {}).get(m, 0) for u in usage.values())

# Top used skills
top_used = sorted(usage.items(), key=lambda x: x[1].get("total", 0), reverse=True)[:20]

# Unused skills with metadata for recommendations
unused_list = []
for s in skills:
    if s["name"] not in usage:
        unused_list.append({
            "name": s["name"],
            "registry": s["registry"],
            "description": (s.get("description", "") or "")[:150],
            "domain": s.get("domain", "") or "none",
            "phase": s.get("phase", "execute") or "execute",
            "triggers": s.get("triggers", []),
            "use_when": s.get("use_when", ""),
        })
# Sort unused by domain for better presentation
unused_list.sort(key=lambda x: x["domain"])

# Rarely used (1-2 calls)
rarely_used = [(name, data) for name, data in usage.items()
               if data.get("total", 0) <= 2]
rarely_used.sort(key=lambda x: x[1].get("total", 0))

# Domain distribution of unused skills
unused_domains = Counter(s["domain"] for s in unused_list)
unused_phases = Counter(s["phase"] for s in unused_list)

updated = datetime.now().strftime("%Y-%m-%d %H:%M")


def escape_js_json(obj):
    """JSON.dumps with </script> escaping to prevent HTML injection."""
    s = json.dumps(obj, ensure_ascii=False)
    return s.replace("</script>", "<\\/script>").replace("<!--", "<\\!--")

# ─── HTML ───
html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Skill Hub — 使用率分析</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #06060b; --card: #0e0e18; --card-hover: #161625; --border: #1a1a2e;
    --text: #e8e8f0; --text-dim: #7878a0; --accent: #7c6cf0; --accent2: #00d4cf;
    --accent3: #ff6b9d; --accent4: #f0c040; --accent5: #40e0a0;
    --glow: rgba(124,108,240,0.15); --danger: #ff5c5c;
  }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:'Inter','SF Pro Display','PingFang SC','Microsoft YaHei',system-ui,sans-serif; background:var(--bg); color:var(--text); line-height:1.6; overflow-x:hidden; }}

  /* ── Hero ── */
  .hero {{ padding:80px 40px 40px; text-align:center; position:relative; overflow:hidden; background:linear-gradient(180deg,#0c0c1a 0%,#0a0a14 100%); }}
  .hero::before {{ content:''; position:absolute; inset:0; background:radial-gradient(ellipse 80% 50% at 50% 0%,rgba(255,92,92,0.1) 0%,transparent 60%),radial-gradient(ellipse 60% 40% at 80% 80%,rgba(124,108,240,0.08) 0%,transparent 50%); pointer-events:none; }}
  .hero h1 {{ font-size:2.8rem; font-weight:800; letter-spacing:-0.02em; background:linear-gradient(135deg,#ff6b9d 0%,#7c6cf0 50%,#00d4cf 100%); background-size:200% 200%; -webkit-background-clip:text; -webkit-text-fill-color:transparent; animation:grad 6s ease infinite; margin-bottom:8px; }}
  @keyframes grad {{ 0%,100%{{background-position:0% 50%}} 50%{{background-position:100% 50%}} }}
  .hero p {{ color:var(--text-dim); font-size:1.1rem; }}
  .hero .updated {{ color:var(--text-dim); font-size:0.75rem; margin-top:8px; opacity:0.5; }}
  .hero-links {{ display:flex; gap:12px; justify-content:center; margin-top:20px; }}
  .hero-btn {{ display:inline-flex; align-items:center; gap:8px; padding:10px 24px; border-radius:10px; font-size:0.9rem; font-weight:600; text-decoration:none; transition:all 0.25s; cursor:pointer; border:none; }}
  .hero-btn-primary {{ background:linear-gradient(135deg,#7c6cf0,#6c5ce7); color:#fff; box-shadow:0 4px 20px rgba(124,108,240,0.3); }}
  .hero-btn-primary:hover {{ transform:translateY(-2px); box-shadow:0 6px 28px rgba(124,108,240,0.45); }}
  .hero-btn-ghost {{ background:rgba(255,255,255,0.05); color:var(--text-dim); border:1px solid var(--border); }}
  .hero-btn-ghost:hover {{ background:rgba(255,255,255,0.1); color:var(--text); border-color:var(--accent); }}
  .hero-btn svg {{ width:18px; height:18px; fill:currentColor; }}

  /* ── Stats ── */
  .stats {{ display:flex; justify-content:center; gap:48px; padding:36px 40px; position:relative; }}
  .stats::before {{ content:''; position:absolute; top:0; left:50%; transform:translateX(-50%); width:80%; height:1px; background:linear-gradient(90deg,transparent,var(--border),transparent); }}
  .stat {{ text-align:center; }}
  .stat-num {{ font-size:2.4rem; font-weight:800; line-height:1.1; }}
  .stat-num.accent {{ background:linear-gradient(135deg,var(--accent),var(--accent2)); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }}
  .stat-num.danger {{ background:linear-gradient(135deg,var(--danger),var(--accent3)); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }}
  .stat-num.success {{ background:linear-gradient(135deg,var(--accent5),var(--accent2)); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }}
  .stat-label {{ font-size:0.75rem; color:var(--text-dim); letter-spacing:1.5px; text-transform:uppercase; margin-top:4px; }}

  /* ── Container ── */
  .container {{ max-width:1440px; margin:0 auto; padding:0 48px 80px; }}
  .section {{ margin-bottom:56px; }}
  .section-title {{ font-size:1.3rem; font-weight:700; margin-bottom:20px; padding-left:14px; border-left:3px solid var(--accent); display:flex; align-items:center; gap:12px; }}

  /* ── Charts ── */
  .charts-row {{ display:grid; grid-template-columns:1fr 1fr; gap:20px; margin-bottom:24px; }}
  .chart-card {{ background:var(--card); border:1px solid var(--border); border-radius:14px; padding:24px; position:relative; overflow:hidden; }}
  .chart-card::before {{ content:''; position:absolute; top:0; left:0; right:0; height:1px; background:linear-gradient(90deg,transparent,rgba(124,108,240,0.2),transparent); }}
  .chart-card h3 {{ font-size:0.85rem; color:var(--text-dim); margin-bottom:16px; font-weight:600; letter-spacing:0.5px; text-transform:uppercase; }}
  .chart-container {{ position:relative; height:260px; }}

  /* ── Usage Bar Chart (animated) ── */
  .usage-bars {{ display:flex; flex-direction:column; gap:8px; }}
  .usage-bar-row {{ display:flex; align-items:center; gap:12px; }}
  .usage-bar-name {{ width:160px; font-size:0.82rem; color:var(--text); text-align:right; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
  .usage-bar-track {{ flex:1; height:24px; background:var(--card); border-radius:6px; overflow:hidden; position:relative; }}
  .usage-bar-fill {{ height:100%; border-radius:6px; background:linear-gradient(90deg,var(--accent),var(--accent2)); transition:width 1.5s cubic-bezier(0.22,1,0.36,1); width:0; position:relative; }}
  .usage-bar-fill::after {{ content:attr(data-count); position:absolute; right:8px; top:50%; transform:translateY(-50%); font-size:0.72rem; font-weight:700; color:#fff; }}
  .usage-bar-fill.zero {{ background:linear-gradient(90deg,rgba(255,92,92,0.3),rgba(255,107,157,0.3)); }}
  .usage-bar-fill.zero::after {{ content:'0'; color:var(--danger); }}

  /* ── Unused Skill Cards ── */
  .unused-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(320px,1fr)); gap:14px; }}
  .unused-card {{ background:var(--card); border:1px solid var(--border); border-radius:12px; padding:18px; position:relative; overflow:hidden; transition:all 0.3s; }}
  .unused-card::before {{ content:''; position:absolute; inset:-1px; border-radius:12px; background:linear-gradient(135deg,rgba(255,92,92,0.2),rgba(124,108,240,0.1)); opacity:0; transition:opacity 0.3s; z-index:0; pointer-events:none; }}
  .unused-card:hover {{ transform:translateY(-3px); border-color:rgba(255,92,92,0.4); box-shadow:0 8px 32px rgba(255,92,92,0.1),0 0 0 1px rgba(255,92,92,0.1); }}
  .unused-card:hover::before {{ opacity:1; }}
  .unused-card > * {{ position:relative; z-index:1; }}
  .unused-name {{ font-weight:700; font-size:0.95rem; margin-bottom:4px; }}
  .unused-source {{ font-size:0.72rem; color:var(--text-dim); opacity:0.7; margin-bottom:6px; }}
  .unused-desc {{ font-size:0.82rem; color:var(--text-dim); line-height:1.5; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }}
  .unused-tags {{ display:flex; gap:5px; flex-wrap:wrap; margin-top:10px; }}
  .unused-tag {{ font-size:0.68rem; padding:2px 8px; border-radius:6px; font-weight:500; }}
  .tag-domain {{ background:rgba(240,192,64,0.08); color:var(--accent4); }}
  .tag-phase {{ background:rgba(124,108,240,0.08); color:var(--accent); }}
  .unused-prompt {{ margin-top:10px; padding:8px 12px; background:rgba(124,108,240,0.06); border-radius:8px; font-size:0.78rem; color:var(--text-dim); border-left:2px solid var(--accent); }}
  .unused-prompt strong {{ color:var(--accent); }}

  /* ── Pulse animation for unused cards ── */
  @keyframes pulse-glow {{ 0%,100%{{box-shadow:0 0 0 0 rgba(255,92,92,0)}} 50%{{box-shadow:0 0 20px 2px rgba(255,92,92,0.08)}} }}
  .unused-card {{ animation:pulse-glow 4s ease-in-out infinite; }}
  .unused-card:nth-child(2n) {{ animation-delay:1s; }}
  .unused-card:nth-child(3n) {{ animation-delay:2s; }}

  /* ── Monthly trend ── */
  .trend-card {{ background:var(--card); border:1px solid var(--border); border-radius:14px; padding:24px; }}
  .trend-card h3 {{ font-size:0.85rem; color:var(--text-dim); margin-bottom:16px; font-weight:600; letter-spacing:0.5px; text-transform:uppercase; }}

  /* ── Footer ── */
  .footer {{ text-align:center; padding:48px 40px; color:var(--text-dim); font-size:0.8rem; border-top:1px solid var(--border); margin-top:40px; }}
  .footer a {{ color:var(--accent); text-decoration:none; }}
  .footer a:hover {{ color:var(--accent2); }}

  /* ── Responsive ── */
  @media (max-width:960px) {{
    .charts-row {{ grid-template-columns:1fr; }}
    .hero h1 {{ font-size:2rem; }} .hero {{ padding:60px 24px 36px; }}
    .stats {{ gap:24px; flex-wrap:wrap; }} .stat-num {{ font-size:1.8rem; }}
    .container {{ padding:0 24px 50px; }}
    .unused-grid {{ grid-template-columns:1fr; }}
    .usage-bar-name {{ width:100px; font-size:0.75rem; }}
  }}
</style>
</head>
<body>

<div class="hero">
  <h1>Skill Usage Analytics</h1>
  <p>{total_skills} 个技能中 {unused_skills} 个从未被调用 — 发现被忽略的能力</p>
  <div class="updated">最后更新：{updated}</div>
  <div class="hero-links">
    <a class="hero-btn hero-btn-primary" href="index_zh.html">
      <svg viewBox="0 0 16 16"><path d="M8 0C3.58 0 0 3.58 0 8c0 4.42 3.58 8 8 8s8-3.58 8-8c0-4.42-3.58-8-8-8zm5.9 7H9.64c-.1 2.67-.95 5.07-2.25 6.72A6.03 6.03 0 0013.9 8zM8 14c-1.13-1.56-1.96-3.84-2.07-6.5h4.13c-.1 2.66-.94 4.94-2.06 6.5zM5.93 6H1.1a6.03 6.03 0 014.58-5.72C4.36 1.93 3.5 4.33 3.4 7l2.53.01zM1.1 10h4.83c.1 2.67.95 5.07 2.25 6.72A6.03 6.03 0 011.1 10zm6.97 6.72C9.37 15.07 10.2 12.79 10.31 10h4.59a6.03 6.03 0 01-6.83 6.72z"/></svg>
      查看主面板
    </a>
    <a class="hero-btn hero-btn-ghost" href="https://github.com/rhwkafn/skill-hub" target="_blank">
      <svg viewBox="0 0 16 16"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>
      GitHub
    </a>
  </div>
</div>

<div class="stats">
  <div class="stat"><div class="stat-num accent" data-target="{total_skills}">0</div><div class="stat-label">总技能数</div></div>
  <div class="stat"><div class="stat-num success" data-target="{used_skills}">0</div><div class="stat-label">已使用</div></div>
  <div class="stat"><div class="stat-num danger" data-target="{unused_skills}">0</div><div class="stat-label">未使用</div></div>
  <div class="stat"><div class="stat-num accent" data-target="{total_calls}">0</div><div class="stat-label">总调用次数</div></div>
</div>

<div class="container">

  <!-- Charts -->
  <div class="charts-row">
    <div class="chart-card">
      <h3>月度调用趋势</h3>
      <div class="chart-container"><canvas id="chartMonthly"></canvas></div>
    </div>
    <div class="chart-card">
      <h3>未使用技能 — 领域分布</h3>
      <div class="chart-container"><canvas id="chartDomain"></canvas></div>
    </div>
  </div>

  <!-- Top Used Skills -->
  <div class="section">
    <div class="section-title">最常使用的技能 Top 20</div>
    <div class="usage-bars" id="usageBars"></div>
  </div>

  <!-- Unused Skills -->
  <div class="section">
    <div class="section-title">
      从未使用的技能
      <span style="font-size:0.8rem;color:var(--danger);font-weight:400;">({unused_skills} 个)</span>
    </div>
    <div class="unused-grid" id="unusedGrid"></div>
  </div>

  <!-- Rarely Used -->
  <div class="section">
    <div class="section-title">低频使用的技能 (≤2 次)</div>
    <div class="unused-grid" id="rarelyGrid"></div>
  </div>

</div>

<div class="footer">
  <a href="https://github.com/rhwkafn/skill-hub">skill-hub</a> &mdash; Skill Usage Analytics Dashboard
</div>

<script>
// Animated counters
document.querySelectorAll('.stat-num[data-target]').forEach(el => {{
  const target = parseInt(el.dataset.target);
  const duration = 1500;
  const start = performance.now();
  function tick(now) {{
    const progress = Math.min((now - start) / duration, 1);
    const ease = 1 - Math.pow(1 - progress, 3);
    el.textContent = Math.round(ease * target);
    if (progress < 1) requestAnimationFrame(tick);
  }}
  requestAnimationFrame(tick);
}});

// Monthly trend chart
const monthlyData = {escape_js_json(list(monthly_counts.values()))};
const monthlyLabels = {escape_js_json(list(monthly_counts.keys()))};
new Chart(document.getElementById('chartMonthly'), {{
  type: 'line',
  data: {{
    labels: monthlyLabels,
    datasets: [{{
      data: monthlyData,
      borderColor: '#7c6cf0',
      backgroundColor: 'rgba(124,108,240,0.1)',
      fill: true,
      tension: 0.4,
      pointBackgroundColor: '#7c6cf0',
      pointBorderColor: '#0e0e18',
      pointBorderWidth: 2,
      pointRadius: 5,
      pointHoverRadius: 8,
    }}]
  }},
  options: {{
    responsive: true,
    maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ grid: {{ color: 'rgba(255,255,255,0.03)' }}, ticks: {{ color: '#7878a0' }} }},
      y: {{ grid: {{ color: 'rgba(255,255,255,0.03)' }}, ticks: {{ color: '#7878a0' }}, beginAtZero: true }},
    }},
    animation: {{ duration: 2000, easing: 'easeOutQuart' }},
  }}
}});

// Domain distribution chart
const domainData = {escape_js_json(dict(unused_domains))};
const domainLabels = Object.keys(domainData);
const domainValues = Object.values(domainData);
const domainColors = ['#ff6b9d','#7c6cf0','#00d4cf','#f0c040','#40e0a0','#a29bfe','#fab1a0','#81ecec'];
new Chart(document.getElementById('chartDomain'), {{
  type: 'doughnut',
  data: {{
    labels: domainLabels,
    datasets: [{{ data: domainValues, backgroundColor: domainColors.slice(0,domainLabels.length), borderWidth:0, hoverBorderWidth:2, hoverBorderColor:'#fff' }}]
  }},
  options: {{
    responsive: true,
    maintainAspectRatio: false,
    plugins: {{ legend: {{ position:'right', labels: {{ color:'#7878a0', font:{{size:11}}, padding:8, boxWidth:12 }} }} }},
    animation: {{ duration: 1500, easing: 'easeOutQuart' }},
  }}
}});

// Top used skills bars
const topUsed = {escape_js_json([{"name": n, "count": d.get("total", 0)} for n, d in top_used])};
const maxCount = Math.max(...topUsed.map(s => s.count), 1);
const barsContainer = document.getElementById('usageBars');
topUsed.forEach((s, i) => {{
  const row = document.createElement('div');
  row.className = 'usage-bar-row';
  const pct = (s.count / maxCount * 100).toFixed(1);
  row.innerHTML = `<div class="usage-bar-name">${{s.name}}</div><div class="usage-bar-track"><div class="usage-bar-fill" data-count="${{s.count}}" style="width:0%"></div></div>`;
  barsContainer.appendChild(row);
  // Animate after a delay
  setTimeout(() => {{
    row.querySelector('.usage-bar-fill').style.width = pct + '%';
  }}, 100 + i * 80);
}});

// Unused skills cards
const unusedSkills = {escape_js_json(unused_list[:60])};
const domainMap = {{"biology":"生物学","science":"科学","engineering":"工程","data-science":"数据科学","writing":"写作","marketing":"营销","chemistry":"化学","none":"通用"}};
const phaseMap = {{"define":"定义","plan":"规划","build":"构建","verify":"验证","review":"审查","ship":"交付","execute":"执行"}};
const unusedGrid = document.getElementById('unusedGrid');
unusedSkills.forEach(s => {{
  const src = s.registry.split('/').pop();
  const dLabel = domainMap[s.domain] || s.domain;
  const pLabel = phaseMap[s.phase] || s.phase;
  // Generate suggested prompt
  let prompt = s.use_when || s.triggers[0] || '';
  if (!prompt) {{
    prompt = `尝试用 "${{s.name}}" 来处理 ${{dLabel !== '通用' ? dLabel : ''}}相关的任务`;
  }}
  const card = document.createElement('div');
  card.className = 'unused-card';
  card.innerHTML = `<div class="unused-name">${{s.name}}</div><div class="unused-source">${{src}}</div><div class="unused-desc">${{s.description}}</div><div class="unused-tags"><span class="unused-tag tag-domain">${{dLabel}}</span><span class="unused-tag tag-phase">${{pLabel}}</span></div><div class="unused-prompt"><strong>试试：</strong>${{prompt}}</div>`;
  unusedGrid.appendChild(card);
}});

// Rarely used skills
const rarelyUsed = {escape_js_json([{"name": n, "count": d.get("total", 0), "last": d.get("last_used", "")} for n, d in rarely_used[:30]])};
const rarelyGrid = document.getElementById('rarelyGrid');
rarelyUsed.forEach(s => {{
  const info = unusedSkills.find(u => u.name === s.name) || {{}};
  const src = (info.registry || '').split('/').pop();
  const dLabel = domainMap[info.domain || 'none'] || info.domain || '通用';
  const card = document.createElement('div');
  card.className = 'unused-card';
  card.innerHTML = `<div class="unused-name">${{s.name}} <span style="font-size:0.7rem;color:var(--accent4);">(${{s.count}}次)</span></div><div class="unused-source">${{src}}</div><div class="unused-desc">${{info.description || ''}}</div><div class="unused-tags"><span class="unused-tag tag-domain">${{dLabel}}</span></div>`;
  rarelyGrid.appendChild(card);
}});
</script>
</body>
</html>"""

# Write
out_dir = Path(__file__).resolve().parent
(out_dir / "skill-usage.html").write_text(html, encoding="utf-8")
print(f"Output: {out_dir / 'skill-usage.html'} ({len(html):,} bytes)")
print(f"Skills: {total_skills} total, {used_skills} used, {unused_skills} unused, {total_calls} calls")
