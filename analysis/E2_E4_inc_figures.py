"""Figures and summary tables for E2, E3, E4, INC-02 and INC-03.

Uses the after-fix runs on cimy-mbp (code_version c735d0c) for E2-E4, and
paired before/after sessions for the two incidents.

Run inside Docker from the repository root:
    docker compose run --rm app python analysis/cimy_e2_e4_inc_figures.py
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "analysis" / "figures_cimy"
OUT.mkdir(parents=True, exist_ok=True)

AFTER = "c735d0c"
CANDIDATES = ["unsorted_list", "sorted_list", "hash_table", "avl_tree", "bplus_tree"]
REFS = ["ref_dict", "ref_bisect"]
STYLE = {"ref_dict": ":", "ref_bisect": ":"}

df = pd.read_csv(ROOT / "results" / "timings.csv")
df["us_per_op"] = df["total_ns"] / df["n_ops"] / 1000


def iqr_line(ax, g, x, label, ls="-"):
    """Plot the median with a shaded band from Q1 to Q3."""
    q = g.groupby(x)["us_per_op"].quantile([0.25, 0.5, 0.75]).unstack()
    line, = ax.plot(q.index, q[0.5], marker="o", ms=4, ls=ls, label=label)
    ax.fill_between(q.index, q[0.25], q[0.75], alpha=0.2, color=line.get_color())


def slope(g, x):
    med = g.groupby(x)["us_per_op"].median()
    return np.polyfit(np.log(med.index), np.log(med.values), 1)[0]


# ------------------------------------------------------------------ E2
e2 = df[(df.experiment == "E2_point_track_id") & (df.code_version == AFTER)]
fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
print("E2 (us/query at n = 114,000, median [Q1, Q3]; log-log slope)")
for ax, op in zip(axes, ["point_hit", "point_miss"]):
    for name in CANDIDATES + REFS:
        g = e2[(e2.index_type == name) & (e2.operation == op)]
        iqr_line(ax, g, "n_keys", name, STYLE.get(name, "-"))
        v = g[g.n_keys == 114000]["us_per_op"]
        print(f"  {op:10} {name:14} {v.median():10.3f} [{v.quantile(.25):.3f}, {v.quantile(.75):.3f}]"
              f"  slope {slope(g, 'n_keys'):.2f}")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_title("hits" if op == "point_hit" else "misses")
    ax.set_xlabel("rows indexed (n)")
axes[0].set_ylabel("µs per query (log)")
axes[1].legend(fontsize=7)
fig.suptitle("E2 point lookups on track_id (after all fixes)")
fig.tight_layout(); fig.savefig(OUT / "E2_point_lookup.png", dpi=150)

# ------------------------------------------------------------------ E3
e3 = df[(df.experiment == "E3_range_tempo") & (df.code_version == AFTER)]
fig, ax = plt.subplots(figsize=(6.5, 4.2))
print("\nE3 (us/query, median [Q1, Q3])")
for name in CANDIDATES + REFS:
    g = e3[e3.index_type == name]
    iqr_line(ax, g, "operation_param", name, STYLE.get(name, "-"))
    row = []
    for p, gg in g.groupby("operation_param"):
        v = gg["us_per_op"]
        row.append(f"{p:g}: {v.median():.2f} [{v.quantile(.25):.2f}, {v.quantile(.75):.2f}]")
    print(f"  {name:14} " + " | ".join(row))
ax.set_xscale("log"); ax.set_yscale("log")
ax.set_xlabel("selectivity (share of distinct tempos)")
ax.set_ylabel("µs per query (log)")
ax.set_title("E3 tempo range queries (after all fixes)")
ax.legend(fontsize=7); fig.tight_layout(); fig.savefig(OUT / "E3_range_tempo.png", dpi=150)

# ------------------------------------------------------------------ E4
e4 = df[(df.experiment == "E4_prefix_track_name") & (df.code_version == AFTER)]
fig, ax = plt.subplots(figsize=(6.5, 4.2))
print("\nE4 (us/query, median [Q1, Q3]; keys examined per query)")
for name in CANDIDATES + REFS:
    g = e4[e4.index_type == name]
    iqr_line(ax, g, "operation_param", name, STYLE.get(name, "-"))
    row = []
    for p, gg in g.groupby("operation_param"):
        v = gg["us_per_op"]
        k = (gg["comparisons"] / gg["n_ops"]).median()
        row.append(f"{p:g}: {v.median():.2f} [{v.quantile(.25):.2f}, {v.quantile(.75):.2f}] k={k:.0f}")
    print(f"  {name:14} " + " | ".join(row))
ax.set_yscale("log"); ax.set_xticks([1, 2, 3, 4, 5])
ax.set_xlabel("prefix length (characters)")
ax.set_ylabel("µs per query (log)")
ax.set_title("E4 track_name prefix search (after all fixes)")
ax.legend(fontsize=7); fig.tight_layout(); fig.savefig(OUT / "E4_prefix_track_name.png", dpi=150)

# ---------------------------------------------------- INC-02 hash table
core = df[(df.experiment == "CORE") & (df.machine_id == "cimy-mbp") & (df.operation == "build")
          & (df.index_type == "hash_table")]
e1 = df[(df.experiment == "E1_build_memory") & (df.index_type == "hash_table")]
fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
for version, label in [("03d990e", "before (03d990e)"), (AFTER, "after (c735d0c)")]:
    g = core[core.code_version == version]
    med = g.groupby("n_keys")["total_ns"].median() / 1e6
    axes[0].plot(med.index, med.values, marker="o", label=label)
    g = e1[e1.code_version == version]
    med = g.groupby("n_keys")["resizes"].median()
    axes[1].plot(med.index, med.values, marker="o", label=label)
axes[0].set_xscale("log"); axes[0].set_yscale("log")
axes[0].set_xlabel("rows (n)"); axes[0].set_ylabel("median build time (ms, log)")
axes[0].set_title("CORE build on cimy-mbp")
axes[1].set_xscale("log")
axes[1].set_xlabel("rows (n)"); axes[1].set_ylabel("resizes during build")
axes[1].set_title("E1 resize count")
for ax in axes: ax.legend(fontsize=8)
fig.suptitle("INC-02: hash table growth, before and after doubling")
fig.tight_layout(); fig.savefig(OUT / "INC-02_hash_build.png", dpi=150)

# -------------------------------------------------------- INC-03 AVL tree
avl = df[(df.index_type == "avl_tree") & (df.operation == "build")]
fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
for (exp, version), label in [(("E1_build_memory", "03d990e"), "E1 before"),
                              (("E1_build_memory", AFTER), "E1 after"),
                              (("E5_insert_order", "03d990e"), "E5 random before"),
                              (("E5_insert_order", AFTER), "E5 random after")]:
    g = avl[(avl.experiment == exp) & (avl.code_version == version)]
    if exp == "E5_insert_order":
        g = g[g.insert_order == "random"]
    med = g.groupby("n_keys")[["rotations", "height"]].median()
    ls = "--" if "after" in label else "-"
    axes[0].plot(med.index, med["rotations"] / med.index, marker="o", ls=ls, label=label)
    axes[1].plot(med.index, med["height"], marker="o", ls=ls, label=label)
n = np.logspace(3, np.log10(114000), 50)
axes[1].plot(n, 1.44 * np.log2(n + 2), color="black", lw=1, label="AVL height limit")
for ax in axes: ax.set_xscale("log"); ax.set_xlabel("keys (n)"); ax.legend(fontsize=8)
axes[0].set_ylabel("rotations per inserted key"); axes[0].set_title("Rotations per key")
axes[1].set_ylabel("tree height"); axes[1].set_title("Tree height")
fig.suptitle("INC-03: AVL height update order, before and after")
fig.tight_layout(); fig.savefig(OUT / "INC-03_avl_rotations_height.png", dpi=150)

print(f"\nFigures saved to {OUT.relative_to(ROOT)}/")