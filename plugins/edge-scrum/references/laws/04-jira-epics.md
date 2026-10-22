# Edge Scrum Law: Epics

> The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).
>
> **Canonical source:** edge-context [`procedures/refining-epics.md`](https://github.com/openshift-eng/edge-context/blob/main/procedures/refining-epics.md), [`procedures/refinement-checklists/epics.md`](https://github.com/openshift-eng/edge-context/blob/main/procedures/refinement-checklists/epics.md). If this file and edge-context disagree, edge-context is authoritative and this file must be updated.

## Epic Issue Type

| Type | Purpose | Sizing | PR Required |
|---|---|---|---|
| **Epic** | Extra-large work bucket spanning multiple sprints | T-shirt size | N/A |

## Epic Sizing (T-shirt)

| Size | Expected Duration |
|---|---|
| XS | ~1 sprint (consider using a Story instead) |
| S | ~2 sprints |
| M | ~3 sprints |
| L | ~4 sprints |
| XL | ~5 sprints (likely too big; split or create a Feature/Initiative) |

## Epic Workflow States

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
**Target Version** SHOULD be set during refinement (before **To Do**) and MUST be set by **In Progress**. Jira automation reminds the assignee when an epic enters In Progress without one.  
The **Epic Status** field MUST be set to **Done** when closed (handled by Jira automation).

## Epic Ownership

Stories without a parent epic are non-compliant. See law 12 for the full epic readiness checklist. Telco-relevant epics MUST have the **Market Portfolio** field set at the epic level to appear on Telco dashboards.
