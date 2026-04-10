# Instructions for AI assistants (`github-analysis`)

This file is for **automated coding agents** (Cursor and similar) in this repository. **Read it when you start work here.**

## `README.md` is protected

- **Do not edit `README.md`** unless the **human explicitly instructs you to** in the current task (e.g. “update the README column table”).
- **Do not silently “fix,” sync, or expand `README.md`** after you change `github_pr_timeline_report.py` or other code—even if `_emit_tsv` headers no longer match the doc. **Stop and ask**, or give the human a **copy-paste-ready** summary of what *they* should change.
- The README states the same rule at the top for humans; your rule is here.

## Where things live

| File | Purpose |
|------|---------|
| **`README.md`** | Human-facing usage and the **canonical TSV column contract** (ordered list). Default: **read-only** for agents. |
| **`AGENTS.md`** | **This file** — agent behavior and README protection. |

## After code changes that affect the TSV

If your change alters columns, meanings, or layout: tell the human exactly how to update the **“TSV column reference (canonical contract)”** section in `README.md`, or request explicit permission to edit the README yourself.
