"""Evidence for INC-02 (hash table) and INC-03 (AVL tree).

Reads results/timings.csv and summarises every *build* row of the hash
table and the AVL tree, grouped by code_version, so the same script shows
the numbers before and after a fix. Saves two figures to
analysis/figures_INC02_03/.

Run inside Docker:
    docker compose run --rm app python analysis/evidence_hash_avl.py
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
FIG_DIR = ROOT / "analysis" / "figures_INC02_03"
FIG_DIR.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(ROOT / "results" / "timings.csv")
builds = df[df["operation"] == "build"].copy()
builds["us_per_key"] = builds["total_ns"] / builds["n_keys"] / 1000


def slope(group: pd.DataFrame, column: str) -> float:
    """Log-log slope of the median `column` against n_keys."""
    med = group.groupby("n_keys")[column].median()
    if len(med) < 2:
        return float("nan")
    return float(np.polyfit(np.log(med.index), np.log(med.values), 1)[0])


# ---------------------------------------------------------------- hash table
print("=" * 70)
print("INC-02  hash table build")
print("=" * 70)
hash_rows = builds[builds["index_type"] == "hash_table"]
for (experiment, version), g in hash_rows.groupby(["experiment", "code_version"]):
    table = g.groupby("n_keys").agg(
        reps=("rep", "count"),
        median_ms=("total_ns", lambda s: s.median() / 1e6),
        us_per_key=("us_per_key", "median"),
        resizes=("resizes", "median"),
    )
    # A table that doubles needs about log2(n / 1024) + 1 resizes.
    table["resizes_if_doubling"] = np.ceil(
        np.log2(np.maximum(table.index / (0.75 * 1024), 1))
    ).astype(int)
    print(f"\n{experiment}  code_version={version}")
    print(table.round(3).to_string())
    print(f"log-log slope of build time vs n: {slope(g, 'total_ns'):.2f}"
          "   (1.0 = linear, 2.0 = quadratic)")

# ------------------------------------------------------------------ AVL tree
print()
print("=" * 70)
print("INC-03  AVL tree build")
print("=" * 70)
avl_rows = builds[builds["index_type"] == "avl_tree"]
for (experiment, version, order), g in avl_rows.groupby(
        ["experiment", "code_version", "insert_order"]):
    table = g.groupby("n_keys").agg(
        reps=("rep", "count"),
        median_ms=("total_ns", lambda s: s.median() / 1e6),
        rotations=("rotations", "median"),
        height=("height", "median"),
    )
    table["rotations_per_key"] = table["rotations"] / table.index
    # AVL height is guaranteed to be below about 1.44 * log2(n + 2).
    table["height_bound"] = (1.44 * np.log2(table.index + 2)).round(1)
    print(f"\n{experiment}  code_version={version}  order={order}")
    print(table.round(3).to_string())

# ------------------------------------------------------------------- figures
fig, ax = plt.subplots(figsize=(6, 4))
for name in ("hash_table", "avl_tree", "ref_dict", "unsorted_list"):
    g = builds[(builds["index_type"] == name) & (builds["experiment"] == "E1_build_memory")]
    if g.empty:
        continue
    med = g.groupby("n_keys")["total_ns"].median() / 1e6
    ax.loglog(med.index, med.values, marker="o", label=name)
ax.set_xlabel("n keys")
ax.set_ylabel("median build time (ms)")
ax.set_title("E1 build time (log-log)")
ax.legend()
fig.tight_layout()
fig.savefig(FIG_DIR / "build_time_loglog.png", dpi=150)

fig, ax = plt.subplots(figsize=(6, 4))
for (version, order), g in avl_rows.groupby(["code_version", "insert_order"]):
    med = g.groupby("n_keys")["rotations"].median()
    ax.semilogx(med.index, med.values / med.index, marker="o",
                label=f"{version[:7]} {order}")
ax.set_xlabel("n keys")
ax.set_ylabel("rotations per inserted key")
ax.set_title("AVL rotations per key")
ax.legend(fontsize=7)
fig.tight_layout()
fig.savefig(FIG_DIR / "avl_rotations_per_key.png", dpi=150)

print(f"\nFigures saved to {FIG_DIR.relative_to(ROOT)}/")