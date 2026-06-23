"""Generate a multi-panel sales dashboard using matplotlib.

Creates a figure with:
  - Bar chart of monthly sales
  - Line chart showing cumulative revenue
  - Pie chart of quarterly breakdown
"""

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for saving to file
import matplotlib.pyplot as plt
import numpy as np


def generate_sales_chart(output_path="sales_chart.png"):
    """Create and save a multi-panel sales dashboard."""

    months = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ]
    sales = np.array([
        12500, 14200, 16800, 15300, 18900, 21000,
        19500, 22300, 20100, 23500, 25800, 28400,
    ])

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Annual Sales Dashboard - 2025", fontsize=18, fontweight="bold", y=0.98)

    # --- Panel 1: Bar chart ---
    ax1 = axes[0, 0]
    colors = plt.cm.Blues(np.linspace(0.4, 0.9, len(months)))
    bars = ax1.bar(months, sales, color=colors, edgecolor="navy", linewidth=0.5)
    for bar, value in zip(bars, sales):
        ax1.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 300,
            f"${value / 1000:.1f}k",
            ha="center", va="bottom", fontsize=7,
        )
    ax1.set_title("Monthly Sales", fontsize=13, fontweight="bold")
    ax1.set_ylabel("Revenue ($)")
    ax1.set_ylim(0, max(sales) * 1.2)
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    ax1.grid(axis="y", alpha=0.3, linestyle="--")
    ax1.set_axisbelow(True)
    ax1.tick_params(axis="x", rotation=45)

    # --- Panel 2: Cumulative line chart ---
    ax2 = axes[0, 1]
    cumulative = np.cumsum(sales)
    ax2.plot(months, cumulative, color="darkorange", marker="o", linewidth=2.5, markersize=6)
    ax2.fill_between(months, cumulative, alpha=0.15, color="darkorange")
    ax2.set_title("Cumulative Revenue", fontsize=13, fontweight="bold")
    ax2.set_ylabel("Total ($)")
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"${x / 1000:.0f}k"))
    ax2.grid(alpha=0.3, linestyle="--")
    ax2.tick_params(axis="x", rotation=45)

    # --- Panel 3: Quarter-over-quarter growth ---
    ax3 = axes[1, 0]
    q1, q2, q3, q4 = sales[:3].sum(), sales[3:6].sum(), sales[6:9].sum(), sales[9:].sum()
    quarters = ["Q1", "Q2", "Q3", "Q4"]
    q_sales = [q1, q2, q3, q4]
    q_growth = [0] + [
        (q_sales[i] - q_sales[i - 1]) / q_sales[i - 1] * 100 for i in range(1, 4)
    ]
    bar_colors = ["#2ecc71" if g >= 0 else "#e74c3c" for g in q_growth]
    bars3 = ax3.bar(quarters, q_growth, color=bar_colors, edgecolor="gray", linewidth=0.5)
    for bar, g in zip(bars3, q_growth):
        ax3.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.5 if g >= 0 else bar.get_height() - 2,
            f"{g:+.1f}%",
            ha="center", va="bottom" if g >= 0 else "top", fontsize=10, fontweight="bold",
        )
    ax3.axhline(y=0, color="black", linewidth=0.8)
    ax3.set_title("Quarter-over-Quarter Growth", fontsize=13, fontweight="bold")
    ax3.set_ylabel("Growth (%)")
    ax3.grid(axis="y", alpha=0.3, linestyle="--")
    ax3.set_axisbelow(True)

    # --- Panel 4: Quarterly pie chart ---
    ax4 = axes[1, 1]
    total = sum(q_sales)
    pct = [s / total * 100 for s in q_sales]
    explode = (0.03, 0.03, 0.03, 0.03)
    wedges, texts, autotexts = ax4.pie(
        q_sales, labels=quarters, autopct="%1.1f%%", startangle=90,
        explode=explode, colors=plt.cm.Set2.colors[:4],
        textprops={"fontsize": 11},
    )
    for t in autotexts:
        t.set_fontweight("bold")
    ax4.set_title("Revenue by Quarter", fontsize=13, fontweight="bold")

    # --- Summary stats ---
    fig.text(
        0.5, 0.01,
        f"Total: ${total:,.0f}  |  Avg monthly: ${sales.mean():,.0f}  |  "
        f"Peak: {months[sales.argmax()]} (${sales.max():,.0f})",
        ha="center", fontsize=11, style="italic",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="lightyellow", alpha=0.8),
    )

    plt.tight_layout(rect=[0, 0.04, 1, 0.95])
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    print(f"Dashboard saved to {output_path}")


if __name__ == "__main__":
    generate_sales_chart()
