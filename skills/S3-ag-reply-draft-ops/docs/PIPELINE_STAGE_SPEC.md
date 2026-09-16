# Pipeline Stage Spec

## Purpose

This file only defines how reply drafting should read `Pipeline_Stage`.

It is not the source of truth for recovery logic.

## Standard Stages

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

## How Draft Ops Uses It

- `*_Replied_Review` means the row is a candidate for template mapping
- `*_Drafted` means a draft may already exist and should be checked before recreating
- `*_Waiting` means we are usually waiting for the other side
- `D1_Done` and `D2_Stop` should not enter new drafting runs
- `Z_Manual_Review` should not auto-draft unless the operator explicitly says so

## Guardrail

Template choice should not be derived from `Pipeline_Stage` alone.

Always combine:

- `Pipeline_Stage`
- `Reply_Stage`
- latest reply content
- pricing state
