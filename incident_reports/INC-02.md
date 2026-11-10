# INC-02: Hash table build cost grows with n

## Summary

Building the hash table was much slower than it should be. With 114,000 keys, the build took about 1,922 ms, and the time per key kept growing as n grew. The cause was in `_grow`: the table added only 1,024 buckets each time it was full, so it had to resize and move all keys 117 times. After we changed it to double the number of buckets, the same build took about 72 ms (about 27 times faster) on the same machine, and the table resized only 14 times.

## Detection

We first saw the problem in the original CORE run (session `266eb953266a`, `code_version=03d990e`, machine `cimy-mbp`). The hash table took 29.8 s for the whole suite, which was slower than the unsorted list (24.4 s). This was strange, because a hash table should be one of the fastest indexes. We then looked at the build rows in E1 (`E1_build_memory`): the hash table was faster than the AVL tree at small n, but it became slower than the AVL tree at about 50,000 keys and was the slowest index at 114,000 keys (see the build figure below). The `resizes` counter was also very high.

## Expected vs. observed

A hash table should insert one key in O(1) time on average. If the table doubles its buckets when it is full, it only needs about log2(n) resizes, and the total build cost is O(n). So the time per key should stay about the same as n grows, and the log-log slope of build time vs. n should be about 1.

What we measured before the fix (`E1_build_memory`, `code_version=03d990e`):

- Time per key grew from 0.64 µs at n = 1,000 to 17.4 µs at n = 114,000 (27 times higher).
- `resizes` grew from 2 at n = 1,000 to 117 at n = 114,000. This grows linearly with n, not like log2(n).
- The log-log slope of build time vs. n was 1.73 in E1 and 2.03–2.09 in CORE. This is close to 2, which means the build is about O(n²).

## Evidence

All numbers come from `results/timings.csv`. They are produced by `analysis/evidence_hash_avl.py` (run with `docker compose run --rm app python analysis/evidence_hash_avl.py`).

Before the fix, `E1_build_memory`, `code_version=03d990e`, median of 5 reps:

| n | median build (ms) | µs per key | resizes |
|---|---|---|---|
| 1,000 | 0.64 | 0.64 | 2 |
| 10,000 | 16.5 | 1.65 | 13 |
| 50,000 | 393.0 | 7.86 | 58 |
| 114,000 | 1,980.0 | 17.37 | 117 |

The `resizes` counter is the same on every machine and every run: CORE gives 13 resizes at n = 10,000 and 117 at n = 114,000 for all three code versions we have before the fix (`03d990e`, `0d49e62`, `f5dfa0b`). So this is not noise. E5 shows the same pattern for all four insert orders (131 resizes at n = 100,000).

Figure: `analysis/figures_INC02_03/build_time_loglog.png` (E1 build time on a log-log scale; the hash table line is much steeper than `ref_dict`).

## Root cause

File: `indexes/hash_table.py` (line numbers from the original code, `03d990e`).

- Line 31: `GROWTH_STEP = 1024`
- Line 60, in `_grow`: `new_capacity = len(self._buckets) + self.GROWTH_STEP`

`insert` calls `_grow` when the table has more than 0.75 keys per bucket (lines 55–56). `_grow` makes a new bucket list and moves every key into it (lines 61–64). Because the table only gets 1,024 more buckets each time, it becomes full again after about 768 more keys. So the number of resizes grows linearly with n, and each resize moves all keys that are already there. In total this is about n² / 1,500 key moves.

The answers are still correct, because every key is still moved to the right bucket. Only the time is wrong.

## Fix

Commit `aeccc40`: the table now doubles its buckets when it grows. (The commit message says "INC-03" because we renumbered the reports after the commit was made.)

```diff
--- a/indexes/hash_table.py
+++ b/indexes/hash_table.py
@@ -28,7 +28,7 @@ class HashTableIndex(Index):
     INITIAL_CAPACITY = 8
     MAX_LOAD_FACTOR = 0.75   # average keys per bucket before the table grows
-    GROWTH_STEP = 1024       # buckets added each time the table grows
+    GROWTH_FACTOR = 2        # the table doubles its buckets each time it grows
 
@@ -57,7 +57,7 @@ class HashTableIndex(Index):
         """Move every entry into a larger list of buckets."""
-        new_capacity = len(self._buckets) + self.GROWTH_STEP
+        new_capacity = len(self._buckets) * self.GROWTH_FACTOR
```

With doubling, each resize moves twice as many keys as the one before, so all resizes together move fewer than 2n keys. The build is O(n), and each insert is O(1) on average.

## Verification

Same machine (`cimy-mbp`), same CORE workload, before (session `266eb953266a`, `code_version=03d990e`) and after (session `e90ee4333937`, `code_version=c735d0c`):

| n | build before (ms) | build after (ms) | resizes before | resizes after |
|---|---|---|---|---|
| 10,000 | 12.7 | 5.4 | 13 | 11 |
| 114,000 | 1,922.1 | 71.9 | 117 | 14 |

The log-log slope in CORE went from 2.06 to 1.06.

E1 after the fix (session `5e84c32c58a5`, `code_version=c735d0c`): time per key stays between 0.47 and 0.62 µs from n = 1,000 to n = 114,000, the slope is 1.01, and `resizes` grows from 8 to 14, about log2(n). (The E1 before-fix rows were run on a different machine, so we compare the counters and the slope here, not the raw times.)

`make test` passes after the fix (168 passed, 3 skipped).

## Impact on recommendations

Yes. Before the fix, the hash table looked like the worst choice for building the index on the full data (F4, nightly import), and much slower than the trees. This could have made us not recommend it for F1 (open one track by `track_id`), even though its lookups were fast. After the fix, the hash table builds 114,000 keys in about 72 ms, which is faster than the AVL tree on the same machine. So it is now a strong choice for F1, and its build cost is no longer a reason against it for F4. It is still not useful for F2 and F3 (prefix and range queries), because it must check every key for those.

## Why the tests didn't catch it

The tests only check that the answers are correct. They do not check how much work the index does, and this bug never gives a wrong answer. A test that would catch it: insert 50,000 keys into a new hash table and check that `stats.resizes` is at most `log2(50,000) + 2` (about 17). With the bug, the table resizes 58 times, so the test fails. With doubling, it resizes about 13 times, so the test passes. A similar test could check that the build time per key does not grow much between n = 10,000 and n = 100,000.