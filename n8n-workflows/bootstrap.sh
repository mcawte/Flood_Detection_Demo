#!/bin/sh
set -e

if [ -d /workflows ]; then
  for wf in /workflows/*.json; do
    if [ -f "$wf" ]; then
      echo "[n8n] Importing workflow $wf"
      n8n import:workflow --input "$wf" || echo "[n8n] Warning: failed to import $wf"
    fi
  done
  echo "[n8n] Activating imported workflows"
  n8n update:workflow --all --active=true || echo "[n8n] Warning: failed to activate workflows"
else
  echo "[n8n] /workflows directory not found; skipping import"
fi

exec n8n start
