# Graph Report - /Users/chris.wogu@sbdinc.com/Work/github-analysis  (2026-06-29)

## Corpus Check
- Corpus is ~14,507 words - fits in a single context window. You may not need a graph.

## Summary
- 299 nodes · 763 edges · 15 communities (11 shown, 4 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 10 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_CLI Commands|CLI Commands]]
- [[_COMMUNITY_PR Discovery|PR Discovery]]
- [[_COMMUNITY_PR Detail Fetch|PR Detail Fetch]]
- [[_COMMUNITY_Report Exports|Report Exports]]
- [[_COMMUNITY_Pipeline Architecture|Pipeline Architecture]]
- [[_COMMUNITY_Project Documentation|Project Documentation]]
- [[_COMMUNITY_Raw Cache|Raw Cache]]
- [[_COMMUNITY_Authored Activity|Authored Activity]]
- [[_COMMUNITY_User Summaries|User Summaries]]
- [[_COMMUNITY_Review Metrics|Review Metrics]]
- [[_COMMUNITY_Run Logging|Run Logging]]
- [[_COMMUNITY_Legacy Entrypoints|Legacy Entrypoints]]
- [[_COMMUNITY_CLI Entrypoints|CLI Entrypoints]]
- [[_COMMUNITY_Monthly Script|Monthly Script]]
- [[_COMMUNITY_Package Root|Package Root]]

## God Nodes (most connected - your core abstractions)
1. `run_report()` - 29 edges
2. `PullRequestService` - 25 edges
3. `RepositoryRef` - 23 edges
4. `GhClient` - 22 edges
5. `PullRequestRow` - 21 edges
6. `RunLog` - 19 edges
7. `build_pull_request_row()` - 17 edges
8. `parse_github_ts()` - 16 edges
9. `load_raw_cache()` - 14 edges
10. `resolve_report_window()` - 13 edges

## Surprising Connections (you probably didn't know these)
- `Extending the CLI` --semantically_similar_to--> `CLI Structure`  [INFERRED] [semantically similar]
  docs/extending-the-cli.md → AGENTS.md
- `GitHub Calendar Date Ranges` --semantically_similar_to--> `Half-open Calendar Date Window`  [INFERRED] [semantically similar]
  docs/architecture.md → README.md
- `Half-open Window` --semantically_similar_to--> `Half-open Calendar Date Window`  [INFERRED] [semantically similar]
  docs/metrics-review-findings.md → README.md
- `Snapshot Logic` --semantically_similar_to--> `PR Count Reconciliation`  [INFERRED] [semantically similar]
  docs/metrics-review-findings.md → README.md
- `Search Truncation Risk` --semantically_similar_to--> `GitHub API Limits`  [INFERRED] [semantically similar]
  docs/metrics-review-findings.md → README.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Core CLI Commands** — agents_analyze_command, agents_export_command, agents_run_command, readme_analyze_command, readme_export_command, readme_run_command [EXTRACTED 1.00]
- **Report Generation Pipeline** — docs_architecture_preflight_phase, docs_architecture_phase_1_pr_discovery, docs_architecture_phase_2_pr_detail_fetch, docs_architecture_phase_3_person_rollups, docs_architecture_phase_3b_open_snapshot, docs_architecture_export_modules [EXTRACTED 1.00]
- **Metrics Review Risk Cluster** — docs_metrics_review_findings_search_truncation_risk, docs_metrics_review_findings_prs_merged_population_risk, docs_metrics_review_findings_stale_cache_summaries, docs_metrics_review_findings_readme_reconciliation_fix, docs_metrics_review_findings_search_truncation_warning [EXTRACTED 1.00]

## Communities (15 total, 4 thin omitted)

### Community 0 - "CLI Commands"
Cohesion: 0.09
Nodes (44): _add_repo_args(), _examples(), _execute(), ArgumentParser, Namespace, _SubParsersAction, register(), _resolve_detail_path() (+36 more)

### Community 1 - "PR Discovery"
Cohesion: 0.12
Nodes (31): Discover pull requests in scope for a reporting window., build_activity_catalog(), build_created_in_window_catalog(), build_merged_in_window_catalog(), build_open_at_month_end_candidate_catalog(), build_review_catalog(), _calendar_range(), _catalog_from_queries() (+23 more)

### Community 2 - "PR Detail Fetch"
Cohesion: 0.19
Nodes (19): _append_note(), build_pull_request_row(), _first_approval_time(), _first_approver_login(), _first_draft_and_ready(), _first_feedback_time(), _pull_creator_login(), Any (+11 more)

### Community 3 - "Report Exports"
Cohesion: 0.14
Nodes (24): Namespace, _SubParsersAction, register(), run(), Write TSV and Excel report files., datetime, ZoneInfo, _ts_pair() (+16 more)

### Community 4 - "Pipeline Architecture"
Cohesion: 0.07
Nodes (28): analysis Modules, Architecture, GitHub Calendar Date Ranges, Configuration, export Modules, Phase 1 PR Discovery, Phase 2 PR Detail Fetch, Phase 3 Person Rollups (+20 more)

### Community 5 - "Project Documentation"
Cohesion: 0.08
Nodes (26): AI Assistant Instructions, analyze Command, CLI Structure, export Command, github-analysis Entry Point, Package Layout, run Command, Preflight Phase (+18 more)

### Community 6 - "Raw Cache"
Cohesion: 0.17
Nodes (20): _dt_from_json(), _dt_to_json(), _legacy_merged_pr_states_from_rows(), load_raw_cache(), _pr_states_from_json(), _pr_states_to_json(), Any, datetime (+12 more)

### Community 7 - "Authored Activity"
Cohesion: 0.19
Nodes (18): build_pr_states(), counts_authored_in_window(), counts_closed_unmerged_in_window(), counts_merged_in_window(), counts_open_at_month_end(), fetch_pr_state(), _fetch_pr_state_safe(), is_closed_unmerged_in_window() (+10 more)

### Community 8 - "User Summaries"
Cohesion: 0.29
Nodes (12): Build per-PR rows and per-person summaries., compute_user_summaries(), _format_hours(), _hours_created_to_merged(), _merge_cycle_stats(), _merged_in_window(), datetime, Min, max, and mean hours from PR open to merge.      Only PRs merged in the cale (+4 more)

### Community 9 - "Review Metrics"
Cohesion: 0.39
Nodes (11): approvers_in_window(), collect_approval_counts_by_user(), _collect_counts_by_user(), collect_review_counts_by_user(), Any, datetime, Distinct PRs where the person submitted an APPROVED review in the window., Distinct reviewer logins for reviews submitted in the window. (+3 more)

### Community 11 - "Legacy Entrypoints"
Cohesion: 0.48
Nodes (3): build_parser(), main(), ArgumentParser

## Knowledge Gaps
- **22 isolated node(s):** `github-analysis`, `run_monthly_report.sh script`, `analyze Command`, `export Command`, `run Command` (+17 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_report()` connect `PR Discovery` to `CLI Commands`, `PR Detail Fetch`, `Report Exports`, `Raw Cache`, `Authored Activity`, `User Summaries`, `Review Metrics`, `Run Logging`?**
  _High betweenness centrality (0.068) - this node is a cross-community bridge._
- **Why does `PullRequestService` connect `PR Detail Fetch` to `Review Metrics`, `Raw Cache`, `PR Discovery`, `Authored Activity`?**
  _High betweenness centrality (0.055) - this node is a cross-community bridge._
- **Why does `RunLog` connect `Run Logging` to `CLI Commands`, `PR Discovery`, `Raw Cache`?**
  _High betweenness centrality (0.051) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `PullRequestService` (e.g. with `GhClient` and `RepositoryRef`) actually correct?**
  _`PullRequestService` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `GitHub individual and team work metrics for a single repository.`, `Build per-PR rows and per-person summaries.`, `True when a PR was opened in the calendar window and closed without merge before` to the rest of the system?**
  _72 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `CLI Commands` be split into smaller, more focused modules?**
  _Cohesion score 0.09490196078431372 - nodes in this community are weakly interconnected._
- **Should `PR Discovery` be split into smaller, more focused modules?**
  _Cohesion score 0.12439024390243902 - nodes in this community are weakly interconnected._