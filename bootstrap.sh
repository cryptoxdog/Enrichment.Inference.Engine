#!/usr/bin/env bash
# =============================================================================
# Venture Forge Toolbox — Bootstrap
#
# Wires ALL tools into an EXISTING repo with one command.
# Safe to re-run (skips existing files, never overwrites .env).
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/YOU/venture-forge-toolbox/main/bootstrap.sh | bash
#   — or —
#   ./bootstrap.sh                     # run from toolbox clone
#   ./bootstrap.sh /path/to/my-repo    # target a specific repo
#
# What it does:
#   1. Copies all tool scripts into tools/
#   2. Copies CI workflow into .github/workflows/
#   3. Copies semgrep rules into .semgrep/
#   4. Creates .env.template (never overwrites existing .env)
#   5. Installs git hooks
#   6. Prints what to fill in
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Resolve paths
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_REPO="${1:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  Venture Forge Toolbox — Bootstrap                          ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "  Source:  $SCRIPT_DIR"
echo "  Target:  $TARGET_REPO"
echo ""

cd "$TARGET_REPO"

# ---------------------------------------------------------------------------
# Helper: copy if not exists (or force with -f flag)
# ---------------------------------------------------------------------------
FORCE=false
[[ "${2:-}" == "-f" ]] && FORCE=true

copy_tool() {
    local src="$1"
    local dst="$2"
    local dir
    dir="$(dirname "$dst")"
    mkdir -p "$dir"

    if [[ -f "$dst" ]] && ! $FORCE; then
        echo "  ○ skip  $dst (exists)"
    else
        cp "$src" "$dst"
        chmod +x "$dst" 2>/dev/null || true
        echo "  ✓ wrote $dst"
    fi
}

# ---------------------------------------------------------------------------
# 1. Tool scripts
# ---------------------------------------------------------------------------
echo "── Tools ──"

copy_tool "$SCRIPT_DIR/tools/infra/check_env.sh"         "tools/infra/check_env.sh"
copy_tool "$SCRIPT_DIR/tools/infra/docker_validate.sh"    "tools/infra/docker_validate.sh"
copy_tool "$SCRIPT_DIR/tools/infra/test_everything.sh"    "tools/infra/test_everything.sh"
copy_tool "$SCRIPT_DIR/tools/infra/deep_mri.sh"           "tools/infra/deep_mri.sh"
copy_tool "$SCRIPT_DIR/tools/infra/precommit_smoke.sh"    "tools/infra/precommit_smoke.sh"
copy_tool "$SCRIPT_DIR/tools/dev/dev_up.sh"               "tools/dev/dev_up.sh"
copy_tool "$SCRIPT_DIR/tools/hooks/install_hooks.sh"      "tools/hooks/install_hooks.sh"
copy_tool "$SCRIPT_DIR/tools/deploy/deploy.sh"            "tools/deploy/deploy.sh"

# ---------------------------------------------------------------------------
# 2. CI workflow
# ---------------------------------------------------------------------------
echo ""
echo "── CI/CD ──"

copy_tool "$SCRIPT_DIR/tools/ci/ci-quality.yml"           ".github/workflows/ci-quality.yml"

# ---------------------------------------------------------------------------
# 3. Semgrep rules
# ---------------------------------------------------------------------------
echo ""
echo "── Lint Rules ──"

copy_tool "$SCRIPT_DIR/.semgrep/semgrep-rules.yaml"     ".semgrep/semgrep-rules.yaml"

# ---------------------------------------------------------------------------
# 4. Templates → create .env.template, never overwrite real .env
# ---------------------------------------------------------------------------
echo ""
echo "── Environment ──"

copy_tool "$SCRIPT_DIR/templates/.env.required.template"     "templates/.env.required.template"
copy_tool "$SCRIPT_DIR/templates/.env.recommended.template"  "templates/.env.recommended.template"
copy_tool "$SCRIPT_DIR/templates/.env.vps.template"          "templates/.env.vps.template"
copy_tool "$SCRIPT_DIR/templates/dev.conf.template"          "templates/dev.conf.template"
copy_tool "$SCRIPT_DIR/templates/styleguide.template.md"     "templates/styleguide.template.md"

# Create starter .env.template if no .env exists
if [[ ! -f ".env" ]] && [[ ! -f ".env.local" ]]; then
    if [[ ! -f ".env.template" ]]; then
        cat > .env.template << 'ENV'
# =============================================================================
# Project Environment — Fill this in, then: cp .env.template .env.local
# =============================================================================

# --- REQUIRED ---
APP_NAME=
APP_API_KEY=
APP_PORT=8000

# --- Database ---
POSTGRES_USER=postgres
POSTGRES_DB=
POSTGRES_PASSWORD=

# --- Containers (match your docker-compose service names) ---
API_CONTAINER=api
REDIS_CONTAINER=redis
POSTGRES_CONTAINER=postgres

# --- Optional (set to 0 to disable checks for services you don't have) ---
NEO4J_PORT=0
DASHBOARD_PORT=0

# --- Dev ---
APP_MODULE=
ENV
        echo "  ✓ created .env.template (fill in → cp to .env.local)"
    fi
fi

# ---------------------------------------------------------------------------
# 5. Git hooks
# ---------------------------------------------------------------------------
echo ""
echo "── Git Hooks ──"

if [[ -d ".git" ]]; then
    # Create a pre-commit hook that runs docker validate
    mkdir -p .git/hooks
    if [[ ! -f ".git/hooks/pre-commit" ]] || $FORCE; then
        cat > .git/hooks/pre-commit << 'HOOK'
#!/bin/bash
# Auto-installed by venture-forge-toolbox bootstrap
# Runs Docker validation before each commit

REPO_ROOT="$(git rev-parse --show-toplevel)"

# Docker validation (if Dockerfiles exist)
if find "$REPO_ROOT" -name "Dockerfile*" -not -path "*/node_modules/*" | grep -q .; then
    echo "🐳 Pre-commit: Docker validation..."
    "$REPO_ROOT/tools/infra/docker_validate.sh" --quick 2>/dev/null || true
fi

# Env check (if .env exists)
if [[ -f "$REPO_ROOT/.env" ]] || [[ -f "$REPO_ROOT/.env.local" ]]; then
    "$REPO_ROOT/tools/infra/check_env.sh" 2>/dev/null || true
fi
HOOK
        chmod +x .git/hooks/pre-commit
        echo "  ✓ installed pre-commit hook"
    else
        echo "  ○ skip  .git/hooks/pre-commit (exists)"
    fi
else
    echo "  ○ skip  Not a git repo — run 'git init' first, then re-run bootstrap"
fi

# ---------------------------------------------------------------------------
# 6. .gitignore additions
# ---------------------------------------------------------------------------
echo ""
echo "── Gitignore ──"

GITIGNORE_ENTRIES=".env
.env.local
.env.vps
*.bak.*"

if [[ -f ".gitignore" ]]; then
    ADDED=0
    while IFS= read -r entry; do
        if ! grep -qF "$entry" .gitignore 2>/dev/null; then
            echo "$entry" >> .gitignore
            ((ADDED++))
        fi
    done <<< "$GITIGNORE_ENTRIES"
    echo "  ✓ added $ADDED entries to .gitignore"
else
    echo "$GITIGNORE_ENTRIES" > .gitignore
    echo "  ✓ created .gitignore"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  ✅ Bootstrap Complete                                      ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║                                                              ║"
echo "║  Next steps:                                                 ║"
echo "║                                                              ║"
echo "║  1. cp .env.template .env.local                             ║"
echo "║     Fill in APP_NAME, APP_API_KEY, POSTGRES_*, etc.         ║"
echo "║                                                              ║"
echo "║  2. Test locally:                                           ║"
echo "║     ./tools/infra/check_env.sh                              ║"
echo "║     ./tools/infra/docker_validate.sh                        ║"
echo "║     ./tools/dev/dev_up.sh                                   ║"
echo "║                                                              ║"
echo "║  3. For VPS deployment:                                     ║"
echo "║     cp templates/.env.vps.template .env.vps                 ║"
echo "║     Fill in VPS_HOST, VPS_REPO, etc.                        ║"
echo "║     ./tools/deploy/deploy.sh --dry-run                      ║"
echo "║                                                              ║"
echo "║  4. For CI (GitHub):                                        ║"
echo "║     Set secrets: SONAR_TOKEN, GITGUARDIAN_API_KEY,          ║"
echo "║                  CODECOV_TOKEN                               ║"
echo "║     Set variables: PYTHON_VERSION, SONAR_PROJECT_KEY,       ║"
echo "║                    SONAR_ORG                                 ║"
echo "║                                                              ║"
echo "║  Tools are in tools/ — you never edit them.                 ║"
echo "║  Config is in .env — you edit that once.                    ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
