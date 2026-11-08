"""Summaries shared by the E6 and Part E report notebooks."""

from pathlib import Path
import subprocess

import numpy as np
import pandas as pd

ORIGINAL = "6eed8a1"  # Intern handoff commit, before changes to any index.
COUNTERS = ("comparisons", "nodes_visited", "rotations", "splits", "resizes")
SESSION = ["machine_id", "code_version", "session_id"]
CONFIG = ["index_type", "index_param", "key_column", "n_keys",
          "operation", "operation_param", "n_ops"]
CORE_SOURCE = ("indexes", "bench/core_suite.py", "bench/timing.py", "loaders",
               "Dockerfile", "requirements.txt")
E6_WORKLOAD_SOURCE = ("indexes/base.py", "bench/experiments.py", "bench/timing.py",
                      "datagen/synthetic.py", "loaders", "Dockerfile", "requirements.txt")
BPLUS_SOURCE = ("indexes/bplus_tree.py",)
ORDERS = (3, 4, 8, 16, 32, 64, 128, 256, 512)
SIZES = (1000, 5000, 10000, 25000, 50000, 114000)
INDEXES = ("unsorted_list", "sorted_list", "hash_table", "avl_tree",
           "bplus_tree", "ref_dict", "ref_bisect")
E6_OPS = {"build": "Build", "point_hit": "Point hit", "point_miss": "Point miss",
          "range": "Tempo range (1%)"}


def load_data(repo):
    """Load official runs and retain raw version/session information."""
    repo = Path(repo)
    rows = pd.read_csv(repo / "results/timings.csv", dtype=str, keep_default_na=False)
    clean = rows["code_version"].str.fullmatch(r"[0-9a-f]{7,40}")
    rows = rows[rows["in_docker"].eq("True") & clean].copy()
    for col in ("n_keys", "n_ops", "rep", "total_ns", "height", "memory_bytes", *COUNTERS):
        rows[col] = pd.to_numeric(rows[col], errors="coerce")
    rows = rows[rows["n_ops"].gt(0) & rows["total_ns"].gt(0)].copy()
    rows["ns_per_op"] = rows["total_ns"] / rows["n_ops"]
    machines = pd.read_csv(repo / "machines.csv")
    return rows, machines


def signature(repo, version, paths):
    """Use Git objects to prove the selected source paths are byte-identical."""
    result = subprocess.run(["git", "ls-tree", version, "--", *paths], cwd=repo,
                            capture_output=True, text=True)
    if result.returncode or len(result.stdout.splitlines()) != len(paths):
        return None
    return result.stdout


def source_objects(repo, versions, paths):
    """Expose the Git objects used to verify each reported version's source."""
    records = []
    for version in sorted(set(versions)):
        source = signature(repo, version, paths)
        for line in (source or "").splitlines():
            metadata, path = line.split("\t")
            records.append((version, path, metadata.split()[-1]))
    return pd.DataFrame(records, columns=["code_version", "path", "git_object"])


def session_manifest(rows, expected):
    """Require a session to cover exactly the intended configs, at five or more reps."""
    records = []
    for session, data in rows.groupby(SESSION, sort=False):
        reps = data.groupby(CONFIG)["rep"].agg(["size", "nunique"])
        complete = (
            set(reps.index) == expected
            and (reps["size"] == reps["nunique"]).all()
            and reps["nunique"].ge(5).all()
        )
        records.append(dict(zip(SESSION, session), member=data["member"].iloc[0],
                            date=data["timestamp_utc"].max(), batches=len(data),
                            min_reps=reps["nunique"].min(), complete=bool(complete),
                            python_version=data["python_version"].iloc[0],
                            hash_seed=data["pythonhashseed"].iloc[0]))
    columns = SESSION + ["member", "date", "batches", "min_reps", "complete",
                         "python_version", "hash_seed"]
    return pd.DataFrame(records, columns=columns).sort_values("date")


def timing_summary(rows, keys):
    """One row per configuration, without pooling independent sessions."""
    return rows.groupby(keys, as_index=False).agg(
        reps=("rep", "nunique"),
        median_ns=("ns_per_op", "median"),
        q1_ns=("ns_per_op", lambda x: x.quantile(0.25)),
        q3_ns=("ns_per_op", lambda x: x.quantile(0.75)),
        mean_ns=("ns_per_op", "mean"),
        std_ns=("ns_per_op", "std"),
    ).assign(cv_percent=lambda t: 100 * t["std_ns"] / t["mean_ns"])


def _e6_configurations():
    configs = set()
    for order in ORDERS:
        base = ("bplus_tree", f"order={order}")
        for size in SIZES:
            configs.update({(*base, "track_id", size, "build", "", size),
                            (*base, "track_id", size, "point_hit", "1.0", 1000),
                            (*base, "track_id", size, "point_miss", "0.0", 1000)})
        configs.add((*base, "tempo", SIZES[-1], "range", "0.01", 200))
    return configs


def e6_summaries(rows, repo, baseline_id=None, final_id=None):
    """Select one same-machine, same-workload pair and retain every timing replicate."""
    e6 = rows[rows["experiment"].eq("E6_bplus_order")].copy()
    e6["order"] = pd.to_numeric(e6["index_param"].str.removeprefix("order="))
    manifest = session_manifest(e6, _e6_configurations())
    manifest["bplus_source"] = [
        signature(repo, version, BPLUS_SOURCE) for version in manifest["code_version"]
    ]
    manifest["workload_source"] = [
        signature(repo, version, E6_WORKLOAD_SOURCE) for version in manifest["code_version"]
    ]
    original = signature(repo, ORIGINAL, BPLUS_SOURCE)
    head = signature(repo, "HEAD", BPLUS_SOURCE)
    manifest["phase"] = "Other version"
    if original is not None:
        manifest.loc[manifest["bplus_source"].eq(original), "phase"] = "Original B+"
    if head is not None and head != original:
        manifest.loc[manifest["bplus_source"].eq(head), "phase"] = "Current B+"

    def candidates(phase, session_id):
        matches = manifest[manifest["complete"] & manifest["phase"].eq(phase)]
        if session_id is not None:
            matches = matches[matches["session_id"].eq(session_id)]
            if matches.empty:
                raise ValueError(f"{session_id} is not a complete {phase} session")
        return matches

    final = candidates("Current B+", final_id).tail(1)
    baseline = candidates("Original B+", baseline_id)
    if len(final):
        for col in ("machine_id", "python_version", "hash_seed", "workload_source"):
            baseline = baseline[baseline[col].eq(final.iloc[0][col])]
        if baseline_id is not None and baseline.empty:
            raise ValueError("Selected E6 sessions differ in machine, Python, seed, or workload source")
    selected = pd.concat([baseline.tail(1), final]).drop(
        columns=["bplus_source", "workload_source"]
    )
    samples = e6.merge(selected[["session_id", "phase"]], on="session_id")
    keys = ["phase", *SESSION, "key_column", "operation", "n_keys", "order"]
    summary = timing_summary(samples, keys)
    diagnostics = samples.assign(**{
        f"{counter}_per_op": samples[counter] / samples["n_ops"] for counter in COUNTERS
    })
    diag_cols = ["height", *[f"{counter}_per_op" for counter in COUNTERS]]
    diagnostics = diagnostics.groupby(keys, as_index=False)[diag_cols].median()
    summary = summary.merge(diagnostics, on=keys)

    rank_keys = ["phase", "key_column", "operation", "n_keys"]
    summary["rank"] = summary.groupby(rank_keys)["median_ns"].rank(method="min").astype(int)
    leaders = []
    for _, data in summary.groupby(rank_keys):
        first, second = data.sort_values(["median_ns", "order"]).iloc[:2].to_dict("records")
        default_ns = data.loc[data["order"].eq(32), "median_ns"].iloc[0]
        leaders.append({**{key: first[key] for key in [*rank_keys, *SESSION]},
                        "best_order": first["order"],
                        "median_ns": first["median_ns"], "q1_ns": first["q1_ns"],
                        "q3_ns": first["q3_ns"], "runner_up_order": second["order"],
                        "runner_up_median_ns": second["median_ns"],
                        "runner_up_iqr_overlaps": first["q3_ns"] >= second["q1_ns"],
                        "default_32_over_best": default_ns / first["median_ns"]})
    return manifest.drop(columns=["bplus_source", "workload_source"]), selected, summary, pd.DataFrame(leaders)


def e6_growth(summary):
    """Estimate log-log slopes for build totals and point time per query."""
    records = []
    for (phase, order, operation), data in summary.groupby(["phase", "order", "operation"]):
        if len(data) < 3:
            continue
        x = np.log(data["n_keys"])
        elapsed = data["median_ns"] * data["n_keys"] if operation == "build" else data["median_ns"]
        y = np.log(elapsed)
        slope, intercept = np.polyfit(x, y, 1)
        variance = ((y - y.mean()) ** 2).sum()
        residual = ((y - (slope * x + intercept)) ** 2).sum()
        r2 = 1 - residual / variance if variance else np.nan
        records.append(dict(phase=phase, order=order, operation=operation,
                            log_log_slope=slope, r_squared=r2))
    return pd.DataFrame(records)


def e6_change(summary):
    """Pair E6 medians and deterministic counters before and after the B+ change."""
    keys = ["key_column", "operation", "n_keys", "order"]
    cols = [*keys, *SESSION, "median_ns", "q1_ns", "q3_ns",
            "nodes_visited_per_op", "comparisons_per_op"]
    before = summary.loc[summary["phase"].eq("Original B+"), cols]
    after = summary.loc[summary["phase"].eq("Current B+"), cols]
    paired = before.merge(after, on=[*keys, "machine_id"], suffixes=("_original", "_current"))
    paired["speedup"] = paired["median_ns_original"] / paired["median_ns_current"]
    return paired


def _core_configurations():
    # The pinned dataset has one nameless track. CORE discards it only for prefixes.
    workloads = [
        ("track_id", 10000, "build", "", 10000),
        ("track_id", 114000, "build", "", 114000),
        ("track_id", 114000, "point_hit", "", 1000),
        ("track_id", 114000, "point_miss", "", 1000),
        ("tempo", 114000, "range", "0.01", 200),
        ("track_name", 113999, "prefix", "3", 200),
    ]
    return {(idx, "order=32" if idx == "bplus_tree" else "", *work)
            for idx in INDEXES for work in workloads}


def core_summaries(rows, repo):
    """Compare complete CORE sessions by raw revision and proven source equivalence."""
    core = rows[rows["experiment"].eq("CORE")]
    manifest = session_manifest(core, _core_configurations())
    versions = manifest["code_version"].unique()
    original_source = signature(repo, ORIGINAL, CORE_SOURCE)
    head_source = signature(repo, "HEAD", CORE_SOURCE)
    # Label each verified source cohort by an actual measured commit within it.
    cohorts, sources = {}, {}
    for version in sorted(versions):
        source = signature(repo, version, CORE_SOURCE)
        if source is None:
            cohorts[version] = f"Unverified {version}"
        else:
            if source == original_source:
                name = "Original source"
            elif source == head_source:
                name = "Current source"
            else:
                name = f"Intermediate source ({version})"
            cohorts[version] = sources.setdefault(source, name)
    manifest["source_cohort"] = manifest["code_version"].map(cohorts)

    # One complete run per machine and revision. Do not mix replicate groups.
    exact = manifest[manifest["complete"]].drop_duplicates(["machine_id", "code_version"], keep="last")
    cohort = exact.drop_duplicates(["machine_id", "source_cohort"], keep="last")
    keys = SESSION + CONFIG
    timings = timing_summary(core[core["session_id"].isin(exact["session_id"])], keys)
    exact_timings = timings.merge(
        exact[["session_id", "source_cohort", "python_version", "hash_seed"]],
        on="session_id",
    )
    rank_keys = ["session_id", "key_column", "n_keys", "operation", "operation_param", "n_ops"]
    exact_timings["rank"] = exact_timings.groupby(rank_keys)["median_ns"].rank(method="min")
    cohort_timings = exact_timings[exact_timings["session_id"].isin(cohort["session_id"])].copy()
    return core, manifest, exact, cohort, exact_timings, cohort_timings


def core_ratios(timings, group="source_cohort"):
    """Fastest/slowest ratios at a fixed workload, only when 2+ machines exist."""
    records = []
    for _, data in timings.groupby([group, *CONFIG]):
        if data["machine_id"].nunique() < 2:
            continue
        fastest, slowest = data.loc[data["median_ns"].idxmin()], data.loc[data["median_ns"].idxmax()]
        records.append({
            **{key: fastest[key] for key in [group, *CONFIG]},
            "machines": data["machine_id"].nunique(),
            "fastest": fastest["machine_id"], "fastest_ns": fastest["median_ns"],
            "slowest": slowest["machine_id"], "slowest_ns": slowest["median_ns"],
            "slowest_over_fastest": slowest["median_ns"] / fastest["median_ns"],
        })
    return pd.DataFrame(records)


def counter_audit(core, manifest, group):
    """Check between- and within-machine repeatability for each counted workload."""
    selection = manifest[["session_id", "source_cohort"]]
    samples = core[core["comparisons"].notna()].merge(selection, on="session_id")
    columns = [group, *CONFIG, "counter", "machines", "distinct_values", "values_by_machine"]
    records = []
    for config, data in samples.groupby([group, *CONFIG]):
        for counter in COUNTERS:
            values = data.groupby("machine_id")[counter].apply(lambda x: sorted(set(x.dropna())))
            records.append([*config, counter, len(values), data[counter].nunique(),
                            "; ".join(f"{m}={v}" for m, v in values.items())])
    return pd.DataFrame(records, columns=columns)


def core_change(core, timings):
    """Pair original and current runs on the same machine and runtime."""
    columns = [*SESSION, *CONFIG, "python_version", "pythonhashseed", *COUNTERS, "ns_per_op"]
    data = core[columns].merge(timings[["session_id", "source_cohort"]].drop_duplicates(),
                               on="session_id")
    runtime = ["python_version", "pythonhashseed"]
    for counter in COUNTERS:
        data[f"{counter}_per_op"] = data[counter] / data["n_ops"]
    keys = ["source_cohort", *SESSION, *CONFIG, *runtime]
    metrics = data.groupby(keys, as_index=False).agg(
        median_ns=("ns_per_op", "median"),
        q1_ns=("ns_per_op", lambda x: x.quantile(0.25)),
        q3_ns=("ns_per_op", lambda x: x.quantile(0.75)),
        comparisons_per_op=("comparisons_per_op", "median"),
        nodes_visited_per_op=("nodes_visited_per_op", "median"),
    )
    original = metrics[metrics["source_cohort"].eq("Original source")].drop(columns="source_cohort")
    current = metrics[metrics["source_cohort"].eq("Current source")].drop(columns="source_cohort")
    paired = original.merge(current, on=["machine_id", *CONFIG, *runtime],
                            suffixes=("_original", "_current"))
    paired["speedup"] = paired["median_ns_original"] / paired["median_ns_current"]
    return paired


def e1_memory(rows, machines, session_id=None):
    """Incremental Python allocations and a linear full-budget extrapolation."""
    e1 = rows[rows["experiment"].eq("E1_build_memory") & rows["memory_bytes"].gt(0)]
    expected = {(idx, "order=32" if idx == "bplus_tree" else "", "track_id", n, "build", "", n)
                for idx in INDEXES for n in SIZES}
    sessions = session_manifest(e1, expected)
    selected = sessions[sessions["complete"]]
    if session_id is not None:
        selected = selected[selected["session_id"].eq(session_id)]
        if selected.empty:
            raise ValueError(f"{session_id} is not a complete E1 memory session")
    selected = selected.tail(1)
    memory = e1[e1["session_id"].isin(selected["session_id"])]
    by_size = memory.groupby([*SESSION, "index_type", "n_keys"], as_index=False).agg(
        memory_bytes=("memory_bytes", "median")
    )
    by_size["memory_mib"] = by_size["memory_bytes"] / 1024**2
    full = by_size[by_size["n_keys"].eq(114000)].copy()
    full["bytes_per_row"] = full["memory_bytes"] / full["n_keys"]
    budget = machines[["machine_id", "ram_gb", "docker_memory_gb"]].rename(
        columns={"machine_id": "comparison_machine"}
    )
    estimates = full.merge(budget, how="cross")
    estimates["docker_budget_pct"] = (
        100 * estimates["memory_bytes"] / (estimates["docker_memory_gb"] * 1024**3)
    )
    estimates["rows_at_full_budget"] = (
        estimates["docker_memory_gb"] * 1024**3 / estimates["bytes_per_row"]
    ).round()
    return sessions, selected, by_size, estimates


def workload_label(rows):
    """Readable CORE column labels, retaining both build sizes."""
    return rows["operation"].map({
        "build": "Build", "point_hit": "Point hit", "point_miss": "Point miss",
        "range": "Tempo range", "prefix": "Title prefix",
    }) + rows["n_keys"].map(lambda n: f" · {n:,} rows").where(rows["operation"].eq("build"), "")
