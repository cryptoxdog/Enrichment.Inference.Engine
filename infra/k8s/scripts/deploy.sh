#!/usr/bin/env bash
set -euo pipefail

# ═══════════════════════════════════════════════════════════════
# Enrichment API — Universal Deploy Script
# Usage: ./deploy.sh [dev|staging|production] [helm|kustomize]
# ═══════════════════════════════════════════════════════════════

ENV="${1:-dev}"
METHOD="${2:-kustomize}"
NAMESPACE="enrichment"
RELEASE_NAME="enrichment-api"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  Enrichment API v2.2.0 — Deploy                            ║"
echo "║  Environment: ${ENV}                                        "
echo "║  Method:      ${METHOD}                                     "
echo "╚══════════════════════════════════════════════════════════════╝"

# ── Pre-flight checks ────────────────────────────────────────
check_tool() {
    if ! command -v "$1" &>/dev/null; then
        echo "❌ $1 not found. Install it first."
        exit 1
    fi
}

check_tool kubectl
[[ "$METHOD" == "helm" ]] && check_tool helm
[[ "$METHOD" == "kustomize" ]] && check_tool kustomize

# Verify cluster connectivity
if ! kubectl cluster-info &>/dev/null; then
    echo "❌ Cannot connect to Kubernetes cluster"
    exit 1
fi
echo "✅ Cluster connected: $(kubectl config current-context)"

# ── Namespace ────────────────────────────────────────────────
if [[ "$ENV" == "production" ]]; then
    NS="$NAMESPACE"
else
    NS="${NAMESPACE}-${ENV}"
fi

kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f -
echo "✅ Namespace: $NS"

# ── Secrets check ────────────────────────────────────────────
if ! kubectl get secret enrichment-credentials -n "$NS" &>/dev/null; then
    echo ""
    echo "⚠️  Secret 'enrichment-credentials' not found in namespace '$NS'"
    echo "   Create it first:"
    echo ""
    echo "   kubectl create secret generic enrichment-credentials \\"
    echo "     --namespace=$NS \\"
    echo "     --from-literal=perplexity-api-key=pplx-YOUR-KEY \\"
    echo "     --from-literal=api-secret-key=\$(openssl rand -hex 32) \\"
    echo "     --from-literal=api-key-hash=YOUR_HASH"
    echo ""
    read -p "   Continue anyway? (y/N) " -n 1 -r
    echo
    [[ ! $REPLY =~ ^[Yy]$ ]] && exit 1
fi

# ── Deploy ───────────────────────────────────────────────────
if [[ "$METHOD" == "kustomize" ]]; then
    OVERLAY_DIR="${ROOT_DIR}/kustomize/overlays/${ENV}"
    if [[ ! -d "$OVERLAY_DIR" ]]; then
        echo "❌ Overlay not found: $OVERLAY_DIR"
        exit 1
    fi

    echo "📦 Building kustomize overlay: $ENV"
    kustomize build "$OVERLAY_DIR" > /tmp/enrichment-manifest.yaml

    echo "🔍 Dry run..."
    kubectl apply --dry-run=server -f /tmp/enrichment-manifest.yaml

    echo "🚀 Applying..."
    kubectl apply -f /tmp/enrichment-manifest.yaml
    rm /tmp/enrichment-manifest.yaml

elif [[ "$METHOD" == "helm" ]]; then
    CHART_DIR="${ROOT_DIR}/helm/enrichment-api"
    VALUES_FILE="${CHART_DIR}/values-${ENV}.yaml"

    HELM_ARGS=(
        upgrade --install "$RELEASE_NAME" "$CHART_DIR"
        --namespace "$NS"
        --create-namespace
        --wait
        --timeout 5m
    )

    if [[ -f "$VALUES_FILE" ]]; then
        HELM_ARGS+=(-f "$VALUES_FILE")
        echo "📦 Using values: $VALUES_FILE"
    fi

    echo "🔍 Dry run..."
    helm "${HELM_ARGS[@]}" --dry-run

    echo "🚀 Installing..."
    helm "${HELM_ARGS[@]}"
fi

# ── Health check ─────────────────────────────────────────────
echo ""
echo "⏳ Waiting for rollout..."
kubectl rollout status deployment/enrichment-api -n "$NS" --timeout=120s || true

echo ""
echo "🏥 Health check..."
sleep 5
kubectl get pods -n "$NS" -l app=enrichment-api -o wide

# Port-forward and test
echo ""
echo "🧪 Testing health endpoint..."
kubectl port-forward svc/enrichment-api 18000:8000 -n "$NS" &
PF_PID=$!
sleep 3

HEALTH=$(curl -sf http://localhost:18000/api/v1/health 2>/dev/null || echo '{"status":"unreachable"}')
kill $PF_PID 2>/dev/null || true

echo "$HEALTH" | python3 -m json.tool 2>/dev/null || echo "$HEALTH"

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  ✅ Deploy complete — $ENV via $METHOD                      "
echo "╚══════════════════════════════════════════════════════════════╝"
