"""
Generate the 6 required report figures from CSV files in results/.
Run after simulate_trace.py:  python visualize.py

Outputs (PDF + PNG) saved to results/figures/.
"""

import csv
import os
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np

os.makedirs("results/figures", exist_ok=True)

def load_csv(filename):
    path = os.path.join("results", filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Missing {path} — run simulate_trace.py first")
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def floats(rows, key):
    return [float(r[key]) for r in rows]


def save(fig, name):
    base = os.path.join("results", "figures", name)
    fig.savefig(base + ".pdf", dpi=150, bbox_inches="tight")
    fig.savefig(base + ".png", dpi=150, bbox_inches="tight")
    print(f"  Saved {base}.[pdf|png]")
    plt.close(fig)


WORKLOADS   = ["sequential", "matrix", "random"]
WL_MARKERS  = {"sequential": "o", "matrix": "s", "random": "^"}
WL_COLORS   = {"sequential": "#4C72B0", "matrix": "#DD8452", "random": "#55A868"}
STYLE = dict(linewidth=1.8, markersize=6)

def fig2_miss_vs_size():
    rows = load_csv("e1_cache_size.csv")
    fig, ax = plt.subplots(figsize=(7, 4))

    for wl in WORKLOADS:
        subset = sorted([r for r in rows if r["workload"] == wl],
                        key=lambda r: int(r["l1_size_kb"]))
        xs = [int(r["l1_size_kb"]) for r in subset]
        ys = floats(subset, "l1_miss_rate")
        ax.plot(xs, ys, marker=WL_MARKERS[wl], color=WL_COLORS[wl],
                label=wl.capitalize(), **STYLE)

    ax.set_xscale("log", base=2)
    ax.set_xlabel("L1 Cache Size (KB)", fontsize=11)
    ax.set_ylabel("L1 Miss Rate", fontsize=11)
    ax.set_title("Figure 2 — Miss Rate vs. L1 Cache Size", fontsize=12)
    ax.legend()
    ax.grid(True, which="both", linestyle="--", alpha=0.5)
    save(fig, "fig2_miss_vs_size")

def fig3_amat_vs_blocksize():
    rows = load_csv("fig3_amat_block_assoc.csv")

    # Average over workloads
    grouped = defaultdict(lambda: defaultdict(list))
    for r in rows:
        grouped[int(r["ways"])][int(r["block_size_b"])].append(float(r["amat"]))

    fig, ax = plt.subplots(figsize=(7, 4))
    colors = ["#4C72B0", "#DD8452", "#55A868", "#C44E52"]
    for i, ways in enumerate([1, 2, 4, 8]):
        data = grouped[ways]
        xs = sorted(data.keys())
        ys = [np.mean(data[x]) for x in xs]
        ax.plot(xs, ys, marker="o", color=colors[i],
                label=f"{ways}-way", **STYLE)

    ax.set_xlabel("Block Size (B)", fontsize=11)
    ax.set_ylabel("AMAT (cycles)", fontsize=11)
    ax.set_title("Figure 3 — AMAT vs. Block Size by Associativity", fontsize=12)
    ax.legend(title="Associativity")
    ax.grid(True, linestyle="--", alpha=0.5)
    save(fig, "fig3_amat_vs_blocksize")

def fig4_cpi_decomposition():
    rows = load_csv("e7_workload.csv")

    # Build one bar per (workload × one baseline config).
    # Use e1 data for 3 different L1 sizes to get a richer chart.
    e1_rows = load_csv("e1_cache_size.csv")
    configs = []
    labels  = []
    for wl in WORKLOADS:
        for kb in [4, 32, 64]:
            match = [r for r in e1_rows
                     if r["workload"] == wl and int(r["l1_size_kb"]) == kb]
            if match:
                configs.append(match[0])
                labels.append(f"{wl[:3].upper()}\n{kb}KB")

    cpi_base = [1.0] * len(configs)
    cpi_l1   = floats(configs, "cpi_l1_stall")
    cpi_l2   = floats(configs, "cpi_l2_stall")

    x = np.arange(len(labels))
    w = 0.55
    fig, ax = plt.subplots(figsize=(max(8, len(labels) * 0.9), 5))

    b1 = ax.bar(x, cpi_base, w, label="Ideal CPI",    color="#4C72B0")
    b2 = ax.bar(x, cpi_l1,   w, bottom=cpi_base,      label="L1 Miss Stall", color="#DD8452")
    b3 = ax.bar(x, cpi_l2,   w,
                bottom=[a + b for a, b in zip(cpi_base, cpi_l1)],
                label="L2 Miss Stall", color="#55A868")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("CPI", fontsize=11)
    ax.set_title("Figure 4 — CPI Decomposition by Configuration", fontsize=12)
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.6)
    save(fig, "fig4_cpi_decomposition")

def fig5_write_policy_traffic():
    rows = load_csv("e4_write_policy.csv")

    wl_order = WORKLOADS
    policies  = ["write_back", "write_through"]
    policy_labels = {"write_back": "Write-Back", "write_through": "Write-Through"}
    colors_p  = {"write_back": "#4C72B0", "write_through": "#DD8452"}

    # Collect traffic per (workload, policy)
    traffic = defaultdict(dict)
    for r in rows:
        traffic[r["workload"]][r["write_policy"]] = int(r["mem_traffic"])

    # Normalize to WB traffic for each workload
    x     = np.arange(len(wl_order))
    width = 0.35
    fig, ax = plt.subplots(figsize=(7, 4))

    for i, policy in enumerate(policies):
        vals = []
        for wl in wl_order:
            wb_val = traffic[wl].get("write_back", 1)
            raw    = traffic[wl].get(policy, 0)
            vals.append(raw / wb_val if wb_val else 0)
        ax.bar(x + i * width, vals, width,
               label=policy_labels[policy], color=colors_p[policy])

    ax.set_xticks(x + width / 2)
    ax.set_xticklabels([w.capitalize() for w in wl_order], fontsize=10)
    ax.set_ylabel("Normalized Memory Traffic\n(relative to Write-Back)", fontsize=10)
    ax.set_title("Figure 5 — Write-Through vs. Write-Back Memory Traffic", fontsize=12)
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.6)
    save(fig, "fig5_write_policy_traffic")

def fig6_prefetch_vs_blocksize():
    rows = load_csv("e6_prefetch_vs_blocksize.csv")

    # Average over workloads
    grouped_cov     = defaultdict(list)
    grouped_useless = defaultdict(list)
    for r in rows:
        bs = int(r["block_size_b"])
        grouped_cov[bs].append(float(r["prefetch_coverage"]))
        grouped_useless[bs].append(float(r["useless_rate"]))

    block_sizes = sorted(grouped_cov.keys())
    cov_avg     = [np.mean(grouped_cov[bs])     for bs in block_sizes]
    useless_avg = [np.mean(grouped_useless[bs]) for bs in block_sizes]

    fig, ax1 = plt.subplots(figsize=(7, 4))
    ax2 = ax1.twinx()

    l1, = ax1.plot(block_sizes, cov_avg, "o-", color="#4C72B0",
                   label="Coverage", **STYLE)
    l2, = ax2.plot(block_sizes, useless_avg, "s--", color="#C44E52",
                   label="Useless-Prefetch Rate", **STYLE)

    ax1.set_xlabel("Block Size (B)", fontsize=11)
    ax1.set_ylabel("Prefetch Coverage", fontsize=11, color="#4C72B0")
    ax2.set_ylabel("Useless-Prefetch Rate", fontsize=11, color="#C44E52")
    ax1.set_title("Figure 6 — Prefetch Coverage & Useless Rate vs. Block Size", fontsize=12)

    lines = [l1, l2]
    ax1.legend(lines, [l.get_label() for l in lines], loc="upper left")
    ax1.grid(True, linestyle="--", alpha=0.5)
    save(fig, "fig6_prefetch_blocksize")

def fig_e2_associativity():
    rows = load_csv("e2_associativity.csv")

    fig, ax = plt.subplots(figsize=(7, 4))

    for wl in WORKLOADS:
        subset = sorted([r for r in rows if r["workload"] == wl],
                        key=lambda r: int(r["ways"]))
        xs = [int(r["ways"]) for r in subset]
        ys = floats(subset, "l1_miss_rate")
        ax.plot(xs, ys, marker=WL_MARKERS[wl], color=WL_COLORS[wl],
                label=wl.capitalize(), **STYLE)

    ax.axvspan(2, 8.4, alpha=0.07, color="white", label="No further gain beyond 2-way")
    ax.axvline(x=2, color="#F9E795", linewidth=1.4, linestyle="--")
    ax.text(2.15, 0.55, "2-way threshold\nconflict misses\neliminated",
            color="#F9E795", fontsize=8.5, va="center")

    ax.set_xlabel("Associativity (ways)", fontsize=11)
    ax.set_ylabel("L1 Miss Rate", fontsize=11)
    ax.set_title("E2 — Miss Rate vs. Associativity (32 KB L1, 64B block, LRU, WB)", fontsize=11)
    ax.set_xticks([1, 2, 4, 8])
    ax.set_xticklabels(["1\n(Direct-Mapped)", "2-way", "4-way", "8-way"])
    ax.set_ylim(-0.05, 1.15)
    ax.legend()
    ax.grid(True, linestyle="--", alpha=0.5)
    save(fig, "e2_associativity")


if __name__ == "__main__":
    print("Generating figures…")
    fig2_miss_vs_size()
    fig3_amat_vs_blocksize()
    fig4_cpi_decomposition()
    fig5_write_policy_traffic()
    fig6_prefetch_vs_blocksize()
    fig_e2_associativity()
    print("Done. All figures saved to results/figures/")
