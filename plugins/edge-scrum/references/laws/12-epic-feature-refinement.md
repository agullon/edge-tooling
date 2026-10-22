# Edge Scrum Law: Epic and Feature Refinement

> The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).
>
> **Canonical source:** edge-context [`procedures/refining-epics.md`](https://github.com/openshift-eng/edge-context/blob/main/procedures/refining-epics.md), [`procedures/refining-features-and-initiatives.md`](https://github.com/openshift-eng/edge-context/blob/main/procedures/refining-features-and-initiatives.md), [`procedures/refinement-checklists/epics.md`](https://github.com/openshift-eng/edge-context/blob/main/procedures/refinement-checklists/epics.md), [`procedures/refinement-checklists/features-and-initiatives.md`](https://github.com/openshift-eng/edge-context/blob/main/procedures/refinement-checklists/features-and-initiatives.md), [`procedures/refinement-checklists/spikes.md`](https://github.com/openshift-eng/edge-context/blob/main/procedures/refinement-checklists/spikes.md). If this file and edge-context disagree, edge-context is authoritative and this file must be updated.

## Epic Refinement Process

**Assignee** is responsible for getting an epic from Planning → To Do.

1. **Set baseline fields:**
   - **Assignee** and **Target Version**.
   - **Parent**: the related OCPSTRAT Feature/Initiative (standalone epics MAY omit it).
   - **Epic Name**: concise, 30–50 characters (shown on boards for child issues).
   - **Component**: one of the workstream components in law 01; if none fit, ask the Team Lead.
   - **Labels**: `ocpedge-plan` only if the epic has no parent and lives outside OCPEDGE; `4.x-candidate`/`5.x-candidate` if it has no initiative or spans releases.
   - **QA Contact**, **Doc Contact** (see below) and **Size**.
2. **Fill out epic description** using the standard template (goal, dependencies, completion criteria).
3. **Create stories:** Either directly (if implementation is clear) or via a refinement spike to allocate sprint capacity for investigation. If a spike is used, the epic's parent Feature is not considered refined until the spike is done. Every child issue MUST have its **Parent** set to the epic.
4. Move epic to **To Do** when steps 1–3 are complete.

**QA Contact:** If no QE is needed, MUST set to `unassigned_jira`. MUST NOT leave blank. If QE is needed, a test strategy document (IEEE 829 format, markdown) is contributed to edge-context and linked from the epic.  
**Doc Contact:** If no docs are needed, MUST set to `unassigned_jira`. MUST NOT leave blank.

## Feature / Initiative Refinement (SME Process)

The **SME** role is responsible for feature refinement. Assigned during release planning.

1. **Verify feature details:** status is **Refinement** (do not refine Features in New); Product Manager, Architect, SME, Assignee, QA Contact (QE Lead) and Docs Contact are set; description has a clear goal.
2. **Create a refinement Spike** in OCPEDGE. Set component to match the feature. Spike MUST have a "blocks" relationship to the Feature/Initiative.
3. **Create a test plan Spike** in OCPEDGE, owned by the **QE Lead** (the Feature's QA Contact). Component matches the feature; MUST have a "blocks" relationship to the Feature/Initiative.
4. **Spike completion criteria:** Refinement spike — all open questions answered, all dependencies identified, enough knowledge to write implementation stories. Test plan spike — test approach documented, QE effort and environment/tooling needs identified.
5. **After both spikes:** Create deliverable Epics (the Feature MUST contain at least one epic, and only epics required for it to complete). Leave a comment on the Feature/Initiative summarizing both spikes and stating it's ready for "Backlog"; the **PM** moves it. If the work is not feasible in one release, capture findings and escalate to the Team Lead and PM.

**Important:** Features SHOULD only contain epics that are **required** for the feature to complete. Optional or nice-to-have epics belong in an Initiative or as standalone epics.

## Implicit Refinement via Epics

A Feature with no child epics is considered **not refined** — there is no epic-level signal to assess. A Feature MAY be considered refined without a direct refinement spike when any of the following hold:

1. **Spike on epic**: A refinement spike in the refinement sprint blocks one of the Feature's child epics (rather than the Feature itself).
2. **Epics past Planning**: All child epics have moved past the **Planning** state, indicating that refinement happened at the epic level without a formal spike.
3. **Stories cover described work**: Each child epic's description outlines work to be done and the child stories/tasks already created under it appear to cover that described scope. This is an LLM-assessed judgment, not a mechanical check.

In all cases, agents SHOULD treat the Feature as refined (no spike-related risk). The preferred process is still to create a spike that blocks the Feature directly, but these alternatives are recognized as valid evidence of completed refinement.

These implicit signals apply to the **refinement spike only**. The **test plan spike** (step 3 of the SME process above — owned by the QE Lead; see edge-context [`roles/qe-lead.md`](https://github.com/openshift-eng/edge-context/blob/main/roles/qe-lead.md)) is still expected whenever the Feature has a QA Contact, and is **not** satisfied by refined epics or an epic-level spike. Assess it separately; skip it only when the Feature's QA Contact is `unassigned_jira`.

**Exception:** If the Feature's own status is **New** or **Refinement**, these implicit signals do not apply. The Feature's workflow state is authoritative — a Feature explicitly in Refinement is not refined regardless of its epics' state.
