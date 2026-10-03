"""
Render the weekly reconciliation report for the retail project as static HTML pages, one per week,
plus a CSV of each week's exceptions. The newest week is also written as index.html.

Reads:  marts.rr_* tables (built by dbt)
Writes: evidence/static/reports/retail-reconciliation/
            index.html               newest week
            week-YYYY-MM-DD.html     every week (Monday the week starts on)
            exceptions-YYYY-MM-DD.csv

The pages are plain HTML and CSS rendered on the server side (no JavaScript needed to read them),
so they print cleanly and open fast. A small script only powers the week picker.

Usage:
    python pipeline/build_recon_report.py
"""

from __future__ import annotations

import csv
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from jinja2 import Environment
from markupsafe import Markup

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT = REPO_ROOT / "evidence" / "static" / "reports" / "retail-reconciliation"

DEPARTMENTS = ["Retail", "Café", "Auto Center"]
CHECKS = [
    ("Sales vs. accounting", "Each department's register sales vs. the revenue booked in accounting, per store and day"),
    ("Card sales vs. bank", "Card batches vs. processor deposits, after the contract fee"),
    ("Cash vs. bank", "Cash taken in by all three departments vs. armored-car deposits"),
    ("Auto parts vs. inventory", "Parts billed on auto center work orders vs. parts issued from store stock"),
    ("Registers vs. product master", "Items and prices rung up vs. the product master and price book"),
]
# Known events shown on the trend chart (part of this sample company's story)
EVENTS = {date(2026, 7, 13): "Parts scanning + automatic café batch close go live"}
SEV_ORDER = {"High": 0, "Medium": 1, "Low": 2}


def num(v):
    return float(v) if isinstance(v, Decimal) else v


def rows(cur, sql: str, params=None) -> list[dict]:
    cur.execute(sql, params or ())
    cols = [d[0] for d in cur.description]
    return [{c: num(v) for c, v in zip(cols, r)} for r in cur.fetchall()]


def money(v, cents=False) -> str:
    if v is None:
        return "–"
    return f"${v:,.2f}" if cents else f"${v:,.0f}"


def week_label(ws: date) -> str:
    we = ws + timedelta(days=6)
    if ws.month == we.month:
        return f"{ws:%b} {ws.day} – {we.day}, {we.year}"
    return f"{ws:%b} {ws.day} – {we:%b} {we.day}, {we.year}"


def delta(cur, prev, pct=True) -> Markup:
    """Neutral change marker: arrows carry direction, colour does not imply good or bad."""
    if prev in (None, 0) or cur is None:
        return Markup('<span class="d">–</span>')
    ch = (cur - prev) / abs(prev)
    if abs(ch) < 0.005:
        return Markup('<span class="d">±0%</span>')
    arrow = "▲" if ch > 0 else "▼"
    return Markup(f'<span class="d">{arrow} {abs(ch) * 100:.0f}%</span>')


def trend_svg(series: list[dict], current: date) -> Markup:
    """26-week bar chart of open (unmatched) dollars, current week highlighted, events marked."""
    W, H, ml, mr, mt, mb = 760, 190, 54, 10, 28, 30
    iw, ih = W - ml - mr, H - mt - mb
    vmax = max(s["open_amount"] for s in series) or 1
    step_opts = [1000, 2000, 2500, 5000, 10000, 20000, 25000, 50000]
    step = next((s for s in step_opts if vmax / s <= 5), 100000)
    top = step * -(-vmax // step)
    n = len(series)
    bw = iw / n
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Unmatched dollars by week for the last {n} weeks">']
    k = 0
    while k <= top:
        y = mt + ih - k / top * ih
        out.append(f'<line x1="{ml}" x2="{W - mr}" y1="{y:.1f}" y2="{y:.1f}" class="g"/>')
        out.append(f'<text x="{ml - 8}" y="{y + 4:.1f}" text-anchor="end" class="ax">${k / 1000:,.0f}K</text>' if k else
                   f'<text x="{ml - 8}" y="{y + 4:.1f}" text-anchor="end" class="ax">$0</text>')
        k += step
    for i, s in enumerate(series):
        x = ml + i * bw + bw * 0.18
        h = s["open_amount"] / top * ih
        cls = "b cur" if s["week_start"] == current else "b"
        title = f'Week of {s["week_start"]:%b} {s["week_start"].day}: {money(s["open_amount"])} unmatched, {s["open_exceptions"]} open items'
        out.append(f'<a href="week-{s["week_start"].isoformat()}.html"><rect x="{x:.1f}" y="{mt + ih - h:.1f}" '
                   f'width="{bw * 0.64:.1f}" height="{max(h, 1):.1f}" class="{cls}"><title>{title}</title></rect></a>')
        cur_i = next(j for j, t in enumerate(series) if t["week_start"] == current)
        if s["week_start"] == current or (i % 4 == 0 and abs(i - cur_i) > 2):
            out.append(f'<text x="{x + bw * 0.32:.1f}" y="{H - 10}" text-anchor="middle" class="ax{" curx" if s["week_start"] == current else ""}">'
                       f'{s["week_start"]:%b} {s["week_start"].day}</text>')
        if s["week_start"] in EVENTS:
            ex = ml + i * bw
            out.append(f'<line x1="{ex:.1f}" x2="{ex:.1f}" y1="{mt - 6}" y2="{mt + ih}" class="ev"/>')
            out.append(f'<text x="{ex + 5:.1f}" y="{mt - 10}" class="evt">{EVENTS[s["week_start"]]}</text>')
    out.append("</svg>")
    return Markup("".join(out))


TEMPLATE = r"""{% macro ex_table(list) %}
<div class="scroll"><table class="ex">
  <thead><tr><th>Severity</th><th>Date</th><th>Store</th><th>What doesn't match, and where to fix it</th><th class="r">Amount</th></tr></thead>
  <tbody>
  {% for e in list %}
    <tr><td><span class="chip {{ e.severity }}">{{ e.severity }}</span></td><td class="dt">{{ e.date }}</td><td class="st">{{ e.store }}</td>
        <td class="what"><b>{{ e.issue }}</b><small>{{ e.detail }}</small><span class="fix"><b>Fix in {{ e.likely_source }}:</b> {{ e.suggested_action }}</span></td>
        <td class="r amt">{{ e.amount }}</td></tr>
  {% endfor %}
  </tbody>
</table></div>
{% endmacro %}
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Store-to-Bank Reconciliation · Week of {{ label }} · Creative Data Solutions</title>
<meta name="description" content="Weekly reconciliation report for a three-department retailer: sales, accounting, bank and inventory matched across six systems.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&family=Space+Grotesk:wght@600;700&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #DCE3EB; --paper: #FFFFFF; --panel: #F7F9FC; --line: #CBD6E3; --grid: #E6ECF3;
    --text-hi: #14213D; --text-lo: #4E5C74; --muted: #7A879C; --value: #2D5FA8; --value-soft: #D6E1F1;
    --accent-cool: #1C3B6B; --link: #1F6FB0; --bar: #9DB6D8; --bar-cur: #1F6FB0;
    --high-bg: #FBE7D6; --high-ink: #8A3B0C; --med-bg: #E3EAF5; --med-ink: #2D4F86; --low-bg: #EEF1F5; --low-ink: #5B6779;
    --ok-bg: #DCEFEA; --ok-ink: #17594C;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; background: var(--bg); color: var(--text-hi); font-family: 'Poppins', system-ui, sans-serif; }
  a { color: var(--link); }
  .wrap { max-width: 1120px; margin: 0 auto; padding: 0 24px 48px; }
  @media (max-width: 640px) { .wrap { padding: 0 16px 40px; } }
  .topbar { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap;
            padding: 18px 0; font-size: 13px; }
  .topbar .brand { font-family: 'Space Grotesk', sans-serif; font-weight: 700; color: var(--accent-cool); text-decoration: none; font-size: 15px; }
  .topbar nav a { color: var(--link); text-decoration: none; margin-left: 18px; font-weight: 500; }
  .topbar nav a:first-child { margin-left: 0; }

  .toolbar { display: flex; justify-content: space-between; align-items: end; gap: 14px; flex-wrap: wrap; margin: 6px 0 14px; }
  .toolbar label { display: flex; flex-direction: column; gap: 5px; font-size: 12px; font-weight: 600; color: var(--text-lo); }
  select { font: inherit; font-size: 14px; font-weight: 500; color: var(--text-hi); background: var(--panel);
           border: 1px solid var(--line); border-radius: 8px; padding: 9px 34px 9px 11px; min-width: 250px;
           appearance: none; -webkit-appearance: none; cursor: pointer;
           background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8'%3E%3Cpath d='M1 1l5 5 5-5' fill='none' stroke='%234E5C74' stroke-width='1.6'/%3E%3C/svg%3E");
           background-repeat: no-repeat; background-position: right 12px center; }
  .actions { display: flex; gap: 10px; flex-wrap: wrap; }
  .btn { display: inline-flex; align-items: center; gap: 6px; font: inherit; font-size: 13px; font-weight: 600; color: var(--value);
         background: var(--panel); border: 1px solid var(--line); border-radius: 20px; padding: 8px 16px; text-decoration: none; cursor: pointer; }
  .btn:hover { border-color: var(--value); }

  .paper { background: var(--paper); border: 1px solid var(--line); border-radius: 6px; box-shadow: 0 10px 30px rgba(20,33,61,.08);
           padding: 44px 52px 40px; }
  @media (max-width: 760px) { .paper { padding: 26px 18px 24px; } }
  .rhead { display: flex; justify-content: space-between; gap: 20px; flex-wrap: wrap; border-bottom: 2px solid var(--accent-cool); padding-bottom: 16px; }
  .eyebrow { font-family: 'IBM Plex Mono', monospace; font-size: 11.5px; letter-spacing: .08em; text-transform: uppercase; color: var(--value); margin: 0 0 6px; }
  h1 { font-family: 'Space Grotesk', sans-serif; font-weight: 700; font-size: 30px; line-height: 1.15; margin: 0; color: var(--accent-cool); }
  .rhead .wk { font-family: 'Space Grotesk', sans-serif; font-weight: 600; font-size: 19px; color: var(--value); margin: 6px 0 0; }
  .rhead .meta { font-size: 12.5px; color: var(--text-lo); text-align: right; line-height: 1.6; }
  @media (max-width: 640px) { h1 { font-size: 24px; } .rhead .meta { text-align: left; } }

  .summary { font-size: 16px; line-height: 1.65; color: var(--text-hi); margin: 22px 0 22px; max-width: 900px; }
  .summary b { font-weight: 600; }
  .kpis { display: grid; grid-template-columns: repeat(4, 1fr); border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); margin-bottom: 34px; }
  .kpi { padding: 16px 18px 14px 0; }
  .kpi + .kpi { padding-left: 18px; border-left: 1px solid var(--grid); }
  .kpi .l { font-size: 12px; color: var(--text-lo); }
  .kpi .v { font-family: 'Space Grotesk', sans-serif; font-weight: 700; font-size: 27px; color: var(--text-hi); margin: 2px 0; }
  .kpi .s { font-size: 12px; color: var(--text-lo); }
  @media (max-width: 760px) { .kpis { grid-template-columns: 1fr 1fr; } .kpi:nth-child(3) { padding-left: 0; border-left: 0; } .kpi:nth-child(n+3) { border-top: 1px solid var(--grid); } }
  .d { font-weight: 600; color: var(--text-hi); white-space: nowrap; }

  h2 { font-family: 'Space Grotesk', sans-serif; font-weight: 700; font-size: 19px; color: var(--accent-cool); margin: 0 0 4px; }
  h2 .n { font-family: 'IBM Plex Mono', monospace; font-size: 12px; color: var(--value); margin-right: 8px; font-weight: 500; }
  .note { font-size: 13px; color: var(--text-lo); margin: 0 0 12px; line-height: 1.5; }
  section { margin-bottom: 36px; }

  .scroll { overflow-x: auto; -webkit-overflow-scrolling: touch; }
  table { width: 100%; border-collapse: collapse; font-size: 13.5px; }
  th { text-align: left; font-size: 11.5px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: .04em;
       padding: 8px 10px 8px 0; border-bottom: 1px solid var(--line); white-space: nowrap; }
  td { padding: 10px 10px 10px 0; border-bottom: 1px solid var(--grid); vertical-align: top; }
  .r { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
  td.what small { display: block; color: var(--text-lo); font-size: 12px; margin-top: 2px; line-height: 1.45; }
  tr.sub td { font-weight: 600; background: var(--panel); }
  .incl { font-weight: 400; font-size: 12px; color: var(--text-lo); margin-left: 4px; }
  tr.store td { padding-top: 16px; font-family: 'Space Grotesk', sans-serif; font-weight: 700; color: var(--accent-cool); border-bottom: 1px solid var(--line); }

  .chip { display: inline-block; font-size: 11.5px; font-weight: 600; padding: 3px 9px; border-radius: 10px; white-space: nowrap; }
  .chip.High, .chip.action { background: var(--high-bg); color: var(--high-ink); }
  .chip.Medium, .chip.review { background: var(--med-bg); color: var(--med-ink); }
  .chip.Low { background: var(--low-bg); color: var(--low-ink); }
  .chip.clean { background: var(--ok-bg); color: var(--ok-ink); }

  .trend svg { width: 100%; min-width: 620px; height: auto; display: block; }
  @media (max-width: 640px) { table.checks td.what small { display: none; } }
  .trend .g { stroke: var(--grid); stroke-width: 1; }
  .trend .ax { font-size: 11px; fill: var(--muted); font-family: 'Poppins', sans-serif; }
  .trend .curx { fill: var(--text-hi); font-weight: 600; }
  .trend .b { fill: var(--bar); }
  .trend .b.cur { fill: var(--bar-cur); }
  .trend a:hover .b { fill: var(--value); }
  .trend .ev { stroke: var(--text-lo); stroke-dasharray: 3 3; stroke-width: 1; }
  .trend .evt { font-size: 11px; fill: var(--text-lo); font-family: 'Poppins', sans-serif; }

  .exgroup { margin: 22px 0 6px; display: flex; justify-content: space-between; gap: 10px; flex-wrap: wrap; align-items: baseline;
             border-bottom: 1px solid var(--line); padding-bottom: 6px; }
  .exgroup h3 { font-size: 15px; font-weight: 600; margin: 0; }
  .exgroup span { font-size: 12.5px; color: var(--text-lo); }
  table.ex td { font-size: 13px; }
  table.ex td.what .fix { display: block; font-size: 12px; color: var(--text-hi); margin-top: 4px; }
  table.ex td.what .fix b { font-weight: 600; color: var(--value); }
  table.ex td.dt, table.ex td.st { white-space: nowrap; }
  table.ex td.amt { font-weight: 600; }
  .none { color: var(--text-lo); font-size: 14px; padding: 10px 0; }
  details { margin: 8px 0 0; }
  details summary { cursor: pointer; font-weight: 600; font-size: 14px; color: var(--accent-cool); }
  details[open] summary { margin-bottom: 4px; }
  @media (max-width: 760px) {
    table.ex thead { display: none; }
    table.ex tr { display: grid; grid-template-columns: auto 1fr auto; gap: 4px 10px; padding: 12px 0; border-bottom: 1px solid var(--grid); }
    table.ex td { border: 0; padding: 0; }
    table.ex td.what { grid-column: 1 / -1; }
    table.ex td.amt { grid-row: 1; grid-column: 3; }
    table.ex td.dt { color: var(--text-lo); font-size: 12px; }
  }

  .archive { display: flex; flex-wrap: wrap; gap: 6px 14px; font-size: 13px; }
  .archive a { text-decoration: none; }
  .archive a.cur { font-weight: 700; color: var(--text-hi); }
  .foot { margin-top: 30px; padding-top: 16px; border-top: 1px solid var(--line); font-size: 12.5px; color: var(--text-lo); line-height: 1.6; }
  footer { margin-top: 22px; font-size: 12.5px; color: var(--muted); text-align: center; }

  @media print {
    body { background: #fff; }
    .topbar, .toolbar, footer, .archive-sec { display: none; }
    .wrap { max-width: none; padding: 0; }
    .paper { border: 0; box-shadow: none; padding: 0; }
    section { break-inside: avoid-page; }
    table.ex tr { break-inside: avoid; }
  }
</style>
</head>
<body>
<div class="wrap">
  <div class="topbar">
    <a class="brand" href="https://creativedatasolutions.tech/portfolio/">Creative Data Solutions · Portfolio</a>
    <nav>
      <a href="https://creativedatasolutions.tech/portfolio/">All projects</a>
      <a href="../../retail-reconciliation/how-it-works">How it was built</a>
      <a href="https://github.com/gbutter1/cds-portfolio">Source code</a>
    </nav>
  </div>

  <div class="toolbar">
    <label>Report week
      <select id="week" aria-label="Choose a report week">
        {% for w in weeks|reverse %}<option value="week-{{ w.iso }}.html"{% if w.iso == iso %} selected{% endif %}>Week of {{ w.label }}{% if loop.first %} (latest){% endif %}</option>{% endfor %}
      </select>
    </label>
    <div class="actions">
      <a class="btn" href="exceptions-{{ iso }}.csv" download>Download exceptions (CSV)</a>
      <button class="btn" type="button" onclick="window.print()">Print / save as PDF</button>
    </div>
  </div>

  <article class="paper">
    <div class="rhead">
      <div>
        <p class="eyebrow">Peachtree Supply Club · Weekly report</p>
        <h1>Store-to-Bank Reconciliation</h1>
        <p class="wk">Week of {{ label }}</p>
      </div>
      <div class="meta">
        3 stores · Retail, Café, Auto Center<br>
        6 systems reconciled · prepared {{ prepared }}
      </div>
    </div>

    <p class="summary">{{ summary }}</p>

    <div class="kpis">
      <div class="kpi"><div class="l">Net sales, all stores</div><div class="v">{{ k.sales }}</div><div class="s">{{ k.sales_d }} vs prior week</div></div>
      <div class="kpi"><div class="l">Gross margin</div><div class="v">{{ k.gm }}</div><div class="s">{{ k.gm_d }}</div></div>
      <div class="kpi"><div class="l">Items reconciled</div><div class="v">{{ k.match }}</div><div class="s">{{ k.items_n }} items compared</div></div>
      <div class="kpi"><div class="l">Unmatched dollars</div><div class="v">{{ k.open }}</div><div class="s">{{ k.open_n }} open items · {{ k.open_d }} vs prior week</div></div>
    </div>

    <section>
      <h2><span class="n">01</span>Where the books stand</h2>
      <p class="note">Five checks run every week. Each compares two systems that should agree; anything that doesn't is listed in section 04.</p>
      <div class="scroll"><table class="checks">
        <thead><tr><th>Check</th><th class="r">Compared</th><th class="r">Matched</th><th class="r">Open items</th><th class="r">Open $</th><th>Status</th></tr></thead>
        <tbody>
        {% for c in checks %}
          <tr><td class="what"><b>{{ c.name }}</b><small>{{ c.desc }}</small></td>
              <td class="r">{{ "{:,}".format(c.items_checked) }}</td><td class="r">{{ c.rate }}</td>
              <td class="r">{{ c.open_exceptions }}</td><td class="r">{{ c.open_amount }}</td>
              <td><span class="chip {{ c.status_cls }}">{{ c.status }}</span></td></tr>
        {% endfor %}
        </tbody>
      </table></div>
    </section>

    <section>
      <h2><span class="n">02</span>Scorecard by store and department</h2>
      <p class="note">Sales are net of discounts, before tax. Margin uses product-master cost, café food cost and a standard labor cost. Volume is register transactions for Retail, items sold for the Café and work orders for the Auto Center. Card and cash deposit issues span departments, so they are counted in each store's total.</p>
      <div class="scroll"><table>
        <thead><tr><th>Department</th><th class="r">Net sales</th><th class="r">vs prior wk</th><th class="r">Gross margin</th><th class="r">Volume</th><th class="r">Open items</th><th class="r">Open $</th></tr></thead>
        <tbody>
        {% for s in stores %}
          <tr class="store"><td colspan="7">{{ s.name }}</td></tr>
          {% for d in s.depts %}
          <tr><td>{{ d.department }}</td><td class="r">{{ d.sales }}</td><td class="r">{{ d.sales_d }}</td><td class="r">{{ d.gm }}</td>
              <td class="r">{{ d.tx }}</td><td class="r">{{ d.open_n }}</td><td class="r">{{ d.open }}</td></tr>
          {% endfor %}
          <tr class="sub"><td>Store total{% if s.bank_n %} <span class="incl">incl. {{ s.bank_n }} deposit item{{ 's' if s.bank_n != 1 }}</span>{% endif %}</td>
              <td class="r">{{ s.sales }}</td><td class="r">{{ s.sales_d }}</td><td class="r">{{ s.gm }}</td><td class="r"></td>
              <td class="r">{{ s.open_n }}</td><td class="r">{{ s.open }}</td></tr>
        {% endfor %}
        </tbody>
      </table></div>
    </section>

    <section class="trend">
      <h2><span class="n">03</span>Are the books getting cleaner?</h2>
      <p class="note">Unmatched dollars by week, excluding timing differences that clear on their own. Click a bar to open that week.</p>
      <div class="scroll">{{ trend }}</div>
    </section>

    <section>
      <h2><span class="n">04</span>Exceptions to resolve</h2>
      <p class="note">One row per problem, highest severity and largest amount first, with the system where the fix belongs. Low-severity items are folded away; the CSV download has everything.</p>
      {% if not groups %}<p class="none">Nothing open this week. Every item matched.</p>{% endif %}
      {% for g in groups %}
        <div class="exgroup"><h3>{{ g.name }}</h3><span>{{ g.n }} item{{ 's' if g.n != 1 }} · {{ g.total }}</span></div>
        {% if g.main %}{{ ex_table(g.main) }}{% endif %}
        {% if g.low %}
        <details><summary>{{ g.low|length }} low-severity item{{ 's' if g.low|length != 1 }} ({{ g.low_total }})</summary>{{ ex_table(g.low) }}</details>
        {% endif %}
      {% endfor %}
      {% if timing %}
      <div class="exgroup"><h3>Timing differences</h3><span>{{ timing|length }} item{{ 's' if timing|length != 1 }} · clear on their own, not counted above</span></div>
      <details><summary>Show timing differences</summary>{{ ex_table(timing) }}</details>
      {% endif %}
    </section>

    <section class="archive-sec">
      <h2><span class="n">05</span>Report archive</h2>
      <div class="archive">{% for w in weeks|reverse %}<a href="week-{{ w.iso }}.html"{% if w.iso == iso %} class="cur" aria-current="page"{% endif %}>{{ w.short }}</a>{% endfor %}</div>
    </section>

    <div class="foot">
      Peachtree Supply Club is a fictional company. Its six systems (retail registers, café registers, auto center, merchandising and inventory, accounting, and bank)
      are realistic sample data with deliberate, real-world mismatches built in, so no real business or customer data is used.
      The report is rebuilt automatically whenever the pipeline runs and is published only if every data test passes.
    </div>
  </article>

  <footer>© Creative Data Solutions · <a href="../../retail-reconciliation/how-it-works">How this report is built</a></footer>
</div>
<script>
  document.getElementById('week').addEventListener('change', function () { window.location.href = this.value; });
  // print everything, including folded sections
  var folded = [];
  window.addEventListener('beforeprint', function () {
    folded = [].slice.call(document.querySelectorAll('details:not([open])'));
    folded.forEach(function (d) { d.open = true; });
  });
  window.addEventListener('afterprint', function () { folded.forEach(function (d) { d.open = false; }); });
</script>
</body>
</html>
"""


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL is not set. Put it in .env or the environment.", file=sys.stderr)
        return 2

    with psycopg2.connect(url) as conn, conn.cursor() as cur:
        stores = rows(cur, "select store_id, city, store_name from marts.rr_dim_store order by store_id")
        summary = rows(cur, "select * from marts.rr_check_summary")
        score = rows(cur, "select * from marts.rr_weekly_scorecard")
        exc = rows(cur, """select exception_id, check_name, exception_type, week_start, business_date, store_id, store,
                                  department, issue, detail, amount, likely_source, suggested_action, severity, is_timing
                           from marts.rr_exceptions order by week_start, business_date""")

    weeks_all = sorted({r["week_start"] for r in score})
    weeks = [{"iso": w.isoformat(), "label": week_label(w), "short": f"{w:%b} {w.day}"} for w in weeks_all]
    by_week_sum = defaultdict(list)
    for r in summary:
        by_week_sum[r["week_start"]].append(r)
    by_week_score = defaultdict(list)
    for r in score:
        by_week_score[r["week_start"]].append(r)
    by_week_exc = defaultdict(list)
    for r in exc:
        by_week_exc[r["week_start"]].append(r)

    trend = [{"week_start": w,
              "open_amount": sum(r["open_amount"] for r in by_week_sum[w]),
              "open_exceptions": sum(r["open_exceptions"] for r in by_week_sum[w])} for w in weeks_all]
    trend_by = {t["week_start"]: t for t in trend}

    env = Environment(autoescape=True, trim_blocks=True, lstrip_blocks=True)
    tpl = env.from_string(TEMPLATE)
    now = datetime.now(timezone.utc)
    prepared = f"{now:%b} {now.day}, {now.year}"
    OUT.mkdir(parents=True, exist_ok=True)

    for i, w in enumerate(weeks_all):
        prev = weeks_all[i - 1] if i else None
        sc, sc_prev = by_week_score[w], by_week_score[prev] if prev else []
        sales = sum(r["net_sales"] for r in sc)
        cost = sum(r["cost"] for r in sc)
        p_sales = sum(r["net_sales"] for r in sc_prev) if prev else None
        p_cost = sum(r["cost"] for r in sc_prev) if prev else None
        gm = (sales - cost) / sales if sales else 0
        p_gm = (p_sales - p_cost) / p_sales if p_sales else None
        checks_w = {r["check_name"]: r for r in by_week_sum[w]}
        items = sum(r["items_checked"] for r in checks_w.values())
        matched = sum(r["items_matched"] for r in checks_w.values())
        t, tp = trend_by[w], trend_by.get(prev)
        ex_w = by_week_exc[w]
        open_ex = [e for e in ex_w if not e["is_timing"]]
        high = [e for e in open_ex if e["severity"] == "High"]

        # plain-language summary
        if not open_ex:
            text = f"Every item matched across all six systems for the week of {week_label(w)}."
        else:
            worst = defaultdict(float)
            for e in open_ex:
                worst[e["check_name"]] += e["amount"]
            top_check = max(worst, key=worst.get)
            text = (f"{matched / items:.1%} of {items:,} items matched across the six systems. "
                    f"{len(open_ex)} item{'s' if len(open_ex) != 1 else ''} worth {money(t['open_amount'])} need attention"
                    f"{f', {len(high)} of them high severity' if high else ''}. "
                    f"The largest share is in {top_check.lower()} ({money(worst[top_check])}).")
            timing = [e for e in ex_w if e["is_timing"]]
            if timing:
                text += f" Another {len(timing)} timing difference{'s' if len(timing) != 1 else ''} will clear on {'their' if len(timing) != 1 else 'its'} own."

        k = {
            "sales": money(sales), "sales_d": delta(sales, p_sales),
            "gm": f"{gm:.1%}",
            "gm_d": Markup(f'<span class="d">{"▲" if gm > p_gm else "▼"} {abs(gm - p_gm) * 100:.1f} pts</span> vs prior week')
                    if p_gm is not None and abs(gm - p_gm) >= 0.0005 else "about the same as prior week",
            "match": f"{matched / items:.1%}", "items_n": f"{items:,}",
            "open": money(t["open_amount"]), "open_n": t["open_exceptions"],
            "open_d": delta(t["open_amount"], tp["open_amount"] if tp else None),
        }

        checks = []
        for name, desc in CHECKS:
            r = checks_w.get(name, {"items_checked": 0, "items_matched": 0, "open_exceptions": 0, "open_amount": 0})
            has_high = any(e["severity"] == "High" and e["check_name"] == name for e in open_ex)
            status, cls = (("Clean", "clean") if r["open_exceptions"] == 0 else
                           ("Action needed", "action") if has_high else ("Review", "review"))
            checks.append({"name": name, "desc": desc, "items_checked": r["items_checked"],
                           "rate": f"{r['items_matched'] / r['items_checked']:.1%}" if r["items_checked"] else "–",
                           "open_exceptions": r["open_exceptions"], "open_amount": money(r["open_amount"]),
                           "status": status, "status_cls": cls})

        store_rows = []
        for s in stores:
            depts = []
            st_sales = st_cost = st_psales = 0.0
            for dep in DEPARTMENTS:
                r = next((x for x in sc if x["store_id"] == s["store_id"] and x["department"] == dep), None)
                rp = next((x for x in sc_prev if x["store_id"] == s["store_id"] and x["department"] == dep), None)
                if not r:
                    continue
                st_sales += r["net_sales"]; st_cost += r["cost"]; st_psales += rp["net_sales"] if rp else 0
                depts.append({"department": dep, "sales": money(r["net_sales"]), "sales_d": delta(r["net_sales"], rp["net_sales"] if rp else None),
                              "gm": f"{r['gross_margin_pct']:.1%}", "tx": f"{int(r['transactions']):,}",
                              "open_n": r["open_exceptions"] or "–", "open": money(r["open_amount"]) if r["open_amount"] else "–"})
            s_open = [e for e in open_ex if e["store_id"] == s["store_id"]]
            bank_n = sum(1 for e in s_open if e["department"] not in DEPARTMENTS)
            store_rows.append({"name": s["store_name"].replace(" - ", " · "), "depts": depts,
                               "sales": money(st_sales), "sales_d": delta(st_sales, st_psales or None),
                               "gm": f"{(st_sales - st_cost) / st_sales:.1%}" if st_sales else "–",
                               "open_n": len(s_open) or "–", "open": money(sum(e["amount"] for e in s_open)) if s_open else "–",
                               "bank_n": bank_n})

        def fmt_e(e):
            return {**e, "date": f"{e['business_date']:%a %b} {e['business_date'].day}", "amount": money(e["amount"], cents=True)}

        groups = []
        for name, _ in CHECKS:
            items_g = sorted([e for e in open_ex if e["check_name"] == name],
                             key=lambda e: (SEV_ORDER[e["severity"]], -e["amount"]))
            if items_g:
                low = [fmt_e(e) for e in items_g if e["severity"] == "Low"]
                groups.append({"name": name, "n": len(items_g),
                               "main": [fmt_e(e) for e in items_g if e["severity"] != "Low"], "low": low,
                               "low_total": money(sum(e["amount"] for e in items_g if e["severity"] == "Low")),
                               "total": money(sum(e["amount"] for e in items_g))})
        timing = [fmt_e(e) for e in sorted((e for e in ex_w if e["is_timing"]), key=lambda e: e["business_date"])]

        html = tpl.render(label=week_label(w), iso=w.isoformat(), weeks=weeks, prepared=prepared, summary=text, k=k,
                          checks=checks, stores=store_rows, trend=trend_svg(trend, w), groups=groups, timing=timing)
        (OUT / f"week-{w.isoformat()}.html").write_text(html, encoding="utf-8")
        if w == weeks_all[-1]:
            (OUT / "index.html").write_text(html, encoding="utf-8")

        with (OUT / f"exceptions-{w.isoformat()}.csv").open("w", newline="", encoding="utf-8") as f:
            cols = ["exception_id", "severity", "check_name", "business_date", "store", "department", "issue", "detail",
                    "amount", "likely_source", "suggested_action", "is_timing"]
            wr = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            wr.writeheader()
            for e in sorted(ex_w, key=lambda e: (e["is_timing"], SEV_ORDER[e["severity"]], -e["amount"])):
                wr.writerow({**e, "amount": f"{e['amount']:.2f}"})

    print(f"wrote {len(weeks_all)} weekly reports + index.html to {OUT.relative_to(REPO_ROOT)} "
          f"({sum(len(v) for v in by_week_exc.values()):,} exceptions)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
