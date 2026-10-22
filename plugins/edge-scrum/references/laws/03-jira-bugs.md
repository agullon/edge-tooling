# Edge Scrum Law: Bugs

> The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).
>
> **Canonical source:** edge-context [`procedures/triaging-bugs.md`](https://github.com/openshift-eng/edge-context/blob/main/procedures/triaging-bugs.md), [`procedures/refinement-checklists/bugs-and-vulnerabilities.md`](https://github.com/openshift-eng/edge-context/blob/main/procedures/refinement-checklists/bugs-and-vulnerabilities.md). If this file and edge-context disagree, edge-context is authoritative and this file must be updated.

## Bug Issue Type

| Type | Purpose | Sizing | PR Required |
|---|---|---|---|
| **Bug** | Error, flaw, or fault in software | Story points (fibonacci), like other work (edge-context decision 0003) | Usually yes |

Bugs are pointed like Stories, Spikes, and Tasks (see law 02). The assignee sets the points before the bug enters an active sprint.

## OCPBUGS Project

The team owns these components in OCPBUGS:

- `Installer / Single Node OpenShift`
- `Two Node with Arbiter`
- `Two Node Fencing`
- `Logical Volume Manager Storage`

LVMS bugs: MUST set Release Blocker to **Rejected**. LVMS does not block OCP releases.

MicroShift bugs: MicroShift-only bugs MUST set Release Blocker to **Rejected**. MicroShift bugs that also affect OCP components: assess during triage and set **Proposed** if potentially blocking.

LVMS bugs do **not** automatically transition from MODIFIED to ON_QA via ART automation. Engineers MUST move LVMS bugs manually.

## Bug Workflow States

| State | Meaning |
|---|---|
| NEW | Reported; not yet triaged |
| ASSIGNED | Triaged; being actively worked (equivalent to In Progress) |
| MODIFIED | Fix merged; awaiting QA |
| ON_QA | In QA verification |
| Verified | QA confirmed fix |
| Closed | Complete |

## OCPBUGS PR Title Format

PR titles MUST follow this format to trigger Jira status automation:

```text
OCPBUGS-<number>: <description>
```

Example: `OCPBUGS-12345: Fix SNO boot failure on low-memory nodes`
