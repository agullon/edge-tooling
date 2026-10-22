# Edge Scrum Law: Stories, Spikes, and Tasks

> The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).
>
> **Canonical source:** edge-context [`procedures/scrum/story-pointing.md`](https://github.com/openshift-eng/edge-context/blob/main/procedures/scrum/story-pointing.md), [`procedures/refinement-checklists/stories.md`](https://github.com/openshift-eng/edge-context/blob/main/procedures/refinement-checklists/stories.md), [`procedures/refinement-checklists/spikes.md`](https://github.com/openshift-eng/edge-context/blob/main/procedures/refinement-checklists/spikes.md). If this file and edge-context disagree, edge-context is authoritative and this file must be updated.

## Issue Hierarchy

```text
Stories / Spikes / Bugs / Tasks
  └── Epics  (linked via the Parent field)
        └── Features / Initiatives  (linked via the Parent field)
```

- Stories and Spikes **MUST** link to an Epic via the **Parent** field before entering a sprint (edge-context story readiness checklist: "Parent (epic) is set"). (Jira Cloud replaced **Epic Link** with Parent; some skills still read the legacy `customfield_10014`.)
- Bugs **SHOULD** link to an Epic via the **Parent** field *when applicable* (edge-context bug checklist: "Parent (epic) set if applicable"). A bug triaged before a suitable epic exists is not non-compliant for lacking a parent.
- Epics link to a Feature or Initiative via the **Parent** field (RECOMMENDED, not REQUIRED; standalone epics may omit this).
- Stories without a parent epic are non-compliant.

**Types NOT used by this team:** Ticket, Subtask (enabled but excluded from scrum functions).

## Issue Types

| Type | Purpose | Sizing | PR Required |
|---|---|---|---|
| **Story** | Capability delivery from the user's perspective | Story Points (fibonacci) | Yes |
| **Spike** | Time-boxed research; ends with written stories or a new spike | Story Points (fibonacci) | No |
| **Task** | Finite piece of work; post-meeting follow-ups, action items | Story Points (fibonacci) | No |
| **Bug** | Error, flaw, or fault in software (see law 03) | Story Points (fibonacci) | Usually |

## Story Pointing

Story points use the **fibonacci sequence**: 0, 1, 2, 3, 5, 8, 13.

Points represent the fraction of a sprint's capacity consumed by the work item:

| Points | Meaning |
|---|---|
| 0 | Trivial; entered for transparency |
| 1 | < 25% of sprint capacity |
| 2 | 25–40% of sprint capacity |
| 3 | 40–60% of sprint capacity |
| 5 | 60–90% of sprint capacity |
| 8 | 90%+ of sprint capacity |
| 13 | Full sprint of dedicated focus — likely too big; split or create an Epic |

**Rules:**

- MUST be pointed by the **assignee**. This includes Bugs (edge-context decision 0003).
- No fixed per-person limit (edge-context decision 0015); ~8 SP per person is a soft guideline. Sprints are planned against team velocity.
- Repoint on assignee change as needed.

## Story Readiness

A Story is ready to enter a sprint when:

- **Parent** (epic) and **Assignee** are set.
- The description has **Acceptance Criteria** clear enough that "done" is not a judgment call, and a **Test Plan** (or a link to one).
- It has a single outcome; dependencies on other teams/components are called out; the affected git repo is identified (more than one repo usually means more than one story).
- **Story Points** are set by the assignee before the story enters an active sprint, including QE testing effort.
- **Priority** SHOULD match the parent epic and MUST NOT exceed it.

## Spike Sizing (Timebox)

Spike story points represent the **timebox**, not the complexity of the answer. A spike's description MUST state its completion criteria (questions to answer, artifacts to create).

| Points | Timebox |
|---|---|
| 1 | Half a day or less |
| 2 | About one day |
| 3 | Two to three days |
| 5 | Most of a sprint |
| 8 | Nearly a full sprint — narrow the question first |
