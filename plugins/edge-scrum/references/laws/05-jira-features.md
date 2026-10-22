# Edge Scrum Law: Features and Initiatives

> The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).
>
> **Canonical source:** edge-context [`procedures/refining-features-and-initiatives.md`](https://github.com/openshift-eng/edge-context/blob/main/procedures/refining-features-and-initiatives.md), [`procedures/refinement-checklists/features-and-initiatives.md`](https://github.com/openshift-eng/edge-context/blob/main/procedures/refinement-checklists/features-and-initiatives.md). If this file and edge-context disagree, edge-context is authoritative and this file must be updated.

## Issue Types

| Type | Purpose | Sizing | PR Required |
|---|---|---|---|
| **Feature** | Tangible value delivered to customers within a release | T-shirt size | N/A |
| **Initiative** | Architectural or improvement work; no direct customer deliverable | T-shirt size | N/A |

## Feature / Initiative Sizing (T-shirt)

| Size | Expected Duration |
|---|---|
| XS | < 30% of release (~2 dev sprints) — consider using an Epic |
| S | 30–60% of release (~2–3 dev sprints) |
| M | 60–90% of release (~3–4 dev sprints) |
| L | 90%+ of release (~4+ dev sprints) |
| XL | Entire release (~5 full dev sprints) — likely too big; split or create an Outcome |

## Feature / Initiative Workflow States

| State | Meaning |
|---|---|
| New | Created; not yet committed work |
| Refinement | SME is investigating; refinement spike in progress |
| Backlog | Refinement complete; epics created; ready to be worked |
| In Progress | Active development underway |
| Release Pending | Work complete; waiting for the release to ship |
| Closed | Acceptance criteria met |

Features in **New** state are **not a commitment** of work.

## Feature Scope

Features SHOULD only contain epics that are **required** for the feature to complete. Optional or nice-to-have epics belong in an Initiative or as standalone epics.

Features and Initiatives live in the `OCPSTRAT` project. A Feature/Initiative belongs to the team when it has the label `ocpedge-plan` or `microshift`. The `edge` label alone is not sufficient — it must be paired with one of these.

A Feature/Initiative is targeted for a release by its **Target Version** (`customfield_10855`), which must include `openshift-{X.Y}` (e.g., `openshift-5.0`).
