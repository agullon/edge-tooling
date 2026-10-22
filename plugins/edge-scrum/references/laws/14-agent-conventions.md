# Edge Scrum Law: Jira Conventions for Agents

> The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).
>
> **Canonical source:** this file. These conventions are specific to automated agents and are maintained here; the team rules they reference come from edge-context.

- **Issue ownership:** An issue belongs to the team if the assignee **or** QA Contact (`customfield_10470`) is a roster member.
- **Bugs are pointed like other work** (edge-context decision 0003); suggest points for bugs just as for stories.
- **Epics use T-shirt sizes**, not SP. Stories/Spikes/Tasks/Bugs use SP.
- **Target version format:** MUST always use `4.x.0` (e.g., `4.16.0`) or `5.x.0`. MUST NOT use `4.x` or `5.x` alone.
- **LVMS bugs:** MUST NOT set Release Blocker to anything other than "Rejected".
- **Backlog entry point:** Apply `ocpedge-plan` label to Outcomes, Features, or Epics to include them in the Jira Plan.
- **OCPBUGS PR title format:** `OCPBUGS-<number>: <description>` — REQUIRED to trigger status automation.
- **Epic Status field:** Does not auto-update on closure. The team has automation for this — MUST NOT manually change unless directed.
- **Automation actor:** MUST use "Automation for Jira" as the rule Actor (not personal accounts or bot accounts) for new automation rules.
- **Sprint planning target:** team velocity (avg completed SP over the last 3 closed sprints), not a per-person cap (edge-context decision 0015). ~8 SP per person is a soft guideline; use it to flag far-above/far-below load, not as a limit.
- **Stories without a parent epic** are non-compliant with team conventions. Flag these during grooming.
- **Telco-relevant epics** MUST have the **Market Portfolio** field set at the epic level to appear on Telco dashboards.
- **Identifying a test plan spike:** among the spikes that block a Feature, a spike is a **test plan spike** when its summary contains "test plan" (case-insensitive) **or** its assignee is the Feature's QA Contact / QE Lead (compare display names, normalized). Otherwise it is a **refinement spike**. The refinement-spike refinement signals (law 12) are satisfied by refinement spikes only — a test plan spike never satisfies them, and vice versa. Skip the test plan spike check entirely when the Feature's QA Contact is `unassigned_jira` (no QE Lead, so none is expected).
