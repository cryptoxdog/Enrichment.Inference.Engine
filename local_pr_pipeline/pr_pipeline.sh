#!/usr/bin/env bash
# Local PR pipeline — parity with .github/workflows (ci, compliance, docs, L9).
# Lives under local_pr_pipeline/ (isolated tooling — not application runtime code).
# Usage: local_pr_pipeline/pr_pipeline.sh [phase|all]
# Env: ORDER=gate|failfast, COVERAGE_THRESHOLD, PR_MYPY_STRICT, PR_SKIP_SEMGREP,
#      PR_SKIP_INTEGRATION, PR_L9_MINIMAL, PR_SKIP_L9, PR_PYTEST_XDIST, PR_SECURITY_STRICT,
#      PR_BASE, PR_HEAD (optional, for L9 diff / contract-bound)
set -euo pipefail

BUNDLE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$BUNDLE_DIR/.." && pwd)"
cd "$ROOT"

export PYTHONPATH="${PYTHONPATH:-}:${ROOT}"

# Prefer venv: `PYTHON=./.venv/bin/python` or rely on PATH `python3` (macOS often has no bare `pip`)
PYTHON_BIN="${PYTHON:-python3}"
pip_run() {
  "$PYTHON_BIN" -m pip "$@"
}

ORDER="${ORDER:-gate}"
COVERAGE_THRESHOLD="${COVERAGE_THRESHOLD:-${COVERAGE_MIN:-60}}"
PHASE="${1:-all}"

COMPOSE_FILE="${BUNDLE_DIR}/docker-compose.pr.yml"
COMPOSE_PROJECT="enrich_pr"

banner() {
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo " PR PIPELINE — $1"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

pr_compose() {
  docker compose -f "$COMPOSE_FILE" -p "$COMPOSE_PROJECT" "$@"
}

services_up() {
  banner "Starting Postgres + Redis (docker-compose.pr.yml)"
  pr_compose up -d
  sleep 10
}

services_down() {
  pr_compose down -v 2>/dev/null || true
}

phase_validate() {
  banner "validate (ci.yml)"
  pip_run install -q pyyaml 2>/dev/null || pip_run install -q pyyaml
  echo "Checking Python syntax..."
  find . -name "*.py" \
    -not -path "./venv/*" \
    -not -path "./.venv/*" \
    -not -path "./__pycache__/*" \
    -not -path "./build/*" \
    -not -path "./dist/*" \
    -not -path "./WIP/*" \
    -exec "$PYTHON_BIN" -m py_compile {} +
  "$PYTHON_BIN" -c "
import yaml
from pathlib import Path
errors = []
for f in Path('.github/workflows').glob('*.yml'):
    try:
        with open(f) as fh:
            yaml.safe_load(fh)
    except yaml.YAMLError as e:
        errors.append(f'{f}: {e}')
if errors:
    for e in errors:
        print(f'❌ {e}')
    raise SystemExit(1)
print('✅ Workflow YAML valid')
"
  "$PYTHON_BIN" "${BUNDLE_DIR}/compliance_kb_validate.py"
}

phase_lint() {
  banner "lint (ci.yml)"
  pip_run install -q -r requirements-ci.txt 2>/dev/null || pip_run install -r requirements-ci.txt
  ruff check . --output-format=full
  ruff format --check .
  # Omit --install-types here: it can invoke the wrong pip on macOS; CI installs stubs explicitly.
  MYPY_CMD=(mypy app --show-error-codes --pretty --ignore-missing-imports)
  if [[ -n "${PR_MYPY_STRICT:-}" ]]; then
    "${MYPY_CMD[@]}"
  else
    "${MYPY_CMD[@]}" || echo "WARN: mypy (non-blocking — matches ci.yml; set PR_MYPY_STRICT=1 to fail on errors)"
  fi
}

phase_semgrep() {
  banner "semgrep"
  if [[ -n "${PR_SKIP_SEMGREP:-}" ]]; then
    echo "SKIP: PR_SKIP_SEMGREP=1"
    return 0
  fi
  if command -v semgrep &>/dev/null; then
    semgrep --config .semgrep/ --error
  elif command -v docker &>/dev/null; then
    docker run --rm -v "${ROOT}:/src" -w /src returntocorp/semgrep:latest semgrep --config .semgrep/ --error
  else
    echo "FAIL: install semgrep CLI or Docker for Semgrep policy checks"
    exit 1
  fi
}

phase_test() {
  banner "test (ci.yml) — requires DATABASE_URL / REDIS_URL"
  if [[ -n "${PR_SKIP_INTEGRATION:-}" ]]; then
    echo "SKIP: PR_SKIP_INTEGRATION=1 (no pytest with services)"
    return 0
  fi
  if ! command -v docker &>/dev/null; then
    echo "FAIL: Docker required for Postgres/Redis test services"
    exit 1
  fi
  pip_run install -q -r requirements-ci.txt 2>/dev/null || pip_run install -r requirements-ci.txt
  pip_run install -q -e ".[dev]" 2>/dev/null || pip_run install -q -e . 2>/dev/null || true
  if [[ -f requirements.txt ]]; then pip_run install -q -r requirements.txt 2>/dev/null || true; fi

  services_up
  trap services_down EXIT

  export DATABASE_URL="${DATABASE_URL:-postgresql://test_user:test_password@127.0.0.1:5432/test_db}"
  export REDIS_URL="${REDIS_URL:-redis://127.0.0.1:6379/0}"
  export TESTING="${TESTING:-true}"

  PYTEST_ARGS=(tests/ -v --tb=short --cov=app --cov-report=term-missing "--cov-fail-under=${COVERAGE_THRESHOLD}" --timeout=300)
  if [[ -n "${PR_PYTEST_XDIST:-}" ]]; then
    PYTEST_ARGS=(-n auto "${PYTEST_ARGS[@]}")
  fi
  PYTHONPATH=. "$PYTHON_BIN" -m pytest "${PYTEST_ARGS[@]}"

  trap - EXIT
  services_down
}

phase_security() {
  banner "security (ci.yml — blocking in ci-gate)"
  pip_run install -q -r requirements-ci.txt 2>/dev/null || pip_run install -r requirements-ci.txt

  if [[ -n "${PR_SKIP_GITLEAKS:-}" ]]; then
    echo "WARN: PR_SKIP_GITLEAKS=1 — skipping secret scan (install gitleaks for CI parity)"
  elif command -v gitleaks &>/dev/null; then
    gitleaks detect --config .gitleaks.toml --source . --verbose
  else
    echo "FAIL: gitleaks not on PATH — install https://github.com/gitleaks/gitleaks or set PR_SKIP_GITLEAKS=1"
    exit 1
  fi

  "$PYTHON_BIN" -m pip_audit --desc

  if [[ -n "${PR_SECURITY_STRICT:-}" ]]; then
    "$PYTHON_BIN" -m safety check
    "$PYTHON_BIN" -m bandit -r app -ll -f screen --exclude ./venv,./.venv,./tests,./build,./dist
  else
    "$PYTHON_BIN" -m safety check || echo "WARN: safety (non-blocking locally; matches CI step)"
    "$PYTHON_BIN" -m bandit -r app -ll -f screen --exclude ./venv,./.venv,./tests,./build,./dist || echo "WARN: bandit (non-blocking locally)"
  fi
}

phase_compliance() {
  banner "compliance (compliance.yml)"
  pip_run install -q -r requirements-ci.txt 2>/dev/null || pip_run install -r requirements-ci.txt
  "$PYTHON_BIN" "${BUNDLE_DIR}/check_compliance_terminology.py"

  echo "Checking chassis isolation..."
  VIOLATIONS=$(find app/ -name "*.py" \
    -not -path "app/api/*" \
    -not -path "app/middleware/*" \
    -not -path "app/main.py" \
    -not -path "app/core/auth.py" \
    -not -path "app/score/score_api.py" \
    -not -name "handlers.py" \
    -exec grep -l "from fastapi import\|import fastapi" {} + 2>/dev/null || true)
  if [[ -n "$VIOLATIONS" ]]; then
    echo "❌ FastAPI imports found outside allowed modules:"
    echo "$VIOLATIONS"
    exit 1
  fi
  echo "✅ Chassis isolation OK"

  "$PYTHON_BIN" "${BUNDLE_DIR}/compliance_kb_validate.py"

  if [[ -f tools/audit_engine.py ]]; then
    PYTHONPATH=. "$PYTHON_BIN" tools/audit_engine.py --strict || echo "WARN: audit_engine (non-blocking per compliance.yml)"
  fi
  if [[ -f tools/verify_contracts.py ]]; then
    PYTHONPATH=. "$PYTHON_BIN" tools/verify_contracts.py || echo "WARN: verify_contracts (non-blocking per compliance.yml)"
  fi
}

phase_l9() {
  banner "L9 (l9-constitution-gate + l9-contract-control)"
  if [[ -n "${PR_SKIP_L9:-}" ]]; then
    echo "SKIP: PR_SKIP_L9=1"
    return 0
  fi

  pip_run install -q pyyaml pytest fastapi 2>/dev/null || pip_run install pyyaml pytest fastapi

  "$PYTHON_BIN" scripts/verify_node_constitution.py

  "$PYTHON_BIN" -m pytest tests/contracts/tier2/test_node_constitution_contract.py \
    tests/contracts/tier2/test_runtime_attestation_contract.py \
    -q --disable-warnings --maxfail=1 -o addopts=""

  "$PYTHON_BIN" scripts/l9_contract_control.py verify-constitution
  "$PYTHON_BIN" scripts/l9_contract_control.py verify-attestation || {
    if "$PYTHON_BIN" -c "import app" 2>/dev/null; then
      exit 1
    fi
    echo "[pr] SKIP attestation (app module not available)"
  }

  if [[ -n "${PR_L9_MINIMAL:-}" ]]; then
    echo "PR_L9_MINIMAL=1 — skipping select-gates command runner"
    return 0
  fi

  BASE="${PR_BASE:-$(git merge-base HEAD origin/main 2>/dev/null || git merge-base HEAD main 2>/dev/null || true)}"
  HEAD_REF="${PR_HEAD:-HEAD}"
  if [[ -z "$BASE" ]]; then
    BASE="HEAD~1"
  fi
  echo "L9 select-gates: base=$BASE head=$HEAD_REF"
  "$PYTHON_BIN" scripts/l9_contract_control.py select-gates --base "$BASE" --head "$HEAD_REF" > "${ROOT}/.gates.pr.json"
  "$PYTHON_BIN" "${BUNDLE_DIR}/run_pr_select_gates.py" "${ROOT}/.gates.pr.json"
  rm -f "${ROOT}/.gates.pr.json"

  if [[ -n "${PR_CONTRACT_BOUND_CHECK:-}" ]]; then
    "$PYTHON_BIN" "${BUNDLE_DIR}/contract_bound_local.py" --base "$BASE" --head "$HEAD_REF"
  fi
}

phase_docs() {
  banner "docs (docs-consistency + docs-sync parity)"
  bash "${BUNDLE_DIR}/docs_consistency_local.sh"
  "$PYTHON_BIN" "${BUNDLE_DIR}/docs_link_check_local.py"
}

run_gate_order() {
  phase_validate
  phase_lint
  phase_semgrep
  phase_test
  phase_security
  phase_compliance
  phase_l9
  phase_docs
}

run_failfast_order() {
  phase_validate
  phase_compliance
  phase_l9
  phase_docs
  phase_lint
  phase_semgrep
  phase_test
  phase_security
}

print_cloud_banner() {
  banner "Post-push (GitHub-only — not run locally)"
  cat <<'EOS'
  • dependency-review (PR), SBOM, OpenSSF Scorecard, Codecov upload
  • SonarCloud / CodeRabbit (if enabled)
  • Optional: gh pr checks
EOS
}

case "${PHASE}" in
  validate) phase_validate ;;
  lint) phase_lint ;;
  semgrep) phase_semgrep ;;
  test) phase_test ;;
  security) phase_security ;;
  compliance) phase_compliance ;;
  l9) phase_l9 ;;
  docs) phase_docs ;;
  all)
    if [[ "$ORDER" == "failfast" ]]; then
      run_failfast_order
    else
      run_gate_order
    fi
    print_cloud_banner
    echo ""
    echo "✅ make pr pipeline completed successfully"
    ;;
  *)
    echo "Usage: $0 [validate|lint|semgrep|test|security|compliance|l9|docs|all]"
    exit 2
    ;;
esac
