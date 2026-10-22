---
name: sprint-health
description: Use when analyzing sprint health — capacity at the start, risks mid-sprint, or retrospective input at the end
allowed-tools: Agent, AskUserQuestion, Write, Read, Glob, Bash, mcp__plugin_mcp-atlassian_mcp-atlassian__jira_get_sprints_from_board, mcp__plugin_mcp-atlassian_mcp-atlassian__jira_search
user-invocable: true
---

# Sprint Health Analysis

You are orchestrating a sprint health analysis for the OCPEDGE team. Data fetching runs inline using MCP tools and transform scripts. Analysis is delegated to sub-agents.

> **Before proceeding**: Read `plugins/edge-scrum/references/Edge-Scrum-Laws.md` to identify which law files apply to Sprint Health, then read those files. Law files are the canonical reference for story pointing rules, workflow states, capacity rules, and hygiene expectations. When in doubt, the Laws win.

## Configuration

```yaml
# Scrum Board
board_id: "11479"
board_name: "OpenShift Edge Scrum"

# Custom Field IDs
fields:
  story_points:  customfield_10028
  parent:        parent              # native issue → Epic link (Jira Cloud)
  epic_link:     customfield_10014   # legacy fallback for the native Parent field
  qa_contact:    customfield_10470
  flagged:       customfield_10021
```

## Execution Model

1. **Steps 0–1**: Load laws/roster, parse args (main context)
2. **Phase 2**: Fetch Jira data inline using MCP tools → save to persisted files → run transform scripts (main context)
3. **Phase 3**: Delegate analysis to a sub-agent (capacity/midpoint/retro)
4. **Step 4**: Assemble and write the final report (main context)

**Rules:**

- Data fetching uses MCP tools directly in the main context
- MCP responses are large and get persisted to files automatically — note those file paths
- Transform scripts (`plugins/edge-scrum/bin/`) convert raw MCP data to structured JSON
- Use `check-page.py` to extract pagination info from persisted files
- Analysis sub-agents only need `Read` and `Write` — they consume the structured JSON
- Never embed raw Jira response data in the main context

## User Arguments

The user may provide arguments: $ARGUMENTS

- Sprint number (e.g., `285`) → target that specific sprint
- No arguments → target the active sprint

---

## Workflow

### Step 0: Load Laws and Roster

Read these files and hold in working memory:

1. `plugins/edge-scrum/references/Edge-Scrum-Laws.md` — read the Sprint Health row in the Agent Task Index to identify required law files
2. Read each law file listed for Sprint Health:
   - `plugins/edge-scrum/references/laws/00-team-roster.md` — SP targets and roster rules
   - `plugins/edge-scrum/references/laws/06-jira-fields.md` — custom field IDs
   - `plugins/edge-scrum/references/laws/07-workflow-states.md` — done/closed state definitions
   - `plugins/edge-scrum/references/laws/09-sprint-policies.md` — capacity rules
3. `plugins/edge-scrum/.roster.json` — extract `username`, `display_name`, `sp_target` per member

If `.roster.json` does not exist, stop: "Roster file not found. Copy `.roster.json.example` to `.roster.json` and populate it before running this skill."

---

### Step 1: Parse Arguments and Select Mode

Parse `$ARGUMENTS`:

- If a sprint number is present, it **MUST** match `^[0-9]+$`. Validate it *before* using it anywhere — it is interpolated into `{WORKDIR}` below, so a value with path or shell metacharacters must never reach the directory name. If it does not match, stop with an error (`Invalid sprint number '<value>' — expected digits only.`) and do not create the work directory. Otherwise set `TARGET_SPRINT="<number>"`.
- Otherwise: `TARGET_SPRINT="active"` (the only non-numeric value allowed).

Use `AskUserQuestion` to ask:

> "Which sprint health mode would you like to run?
>
> - **capacity** — start-of-sprint load and commitment health
> - **mid-sprint** — burndown, blockers, and sprint goal risk
> - **retro** — delivery summary, churn, and goal analysis"

Set `MODE` to one of: `capacity`, `mid-sprint`, `retro`.

Set `TODAY` = today's date as `YYYY-MM-DD`.

Create the work directory:

```bash
WORKDIR=/tmp/sprint-health-$(echo "$TARGET_SPRINT")-$(date +%Y%m%d) && mkdir -p "$WORKDIR" && echo "$WORKDIR"
```

Record `WORKDIR`.

---

> **Phase 2 is sequential**: Complete Phase 2a before starting Phase 2b — Phase 2b requires `SPRINT_ID` from Phase 2a's output.

### Phase 2a: Fetch Sprint Metadata (inline)

#### 2a.1 — Fetch sprints from Jira

Call `jira_get_sprints_from_board` for board_id `"11479"` three times:

- `state="active"`
- `state="closed"` — paginate using `page_token` (see pagination protocol below)
- `state="future"`

After each MCP call, the response is persisted to a file. Note each file path.

#### 2a.2 — Run transform script

```bash
python3 plugins/edge-scrum/bin/transform-sprints.py \
  --input <all_persisted_file_paths> \
  --output {WORKDIR}/sprints.json \
  --today {TODAY} \
  --target-sprint {TARGET_SPRINT}
```

#### 2a.3 — Verify and extract

Read `{WORKDIR}/sprints.json`. Verify `target_sprint` is non-null. If null, stop: "Could not find sprint '{TARGET_SPRINT}'."

Extract:

- `SPRINT_ID` = `target_sprint.id`
- `SPRINT_START` = `target_sprint.start`
- `SPRINT_NAME` = `target_sprint.name`
- `SPRINT_NUM` = last digits from `target_sprint.name` (e.g., `"OCPEDGE Sprint 285"` → `285`)

---

### Phase 2b: Fetch Sprint Issues (inline)

#### 2b.1 — Fetch issues from Jira

Call `jira_search` with:

- **JQL:** `project in (OCPEDGE, USHIFT, OCPBUGS) AND sprint = {SPRINT_ID} ORDER BY priority ASC`
- **Fields:** `key, summary, description, status, issuetype, assignee, created, updated, labels, issuelinks, customfield_10028, parent, customfield_10014, customfield_10021, customfield_10470`
- **limit:** `50`

Paginate using `page_token` (see pagination protocol below). Note all persisted file paths.

#### 2b.2 — Run transform script

Write the sprint metadata to a file with the `Write` tool first (never interpolate the Jira sprint name into a shell command — it is attacker-influenced text):

`{WORKDIR}/sprint_issues.meta.json` = `{"sprint_id": {SPRINT_ID}, "sprint_name": <SPRINT_NAME as a JSON-escaped string>}`

JSON-encode `SPRINT_NAME` (a name containing `"` or `\` breaks the file otherwise) and confirm the metadata file parses as JSON before running the transform.

```bash
python3 plugins/edge-scrum/bin/transform-sprint-issues.py \
  --input <all_persisted_file_paths> \
  --output {WORKDIR}/sprint_issues.json \
  --sprint-meta {WORKDIR}/sprint_issues.meta.json \
  --today {TODAY}
```

#### 2b.3 — Verify

Read `{WORKDIR}/sprint_issues.json`. If `total_issues` is 0, warn: "Sprint {SPRINT_NAME} has no issues — analysis sections will be sparse." Proceed anyway.

---

### Phase 2c: Team Velocity (capacity mode only)

For `MODE = capacity`, compute the team's measured velocity — the average completed SP over the last 3 closed sprints (edge-context decision 0015). Skip this phase for mid-sprint and retro modes. If the data is unavailable, skip it and proceed; the capacity analyzer falls back to the roster-capacity figure and says so.

Write this run's velocity files to a fresh, uniquely named directory created with `mktemp -d`. Because the directory is new each run (a random suffix, no predictable path), there are no stale files for a glob to pick up and nothing to delete:

```bash
VELOCITY_DIR=$(mktemp -d "{WORKDIR}/velocity.XXXXXX") && echo "$VELOCITY_DIR"
```

Record `VELOCITY_DIR` and substitute it for `{VELOCITY_DIR}` below. It sits inside `{WORKDIR}`, so the end-of-run cleanup removes it with the rest of the run directory.

1. Read `{WORKDIR}/sprints.json` → `sprint_map`. Pick the three `closed` sprints with the highest `num` that is `< SPRINT_NUM` (the three most recent closed sprints before the target). Phase 2a transformed the board data **without** `--first-sprint`/`--last-sprint`, so `sprint_map` holds the full sprint history and no extra board call is needed. Record each sprint's `id`, `num`, and (if available) `start`/`end` (the sprint_map date keys), and collect the exact file path you write for each into `{VELOCITY_FILES}`.
2. For each of those sprint IDs, call `jira_search`:
   - **JQL:** `project in (OCPEDGE, USHIFT, OCPBUGS) AND sprint = {SPRINT_ID}`
   - **Fields:** `key, summary, status, issuetype, assignee, resolutiondate, customfield_10028, customfield_10470, customfield_10020`
   - **limit:** `50`, paginate with `page_token`.

   Write the sprint metadata to a file with the `Write` tool (never interpolate the Jira sprint name into a shell command):

   `{VELOCITY_DIR}/velocity_s{NUM}.meta.json` =
   `{"sprint_id": {SPRINT_ID}, "sprint_name": <SPRINT_NAME as a JSON-escaped string>, "sprint_start": <"YYYY-MM-DD" or null>, "sprint_end": <"YYYY-MM-DD" or null>}`

   JSON-encode `SPRINT_NAME` (a name containing `"` or `\` breaks the file otherwise) and use the bare JSON literal `null` for a missing date, never the string `"null"` (which `compute-velocity.py` would treat as a real date). Read the metadata file back and confirm it parses as JSON before running the transform; if it does not, skip this sprint's velocity contribution.

   Then run (pass the metadata file, not `--sprint-name`):

   ```bash
   python3 plugins/edge-scrum/bin/transform-sprint-issues.py \
     --input <all_persisted_file_paths> \
     --output {VELOCITY_DIR}/velocity_s{NUM}.json \
     --sprint-meta {VELOCITY_DIR}/velocity_s{NUM}.meta.json \
     --today {TODAY}
   ```

3. Compute velocity from the (up to) three sprint files. Pass the **exact** files you wrote in `{VELOCITY_FILES}` (space-separated, each under `{VELOCITY_DIR}`), never a `velocity_s*.json` glob:

   ```bash
   python3 plugins/edge-scrum/bin/compute-velocity.py \
     --sprint-issues {VELOCITY_FILES} \
     --roster plugins/edge-scrum/.roster.json \
     --output {VELOCITY_DIR}/velocity.json
   ```

   Velocity counts completed SP of **team-owned** issues (assignee or QA Contact on the roster, per law 00); bugs count like other work (decision 0003). A done issue is credited only to the sprint it finished in — the sprint with the latest end date among the sprints it belonged to (falling back to the highest sprint id, then its resolution date, when end dates are missing; Jira does not return the list in reliable order) — so a carried-over issue is not double-counted. The capacity analyzer reads `{VELOCITY_DIR}/velocity.json` if present.

---

### Pagination Protocol

This Jira instance uses `page_token` pagination, NOT `start_at`. Follow this protocol for all paginated MCP calls:

1. Make the first call without `page_token`
2. The response is persisted to a file. Note the file path.
3. Run `check-page.py` to get pagination info:

   ```bash
   python3 plugins/edge-scrum/bin/check-page.py <persisted_file_path>
   ```

   Output: `{"issues_count": N, "has_more": bool, "next_page_token": "..."}`
4. If `has_more` is `true`: make the next call with `page_token` set to the `next_page_token` value. Repeat from step 2.
5. If `has_more` is `false`: pagination is complete.

For `jira_get_sprints_from_board`: closed sprints may require multiple pages. Active and future typically fit in one page each.

---

### Phase 3: Mode-Specific Analysis (sub-agent)

Based on `MODE`, read the corresponding skill file, substitute placeholders, and spawn as a sub-agent.

**capacity:**

Read `plugins/edge-scrum/skills/sprint-health-capacity-analyzer/SKILL.md`. Substitute:

- `{WORKDIR}` → work directory path
- `{VELOCITY_DIR}` → velocity directory path from Phase 2c (holds `velocity.json` when it ran; if Phase 2c was skipped, substitute an empty value and the analyzer uses the roster fallback)
- `{TODAY}` → today's date
- `{SPRINT_START}` → sprint start date

**mid-sprint:**

Read `plugins/edge-scrum/skills/sprint-health-midpoint-analyzer/SKILL.md`. Substitute:

- `{WORKDIR}` → work directory path
- `{TODAY}` → today's date

**retro:**

Read `plugins/edge-scrum/skills/sprint-health-retro-analyzer/SKILL.md`. Substitute:

- `{WORKDIR}` → work directory path
- `{TODAY}` → today's date
- `{SPRINT_START}` → sprint start date
- `{SPRINT_ID}` → sprint ID integer

After the sub-agent completes, read `{WORKDIR}/analysis.md` to verify it was written successfully.

---

### Step 4: Generate Report

1. Read `{WORKDIR}/sprints.json` to get `target_sprint` values. Read `{WORKDIR}/sprint_issues.json` to get `total_sp` and `total_issues`.
2. Determine the capacity line:
   - If this run produced a velocity file (`{VELOCITY_DIR}/velocity.json`, capacity mode only) and it exists, read `team_velocity` and set
     `CAPACITY_LINE` = `Team velocity (last 3 sprints): {team_velocity} SP`.
   - Otherwise compute `total_roster_sp` = sum of all `sp_target` values in `.roster.json`
     and set `CAPACITY_LINE` = `{total_roster_sp} SP (roster fallback — velocity not measured)`.
3. Assemble the final report:

   a. Write this header:

   ```markdown
   # Sprint Health: {SPRINT_NAME}

   **Date**: {TODAY}
   **Mode**: {MODE}
   **Sprint**: {target_sprint.start} – {target_sprint.end} | {target_sprint.days_elapsed} of {target_sprint.total_days} days elapsed
   **Goal**: {target_sprint.goal or "Not set"}
   **Team**: {roster_size} members | {CAPACITY_LINE}
   **Committed**: {total_sp} SP across {total_issues} issues

   ---
   ```

   b. Append the body from `{WORKDIR}/analysis.md`, replacing each line that matches the pattern `===SECTION:<name>===` (any section name) with a blank line.

4. Write the assembled report to:

   ```text
   .reports/sprint_health_{SPRINT_NUM}_{MODE}_{TODAY}.md
   ```

5. Clean up:

   ```bash
   test -n "$WORKDIR" && [[ "$WORKDIR" == /tmp/sprint-health-* ]] && rm -rf -- "$WORKDIR"
   ```

---

## Edge Cases

- **No active sprint**: `transform-sprints.py` selects the highest-numbered closed sprint; report proceeds normally.
- **Empty sprint**: warn user, proceed — analysis sections will indicate no issues.
- **No sprint goal**: all three modes handle null goal gracefully — retro and mid-sprint note "No sprint goal set."
- **Unrostered assignees**: capacity analyzer lists them under "Unrostered assignees."
- **OCPBUGS issues**: included in queries; pointed and counted like other work per Laws (decision 0003).

---

## Important Notes

- **Read-only**: This skill does not modify any Jira data.
- **Transform scripts**: `plugins/edge-scrum/bin/` — reusable data transformation (no LLM needed)
- **Analysis sub-agents**: `plugins/edge-scrum/skills/sprint-health-*/SKILL.md` — LLM-driven analysis
- **Work directory**: cleaned up after each run; rerunning same day overwrites prior files.
- **Laws**: sub-agents read their required law files from `plugins/edge-scrum/references/laws/` (per the index in `references/Edge-Scrum-Laws.md`) — never hardcode rules here.
