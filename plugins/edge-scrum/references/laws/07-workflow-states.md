# Edge Scrum Law: Workflow States

> The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).
>
> **Canonical source:** edge-context [`procedures/refining-epics.md`](https://github.com/openshift-eng/edge-context/blob/main/procedures/refining-epics.md), [`procedures/refining-features-and-initiatives.md`](https://github.com/openshift-eng/edge-context/blob/main/procedures/refining-features-and-initiatives.md), [`procedures/triaging-bugs.md`](https://github.com/openshift-eng/edge-context/blob/main/procedures/triaging-bugs.md). If this file and edge-context disagree, edge-context is authoritative and this file must be updated.

## Feature / Initiative States

| State | Meaning |
|---|---|
| New | Created; not yet committed work |
| Refinement | SME is investigating; refinement spike in progress |
| Backlog | Refinement complete; epics created; ready to be worked |
| In Progress | Active development underway |
| Release Pending | Work complete; waiting for the release to ship |
| Closed | Acceptance criteria met |

Features in **New** state are not a commitment of work.

**Done states:** `Release Pending`, `Closed`

## Epic States

| State | Meaning |
|---|---|
| New | Created; refinement not started |
| Planning | Being refined; stories not yet created |
| To Do | Refinement done; ready for sprint planning |
| In Progress | Stories being actively worked |
| Dev Complete | All implementation PRs merged (docs/QE/CI stories MAY still be open) |
| Testing | QE verification of the delivered work |
| Release Pending | Work complete; waiting for the release to ship |
| Closed | All acceptance criteria met |

When an Epic transitions to **Dev Complete**, MUST set the **Fix Version**.  
**Target Version** SHOULD be set during refinement (before **To Do**) and MUST be set by **In Progress**.  
The **Epic Status** field MUST be set to **Done** when closed (handled by Jira automation).

**Done states:** `Dev Complete`, `Testing`, `Release Pending`, `Closed`

## Story / Spike / Task States

| State | Meaning |
|---|---|
| To Do | Ready to be worked; in a sprint |
| In Progress | Actively being worked |
| Review | PR open; waiting for review/merge |
| Closed | Done; acceptance criteria met |

**Done states:** `Closed`

## Bug States (OCPEDGE)

| State | Meaning |
|---|---|
| To Do | Ready to be worked; in a sprint |
| In Progress | Actively being worked |
| Review | PR open; waiting for review/merge |
| Closed | Done; acceptance criteria met |

**Done states:** `Closed`

## Bug States (OCPBUGS)

| State | Meaning |
|---|---|
| NEW | Reported; not yet triaged |
| ASSIGNED | Triaged; being actively worked (equivalent to In Progress) |
| MODIFIED | Fix merged; awaiting QA |
| ON_QA | In QA verification |
| Verified | QA confirmed fix |
| Closed | Complete |

Bugs closed without story points are auto-set to 0 by automation.

**Note:** LVMS bugs do **not** automatically transition from MODIFIED to ON_QA via ART automation. Engineers MUST move LVMS bugs manually.

**Done states:** `Verified`, `Closed`
