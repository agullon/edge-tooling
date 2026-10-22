# Edge Scrum Law: Jira Projects

> The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).
>
> **Canonical source:** edge-context [`procedures/jira-reference.md`](https://github.com/openshift-eng/edge-context/blob/main/procedures/jira-reference.md), [`about/workstreams.md`](https://github.com/openshift-eng/edge-context/blob/main/about/workstreams.md). If this file and edge-context disagree, edge-context is authoritative and this file must be updated.

## Projects

| Key | Purpose |
|---|---|
| `OCPEDGE` | Primary project: all team stories, bugs, spikes, tasks, and epics |
| `OCPBUGS` | Secondary bugs project; team owns: `Installer / Single Node OpenShift`, `Two Node with Arbiter`, `Two Node Fencing`, `Logical Volume Manager Storage` |
| `OCPSTRAT` | Features and Initiatives for the release cycle; team ownership identified by labels `ocpedge-plan` or `microshift` |
| `USHIFT` | MicroShift feature and bug tracking (issues rolled into board in OCPEDGE; no dedicated scrum board) |

## Labels

All team labels SHOULD use the `OCPEDGE:` namespace prefix.

| Label | Usage |
|---|---|
| `ocpedge-plan` | Apply to Outcome, Feature, or Epic. Recursively adds labeled work to the Jira Plan (backlog). Also identifies OCPSTRAT issues as team-owned. |
| `microshift` | Identifies OCPSTRAT issues as team-owned (MicroShift workstream). |
| `edge` | General edge label. **Not sufficient alone** for team ownership — requires `ocpedge-plan` or `microshift` alongside it. |
| `ocpedge` | Apply at Epic and Story level. **Only needed for work outside the OCPEDGE project.** |
| `no_core_payload` | Work for a component that ships outside the OpenShift core payload (e.g. LVMS, MicroShift). Informs release-blocker handling and payload reporting. |
| `4.x-candidate` / `5.x-candidate` | Apply to an Epic (matching its Target Version) when it has no parent Initiative/Feature or the parent spans multiple releases. |
| `OCPEDGE:Docs` | Doc-specific tasks |
| `OCPEDGE:QE` | QE-specific tasks |
| `OCPEDGE:RHEL-Verification` | RHEL ticket verification tasks for TNF |
| `OCPEDGE:CI` | CI-affecting bugs; CI automation outside Payload Manager duties |
| `OCPEDGE:Payload-Manager` | Work done as part of Payload Manager duties |
| `OCPEDGE:Tooling` | Team tooling improvements (e.g., edge-tooling repo) |
| `OCPEDGE:Scrum` | Scrum process improvements or scrum-related automation |

## Components (Workstreams)

Components have a 1-to-1 correlation with workstreams. Use these exactly:

- `MicroShift`
- `Two Node with Arbiter`
- `Two Node with Fencing`
- `SNO`
- `Logical Volume Manager Storage`
- `Bandwidth Reduction`
- `Topology Transition` (covers MicroShift-to-SNO and Adaptable Topology)

Work outside these workstreams uses a scoped label instead of a component.

## Jira Filters (Target State)

| Filter | Type | Purpose |
|---|---|---|
| OpenShift Edge - Scrum Board | Core | Top-of-funnel; drives the scrum board |
| OpenShift Edge - Core Backlog | Core | All OCPEDGE and USHIFT backlog items |
| OpenShift Edge - External Projects | Core | Work in external Jira projects |
| OpenShift Edge - Bugs and CVEs | Core | Bugs and CVEs from OCPEDGE, USHIFT, OCPBUGS |
| OpenShift Edge - Team Assigned | Utility | Limits results to team members |
| OpenShift Edge - QE Assigned | Utility | Issues in QA state with a team member as QA contact |
| OpenShift Edge - Labels | Utility | Issues with any team-relevant label |
| OpenShift Edge - Components | Utility | Issues with any team-relevant component |
| OpenShift Edge Workstream - SNO | Utility | SNO-scoped issues |
| OpenShift Edge Workstream - TNA | Utility | Two Node Arbiter-scoped issues |
| OpenShift Edge Workstream - TNF | Utility | Two Node Fencing-scoped issues |
| OpenShift Edge Workstream - MicroShift | Utility | MicroShift-scoped issues |
| OpenShift Edge Workstream - LVMS | Utility | LVMS-scoped issues |
| OpenShift Edge Workstream - Adaptable Topology | Utility | NextGen Adaptable Topology issues |
| OpenShift Edge Workstream - MicroShift to SNO | Utility | NextGen MicroShift to SNO issues |
| OpenShift Edge Workstream - Bandwidth Reduction | Utility | Bandwidth Reduction issues |
