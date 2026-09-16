# Job Manifest Template

Recommended columns:

```text
job_id
row_id
source_ref
to
subject
body
body_hash
status
draft_id
attempt_count
error
created_at
updated_at
```

Recommended status values:

```text
pending
sampled
done
skipped
failed
duplicate
deleted
```

Recommended uniqueness rules:

- default: `to + subject`
- stricter mode: `to + subject + body_hash`

Recommended batch bookkeeping:

- total_jobs
- completed_jobs
- failed_jobs
- duplicate_jobs
- missing_jobs
