# WF Index

`WF/` stores the sub-workflows used by the root runner `../WF_Int.md`.

Use `WF_Int.md` as the only default entry point. Edit the files in this folder only when a specific stage changes.

## Active Workflows

- `WF_Spec.md`: legacy spec compatibility notes.
- `L1-WF_x_kol_discovery_csv.md`: Layer1 X search and candidate normalization.
- `L2-WF_x_kol_enrichment_csv.md`: Layer2 profile enrichment and provider chunking.
- `L3-WF_x_kol_selection_csv.md`: Layer3 scoring and shortlist rules.
- `L3-WF_to-S2-cold-outreach-mapping.md`: L3 shortlist to S2 cold mapping and deliverables mirroring.
- `S2-WF_merge-deliverables-and-dm-3.2.md`: multi-batch S2 merge, org filtering, sorting, and 3.2 DM fill handoff.
- `L3-WF_to-S2-DM-fill.md`: legacy in-skill DM fill rules; superseded for 3.2 runs by the dedicated S2 Gmail bulk drafts workflow.
- `Lx-Field-Matrix_x_kol_csv.md`: field contracts across L1/L2/L3.

## Legacy

- `legacy/L3-WF_to-S1-inbox-mapping-full.md`: full historical L3 to S1 mapping doc.
- `../legacy/L3-WF_to-S1-inbox-mapping.md`: short legacy notice kept for compatibility.
