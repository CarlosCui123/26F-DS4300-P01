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
from datagen.synthetic import arrange, point_queries, random_keys

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

# Register experiments here: name -> function(writer, tracks, reps).
EXPERIMENTS: dict[str, Callable[[ResultsWriter, list[dict], int], None]] = {
    "example": example_point_lookups,
    ## The command-line entry point for registering E1.
    'E1_build_memory': e1_build_memory,
    # The command-line entry point for registering E5.
    'E5_insert_order': e5_insert_order,
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
