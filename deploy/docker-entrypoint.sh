#!/usr/bin/env bash
# Rockbase container entrypoint.
#
# Picks one Rockbase runtime role per container based on ROCKBASE_SERVICE:
#   console   -> authenticated operations workbench (HTTP 8790)
#   receiver  -> mailkit inbound HTTP receiver (mailgofer-compatible API)
#   pipeline  -> one-shot full Rockbase server pipeline (S1/S2/mailkit/S3/S5)
#   health    -> JSON health probe for supervisord / docker --health-cmd
#
# Default role is "console" for backward compatibility, but a real deployment
# should run one role per container and connect them via Compose / Kubernetes.
set -euo pipefail

ROLE="${1:-${ROCKBASE_SERVICE:-console}}"
EXTRA_ARGS=()
if [[ "${1:-}" == "${ROLE}" ]]; then
  shift
  EXTRA_ARGS=("$@")
fi
REPO="/opt/rockbase"
VENV="/opt/rockbase/.venv"

export PYTHONDONTWRITEBYTECODE=1
export PYTHONUNBUFFERED=1
export PYTHONPATH="${REPO}:${PYTHONPATH:-}"

# Business root layout: the master CSV lives directly next to a workbench/
# directory (csv_parent/workbench). S2 resolves its project root from cwd, so
# whoever runs the pipeline must cd to the CSV parent directory.
rockbase_prepare_workdir() {
  local csv="${ROCKBASE_MASTER_CSV:-}"
  [[ -z "${csv}" ]] && return 0
  local workdir
  workdir="$(dirname "${csv}")"
  mkdir -p "${workdir}/workbench" 2>/dev/null || true
}

cd "${REPO}"

case "${ROLE}" in
  console)
    rockbase_prepare_workdir
    exec "${VENV}/bin/python" -m console.server
    ;;
  receiver)
    : "${MAILKIT_DB_PATH:=/var/lib/rockbase/mailkit/mailkit.db}"
    : "${MAILKIT_RECEIVER_HOST:=0.0.0.0}"
    : "${MAILKIT_RECEIVER_PORT:=8788}"
    : "${MAILKIT_RECEIVER_API_KEY:=}"
    exec "${VENV}/bin/python" -m mailkit.mailkit.receiver \
      --db "${MAILKIT_DB_PATH}" \
      --host "${MAILKIT_RECEIVER_HOST}" \
      --port "${MAILKIT_RECEIVER_PORT}" \
      --api-key "${MAILKIT_RECEIVER_API_KEY}"
    ;;
  pipeline)
    : "${ROCKBASE_MASTER_CSV:?ROCKBASE_MASTER_CSV must point at the master CSV}"
    : "${ROCKBASE_MAILKIT_CONFIG:?ROCKBASE_MAILKIT_CONFIG must point at mailkit config.toml}"
    : "${ROCKBASE_PIPELINE_STATE:=/var/lib/rockbase/state/pipeline.json}"
    : "${ROCKBASE_PIPELINE_FETCH_OUT:=/var/lib/rockbase/workbench/replies-current}"
    : "${ROCKBASE_PIPELINE_DATE:=$(date -u +%Y-%m-%d)}"
    : "${ROCKBASE_PIPELINE_PLATFORM:=youtube}"
    : "${ROCKBASE_PIPELINE_RETRIES:=0}"
    PIPELINE_ARGS=(
      --csv "${ROCKBASE_MASTER_CSV}"
      --config "${ROCKBASE_MAILKIT_CONFIG}"
      --state "${ROCKBASE_PIPELINE_STATE}"
      --fetch-out "${ROCKBASE_PIPELINE_FETCH_OUT}"
      --date "${ROCKBASE_PIPELINE_DATE}"
      --platform "${ROCKBASE_PIPELINE_PLATFORM}"
      --retries "${ROCKBASE_PIPELINE_RETRIES}"
    )
    [[ "${ROCKBASE_PIPELINE_WITH_S1:-0}" == "1" ]] && PIPELINE_ARGS+=(--with-s1)
    [[ "${ROCKBASE_PIPELINE_S1_APPLY:-0}" == "1" ]] && PIPELINE_ARGS+=(--s1-apply)
    [[ "${ROCKBASE_PIPELINE_S2_WRITE:-0}" == "1" ]] && PIPELINE_ARGS+=(--s2-write)
    [[ "${ROCKBASE_PIPELINE_WITH_S5:-0}" == "1" ]] && PIPELINE_ARGS+=(--with-s5)
    [[ "${ROCKBASE_PIPELINE_S5_WRITE:-0}" == "1" ]] && PIPELINE_ARGS+=(--s5-write)
    [[ "${ROCKBASE_PIPELINE_EXECUTE_SEND:-0}" == "1" ]] && PIPELINE_ARGS+=(--execute-send)
    [[ "${ROCKBASE_PIPELINE_EXECUTE_SYNC:-0}" == "1" ]] && PIPELINE_ARGS+=(--execute-sync)
    if [[ -n "${ROCKBASE_PIPELINE_IMAGE_DIR:-}" ]]; then
      PIPELINE_ARGS+=(--image-dir "${ROCKBASE_PIPELINE_IMAGE_DIR}")
      PIPELINE_ARGS+=(--s5-engine "${ROCKBASE_PIPELINE_S5_ENGINE:-auto}")
    fi
    # The runner anchors S1/S2 to the CSV directory (workbench/ sibling)
    # itself; PYTHONPATH resolves `scripts` and installed packages from any cwd.
    exec "${VENV}/bin/python" -m scripts.run_full_pipeline "${PIPELINE_ARGS[@]}" "${EXTRA_ARGS[@]}"
    ;;
  health)
    : "${ROCKBASE_HEALTH_STATE:=/var/lib/rockbase/state/pipeline.json}"
    exec "${VENV}/bin/python" -m scripts.rockbase_health --state "${ROCKBASE_HEALTH_STATE}"
    ;;
  *)
    echo "unknown ROCKBASE_SERVICE='${ROLE}' (expected console|receiver|pipeline|health)" >&2
    exit 64
    ;;
esac