#!/bin/bash
# Wächter für den GitHub-Runner auf dem Mac mini (siehe tests/MAC-MINI.md).
# Läuft vor jedem Job (ACTIONS_RUNNER_HOOK_JOB_STARTED in ~/actions-runner/.env,
# eingetragen von tests/mac-mini-setup.sh) und lässt nur Jobs aus diesem Repo zu,
# die per Push auf main oder von Hand (workflow_dispatch) gestartet wurden.
# Das Repo ist öffentlich: Ein Pull-Request kann die if:-Bedingung in
# .github/workflows/test.yml umschreiben, diese Datei auf dem Mac aber nicht.
# Die Datei wird nach ~/.config/halo-spaces/ kopiert, nicht aus dem Checkout benutzt.
REPO="sruf79/halo-spaces"

if [[ "$GITHUB_REPOSITORY" != "$REPO" ]]; then
  echo "Abgelehnt: Job aus $GITHUB_REPOSITORY – dieser Rechner testet nur $REPO"
  exit 1
fi
case "$GITHUB_EVENT_NAME" in
  push) [[ "$GITHUB_REF" == refs/heads/main ]] && exit 0 ;;
  workflow_dispatch) exit 0 ;;
esac
echo "Abgelehnt: $GITHUB_EVENT_NAME auf $GITHUB_REF – dieser Rechner nimmt nur Push auf main oder manuellen Start an"
exit 1
