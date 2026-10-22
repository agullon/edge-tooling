# Edge Scrum Law: Key Roles

> The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).
>
> **Canonical source:** edge-context [`roles/`](https://github.com/openshift-eng/edge-context/blob/main/roles/). If this file and edge-context disagree, edge-context is authoritative and this file must be updated.

## SME

Engineering lead for a Feature/Initiative. Responsible for refinement, understanding desired outcomes, and raising questions with PM.

## QE Lead

Equal to the **QA Contact** on a Feature/Initiative. Owns the test plan spike, executes the test plan, and represents quality during feature refinement. Any role on the team can fill it.

## QE Workstream Lead

Quality counterpart to the Team Lead in a workstream's leadership triad (Manager, Team Lead, QE Workstream Lead). Owns the workstream's quality strategy and is the QA Contact for bugs triaged in the workstream.

## Epic Assignee

Accountable for epic refinement into deliverable stories, story pointing, sprint planning, and maintaining accurate epic description.

## Scrum Master

Operational role. Leads all sprint ceremonies; ensures 100% of sprint stories are SP'd; ensures 100% of epics are sized; ensures the sprint is reasonably committed according to historical delivery patterns; manages Jira dashboards, filters, and automations; unblocks Jira workflow issues.

## Team Lead

Technical role. Drives architectural alignment; advises on release backlog ranking; ensures bugs are triaged; monitors CI; responsible for at least one component lead role in OCPBUGS.

## OCP Payload Manager (Rotational)

Sprintly rotation keeping Edge CI healthy across OCP payloads so SNO/TNA/TNF don't block releases.

**Daily:** Review the Edge OCP CI Monitor dashboard; attend the TRT standup with findings; file or update Jira tickets for blocking failures (within 1 business day).

**Weekly:** Review Component Readiness regressions (HA vs edge topologies), e.g. with `ci-tooling/readiness-report` (`go run ./cmd -release <ver> -format md -untriaged`); attend the Payload Manager Sync; escalate blockers persisting 3+ payloads.

**Sprintly:** Run the transition runbook with the next person and update the `openshift-edge-payload-manager` Slack alias.

## MicroShift Payload Manager (Rotational)

Sprintly developer rotation, tracked by a per-sprint Jira task; the role is the holder's main priority for the sprint. Reviews the daily CI Doctor report, keeps the main-branch rebase landing by the end of every sprint, verifies EC/RC builds reach the mirror, resolves payload-blocking job failures within 4 hours, and leads emergency response.
