### Q1. Search cost as n grows

Big-O tells us how the work grows when the number of keys *n* grows. O(1) means the work stays the same. O(log n) means the work grows very slowly. O(n) means the work grows at the same speed as *n*.

**Hash table: O(1) on average.** In `search` (`indexes/hash_table.py`, lines 68–77), the code first finds one bucket using `hash(key) % len(self._buckets)` (line 40). Then it only checks the keys inside this bucket (lines 71–75). The table makes more buckets when there are more than 0.75 keys per bucket on average (lines 30, 55–56). So each bucket is very short, and search does not get slower when *n* gets bigger. In the worst case, many keys go into the same bucket and search becomes O(n), but this rarely happens.

**AVL tree: O(log n).** In `search` (`indexes/avl_tree.py`, lines 120–133), the code starts from the root and goes down one path. At each node, it goes left or right (lines 125–128). It stops when it finds the key (line 130) or when there is no more node (line 123). The AVL tree keeps itself balanced (`_rebalance`, lines 85–98), so the tree height is about log n. This means a search only checks about log n nodes.

### Q2. Why the hash table needs to check every key for a range query

A hash function puts keys into buckets in a mixed-up way. The bucket number comes from `hash(key) % len(self._buckets)` (line 40). Because of this, two keys that are close, for example tempo 125.0 and 125.1, can go into very different buckets. The order of the keys is lost.

So for a range query, a key between `lo` and `hi` can be in any bucket. The code does not know where to start or where to stop. That is why `range_search` (lines 79–88) loops over every bucket and every key (lines 82–84). The code also counts this: it adds all keys to `comparisons` (line 86) and all buckets to `nodes_visited` (line 87). Prefix search has the same problem, because it is also a range query (`base.py`, line 102).

### Q3. Inserting 10, 20, 30 into an empty AVL tree

In an AVL tree, the left and right side of every node can only have a height difference of 1. After each insert, the code calls `_rebalance` (line 117) on each node on the way back up.

1. **Insert 10.** The tree is empty, so 10 becomes the root (line 107). Its height is 1.
2. **Insert 20.** 20 is bigger than 10, so it goes to the right of 10 (line 113). Node 10 now has height 2 and balance 0 − 1 = −1. This is OK, so no rotation.
3. **Insert 30.** 30 is bigger than 10 and 20, so it goes to the right of 20. Then the code checks the nodes on the way back:
   - Node 20: height 2, balance −1. This is OK.
   - Node 10: height 3, balance 0 − 2 = **−2**. The right side is too tall, so the code goes into the branch at **line 93**.
   - Line 95 checks node 20. Its balance is −1 (not bigger than 0), so this is the **right-right case**. Only one rotation is needed.
   - **Line 97 calls `_rotate_left(10)`.** In lines 75–78, node 20 moves up and becomes the new root, and node 10 becomes its left child. Line 82 adds 1 to `rotations`.

The final tree:

```
    20
   /  \
  10   30
```

The height of the tree is 2, and `rotations` is 1.

### Q5. What the counters count (hash table and AVL tree)

The counters are saved in `index.stats` (`base.py`, lines 32–48).

**Hash table**
- `nodes_visited`: how many buckets the code opens. `insert` and `search` open one bucket each time (line 39). `range_search` opens all buckets (line 87).
- `comparisons`: how many keys the code compares. This happens in `insert` (lines 46, 53), in `search` (lines 72, 74, 76), and for all keys in `range_search` (line 86).
- `resizes`: how many times the table grows (line 66). Each time, all keys are moved to a new bigger bucket list.
- `rotations` and `splits` are always 0.

**AVL tree**
- `nodes_visited` and `comparisons`: both add 1 for each node on the path, so they are always the same number (insert: lines 108–109, search: lines 131–132, range: lines 145–146).
- `rotations`: adds 1 for each rotation (lines 64, 82). A left-right or right-left case counts as 2.
- `splits` and `resizes` are always 0.

**Why we need counters when we already have timings.** Timings change from computer to computer, and even from run to run, because of hardware, other programs, and Python itself. Counters do not change: the same keys and queries always give the same counts on any computer. So counters help us in three ways. First, we can compare the growth directly with the big-O. Second, we can check that different computers did the same work. Third, counters show *which* work is too much (for example, too many `resizes` or `rotations`), while timing only shows that something is slow. But counters do not count everything, for example the time for `hash()`, so we still need timings too.
