#!/usr/bin/env bash
set -euo pipefail

ENV="${1:-dev}"
METHOD="${2:-kustomize}"
NAMESPACE="enrichment"

if [[ "$ENV" == "production" ]]; then
    NS="$NAMESPACE"
else
    NS="${NAMESPACE}-${ENV}"
fi

echo "🔄 Rolling back enrichment-api in $NS..."

if [[ "$METHOD" == "helm" ]]; then
    helm rollback enrichment-api -n "$NS"
    echo "✅ Helm rollback complete"
else
    kubectl rollout undo deployment/enrichment-api -n "$NS"
    echo "✅ Rollout undo complete"
fi

kubectl rollout status deployment/enrichment-api -n "$NS" --timeout=120s
kubectl get pods -n "$NS" -l app=enrichment-api
