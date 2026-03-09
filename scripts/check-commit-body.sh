#!/usr/bin/env bash
# Enforce that commit body lines (if present) start with "- "
set -euo pipefail

commit_msg_file="${1}"
commit_msg=$(cat "${commit_msg_file}")

# Strip comment lines, then split into subject / body
body=$(echo "${commit_msg}" | grep -v '^#' | tail -n +3)

if [ -z "${body}" ]; then
    exit 0
fi

while IFS= read -r line; do
    [ -z "${line}" ] && continue  # skip blank lines
    if [[ ! "${line}" =~ ^-\  ]]; then
        echo "Commit body lines must start with '- '"
        echo "  Offending line: ${line}"
        exit 1
    fi
done <<< "${body}"
