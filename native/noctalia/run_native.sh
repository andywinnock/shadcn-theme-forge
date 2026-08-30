#!/usr/bin/env bash
set -u

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
native_bin="${repo_root}/out/native/noctalia-root/bin/noctalia"
system_bin="/usr/bin/noctalia"

if [[ -x "${native_bin}" ]] \
  && "${native_bin}" --version >/dev/null 2>&1 \
  && "${native_bin}" config validate >/dev/null 2>&1; then
  exec "${native_bin}" "$@"
fi

echo "warning: native Noctalia unavailable or invalid; using ${system_bin}" >&2
exec "${system_bin}" "$@"
