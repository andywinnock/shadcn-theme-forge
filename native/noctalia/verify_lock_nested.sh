#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
native_bin="${repo_root}/out/native/noctalia-root/bin/noctalia"
parent_runtime="${XDG_RUNTIME_DIR:?XDG_RUNTIME_DIR is required}"
parent_display="${WAYLAND_DISPLAY:?WAYLAND_DISPLAY is required}"
hold_seconds="${1:-45}"
capture_path="${2:-/tmp/shadcn-nested-lock.png}"
theme_mode="${3:-dark}"

if [[ ! "${hold_seconds}" =~ ^[0-9]+$ ]] || ((hold_seconds < 1 || hold_seconds > 300)); then
  echo "hold time must be an integer from 1 to 300 seconds" >&2
  exit 2
fi
if [[ "${theme_mode}" != "dark" && "${theme_mode}" != "light" ]]; then
  echo "theme mode must be dark or light" >&2
  exit 2
fi
if [[ ! -x "${native_bin}" ]]; then
  echo "native Noctalia is not built: ${native_bin}" >&2
  exit 2
fi
if ! command -v niri >/dev/null; then
  echo "niri is required for isolated lock verification" >&2
  exit 2
fi

nested_runtime="$(mktemp -d /tmp/shadcn-nested-lock.XXXXXX)"
case "${nested_runtime}" in
  /tmp/shadcn-nested-lock.*) ;;
  *) echo "unexpected temporary directory: ${nested_runtime}" >&2; exit 2 ;;
esac
chmod 700 "${nested_runtime}"
mkdir -p "${nested_runtime}/config"
cp -a "${HOME}/.config/noctalia" "${nested_runtime}/config/noctalia"
printf 'hotkey-overlay { skip-at-startup }\n' >"${nested_runtime}/niri.kdl"

cleanup() {
  if [[ -n "${runner_pid:-}" ]]; then
    kill "${runner_pid}" 2>/dev/null || true
    wait "${runner_pid}" 2>/dev/null || true
  fi
  rm -rf -- "${nested_runtime}"
}
trap cleanup EXIT INT TERM

export SHADCN_NESTED_RUNTIME="${nested_runtime}"
export SHADCN_PARENT_RUNTIME="${parent_runtime}"
export SHADCN_PARENT_DISPLAY="${parent_display}"
export SHADCN_NATIVE_BIN="${native_bin}"
export SHADCN_HOLD_SECONDS="${hold_seconds}"
export SHADCN_CAPTURE_PATH="${capture_path}"
export SHADCN_THEME_MODE="${theme_mode}"

bash -c '
  set -euo pipefail
  export XDG_RUNTIME_DIR="${SHADCN_NESTED_RUNTIME}"
  export XDG_CONFIG_HOME="${SHADCN_NESTED_RUNTIME}/config"
  export XDG_STATE_HOME="${SHADCN_NESTED_RUNTIME}/state"
  export XDG_CACHE_HOME="${SHADCN_NESTED_RUNTIME}/cache"
  export XDG_DATA_HOME="${SHADCN_NESTED_RUNTIME}/data"
  export WAYLAND_DISPLAY="${SHADCN_PARENT_RUNTIME}/${SHADCN_PARENT_DISPLAY}"
  niri -c "${SHADCN_NESTED_RUNTIME}/niri.kdl" >"${SHADCN_NESTED_RUNTIME}/niri.log" 2>&1 &
  compositor_pid=$!
  for _attempt in {1..100}; do
    nested_socket="$(find "${SHADCN_NESTED_RUNTIME}" -maxdepth 1 -type s -name "wayland-*" -printf "%f\n" | head -1)"
    [[ -n "${nested_socket}" ]] && break
    sleep 0.1
  done
  if [[ -z "${nested_socket:-}" ]]; then
    sed -n "1,200p" "${SHADCN_NESTED_RUNTIME}/niri.log" >&2
    exit 1
  fi
  if ! kill -0 "${compositor_pid}" 2>/dev/null; then
    sed -n "1,200p" "${SHADCN_NESTED_RUNTIME}/niri.log" >&2
    exit 1
  fi

  export WAYLAND_DISPLAY="${nested_socket}"
  "${SHADCN_NATIVE_BIN}" >"${SHADCN_NESTED_RUNTIME}/noctalia.log" 2>&1 &
  noctalia_pid=$!
  sleep 4
  if ! kill -0 "${noctalia_pid}" 2>/dev/null; then
    sed -n "1,200p" "${SHADCN_NESTED_RUNTIME}/niri.log" >&2
    sed -n "1,200p" "${SHADCN_NESTED_RUNTIME}/noctalia.log" >&2
    exit 1
  fi
  "${SHADCN_NATIVE_BIN}" msg theme-mode-set "${SHADCN_THEME_MODE}" >/dev/null
  if ! "${SHADCN_NATIVE_BIN}" msg session lock >"${SHADCN_NESTED_RUNTIME}/lock.log" 2>&1; then
    sed -n "1,200p" "${SHADCN_NESTED_RUNTIME}/niri.log" >&2
    sed -n "1,200p" "${SHADCN_NESTED_RUNTIME}/noctalia.log" >&2
    sed -n "1,80p" "${SHADCN_NESTED_RUNTIME}/lock.log" >&2
    exit 1
  fi
  sleep 2
  if ! XDG_RUNTIME_DIR="${SHADCN_PARENT_RUNTIME}" WAYLAND_DISPLAY="${SHADCN_PARENT_DISPLAY}" \
      grim "${SHADCN_CAPTURE_PATH}"; then
    sed -n "1,200p" "${SHADCN_NESTED_RUNTIME}/niri.log" >&2
    sed -n "1,200p" "${SHADCN_NESTED_RUNTIME}/noctalia.log" >&2
    sed -n "1,80p" "${SHADCN_NESTED_RUNTIME}/lock.log" >&2
    exit 1
  fi
  echo "NESTED_LOCK_READY"
  sleep "${SHADCN_HOLD_SECONDS}"
  kill "${noctalia_pid}" "${compositor_pid}" 2>/dev/null || true
  wait "${noctalia_pid}" "${compositor_pid}" 2>/dev/null || true
' &
runner_pid=$!
wait "${runner_pid}"
runner_pid=""
