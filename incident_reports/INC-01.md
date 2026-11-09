# INC-01: <one-line></one-line>Sorted List Point Lookup Uses a Linear Scan Instead of Binary Search

## Summary

Before the repair, although the ordered list index sorted_list saved the keys in order, the search method still performed a linear scan from the beginning. Under the configuration of one hundred thousand different keys and random insertion in E5, after replacing the linear scan with binary search, the average time for a single hit query decreased from 2,242.143 microseconds to 1.974 microseconds, approximately accelerating by 1,135.6 times; the average number of comparisons recorded decreased from 51,742.148 times to 17.663 times.

## Detection

Firstly, we identified the problem by analyzing the original results and the number of comparisons of E5. The code version before the fix was 03d990e, corresponding to the running session_id as 240c73092ceb.

When the number of different keys increased from 1,000 to 100,000, the average number of comparisons for each successful query increased from 500.733 to 51,742.148, almost increasing proportionally with the data volume. This growth trend led us to suspect that the search process did not fully utilize the ordered nature of the keys. 

Each configuration was measured five times, and each measurement included 1,000 hit queries.

## Expected vs. observed

The n in here represents the number of different keys. For an ordered list using binary search, a single search should have a time complexity of O(log n); after locating the candidate position, the final equality check will add at most one more comparison count.

Observations show that the number of comparisons before the fix approximately linearly increases with n, matching the performance of O(n) scanning. After the fix, the data volume increases by a hundred times, while the average number of comparisons only increases from 10.976 to 17.663, which conforms to the logarithmic growth trend of binary search.

The version of the code before the fix was 03d990e, and the version after the fix was 870c3a9. The two rounds of experiments used the same keys, queries, and random seeds: keys_seed = 4300, query_seed = 4301, order_seed = 4302.

## Evidence

We use the E5_insert_order results from the **'results/timings.csv**' file. The version before the fix was 03d990e (session: 240c73092ceb), and the version after the fix was 870c3a9 (session: 558bce9a341a). Both experiments were run in the Docker environment on **fenghao-pc**, using the same keys, queries, and random seeds; each configuration was repeated five times, with each batch containing 1,000 hit queries.

![Lookup performance before and after the fix](../analysis/figures_INC01/INC-01_lookup_time.png)

Each point in the graph represents the average query time obtained from five repeated measurements. The error bars indicate the sample standard deviation. Under the four insertion orders, the query time after repair has significantly decreased, and it increases more slowly as the number of keys increases.

![Lookup performance before and after the fix](../analysis/figures_INC01/INC-01_lookup_comparisons.png)

Before the repair, the number of comparisons increased approximately linearly with the data size. After the repair, the growth was slow, which was consistent with the expectation of binary search. The same number of comparisons were obtained for the four insertion orders because the final ordered key array and the query sequence were the same.

![Table 1: Before-and-after lookup performance under random insertion order](../analysis/figures_INC01/INC01_random_order_before_after_table.png)

The statistical data in the table are all derived from five repeated measurements. The displayed values are rounded to three decimal places, and the speed-up factor is calculated using the average time consumption with full precision. All charts can be regenerated through the file '**analysis/INC-01_sorted_list.ipynb**'.

Additionally, using the same random seed 4300 and key generation parameters as in E5, rebuild a sorted list index containing 100,000 keys in ascending order.

Calling `structure_info()` ：

```
{'distinct_keys': 100000}
```

This result confirms that there are 100,000 different keys stored in the index, which is consistent with the value of n for this configuration. This structure check can be reproduced using the same Notebook; the time taken and the number of comparisons still use the official E5 experimental records.

## Root cause

The root cause is located in the **indexes/sorted_list.py** file of the previous version 03d990e, specifically in lines 53-65 of the SortedListIndex.search method. Although self._keys has been sorted in ascending order, line 57 still iterates through the keys from the beginning using **for i, k in** **enumerate(self._keys)**, and line 58 increments the comparison count in each iteration.

When the query key is at the end of the list, or the unmatched query key is greater than the maximum key, the code needs to scan all the different keys. In E5, all the keys are distinct, so the number of different keys is equal to n, and the worst-case search cost is O(n). For uniformly distributed hit queries, on average, approximately n/2 keys need to be checked, which is consistent with the phenomenon that the number of comparisons in the experiment approximately grows linearly.

Lines 27-42 of the same file already provide the binary search helper method _bisect_left, which finds the position of the first key that is greater than or equal to the target key by continuously narrowing the search range at a cost of O(log n). However, the original search did not call this method, thus not fully leveraging the orderliness of the keys. Lines 82-83 of the **structure_info** return **distinct_keys**, which is the length of self._keys; this also indicates that the workload of the linear scan depends on the number of different keys.

The original implementation can still return the correct answer: When a matching key is found, lines 59-61 return the corresponding list of values; when a key larger than the target is encountered, lines 62-63 can correctly stop prematurely because the subsequent keys cannot match either. Therefore, this issue affects the query efficiency, but the returned result is still correct.

## Fix

The fix is submitted as 870c3a9, and the submission message is 'Use binary search for sorted list lookups.''

In the SortedListIndex.search, the existing **_bisect_left(key)** is used instead of the original linear scan to find the position pos where the key is greater than or equal to the target key. Then, it checks if pos is within the list range and confirms if the key at that position is equal to the target key. If a match is found, the corresponding value list is returned; otherwise, an empty list is returned.

**_bisect_left** already records the comparison count during the binary search process, so only an additional count is needed for the final equality check of the candidate key. After the fix, the worst-case time complexity of the search is reduced from O(n) to O(log n).

```diff
File: indexes/sorted_list.py
Function: SortedListIndex.search()

Before fix: 03d990e
After fix: 870c3a9

Git diff command:
git diff 03d990e..870c3a9 -- indexes/
```

```diff
diff --git a/indexes/sorted_list.py b/indexes/sorted_list.py
index 3519135..4233282 100644
--- a/indexes/sorted_list.py
+++ b/indexes/sorted_list.py
@@ -50,18 +50,41 @@ class SortedListIndex(Index):
             self._values.insert(pos, [value])
         self._size += 1
 
+    # def search(self, key: Any) -> list[Any]:
+    #     # The keys are sorted, so we can stop as soon as we have passed the
+    #     # place where ``key`` would be.
+    #     comparisons = 0
+    #     for i, k in enumerate(self._keys):
+    #         comparisons += 1
+    #         if k == key:
+    #             self.stats.comparisons += comparisons
+    #             return self._values[i]
+    #         if k > key:
+    #             break
+    #     self.stats.comparisons += comparisons
+    #     return []
+
+    # developed
     def search(self, key: Any) -> list[Any]:
-        # The keys are sorted, so we can stop as soon as we have passed the
-        # place where ``key`` would be.
-        comparisons = 0
-        for i, k in enumerate(self._keys):
-            comparisons += 1
-            if k == key:
-                self.stats.comparisons += comparisons
-                return self._values[i]
-            if k > key:
-                break
-        self.stats.comparisons += comparisons
+        '''
+        Find a key using binary search.
+
+        Args:
+            key: The key to look up.
+
+        Returns:
+            The stored values for this key, or an empty list if absent.
+        '''
+        # the position of the first stored key >= key.
+        pos = self._bisect_left(key)
+
+        # pos may equal the list length when every stored key is smaller.
+        if pos < len(self._keys):
+            # binary search already counted its work; count this final key check.
+            self.stats.comparisons += 1
+            if self._keys[pos] == key:
+                return self._values[pos]
+
         return []
 
     def range_search(self, lo: Any, hi: Any) -> list[Any]:


```

## Verification

The verification before and after the repair was conducted on the same machine, fenghao-pc, using the same E5 workload, including 1,000, 10,000, and 100,000 different keys, as well as four insertion orders: random, sorted, reversed, and nearly_sorted. The random seeds used for key generation, query generation, and insertion order were 4300, 4301, and 4302 respectively. Each configuration was repeated five times, and each search measurement included 1,000 hit queries.

The compared code versions were **03d990e** before the repair and **870c3a9** after the repair. Under 100,000 keys and random insertion order, the average query time decreased from 2,242.143 microseconds to 1.974 microseconds. According to the unrounded mean value, the improvement was approximately 1,135.632 times. The average number of comparisons per query decreased from 51,742.148 to 17.663. All four insertion orders showed the same change in the number of comparisons, supporting that the repair's search workload met the expected O(log n) expectation.

After the repair, the project was tested using docker compose run **--rm app python -m pytest**. The result was 168 passed, 3 skipped. The three skipped items came from the test suite's range query result sorting check for unordered indexes, which is an expected behavior. The test results indicate that this modification reduced the search workload while passing the existing correctness checks.

## Impact on recommendations

This defect may affect the index recommendation of F1 (Track page). Before the fix, the point search cost of sorted_list is O(n). The experimental results would underestimate the expected query performance of the sorted list, which might lead us to prematurely exclude this index. After the fix, the point search cost is reduced to O(log n), so the measured results after the fix should be used. These should be compared with indexes such as hash tables, AVL trees, and B+ trees.

For F2 (Search-as-you-type) and F3 (Workout mode), the hit point search data of E5 this time cannot directly indicate that these operations also achieved the same performance improvement. The recommendations for these two functions should be determined based on independent measurements of the corresponding query operations.

For F4 (Catalog import), this repair does not eliminate the element movement cost that may occur when inserting new keys into the sorted list. Therefore, the acceleration of point search cannot be directly regarded as an improvement in import speed. The recommendation for F4 also needs to be combined with the build time and memory measurement of E1, as well as the build results under different insertion orders in E5. The final choice should be based on comparable data after the repair of each index.

## Why the tests didn't catch it

The current tests mainly check whether the query results are correct, but do not set an upper limit of O(log n) for the number of comparisons when the search is performed as the data size increases. The original linear scan can still correctly return the list of values matching the key, and return an empty list when the target key is not found. Therefore, it can pass the correctness test.

The problem was discovered through complexity regression tests based on comparison counts. For example, construct ordered lists containing 1,024, 2,048, and 4,096 different keys respectively, and then query the largest key, as well as a key that is greater than the largest key but does not exist. Before each query, reset the statistical count and check the search results against the number of comparisons. For the current binary search implementation, the upper limit of the number of comparisons for a single query can be set to ceil(log2(n + 1)) + 1, where ceil represents rounding up, and an additional 1 is used for the equality check of the final candidate keys.

The original linear scan needs to check all n keys in these queries, which would exceed the above limit. Using the number of comparisons as an assertion can also reduce the impact of machine performance and system load on the test judgment, which is more stable than setting a fixed time threshold.


