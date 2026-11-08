# Member C handoff

- Base of the handoff branch: `a61210d` from `main`.
- E6 baseline: `a152bd8`. B+ range repair: `0d49e62`.
- E6: `make experiments MEMBER=zuoheng MACHINE=zuoheng-mbp ONLY=E6_bplus_order`. Both Docker runs contain 855 batches. The original session is `449665fab6ee` and the repaired session is `1873dc08b837`.
- C CORE sessions are `214c115ab1fa` (original `f5dfa0b`) and `60616fab1fe7` (current `0d49e62`), 210 batches each.
- E3 session `4bfebe4a211e` and E4 session `e32f04a9efaa` are the full seven-index retests at `0d49e62`.
- INC-04 explains the B+ range and prefix scan and includes before/after timing and counter evidence. The supplied Docker test suite passed 168 tests with 3 expected skips.
- `analysis/E6_bplus_order.ipynb` produces the order sweep. `analysis/Part_E_hardware.ipynb` produces machine coverage, counter agreement, median ratios, ranks, CVs and RAM estimates. `analysis/team_evidence.ipynb` audits the A/B handoff and compares the post-B+ retests. Run them from the repository root or `analysis/` with the provided Jupyter environment.

`make check` passes the supplied tests, C's two CORE runs, and the E1-E6, incident and notebook checks. Its two remaining failures are the missing final CORE sessions for `fenghao-pc` and `cimy-mbp`.

## Finish the team handoff

1. Bring in any outstanding hash-table and AVL work from B. At `a61210d`, the hash table still adds 1,024 buckets per resize and rehashes every entry. The AVL rotation methods update the promoted node's height before updating its demoted child. Confirm and document each change with its own incident evidence before rerunning affected experiments.
2. Agree on one clean final source commit. Each member runs CORE on their own machine from that commit. Preserve the original sessions and any intermediate runs. Rerun the affected E1–E6 experiments after additional index fixes and update the report's session selections and recommendations.

   ```sh
   make data
   make core MEMBER=fenghao MACHINE=fenghao-pc
   # On Cimy's own machine at the same final commit:
   make core MEMBER=cimy MACHINE=cimy-mbp
   # On Zuoheng's own machine at the same final commit:
   make core MEMBER=zuoheng MACHINE=zuoheng-mbp
   ```

3. Merge the CSVs by header, preserving each original row and avoiding duplicate session IDs. Retain both the recorded code version and machine ID. Use the same Python image and hash seed for all runs.
4. Insert the remaining Part A text and teammate sections into `REPORT_INTEGRATION.md`. Check the final recommendations against the same-version measurements, run `make check`, and export the final PDF for the team's Gradescope submitter.
