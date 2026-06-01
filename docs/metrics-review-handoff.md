# Metrics logic review — agent handoff

Use this document to audit whether the tool’s **person-summary metrics** match intended business semantics, and to review **code quality**, **documentation accuracy**, and **gaps** between the two.

**Audience:** A reviewer agent (or human) with repo access and `gh` authenticated. No prior conversation context required.

**User-facing docs:** [README.md](../README.md) (CLI, columns, date windows)  
**Contributor docs:** [architecture.md](architecture.md), [extending-the-cli.md](extending-the-cli.md)

---

## 1. What we are trying to measure

Monthly team metrics for one GitHub repository over a **half-open calendar window** in US Eastern (`America/New_York`):

```
--start-date <= event time < --end-date
```

Example — all of May 2026: `--start-date 2026-05-01 --end-date 2026-06-01`.

### Person-summary PR columns (intended semantics)

| Column | Window filter on **create**? | Window filter on **merge/close**? | Can exceed `prs_authored`? |
|--------|------------------------------|-----------------------------------|----------------------------|
| `prs_authored` | **Yes** — opened in window | — | — (baseline for window-opened PRs) |
| `prs_merged` | **No** — any open date | **Yes** — merged in window | **Yes** (carry-over PRs opened before window) |
| `prs_open` | **No** — any open date | Snapshot at **window end** (still unmerged, not closed-without-merge before end) | **Yes** (PRs opened before window still open at month-end) |
| `prs_closed_unmerged` | **Yes** — opened in window | Closed without merge **before** window end | No (subset of window-opened) |

**Key insight the product owner cares about:** `prs_open` and `prs_merged` are **not** restricted to PRs created in the window. Only `prs_authored` and `prs_closed_unmerged` are. Therefore:

- `prs_open` **can be greater than** `prs_authored`.
- `prs_merged` **can be greater than** `prs_authored`.
- Do **not** expect `prs_authored = prs_merged + prs_open + prs_closed_unmerged` using the **totals** of those columns.

### Reconciliation (window-opened PRs only)

For PRs **opened in the window**, at window end each falls into exactly one outcome bucket:

| Outcome at window end | Counted in |
|-----------------------|------------|
| Merged before window end | `prs_merged` (if merge timestamp is in window) |
| Still open (not merged, not closed-without-merge) | `prs_open` |
| Closed without merge before window end | `prs_closed_unmerged` |

So for **window-opened PRs only**:

```
prs_authored ≈ merged_in_window(window_opened)
            + open_at_end(window_opened)
            + prs_closed_unmerged
```

**Exception:** A PR opened in the window, still open at month-end, but merged **after** the window counts as `prs_authored=1`, `prs_open=1`, `prs_merged=0` until a later report window includes the merge.

### Other person-summary columns

| Column | Intended semantics |
|--------|-------------------|
| `prs_reviewed` | Distinct PRs where this person submitted **any** formal review with `submitted_at` in the window |
| `prs_approved` | Distinct PRs where this person submitted an **APPROVED** review in the window |
| `avg_files_*`, merge-cycle hours | Derived from **PR detail rows** (see §4 — different population than all summary counts) |

---

## 2. Code map — where logic lives

```
pipeline/runner.py          Orchestration: Phase 1 search → Phase 2 fetch → Phase 3 summarize
catalog/search.py           GitHub search queries (Phase 1 catalogs)
time_utils.py               window_bounds_utc(), parse_github_ts()
analysis/authored_activity.py   is_open_at_month_end, is_closed_unmerged_in_window, count helpers
analysis/summaries.py       compute_user_summaries() — rolls up per-user rows
analysis/reviews.py         prs_reviewed / prs_approved from review submitted_at
analysis/pr_builder.py      PullRequestRow detail from REST API
cache/raw_store.py          _raw.json save/load; --from-cache recomputation
export/tsv.py               Column headers and footnotes in TSV output
```

### Phase 1 — PR discovery (`catalog/search.py`)

| Catalog | Builder | Used for |
|---------|---------|----------|
| Activity | `build_activity_catalog()` | Phase 2 detail fetch (union of merged-in-window + created-in-window unless `--merged-only`) |
| Created | `build_created_in_window_catalog()` | `prs_authored`, `prs_closed_unmerged` state resolution |
| Open candidates | `build_open_at_month_end_candidate_catalog()` | Candidate set for `prs_open` (timestamp-filtered in Phase 3b) |
| Review | `build_review_catalog()` | PRs scanned for review/approval counts |

Search uses **inclusive calendar ranges** aligned to the report window, e.g. `merged:2026-05-01..2026-05-31` for May with `--end-date 2026-06-01`. Do **not** use ISO timestamp qualifiers in search — they were found unreliable.

### Phase 3b — Count functions (`analysis/authored_activity.py`)

| Function | Implements |
|----------|------------|
| `counts_authored_in_window()` | `prs_authored` |
| `counts_merged_in_window_from_rows()` | `prs_merged` (from fetched detail rows) |
| `counts_open_at_month_end()` | `prs_open` |
| `counts_closed_unmerged_in_window()` | `prs_closed_unmerged` |
| `is_open_at_month_end()` | Core snapshot logic for open-at-end |
| `is_closed_unmerged_in_window()` | Core logic for closed-without-merge |

### Time boundaries (`time_utils.py`)

```python
window_bounds_utc(start_d, end_exclusive_d, report_tz)
# start_local  = start_d 00:00:00 in report_tz → UTC
# end_exclusive = end_exclusive_d 00:00:00 in report_tz → UTC
# All comparisons: start_utc <= t < end_exclusive_utc
```

---

## 3. Review checklist — metrics correctness

Work through each item. For each metric, pick 2–3 users from a production `_raw.json` and **manually verify** against `gh api`.

### 3.1 Date window

- [ ] Confirm all count helpers use the same half-open interval (`>= start`, `< end_exclusive`).
- [ ] Confirm README “Date windows” section matches `window_bounds_utc()` behavior.
- [ ] Spot-check a PR merged exactly at `--end-date 00:00 Eastern` — should be **excluded**.

**Files:** `time_utils.py`, `authored_activity.py`, `reviews.py`, `summaries.py`

### 3.2 `prs_authored`

- [ ] Counts PRs with `created_at` in `[start, end)`.
- [ ] Uses `created_catalog` + `build_pr_states()` (not only activity-catalog detail rows).
- [ ] Author = GitHub PR `user.login`, not assignee.

**Verify:**

```bash
gh api "search/issues?q=repo:OWNER/REPO+is:pr+created:YYYY-MM-DD..YYYY-MM-DD" --paginate \
  --jq '.items[] | "\(.number) \(.user.login) \(.created_at)"'
```

Compare per-author totals to person summary.

### 3.3 `prs_merged`

- [ ] Counts PRs with `merged_at` in `[start, end)` **regardless of create date**.
- [ ] Implemented via `counts_merged_in_window_from_rows()` over Phase 2 detail rows.
- [ ] Under `--merged-only`, activity catalog is merged-only, so detail rows are merged-in-window PRs — consistent.
- [ ] Carry-over: PR opened before window, merged in window → `prs_merged=1`, `prs_authored=0`.

**Verify:** Same as above with `is:merged merged:START..LAST_DAY`.

### 3.4 `prs_open` (open at window end)

- [ ] Snapshot at instant **before** `--end-date 00:00 Eastern`.
- [ ] Includes PRs created **before** the window if still open at end.
- [ ] Excludes PRs merged before end, and PRs closed-without-merge before end.
- [ ] `is_open_at_month_end()` logic matches the above.

**Verify manually** for sample PRs:

```bash
gh api repos/OWNER/REPO/pulls/PR_NUMBER --jq '{created:.created_at, merged:.merged_at, closed:.closed_at, state:.state}'
```

Apply `is_open_at_month_end()` rules by hand.

### 3.5 Open-at-end candidate catalog completeness

`build_open_at_month_end_candidate_catalog()` uses four searches:

1. `is:open created:<end`
2. `created:<end merged:>=end`
3. `created:<end closed:>=end`
4. `created:<start updated:start..last`

- [ ] Confirm no PR that was open at window end can fall through all four queries (especially: created before window, no May activity, closed after window).
- [ ] Document any proven gap or confirm searches are sufficient.

**Risk:** GitHub search returns max **1,000** results per query (`SEARCH_MAX_PAGES` in `config.py`). Large repos may silently truncate catalogs.

### 3.6 `prs_closed_unmerged`

- [ ] Requires: opened in window, **not** merged, `closed_at` in `[start, end)`.
- [ ] Mutually exclusive with `prs_open` for the same PR at window end.

### 3.7 Reviews

- [ ] `prs_reviewed` / `prs_approved` use review `submitted_at` in window, not PR merge date.
- [ ] Counts **distinct PRs**, not review events (one person, two reviews on same PR = 1).
- [ ] Comments without a formal review object are excluded.

**Files:** `analysis/reviews.py`

### 3.8 `--from-cache` path

- [ ] `load_raw_cache()` recomputes authored/open/closed_unmerged from cached `created_pr_states` / `open_pr_states`.
- [ ] Older caches without `open_pr_states` fall back to `created_pr_states` only — flag if that understates `prs_open`.

**File:** `cache/raw_store.py`

---

## 4. Review checklist — code quality & consistency

### 4.1 Detail rows vs summary metrics (population mismatch)

| Data | Population |
|------|------------|
| PR detail TSV / sheet | Activity catalog PRs fetched in Phase 2 |
| `prs_merged` | Same detail rows (merged timestamp filter) |
| `prs_authored`, `prs_open`, `prs_closed_unmerged` | Separate catalogs + state fetches |
| `avg_files_*` per user | Mean over **that user’s detail rows only** |
| Merge-cycle min/max/avg hours | Detail rows merged in window (`summaries._merge_cycle_stats`) |

- [ ] Confirm this mismatch is **documented** and acceptable for reporting.
- [ ] Under `--merged-only`, file averages and merge-cycle stats are over **merged-in-window** PRs only — not over all authored PRs.

**Files:** `summaries.py`, `runner.py`, README “Output columns”

### 4.2 Author attribution consistency

Phase 1 catalog stores author from search `user.login`. Phase 2 uses that as `report_author` but `PullRequestRow.author` comes from live API.

- [ ] Check for catalog/API author mismatches (force-push reassign? rare).
- [ ] Skipped PRs: excluded from detail rows but may still appear in catalogs — check `_log_person_coverage()` warnings.

### 4.3 Dead or duplicate code

- [ ] `counts_merged_in_window()` (on `pr_states` dict) vs `counts_merged_in_window_from_rows()` — runner uses only the latter. Is the former unused? Should one path be removed?

### 4.4 Error handling & observability

- [ ] Skipped PRs logged in run log and `_raw.json` — sufficient for audit?
- [ ] Phase 3b fetches missing PR state for catalog entries not in detail rows — failures logged as skips?

### 4.5 Tests

- [ ] **No automated tests exist today.** Recommend unit tests for:
  - `is_open_at_month_end()` edge cases (pre-window create, merge/close exactly at boundary)
  - `is_closed_unmerged_in_window()`
  - `window_bounds_utc()` across DST transitions
  - Reconciliation identity for synthetic `pr_states` fixtures

### 4.6 Configuration & limits

| Setting | File | Review |
|---------|------|--------|
| `SEARCH_MAX_PAGES` | `config.py` | 1,000-result search cap |
| `REPORT_TZ` | `config.py` | All calendar semantics |
| `--workers` | `runner.py` | Thread-per-PR fetch; rate-limit behavior |

---

## 5. Known documentation gaps & inconsistencies

Fix or confirm these during review.

### 5.1 README reconciliation formula (likely wrong as written)

**Location:** README.md — “PR count columns for PRs opened in the window reconcile as”

**Current text:**

```
prs_authored ≈ prs_merged + prs_open + prs_closed_unmerged
```

**Problem:** `prs_merged` and `prs_open` include carry-over PRs (opened **before** the window). The example table on the next lines **contradicts** the formula (e.g. “Opened in April, still open May 31 → authored=0, open=1”).

**Recommended fix:** Replace with the window-opened-only reconciliation from §1 above, and add an explicit note that **`prs_merged` and `prs_open` are not subsets of `prs_authored`**.

### 5.2 Example row “Opened 8 in May; merged 5; 2 still open; 1 closed unmerged”

The table shows `prs_merged=5` alongside `prs_authored=8`. That only reconciles if all 5 merges are among the 8 window-opened PRs. If any of the 5 merges are carry-over, the example is misleading. Clarify or split into two examples.

### 5.3 `export/tsv.py` footnotes vs README

Compare person-summary header comments in `export/tsv.py` with README “Output columns”. They should say the same thing about open-at-end including pre-window PRs.

### 5.4 `architecture.md` Phase 3b label

Says “Open-at-window-end snapshot” — good. Ensure it mentions **separate catalogs** for created vs open-candidate, not just activity catalog.

### 5.5 Terminology

Code and logs use `open_at_month_end` / “month-end” even for non-month windows (e.g. one-week reports). Consider renaming in docs to “open at window end” for accuracy (code rename optional).

---

## 6. Suggested verification workflow

Use existing production artifacts (May 2026) if available:

| Repo | Typical cache path |
|------|-------------------|
| global-services | `~/Documents/global-services-may-2026_raw.json` |
| global-user-services | `~/Documents/global-user-services-may-2026_raw.json` |
| polaris-turbo | `~/Documents/polaris-turbo-may-2026_raw.json` |

### Step A — Recompute from cache

```bash
cd /path/to/github-analysis
uv run github-analysis analyze \
  --from-cache ~/Documents/global-services-may-2026_raw.json \
  --repo global-services \
  --start-date 2026-05-01 --end-date 2026-06-01 \
  -o /tmp/gs-verify.tsv
```

Confirm person summary matches the production xlsx.

### Step B — Spot-check one user (e.g. monika-sbd)

From prior validation (May 2026, three repos):

| Repo | authored | merged | open | closed_unmerged |
|------|----------|--------|------|-----------------|
| global-services | 2 | 0 | 1 | 1 |
| global-user-services | 3 | 3 | 0 | 0 |
| polaris-turbo | 10 | 9 | 0 | 1 |

Pick one “interesting” user (non-zero closed_unmerged or open > authored). For each of their PRs in `_raw.json` → `created_pr_states` / `open_pr_states`, trace which bucket it landed in.

### Step C — GitHub API cross-check

For that user’s PR numbers, fetch timestamps and apply window rules by hand. Document any delta.

### Step D — Search cap audit

For each catalog query in the run log, check whether result count hit 1,000. If yes, flag as **data completeness risk**.

---

## 7. Deliverables expected from reviewer

1. **Metrics verdict** — For each person-summary column: correct / incorrect / acceptable-with-caveats, with evidence.
2. **Gap list** — Catalog completeness, search caps, skipped PRs, cache fallbacks.
3. **Doc patch list** — Specific README/architecture/tsv footnote edits (especially §5.1).
4. **Code patch list** — Bugs, dead code, missing tests, naming fixes — prioritized.
5. **Optional:** Small unit-test module for `authored_activity.py` and `time_utils.py` with boundary-case fixtures.

---

## 8. Reference — core snapshot logic (verify matches intent)

```python
# analysis/authored_activity.py — paraphrased

def is_open_at_month_end(pr_created, merged_at, closed_at, *, end_exclusive_utc):
    if pr_created is None or pr_created >= end_exclusive_utc:
        return False
    if merged_at is not None and merged_at < end_exclusive_utc:
        return False
    if closed_at is not None and closed_at < end_exclusive_utc:
        return False
    return True

def is_closed_unmerged_in_window(pr_created, merged_at, closed_at, *, start_inclusive_utc, end_exclusive_utc):
    if pr_created is None or pr_created < start_inclusive_utc or pr_created >= end_exclusive_utc:
        return False
    if merged_at is not None:
        return False
    if closed_at is None or closed_at >= end_exclusive_utc:
        return False
    return True
```

If these functions match §1 semantics, the **count helpers are structurally correct**; remaining risk is **Phase 1 catalog completeness** and **search truncation**.

---

## 9. Out of scope (unless explicitly requested)

- Excel formatting / xlsx writer aesthetics
- Legacy scripts (`github_pr_timeline_report.py`, `export_report_xlsx.py`)
- CI/CD or release process
- Re-running full-month production fetches (use `--from-cache` for logic review)
