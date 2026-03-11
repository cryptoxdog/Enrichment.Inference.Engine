#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
ERRORS=0

echo "═══════════════════════════════════════════════════════════════"
echo "  Enrichment API — Manifest Validation"
echo "═══════════════════════════════════════════════════════════════"

# ── Kustomize build validation ───────────────────────────────
for overlay in dev staging production; do
    DIR="${ROOT_DIR}/kustomize/overlays/${overlay}"
    if [[ -d "$DIR" ]]; then
        if kustomize build "$DIR" > /dev/null 2>&1; then
            echo "  ✅ kustomize build overlays/$overlay"
        else
            echo "  ❌ kustomize build overlays/$overlay FAILED"
            ERRORS=$((ERRORS + 1))
        fi
    fi
done

# ── Helm lint ────────────────────────────────────────────────
CHART="${ROOT_DIR}/helm/enrichment-api"
if [[ -d "$CHART" ]]; then
    if helm lint "$CHART" > /dev/null 2>&1; then
        echo "  ✅ helm lint enrichment-api"
    else
        echo "  ❌ helm lint FAILED"
        ERRORS=$((ERRORS + 1))
    fi

    for env in dev staging; do
        VALUES="${CHART}/values-${env}.yaml"
        if [[ -f "$VALUES" ]]; then
            if helm template test "$CHART" -f "$VALUES" > /dev/null 2>&1; then
                echo "  ✅ helm template (values-${env})"
            else
                echo "  ❌ helm template (values-${env}) FAILED"
                ERRORS=$((ERRORS + 1))
            fi
        fi
    done
fi

# ── kubeval (if installed) ───────────────────────────────────
if command -v kubeval &>/dev/null; then
    for overlay in dev staging production; do
        DIR="${ROOT_DIR}/kustomize/overlays/${overlay}"
        if [[ -d "$DIR" ]]; then
            if kustomize build "$DIR" | kubeval --strict > /dev/null 2>&1; then
                echo "  ✅ kubeval overlays/$overlay"
            else
                echo "  ⚠️  kubeval overlays/$overlay (warnings)"
            fi
        fi
    done
else
    echo "  ⚠️  kubeval not installed — skipping schema validation"
fi

echo ""
if [[ $ERRORS -eq 0 ]]; then
    echo "  ✅ All validations passed"
else
    echo "  ❌ $ERRORS validation(s) failed"
    exit 1
fi
