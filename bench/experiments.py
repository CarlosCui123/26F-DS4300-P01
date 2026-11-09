"""Your experiments.  *** YOU EXTEND THIS FILE. ***

Run one experiment, or all of them:

    make experiments MEMBER=alice MACHINE=alice-mbp                 # all
    make experiments MEMBER=alice MACHINE=alice-mbp ONLY=example     # one

``example_point_lookups`` below is the summer 2024 interns' one finished experiment, and it works. Copy its
pattern for each experiment the README asks for (E1-E6), and register each
new function in ``EXPERIMENTS`` at the bottom of this file.

The pattern, for every configuration you measure:
    1. prepare keys and queries OUTSIDE the timed region,
    2. build a fresh index (time it with ``time_build`` if build cost matters),
    3. ``index.reset_stats()``, then time one batch with ``time_batch``,
    4. ``writer.record(index, ...)`` one row,
    5. repeat for ``reps`` replicates.
"""

from __future__ import annotations

import random
import time
from typing import Callable, Optional, Sequence

from bench.cli import parse, parser, writer_from_args
from bench.results import ResultsWriter
from bench.timing import build_memory_bytes, time_batch, time_build
# added for E1 nd E5
from datagen.synthetic import arrange, point_queries, prefix_queries, random_keys, range_queries
from indexes import ALL_INDEXES, make_index
from loaders.spotify import key_value_pairs, load_tracks

SEED = 4300

# E1: Analyze the first n records using Spotify data, and compare the establishment times
# and memory usage for six different scales.
SPOTIFY_SIZES = (1000, 5000, 10000, 25000, 50000, 114000)

# E5: Use non-repeating synthetic keys and compare the three data sizes.
SYNTHETIC_SIZES = (1000, 10000, 100000)

# E5: Random input order, ascending order, descending order, and input order
# with a few exchanges after ascending order.
SYNTHETIC_ORDERS = ('random', 'sorted', 'reversed', 'nearly_sorted')

# For each batch, 1,000 queries are precisely conducted; the number of repeated measurements
# is controlled separately by the --reps option.
N_POINT = 1000

def example_point_lookups(writer: ResultsWriter, tracks: list[dict], reps: int) -> None:
    """Build cost and point-lookup (hit) cost on track_id as the index grows."""
    pairs = key_value_pairs(tracks, "track_id")  # file order
    rng = random.Random(SEED)

    for n in (1_000, 10_000, len(pairs)):
        subset = pairs[:n]
        queries = [key for key, _ in rng.sample(subset, 500)]  # every query is a hit

        for name in ALL_INDEXES:
            # Memory once per configuration (tracing is slow; never time it).
            memory = build_memory_bytes(lambda: make_index(name), subset)

            for rep in range(reps):
                common = dict(
                    experiment="example", dataset="spotify", key_column="track_id",
                    insert_order="file", n_keys=n, rep=rep,
                )

                index = make_index(name)
                ns = time_build(index, subset)
                writer.record(
                    index, **common, operation="build", operation_param="",
                    n_ops=n, total_ns=ns, memory_bytes=memory,
                )

                index.reset_stats()
                ns = time_batch(index.search, queries)
                writer.record(
                    index, **common, operation="point_hit", operation_param=1.0,
                    n_ops=len(queries), total_ns=ns,
                    height=index.structure_info().get("height", ""),
                )
            print(f"  n={n:>7,}  {name:<14} done", flush=True)

def e1_build_memory(writer: ResultsWriter, tracks: list[dict], reps: int) -> None:
    '''
    E1：Compare the index establishment time and memory usage under different data scales of Spotify.

    Insert "track_id" in the original order of the file, and test six data scales and all indexes.
    Measure the memory and build time separately to avoid the impact of memory tracking on the timing.

    Args:
        writer: The results are written to the object, and each measurement is appended to the results CSV.
        tracks: The list of song records read from Spotify CSV, each record is a dictionary.
        reps: The repeated timing times for each data scale and each type of index.

    Returns:
        None. The measurement results are written to CSV through the writer.
    '''
    # Prepare the data before timing, preserving the original order in the CSV.
    pairs = key_value_pairs(tracks, 'track_id')
    if len(pairs) < max(SPOTIFY_SIZES):
        raise ValueError('E1 needs 114,000 track_id pairs from the full dataset.')

    for n in SPOTIFY_SIZES:
        subset = pairs[:n]

        for name in ALL_INDEXES:
            # Measure memory separately for each index and each scale.
            # Memory tracing will slow down the program, so it is carried out separately from the formal timing.
            memory = build_memory_bytes(lambda: make_index(name), subset)

            for rep in range(reps):
                # Each repeated measurement uses a brand-new empty index.
                index = make_index(name)
                index.reset_stats()

                # only time the process of inserting this batch of data.
                ns = time_build(index, subset)

                # One timing is written in one line; the index name and counter are automatically
                # filled in by the writer.
                writer.record(
                    index, experiment='E1_build_memory', dataset='spotify',
                    key_column='track_id', insert_order='file', n_keys=n,
                    operation='build', operation_param='', n_ops=n, rep=rep,
                    total_ns=ns, memory_bytes=memory,
                    height=index.structure_info().get('height', ''),
                    notes='memory measured once per configuration, separately from timing',
                )

            # Once all the repeated measurements within the current scale have been completed,
            # this index will display the progress.
            print(f'  n={n:>7,}  {name:<14} done', flush=True)

def e5_insert_order(writer: ResultsWriter, tracks: list[dict], reps: int) -> None:
    '''
    E5：Compare the impact of input sequence on the performance of index establishment and precise search.

    Use three dataset sizes of distinct synthetic keys and compare four insertion orders.
    Record the establishment time, hit search time, tree height, and operation counters.

    Args:
        writer: The results are written to the object, and each measurement is appended to the results CSV.
        tracks: To maintain a unified experimental interface, synthetic data is used in this experiment.
        reps: The repeated timing counts for each scale, each sequence, and each index.

    Returns:
        None. The measurement results are written to CSV through the writer.
    '''
    # Generate the largest number of different keys at once,
    # and then select the first n of them for each scale.
    all_keys = random_keys(max(SYNTHETIC_SIZES), length=8, seed=SEED)

    for n in SYNTHETIC_SIZES:
        keys = all_keys[:n]

        # Fix the correspondence between the key and the row_id,
        # so that the experiment only changes the insertion order.
        row_ids = {key: row_id for row_id, key in enumerate(keys)}

        # Generate all the matching queries before timing;
        # use the same batch of queries for each sequence and each index.
        queries = point_queries(keys, N_POINT, hit_rate=1.0, seed=SEED + 1)

        for order in SYNTHETIC_ORDERS:
            # Using the same key set, four different input sequences are generated respectively.
            ordered_keys = arrange(keys, order, seed=SEED + 2, swap_fraction=0.05)
            pairs = [(key, row_ids[key]) for key in ordered_keys]

            for name in ALL_INDEXES:
                for rep in range(reps):
                    # Establish and search for the common experimental information used for records.
                    common = dict(
                        experiment='E5_insert_order', dataset='synthetic',
                        key_column='random_string', insert_order=order,
                        n_keys=n, rep=rep,
                        notes=(f'keys_seed={SEED}; query_seed={SEED + 1}; '
                               f'order_seed={SEED + 2}; length=8; swap_fraction=0.05'),
                    )

                    # Each time the index is recreated and the establishment time
                    # of the entire batch of data is measured.
                    index = make_index(name)
                    index.reset_stats()
                    ns = time_build(index, pairs)

                    # After the timing is completed, read the tree height;
                    # leave the index blank if there is no tree height indicator.
                    height = index.structure_info().get('height', '')

                    # Firstly, record the establishment results and retain the counts of rotations,
                    # splits, etc. that were present during the establishment process.
                    writer.record(
                        index, **common, operation='build', operation_param='',
                        n_ops=n, total_ns=ns, height=height,
                    )

                    # Look for the previous zero-reset counter to avoid including
                    # the workload of the recent index establishment.
                    index.reset_stats()
                    ns = time_batch(index.search, queries)

                    # Record the time consumption and count of all hits for this batch of queries.
                    writer.record(
                        index, **common, operation='point_hit', operation_param=1.0,
                        n_ops=len(queries), total_ns=ns, height=height,
                    )

                print(f'  n={n:>7,}  {order:<14}  {name:<14} done', flush=True)

def e2_point_lookups(writer: ResultsWriter, tracks: list[dict], reps: int) -> None:
    '''
    E2: How does point-lookup cost grow with n, for hits and for misses?

    Uses track_id in file order at the same six sizes as E1 (SPOTIFY_SIZES).
    For each size, one batch of N_POINT hit queries (hit_rate=1.0) and one
    batch of N_POINT miss queries (hit_rate=0.0) is generated before timing.
    Each index is built once per (size, index); every replicate then times
    both batches on that index.

    Args:
        writer: Results writer; each timed batch becomes one CSV row.
        tracks: Spotify rows from load_tracks().
        reps: Number of timed replicates per configuration.
    '''
    pairs = key_value_pairs(tracks, 'track_id')

    for n in SPOTIFY_SIZES:
        subset = pairs[:n]
        # track_id is not unique, so queries are drawn from the distinct ids.
        distinct = list(dict.fromkeys(key for key, _ in subset))
        batches = {
            'point_hit': (1.0, point_queries(distinct, N_POINT, hit_rate=1.0, seed=SEED + 10)),
            'point_miss': (0.0, point_queries(distinct, N_POINT, hit_rate=0.0, seed=SEED + 11)),
        }

        for name in ALL_INDEXES:
            # Build is not the subject of E2 (E1 measures it), so build once.
            index = make_index(name)
            time_build(index, subset)
            height = index.structure_info().get('height', '')

            for rep in range(reps):
                for operation, (hit_rate, queries) in batches.items():
                    index.reset_stats()
                    ns = time_batch(index.search, queries)
                    writer.record(
                        index, experiment='E2_point_track_id', dataset='spotify',
                        key_column='track_id', insert_order='file', n_keys=n,
                        operation=operation, operation_param=hit_rate,
                        n_ops=len(queries), rep=rep, total_ns=ns, height=height,
                        notes=f'distinct_keys={len(distinct)}; hit_seed={SEED + 10}; miss_seed={SEED + 11}',
                    )
            print(f'  n={n:>7,} {name:<14} done', flush=True)

# E3: range-query widths, as fractions of the distinct tempo values.
SELECTIVITIES = (0.0001, 0.001, 0.01, 0.05, 0.1, 0.25)
# Range queries per batch (the same number the CORE suite uses).
N_RANGE = 200


def e3_range_tempo(writer: ResultsWriter, tracks: list[dict], reps: int) -> None:
    '''
    E3: How does range-query cost depend on how much of the data the range covers?

    Uses tempo for all 114,000 rows, in file order. For each selectivity, one
    batch of N_RANGE ranges is generated before timing; each range covers
    exactly w = round(selectivity * d) distinct tempo values (d = distinct count).
    Each index is built once; every replicate then times every batch on it.

    Args:
        writer: Results writer; each timed batch becomes one CSV row.
        tracks: Spotify rows from load_tracks().
        reps: Number of timed replicates per configuration.
    '''
    pairs = key_value_pairs(tracks, 'tempo')
    keys = [key for key, _ in pairs]
    distinct_count = len(set(keys))

    # Generate every batch of ranges before any timing starts.
    batches = {
        selectivity: range_queries(keys, N_RANGE, selectivity, seed=SEED + 20)
        for selectivity in SELECTIVITIES
    }

    for name in ALL_INDEXES:
        # Build is not the subject of E3 (E1 measures it), so build once.
        index = make_index(name)
        time_build(index, pairs)
        height = index.structure_info().get('height', '')

        for selectivity, queries in batches.items():
            width = max(1, round(selectivity * distinct_count))
            for rep in range(reps):
                index.reset_stats()
                ns = time_batch(lambda q: index.range_search(*q), queries)
                writer.record(
                    index, experiment='E3_range_tempo', dataset='spotify',
                    key_column='tempo', insert_order='file', n_keys=len(pairs),
                    operation='range', operation_param=selectivity,
                    n_ops=len(queries), rep=rep, total_ns=ns, height=height,
                    notes=f'distinct_keys={distinct_count}; width={width}; seed={SEED + 20}',
                )
        print(f'  {name:<14} done', flush=True)

# E4: prefix lengths to test (how many characters the user has typed).
PREFIX_LENGTHS = (1, 2, 3, 4, 5)


def e4_prefix_track_name(writer: ResultsWriter, tracks: list[dict], reps: int) -> None:
    '''
    E4: How does prefix-search cost depend on prefix length?

    Uses track_name (lower-cased and trimmed by the loader) for every row
    that has a name, in file order. For each prefix length, one batch of
    N_RANGE prefixes is generated before timing; every prefix is the start
    of a real title, so it matches at least one key.
    Each index is built once; every replicate then times every batch on it.

    Args:
        writer: Results writer; each timed batch becomes one CSV row.
        tracks: Spotify rows from load_tracks().
        reps: Number of timed replicates per configuration.
    '''
    pairs = key_value_pairs(tracks, 'track_name')
    keys = [key for key, _ in pairs]
    distinct_count = len(set(keys))

    # Generate every batch of prefixes before any timing starts.
    batches = {
        length: prefix_queries(keys, N_RANGE, length, seed=SEED + 30)
        for length in PREFIX_LENGTHS
    }

    for name in ALL_INDEXES:
        # Build is not the subject of E4 (E1 measures it), so build once.
        index = make_index(name)
        time_build(index, pairs)
        height = index.structure_info().get('height', '')

        for length, queries in batches.items():
            for rep in range(reps):
                index.reset_stats()
                ns = time_batch(index.prefix_search, queries)
                writer.record(
                    index, experiment='E4_prefix_track_name', dataset='spotify',
                    key_column='track_name', insert_order='file', n_keys=len(pairs),
                    operation='prefix', operation_param=length,
                    n_ops=len(queries), rep=rep, total_ns=ns, height=height,
                    notes=f'distinct_keys={distinct_count}; seed={SEED + 30}',
                )
        print(f'  {name:<14} done', flush=True)

BPLUS_ORDERS = (3, 4, 8, 16, 32, 64, 128, 256, 512)


def e6_bplus_order(writer: ResultsWriter, tracks: list[dict], reps: int) -> None:
    """Sweep B+ tree order on track ID builds and lookups and on tempo ranges."""
    id_pairs = key_value_pairs(tracks, 'track_id')
    tempo_pairs = key_value_pairs(tracks, 'tempo')
    if min(len(id_pairs), len(tempo_pairs)) < max(SPOTIFY_SIZES):
        raise ValueError('E6 needs all 114,000 Spotify track_id and tempo pairs.')

    for n in SPOTIFY_SIZES:
        subset = id_pairs[:n]
        # Match E2: draw from the distinct IDs in their first appearance order.
        distinct_ids = list(dict.fromkeys(key for key, _ in subset))
        hits = point_queries(distinct_ids, N_POINT, hit_rate=1.0, seed=SEED + 10)
        misses = point_queries(distinct_ids, N_POINT, hit_rate=0.0, seed=SEED + 11)
        batches = (('point_hit', 1.0, hits), ('point_miss', 0.0, misses))

        for order in BPLUS_ORDERS:
            for rep in range(reps):
                common = dict(
                    experiment='E6_bplus_order', dataset='spotify', key_column='track_id',
                    insert_order='file', n_keys=n, rep=rep,
                )
                index = make_index('bplus_tree', order=order)
                index.reset_stats()
                ns = time_build(index, subset)
                height = index.structure_info()['height']
                writer.record(
                    index, **common, operation='build', operation_param='',
                    n_ops=n, total_ns=ns, height=height,
                    notes=f'distinct_keys={len(distinct_ids)}',
                )

                for operation, hit_rate, queries in batches:
                    index.reset_stats()
                    ns = time_batch(index.search, queries)
                    writer.record(
                        index, **common, operation=operation, operation_param=hit_rate,
                        n_ops=len(queries), total_ns=ns, height=height,
                        notes=(f'distinct_keys={len(distinct_ids)}; '
                               f'hit_seed={SEED + 10}; miss_seed={SEED + 11}'),
                    )
            print(f'  n={n:>7,} order={order:<3} build and point done', flush=True)

    # Match the 1% batch from E3, including its full tempo input and seed.
    selectivity = 0.01
    tempos = [key for key, _ in tempo_pairs]
    queries = range_queries(tempos, N_RANGE, selectivity, seed=SEED + 20)
    distinct_count = len(set(tempos))
    width = max(1, round(selectivity * distinct_count))
    for order in BPLUS_ORDERS:
        index = make_index('bplus_tree', order=order)
        for key, row_id in tempo_pairs:
            index.insert(key, row_id)
        height = index.structure_info()['height']

        for rep in range(reps):
            index.reset_stats()
            ns = time_batch(lambda q: index.range_search(*q), queries)
            writer.record(
                index, experiment='E6_bplus_order', dataset='spotify',
                key_column='tempo', insert_order='file', n_keys=len(tempo_pairs),
                operation='range', operation_param=selectivity, n_ops=len(queries),
                rep=rep, total_ns=ns, height=height,
                notes=f'distinct_keys={distinct_count}; width={width}; seed={SEED + 20}',
            )
        print(f'  order={order:<3} tempo range done', flush=True)


# Register experiments here: name -> function(writer, tracks, reps).
EXPERIMENTS: dict[str, Callable[[ResultsWriter, list[dict], int], None]] = {
    "example": example_point_lookups,
    ## The command-line entry point for registering E1.
    'E1_build_memory': e1_build_memory,
    # The command-line entry point for registering E5.
    'E5_insert_order': e5_insert_order,
    'E2_point_track_id': e2_point_lookups,
    'E3_range_tempo': e3_range_tempo,
    'E4_prefix_track_name': e4_prefix_track_name,
    'E6_bplus_order': e6_bplus_order,
}


def main(argv: Optional[Sequence[str]] = None) -> None:
    p = parser("Run your experiments.")
    p.add_argument("--only", choices=sorted(EXPERIMENTS), help="run just this experiment")
    args = parse(p, argv)
    writer = writer_from_args(args)
    tracks = load_tracks()
    names = [args.only] if args.only else list(EXPERIMENTS)
    for name in names:
        print(f"{name}: {args.reps} reps, session {writer.session_id}", flush=True)
        started = time.perf_counter()
        EXPERIMENTS[name](writer, tracks, args.reps)
        print(f"{name}: finished in {time.perf_counter() - started:.1f}s", flush=True)


if __name__ == "__main__":
    main()
