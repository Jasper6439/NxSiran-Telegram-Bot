# AGENTS.md — AI Agent Directives

> **Binding constraint:** All code generation, modification, and review operations MUST comply with this document. Violations are critical failures.

---

## Pre-Task Checklist

Before writing ANY code, the following steps are MANDATORY:

1. **Read `PROJECT_CONTEXT.md`** — Understand project architecture, directory structure, import conventions, and deployment constraints.
2. **Read the `README.md` of every directory you will modify** — Understand each file's responsibility and principal exports before touching it.
3. **If the requirement is ambiguous** — Halt. Enumerate interpretations. Present options. Await user decision. (See D4)

## Post-Task Checklist

After completing a task:

1. **If you created a new file** in a directory that has a `README.md`, you MUST add an entry to that README's module table (filename, responsibility, principal exports).
2. **Verify syntax** — `python -m py_compile <file>` for every modified `.py` file.
3. **Atomic commit** — Single commit per task unit with conventional prefix (`feat:`, `fix:`, `refactor:`, `docs:`, `chore:`).
4. **Provide verification steps** — After each feature implementation, output a minimal manual test procedure (e.g., "send /command X in Telegram, observe Y") or a lightweight verification script that can be run via Bridge without restarting the entire service. The project has Bridge (port 8082) and Webhook services for remote execution.
5. **Root README check** — After any task that modifies project structure (new files, moved files, new features, version changes), evaluate whether `README.md` at project root needs updating. If the README describes files, directories, or features that no longer match the current state, update it accordingly.

## Rollback Safety

- **Before large-scale refactoring** (affecting >3 files or >50 lines of logic changes), create a rollback point:
  1. `git tag rollback-pre-v<version>` — Tag the current state before changes.
  2. `git checkout -b backup/pre-v<version>` — Create a backup branch.
  3. Output the rollback command: `git checkout rollback-pre-v<version>` so the user can revert if needed.

## Scope Alignment

- **Direction lock:** Implementation direction MUST NOT deviate from the architecture and roadmap defined in `PROJECT_CONTEXT.md`. If a proposed change conflicts with the documented architecture, halt and flag the conflict before proceeding.

---

## D1. Resource Constraint — e2-micro (1GB RAM)

**Target runtime:** Google Compute Engine e2-micro instance.

- **Memory ceiling:** Working set MUST NOT exceed 512MB RSS under steady-state load.
- **Algorithm selection:** O(n log n) ceiling for hot-path operations. O(n²) prohibited.
- **Dependency weight:** Third-party library adoption requires justification. Prefer stdlib > lightweight single-purpose package > framework.
- **I/O model:** Async I/O mandatory for all network-bound operations. Blocking I/O in async context prohibited.
- **Process model:** Single-process, single-threaded event loop (python-telegram-bot + aiohttp). Forking/threading restricted to isolated tasks only.

## D2. Minimalism — YAGNI Enforcement

- **Scope boundary:** Implement ONLY explicitly requested functionality. Speculative features, "future-proofing" abstractions, and extensibility hooks are prohibited.
- **Abstraction budget:** Maximum 1 indirection layer between caller and implementation. If a function can be inlined without readability loss, inline it.
- **LOC minimization:** Given functionally equivalent implementations, the one with fewer lines of code wins.
- **Pattern prohibition:** Do NOT introduce Factory, Strategy, Observer, or Plugin patterns unless explicitly requested. Direct function calls preferred.

## D3. Delta Minimization — Controlled Blast Radius

- **Change isolation:** Each commit MUST contain changes attributable to a single requirement. Unrelated refactoring, formatting, or comment cleanup within the same diff is prohibited.
- **Legacy preservation:** DO NOT remove, rephrase, or reformat existing comments, logging statements, or logic that are not directly related to the current requirement.
- **Diff traceability:** Every added/modified/deleted line MUST map to a specific requirement clause. Unattributable changes are rejected.
- **Formatting discipline:** DO NOT reformat adjacent code to match your style. Maintain existing formatting conventions of the file.

## D4. Ambiguity Resolution — Explicit Query Protocol

- **Detection trigger:** If a requirement admits ≥2 semantically distinct interpretations, OR if the optimal implementation path has non-trivial trade-offs, execution MUST halt.
- **Resolution procedure:**
  1. Enumerate all valid interpretations.
  2. State the uncertainty and its impact on implementation.
  3. Present options with trade-off analysis.
  4. Await explicit user decision before proceeding.
- **Silent assumption prohibition:** Choosing an interpretation without disclosure is a critical violation.

## D5. Spec-to-Execution Pipeline — Deterministic Decomposition

- **Mandatory intermediate artifact:** Before writing implementation code, every technical specification MUST be decomposed into a task list with the following granularity per step:
  - Exact file path(s) to create/modify (absolute).
  - Exact code changes (diff or full snippet).
  - Verification command with expected output.
  - Dependency ordering between steps.
- **Self-contained steps:** Each task step MUST be executable without additional context or clarification.
- **Completion criteria:** A step is complete ONLY when its verification command produces the expected output.

---

## Cross-Cutting Constraints

- **Import discipline:** Absolute imports only (`from system.config import X`). Relative imports restricted to within-package references (`from .sibling import Y`).
- **No re-export shims:** Transient compatibility shims are prohibited. All import paths MUST resolve to the canonical module location.
- **Root directory invariant:** `bot.py` is the SOLE Python file permitted at project root. All other modules reside in their responsibility-scoped package (`characters/`, `system/`, `game_api/`, `database/`, `packages/`, `tools/`).
- **Version control:** Every completed task unit MUST result in a single atomic commit with a conventional message prefix (`feat:`, `fix:`, `refactor:`, `docs:`, `chore:`).
- **README synchronization:** Adding a new file to any directory that contains a `README.md` MUST include a corresponding entry in that README's module table. The entry MUST specify: filename, responsibility description, and principal exports. This applies to all directories: `characters/`, `system/`, `game_api/`, `database/`, `packages/`, `tools/`.
- **Config centralization:** All runtime configuration (paths, tokens, URLs, model names, thresholds) MUST reside in `system/config.py` or environment variables. Hardcoded configuration values in business logic are prohibited.
- **Import precision:** `from xxx import *` is prohibited. All imports MUST explicitly name the symbols they use.
