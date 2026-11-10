# Member C handoff

## Final CORE and hardware comparison

Each session has 210 timed batches (42 configurations with five replicates). The original and final comparisons use Python 3.13.18 in Docker with `PYTHONHASHSEED=0`.

| Machine | Original version and session | Final version and session |
|---|---|---|
| `fenghao-pc` | `f5dfa0b` · `7b67239288ad` | `2c1d06b` · `c5a132b49b79` |
| `cimy-mbp` | `03d990e` · `266eb953266a` | `814d553` · `2f7a50dd113f` |
| `zuoheng-mbp` | `f5dfa0b` · `214c115ab1fa` | `2c1d06b` · `cfec07b65b4f` |

The final recorded commits have identical Git objects for the index implementations, CORE suite, timer, loaders, Dockerfile and requirements. The two original recorded commits also match on those paths. All 150 workload-counter checks agree across the three machines within each phase. The raw CSV retains C's intermediate CORE session `60616fab1fe7` at `0d49e62` and B's earlier run of the final source, session `e90ee4333937` at `c735d0c`. The final comparison uses the sessions listed above.

The power source on `zuoheng-mbp` was not held constant. The Mac reported battery power before and after the final run and AC power at one intervening check. The recorded host and Docker specs are in `machines.csv`.

To reproduce the benchmark on the same machine, use the recorded commit in a clean checkout and run `make core MEMBER=zuoheng MACHINE=zuoheng-mbp` in Docker. Preserve each run's actual code version and session ID when combining results. Run [Part_E_hardware.ipynb](../analysis/Part_E_hardware.ipynb) from the repository root or `analysis/` to regenerate the source audit, tables, and figures.

## E6 and INC-04

- E6 baseline session `449665fab6ee` at `a152bd8` and repaired session `1873dc08b837` at `0d49e62` each contain 855 timed batches. The B+ implementation and E6 workload source match the repaired session in the final code. Reproduce with `make experiments MEMBER=zuoheng MACHINE=zuoheng-mbp ONLY=E6_bplus_order`.
- [INC-04](../incident_reports/INC-04.md) documents the bounded B+ range and prefix scan with before/after timings and counters. [E6_bplus_order.ipynb](../analysis/E6_bplus_order.ipynb) produces the order sweep and repair comparison.
- The C E3/E4 sessions `4bfebe4a211e` and `e32f04a9efaa` measured all seven indexes at `0d49e62` after the B+ repair. The team's final E3/E4 sessions `55119fb085e7` and `8b3c0da12df2` measured the fully repaired implementations at `c735d0c`.

The [shared Google Doc](https://docs.google.com/document/d/1uFSsTSW0JDJm0reU2HMKeptNmE1PhNzXbpH0N46XPH8/edit) is the submission report source. Use `make check` to verify the repository before submitting the PDF.
