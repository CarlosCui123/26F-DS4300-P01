"""Synthetic keys and query workloads.  *** YOU IMPLEMENT THIS FILE. ***

Real data (Spotify) shows how the indexes behave on realistic keys.
Synthetic data lets you control one variable at a time: how many keys, what
order they arrive in, how many lookups hit vs miss, how wide a range is.

Rules for every function:

* Use ``rng = random.Random(seed)`` and draw all randomness from ``rng``, so
  the same seed always produces the same output (on any machine).
* Never modify the list you are given; return a new one.

``tests/test_synthetic.py`` checks each function against this spec. Run it
with ``make test``.
"""

from __future__ import annotations

import random
import string
from typing import Any, Optional, Sequence


def random_keys(
    n: int,
    length: int = 8,
    alphabet: str = string.ascii_lowercase,
    seed: Optional[int] = None,
) -> list[str]:
    """Return ``n`` *distinct* random strings, each exactly ``length`` characters
    long, using only characters from ``alphabet``, in random order.

    Raise ``ValueError`` if ``n`` is larger than the number of possible
    strings (``len(alphabet) ** length``).
    """
    rng = random.Random(seed)
    alphabet = ''.join(dict.fromkeys(alphabet))
    if n < 0 or length < 0 or n > len(alphabet) ** length:
        raise ValueError('Cannot generate the requested number of distinct keys.')

    result = []
    seen = set()
    while len(result) < n:
        key = ''.join(rng.choices(alphabet, k=length))
        if key not in seen:
            seen.add(key)
            result.append(key)
    return result


def arrange(
    keys: Sequence[Any],
    order: str,
    seed: Optional[int] = None,
    swap_fraction: float = 0.05,
) -> list[Any]:
    """Return a new list holding the same keys in the requested order.

    order:
        "random"        shuffled
        "sorted"        ascending
        "reversed"      descending
        "nearly_sorted" ascending, then ``round(swap_fraction * len(keys))``
                        swaps of two randomly chosen positions

    Raise ``ValueError`` for any other ``order``.
    """
    rng = random.Random(seed)
    result = list(keys)

    if order == 'random':
        rng.shuffle(result)
    elif order in ('sorted', 'reversed', 'nearly_sorted'):
        result.sort(reverse=(order == 'reversed'))
        if order == 'nearly_sorted' and len(result) > 1:
            for _ in range(round(swap_fraction * len(result))):
                i, j = rng.sample(range(len(result)), 2)
                result[i], result[j] = result[j], result[i]
    else:
        raise ValueError(f'Unknown order: {order!r}')

    return result


def point_queries(
    keys: Sequence[str],
    n_queries: int,
    hit_rate: float,
    seed: Optional[int] = None,
) -> list[str]:
    """Return ``n_queries`` lookup keys in random order.

    Exactly ``round(n_queries * hit_rate)`` of them are *hits*: chosen at
    random (repeats allowed) from ``keys``. The rest are *misses*: random
    strings that are guaranteed NOT to be in ``keys``, each the same length as
    a randomly chosen key from ``keys``.
    """
    rng = random.Random(seed)
    key_set = set(keys)
    queries = [rng.choice(keys) for _ in range(round(n_queries * hit_rate))]
    lengths = [len(key) for key in keys if key]

    if len(queries) < n_queries and not lengths:
        raise ValueError('Cannot generate misses using only empty keys.')
    alphabet = string.ascii_letters + string.digits

    if lengths and len(alphabet) ** min(lengths) <= len(key_set):
        alphabet = ''.join(chr(i) for i in range(len(key_set) + 1))

    while len(queries) < n_queries:
        query = ''.join(rng.choices(alphabet, k=rng.choice(lengths)))
        if query not in key_set:
            queries.append(query)

    rng.shuffle(queries)
    return queries


def range_queries(
    keys: Sequence[Any],
    n_queries: int,
    selectivity: float,
    seed: Optional[int] = None,
) -> list[tuple[Any, Any]]:
    """Return ``n_queries`` ranges ``(lo, hi)`` for ``index.range_search(lo, hi)``.

    Let ``d`` be the number of *distinct* keys and ``w = max(1, round(selectivity * d))``.
    Sort the distinct keys, pick a random starting position that leaves room
    for ``w`` keys, and use the key there as ``lo`` and the key ``w - 1``
    positions later as ``hi``. So exactly ``w`` distinct keys satisfy
    ``lo <= key <= hi``. Works for any comparable keys (strings or numbers).
    """
    rng = random.Random(seed)
    if n_queries < 0 or not 0 <= selectivity <= 1:
        raise ValueError('Invalid query count or selectivity.')

    distinct = sorted(set(keys))
    if n_queries > 0 and not distinct:
        raise ValueError('Cannot generate ranges without keys.')

    width = max(1, round(selectivity * len(distinct)))
    queries = []
    for _ in range(n_queries):
        start = rng.randrange(len(distinct) - width + 1)
        lo = distinct[start]
        hi = distinct[start + width - 1]
        queries.append((lo, hi))
    return queries


def prefix_queries(
    keys: Sequence[str],
    n_queries: int,
    prefix_length: int,
    seed: Optional[int] = None,
) -> list[str]:
    """Return ``n_queries`` prefixes for ``index.prefix_search(prefix)``.

    Each prefix is the first ``prefix_length`` characters of a randomly chosen
    key that is at least ``prefix_length`` characters long, so every prefix
    matches at least one key.
    """
    rng = random.Random(seed)
    if n_queries < 0 or prefix_length < 0:
        raise ValueError('Query count and prefix length must be non-negative.')

    eligible = [key for key in keys if len(key) >= prefix_length]
    if n_queries > 0 and not eligible:
        raise ValueError('No key is long enough for the requested prefix.')

    return [rng.choice(eligible)[:prefix_length] for _ in range(n_queries)]
