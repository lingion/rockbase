# Reply Stage Mapping Policy

## Purpose

This file defines how recovery-stage findings should map into operational pipeline stages.

## Layer 1. Reply_Stage

Recovery owns:

- `mail1_waiting_reply`
- `mail1_replied_waiting_mail2`
- `mail2_waiting_reply`
- `mail2_replied`
- `mail3_waiting_reply`
- `mail3_replied`
- `closed`
- `manual_review`

## Layer 2. Pipeline_Stage

Operational pipeline owns:

- `M1_1_Drafted`
- `M1_2_Waiting`
- `M1_3_Replied_Review`
- `M2_1_Drafted`
- `M2_2_Waiting`
- `M2_3_Replied_Review`
- `M3_1_Drafted`
- `M3_2_Waiting`
- `M3_3_Replied_Review`
- `D1_Done`
- `D2_Stop`
- `Z_Manual_Review`

## Default Mapping

- `mail1_waiting_reply` -> `M1_2_Waiting`
- `mail1_replied_waiting_mail2` -> `M1_3_Replied_Review`
- `mail2_waiting_reply` -> `M2_2_Waiting`
- `mail2_replied` -> `M2_3_Replied_Review`
- `mail3_waiting_reply` -> `M3_2_Waiting`
- `mail3_replied` -> `M3_3_Replied_Review`
- `closed` -> `D1_Done`
- `manual_review` -> `Z_Manual_Review`

## Guardrail

Recovery may initialize or refresh `Pipeline_Stage` only when the current value is blank or still in a waiting/drafted state.

Recovery should not aggressively overwrite:

- manually reviewed stages
- final stages
- operator-managed stop states
