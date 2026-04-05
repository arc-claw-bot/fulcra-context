#!/usr/bin/env python3
"""
Generate accurate sleep data visualizations from Fulcra data.
Dark theme, premium health-tech aesthetic. Real data, real charts.
"""

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

# Default data directory - can be overridden via environment or command line
DEFAULT_DATA_DIR = Path.home() / ".openclaw/workspace/data/fulcra-analysis"

# Premium dark theme
BG = '#0d1117'
CARD = '#161b22'
TEXT = '#e6edf3'
DIM = '#7d8590'
GRID = '#21262d'
DEEP = '#1f6feb'
CORE = '#8b5cf6'
REM = '#f59e0b'
AWAKE = '#f85149'
GREEN = '#3fb950'
ACCENT = '#58a6ff'


def load_data(data_dir=None):
    if data_dir is None:
        data_dir = DEFAULT_DATA_DIR
    data_dir = Path(data_dir)
    
    for name in ["sleep-briefing-latest.json", "sleep-briefing.json"]:
        p = data_dir / name
        if p.exists():
            return json.loads(p.read_text())
    return None


def create_chart(data: dict, output: str):
    d = data.get("data", data)
    ln = d.get("last_night", {})
    history = d.get("history", [])

    stages = ln.get("stages", {})
    deep = stages.get("deep", 0)
    core = stages.get("core", 0)
    rem = stages.get("rem", 0)
    awake = ln.get("awake_min", stages.get("awake", 0))
    total_h = ln.get("total_sleep_h", 0)
    deep_pct = ln.get("deep_pct", 0)
    rem_pct = ln.get("rem_pct", 0)
    eff = ln.get("efficiency", 0)
    bedtime = ln.get("bedtime_str", "")
    wake = ln.get("wake_str", "")
    frag = ln.get("frag_pct", 0)

    fig = plt.figure(figsize=(10, 13), facecolor=BG)

    # ── Title ──
    fig.text(0.5, 0.97, 'SLEEP ANALYSIS', fontsize=22, fontweight='bold',
             color=TEXT, ha='center', fontfamily='sans-serif')
    night_date = history[0]["date"] if history else ""
    fig.text(0.5, 0.945, f'{night_date}  •  {bedtime} → {wake}  •  {total_h:.1f}h total',
             fontsize=11, color=DIM, ha='center')

    # ── Panel 1: Donut + Metrics (top) ──
    ax1 = fig.add_axes([0.05, 0.74, 0.35, 0.18])
    ax1.set_facecolor(BG)

    vals = [v for v in [deep, core, rem, awake] if v > 0]
    cols = [c for v, c in zip([deep, core, rem, awake], [DEEP, CORE, REM, AWAKE]) if v > 0]

    if vals:
        ax1.pie(vals, colors=cols, startangle=90,
                wedgeprops=dict(width=0.32, edgecolor=BG, linewidth=2))
        ax1.text(0, 0.08, f'{total_h:.1f}h', fontsize=24, fontweight='bold',
                 color=TEXT, ha='center', va='center')
        ax1.text(0, -0.18, f'{eff:.0f}% efficient', fontsize=9, color=DIM, ha='center')

    # Metrics panel
    ax2 = fig.add_axes([0.45, 0.74, 0.52, 0.18])
    ax2.set_facecolor(BG)
    ax2.axis('off')

    metrics = [
        (f'{deep:.0f}', 'min', f'Deep ({deep_pct:.0f}%)', DEEP),
        (f'{rem:.0f}', 'min', f'REM ({rem_pct:.0f}%)', REM),
        (f'{core:.0f}', 'min', f'Core ({ln.get("core_pct", 0):.0f}%)', CORE),
        (f'{frag:.0f}%', '', f'Fragmentation', AWAKE if frag > 15 else DIM),
    ]

    for i, (val, unit, label, color) in enumerate(metrics):
        row, col = divmod(i, 2)
        x, y = 0.05 + col * 0.5, 0.72 - row * 0.48
        ax2.text(x, y, val, fontsize=22, fontweight='bold', color=color, transform=ax2.transAxes)
        ax2.text(x + 0.22, y + 0.02, unit, fontsize=10, color=DIM, transform=ax2.transAxes)
        ax2.text(x, y - 0.18, label, fontsize=9, color=DIM, transform=ax2.transAxes)

    # ── Panel 2: Stage bar ──
    ax3 = fig.add_axes([0.12, 0.70, 0.76, 0.025])
    ax3.set_facecolor(BG)
    total_min = deep + core + rem + awake or 1
    left = 0
    for mins, color, label in [(deep, DEEP, 'Deep'), (core, CORE, 'Core'),
                                (rem, REM, 'REM'), (awake, AWAKE, 'Awake')]:
        w = mins / total_min
        if w > 0:
            ax3.barh(0, w, left=left, color=color, height=0.8, edgecolor=BG, linewidth=1)
            if w > 0.07:
                ax3.text(left + w / 2, 0, f'{label} {mins:.0f}m',
                         ha='center', va='center', fontsize=7, color='white', fontweight='bold')
            left += w
    ax3.set_xlim(0, 1)
    ax3.set_ylim(-0.5, 0.5)
    ax3.axis('off')

    # ── Panel 3: 7-Night Deep Sleep Trend ──
    ax4 = fig.add_subplot(4, 1, 3)
    ax4.set_facecolor(CARD)

    if history:
        hist = list(reversed(history))  # oldest first
        dates = [h.get("date", "")[-5:] for h in hist]  # MM-DD
        deep_mins = [h["total_h"] * 60 * h["deep_pct"] / 100 for h in hist]

        bars = ax4.bar(range(len(deep_mins)), deep_mins, color=DEEP, alpha=0.75,
                       width=0.6, edgecolor=BG, linewidth=1)
        if bars:
            bars[-1].set_alpha(1.0)
            bars[-1].set_edgecolor(ACCENT)
            bars[-1].set_linewidth(2)

        avg = np.mean(deep_mins)
        ax4.axhline(avg, color=DIM, linestyle='--', linewidth=1, alpha=0.5)
        ax4.text(len(deep_mins) - 0.5, avg + 2, f'avg {avg:.0f}m', fontsize=8, color=DIM, ha='right')

        ax4.set_xticks(range(len(dates)))
        ax4.set_xticklabels(dates, fontsize=8, color=DIM)
        for i, v in enumerate(deep_mins):
            ax4.text(i, v + 1.5, f'{v:.0f}', ha='center', fontsize=9, color=TEXT, fontweight='bold')

    ax4.set_title('Deep Sleep — 7 Night Trend (min)', fontsize=12, color=TEXT, pad=10, fontweight='bold')
    ax4.set_ylabel('Minutes', fontsize=9, color=DIM)
    for spine in ['top', 'right']:
        ax4.spines[spine].set_visible(False)
    for spine in ['left', 'bottom']:
        ax4.spines[spine].set_color(GRID)
    ax4.tick_params(colors=DIM, labelsize=8)
    ax4.yaxis.grid(True, color=GRID, linewidth=0.5)
    ax4.set_axisbelow(True)

    # ── Panel 4: Total Sleep + Efficiency Trend ──
    ax5 = fig.add_subplot(4, 1, 4)
    ax5.set_facecolor(CARD)

    if history:
        hist = list(reversed(history))
        dates = [h.get("date", "")[-5:] for h in hist]
        totals = [h["total_h"] for h in hist]
        effs = [h.get("efficiency", 0) for h in hist]

        ax5.bar(range(len(totals)), totals, color=ACCENT, alpha=0.6, width=0.6,
                edgecolor=BG, linewidth=1, label='Total Sleep (h)')
        for i, v in enumerate(totals):
            ax5.text(i, v + 0.1, f'{v:.1f}', ha='center', fontsize=9, color=TEXT, fontweight='bold')

        ax5b = ax5.twinx()
        ax5b.plot(range(len(effs)), effs, color=GREEN, linewidth=2.5, marker='o',
                  markersize=5, label='Efficiency %', zorder=3)
        ax5b.set_ylabel('Efficiency %', fontsize=9, color=GREEN)
        ax5b.tick_params(colors=GREEN, labelsize=8)
        ax5b.spines['right'].set_color(GRID)
        ax5b.spines['top'].set_visible(False)
        ax5b.set_ylim(60, 100)

        ax5.set_xticks(range(len(dates)))
        ax5.set_xticklabels(dates, fontsize=8, color=DIM)

    ax5.set_title('Total Sleep & Efficiency — 7 Nights', fontsize=12, color=TEXT, pad=10, fontweight='bold')
    ax5.set_ylabel('Hours', fontsize=9, color=DIM)
    for spine in ['top', 'right']:
        ax5.spines[spine].set_visible(False)
    for spine in ['left', 'bottom']:
        ax5.spines[spine].set_color(GRID)
    ax5.tick_params(colors=DIM, labelsize=8)
    ax5.yaxis.grid(True, color=GRID, linewidth=0.5)
    ax5.set_axisbelow(True)

    # ── Footer ──
    fig.text(0.5, 0.01, 'Powered by Fulcra', fontsize=8, color=DIM, ha='center', style='italic')

    fig.subplots_adjust(hspace=0.45, top=0.92, bottom=0.04, left=0.12, right=0.92)
    plt.savefig(output, dpi=150, facecolor=BG, bbox_inches='tight', pad_inches=0.3)
    plt.close()
    print(f"Chart saved: {output}")


if __name__ == "__main__":
    data_dir = None
    if len(sys.argv) > 2 and sys.argv[2].startswith("--data-dir="):
        data_dir = sys.argv[2].split("=", 1)[1]
    
    data = load_data(data_dir)
    if not data:
        print("No sleep data found", file=sys.stderr)
        sys.exit(1)
    
    output_file = sys.argv[1] if len(sys.argv) > 1 else str(DEFAULT_DATA_DIR / "sleep-briefing-chart.png")
    create_chart(data, output_file)