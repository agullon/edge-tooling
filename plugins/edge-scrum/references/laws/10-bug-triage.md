# Edge Scrum Law: Bug Triage

> The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).
>
> **Canonical source:** edge-context [`procedures/triaging-bugs.md`](https://github.com/openshift-eng/edge-context/blob/main/procedures/triaging-bugs.md), [`procedures/refinement-checklists/bugs-and-vulnerabilities.md`](https://github.com/openshift-eng/edge-context/blob/main/procedures/refinement-checklists/bugs-and-vulnerabilities.md). If this file and edge-context disagree, edge-context is authoritative and this file must be updated.

**Goal:** Move a bug from `NEW` to `ASSIGNED` (i.e., triaged and being worked) or determine next steps (reassign, close).

## Step 1: Check required fields

- **Severity** — SHOULD be set by reporter; estimate if missing.
- **Component(s)** — set.
- **Assignee** — set to the person who will do the work.
- **QA Contact** — set to the workstream's QE Workstream Lead (see edge-context `about/workstreams.md`); no longer set automatically in Jira Cloud.
- **Docs Contact** — set.
- **Parent** (epic) — set if applicable.
- **Priority** — set by triager; reflects engineering view of importance (does not need to match severity).
- **Affects Version** — all versions where the bug is known to exist.
- **Release Blocker**:
  - LVMS bugs: MUST be **Rejected** (LVMS does not block OCP releases).
  - SNO/TNA/TNF bugs: assess during triage; set to Proposed if potentially blocking.
  - MicroShift bugs: MicroShift-only MUST be **Rejected**; if OCP components are also affected, assess and set Proposed if potentially blocking.

## Step 2a: LVMS bugs

MUST require a must-gather at minimum (confirms deployment topology and LVMS CRs).

## Step 2b: SNO / TNA / TNF bugs

MUST require a must-gather; sosreport MAY be needed for OS-level issues. Verify the issue is actually topology-specific before accepting the bug.

## Step 2c: MicroShift bugs

MUST require a must-gather and a sosreport.

## Step 3: Working the bug

- SHOULD set **Affects Version** to every version where the bug is confirmed, not only the reported one.
- MUST set **Target Version** (e.g., `4.16.0` — use full y.z.0, not `4.16`).
- Decide with the QE Lead whether QE is needed; if both agree it is not, add the `no-qe` label.
- SHOULD set **Target Backport Versions** after consulting reporter and PM; minimize unnecessary backports.
- MUST include the bug number in the PR title: `OCPBUGS-12345: Fix description`. This triggers Jira automation to update bug status as the PR progresses.

Bugs of sufficient severity, priority, or that block a release are pulled into the sprint and take priority over other work.
