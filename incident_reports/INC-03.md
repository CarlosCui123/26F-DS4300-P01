# INC-03: AVL tree does too many rotations because stored heights are wrong

## Summary

The AVL tree did about 10 to 15 rotations for every inserted key, and the number kept growing with n. A correct AVL tree needs less than about 1 rotation per key. The cause was in the two rotation functions: they updated the new parent's height before the new child's height, so the parent used an old height. After we changed the order, the tree does about 0.55 to 1.0 rotations per key, the tree height is back under the AVL limit, and building 114,000 keys is about 1.8 times faster on the same machine.

## Detection

While answering Part A Q3 (insert 10, 20, 30), we ran the example on the original code. The tree had the correct shape (20 at the root, 10 and 30 as children), but node 20 stored height 4, not 2. Then we looked at the `rotations` counter in E1 and E5. For 114,000 keys, the original code did 1,476,511 rotations, about 13 per key. This was far too many, so we looked at the rotation code.

## Expected vs. observed

An AVL tree keeps the heights of the two children of every node within 1 of each other. Theory says:

- The tree height is less than about 1.44 · log2(n + 2).
- Insert is O(log n), and the number of rotations per insert is O(1). In practice it is less than 1 for random keys and about 1 for sorted keys.

What we measured before the fix:

- Rotations per key grew from 6.4 at n = 1,000 to 13.0 at n = 114,000 (`E1_build_memory`, `code_version=03d990e`). It grows with n instead of staying constant.
- The tree height was higher than the AVL limit. In E5 with random order and n = 100,000, the height was 26, but the limit is 23.9. In E1 at n = 25,000 the height was 22, and the limit is 21.0. So the tree was not really balanced.

## Evidence

All numbers come from `results/timings.csv` and are produced by `analysis/evidence_hash_avl.py`.

Before the fix, `E1_build_memory`, `code_version=03d990e`, median of 5 reps:

| n | rotations | rotations per key | height | AVL height limit |
|---|---|---|---|---|
| 1,000 | 6,380 | 6.38 | 14 | 14.4 |
| 10,000 | 95,917 | 9.59 | 19 | 19.1 |
| 25,000 | 286,839 | 11.47 | 22 | 21.0 |
| 114,000 | 1,476,511 | 12.95 | 23 | 24.2 |

The problem happens with every insert order. In E5 (`code_version=03d990e` and `870c3a9`) at n = 100,000, rotations per key were 14.6 (random), 10.3 (nearly sorted) and 11.4 (sorted and reversed). The counters are exactly the same in all CORE runs before the fix (`03d990e`, `0d49e62`, `f5dfa0b`): 95,917 rotations at n = 10,000 and 1,476,511 at n = 114,000.

Figure: `analysis/figures_INC02_03/avl_rotations_per_key.png` (rotations per key vs. n for each code version and insert order).

## Root cause

File: `indexes/avl_tree.py` (line numbers from the original code, `03d990e`).

- `_rotate_right`, lines 62–63: `_update_height(x)` then `_update_height(y)`
- `_rotate_left`, lines 80–81: `_update_height(y)` then `_update_height(x)`

A node's height is 1 + the height of its taller child. After a rotation, the old parent becomes a child of the new parent. So the code must update the child first, and then the new parent. The original code does it the other way around. The new parent is computed from the child's old height, which is too big. For example, after inserting 10, 20, 30, node 20 stores height 4 instead of 2.

These wrong heights make `_rebalance` think some subtrees are taller than they are. It then does rotations that are not needed and misses some that are needed, so the tree does many extra rotations and can become taller than an AVL tree should be. Search still finds the right keys, because rotations never break the order of the keys. Only the work and the tree shape are wrong.

## Fix

Commit `d0d4605`: update the child's height first, then the new parent's. (The commit message says "INC-05" because we renumbered the reports after the commit was made.)

```diff
--- a/indexes/avl_tree.py
+++ b/indexes/avl_tree.py
@@ -58,9 +58,9 @@ class AVLTreeIndex(Index):
         y.left = x.right
         x.right = y
-        # x and y swapped places; refresh their stored heights.
-        _update_height(x)
+        # y is now the child of x, so update y first, then x.
         _update_height(y)
+        _update_height(x)
         self.stats.rotations += 1
         return x
@@ -76,9 +76,9 @@ class AVLTreeIndex(Index):
         x.right = y.left
         y.left = x
-        # x and y swapped places; refresh their stored heights.
-        _update_height(y)
+        # x is now the child of y, so update x first, then y.
         _update_height(x)
+        _update_height(y)
         self.stats.rotations += 1
         return y
```

## Verification

Same machine (`cimy-mbp`), same CORE workload, before (session `266eb953266a`, `code_version=03d990e`) and after (session `e90ee4333937`, `code_version=c735d0c`):

| n | build before (ms) | build after (ms) | rotations before | rotations after |
|---|---|---|---|---|
| 10,000 | 60.6 | 36.6 | 95,917 | 6,479 |
| 114,000 | 944.1 | 532.0 | 1,476,511 | 62,826 |

E1 after the fix (session `5e84c32c58a5`): rotations per key stay between 0.55 and 0.72 for all sizes, and the height is 12 at n = 1,000 and 20 at n = 114,000, always under the limit.

E5 after the fix (session `b328321a8cc3`) at n = 100,000: 0.70 rotations per key for random order, 1.19 for nearly sorted, and 1.00 for sorted and reversed, with heights 20, 20, 17 and 17. All heights are under the limit of 23.9. About 1 rotation per key for sorted input is what theory predicts, because every new key goes to the right end of the tree.

We also checked the Part A example again: after inserting 10, 20, 30, node 20 now stores height 2.

`make test` passes after the fix (168 passed, 3 skipped).

## Impact on recommendations

Partly. Before the fix, the AVL tree built more slowly than it should, and it was taller than needed, so lookups and range queries walked a slightly longer path (height 26 instead of 20 at n = 100,000). This made the AVL tree look worse than it really is compared with the B+ tree and the sorted list, for example for F3 (range queries on tempo) and F4 (build). After the fix, the AVL tree builds about 1.8 times faster and has a normal height, so our comparisons in E2–E5 use the fixed version.

## Why the tests didn't catch it

The tests only check that search returns the right values, and wrong heights do not change the answers. Tests that would catch this bug:

- Insert 10, 20, 30 and check that the root's stored height is 2.
- Insert 1,000 sorted keys and check that `stats.rotations` is at most n, and that `structure_info()["height"]` is at most 1.44 · log2(n + 2).
- After many random inserts, check that every node's stored height equals the real height of its subtree.
