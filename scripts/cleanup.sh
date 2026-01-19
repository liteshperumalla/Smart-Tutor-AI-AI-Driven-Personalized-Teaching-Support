#!/bin/bash
# ======================================
# Smart AI Tutor - Weekly Cleanup Script
# ======================================
# Removes temporary files, caches, and build artifacts
# Run weekly to keep the project clean
#
# Usage:
#   ./scripts/cleanup.sh
#   ./scripts/cleanup.sh --dry-run  # See what would be removed

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN=true
    echo -e "${YELLOW}🔍 DRY RUN MODE - No files will be deleted${NC}\n"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo -e "${BLUE}🧹 Smart AI Tutor - Weekly Cleanup${NC}"
echo "========================================"
echo ""

# Function to remove files
remove_files() {
    local description=$1
    local command=$2

    echo -e "${YELLOW}Checking:${NC} $description"

    if $DRY_RUN; then
        eval "$command -print" 2>/dev/null | head -5
        local count=$(eval "$command -print" 2>/dev/null | wc -l)
        echo -e "  Would remove: ${count} items"
    else
        local count=$(eval "$command -print" 2>/dev/null | wc -l)
        eval "$command -exec rm -rf {} + 2>/dev/null" || true
        echo -e "  ${GREEN}✓${NC} Removed: ${count} items"
    fi
    echo ""
}

# 1. Python cache files
echo -e "${BLUE}1. Python Cache${NC}"
remove_files "__pycache__ directories" "find . -type d -name '__pycache__'"
remove_files ".pyc files" "find . -name '*.pyc'"
remove_files ".pyo files" "find . -name '*.pyo'"

# 2. Log files
echo -e "${BLUE}2. Log Files${NC}"
if $DRY_RUN; then
    echo -e "${YELLOW}Checking:${NC} Log files in logs/"
    ls logs/*.log 2>/dev/null | head -5 || echo "  No log files found"
    echo ""
else
    if [ -d "logs" ]; then
        rm -f logs/*.log 2>/dev/null || true
        echo -e "  ${GREEN}✓${NC} Removed log files"
    else
        echo -e "  ${YELLOW}⚠${NC}  No logs/ directory"
    fi
    echo ""
fi

# 3. macOS metadata
echo -e "${BLUE}3. macOS Metadata${NC}"
remove_files ".DS_Store files" "find . -name '.DS_Store'"

# 4. Next.js build cache
echo -e "${BLUE}4. Next.js Build Cache${NC}"
if [ -d "frontend/.next" ]; then
    if $DRY_RUN; then
        echo -e "${YELLOW}Checking:${NC} frontend/.next/"
        du -sh frontend/.next/ 2>/dev/null || true
        echo ""
    else
        local size=$(du -sh frontend/.next/ 2>/dev/null | cut -f1 || echo "unknown")
        rm -rf frontend/.next/
        echo -e "  ${GREEN}✓${NC} Removed: frontend/.next/ ($size)"
        echo ""
    fi
else
    echo -e "  ${YELLOW}⚠${NC}  No frontend/.next/ directory"
    echo ""
fi

# 5. Node modules cache (optional - uncomment if needed)
# echo -e "${BLUE}5. Node Modules Cache${NC}"
# if [ -d "frontend/node_modules/.cache" ]; then
#     if $DRY_RUN; then
#         echo -e "${YELLOW}Checking:${NC} frontend/node_modules/.cache/"
#         du -sh frontend/node_modules/.cache/ 2>/dev/null || true
#     else
#         rm -rf frontend/node_modules/.cache/
#         echo -e "  ${GREEN}✓${NC} Removed: frontend/node_modules/.cache/"
#     fi
# fi
# echo ""

# 6. Pytest cache
echo -e "${BLUE}6. Pytest Cache${NC}"
remove_files ".pytest_cache directories" "find . -type d -name '.pytest_cache'"

# 7. Coverage files
echo -e "${BLUE}7. Coverage Files${NC}"
remove_files ".coverage files" "find . -name '.coverage'"
remove_files "htmlcov directories" "find . -type d -name 'htmlcov'"

# Summary
echo "========================================"
if $DRY_RUN; then
    echo -e "${YELLOW}🔍 DRY RUN COMPLETE${NC}"
    echo ""
    echo "To actually clean files, run:"
    echo "  ./scripts/cleanup.sh"
else
    echo -e "${GREEN}✅ CLEANUP COMPLETE${NC}"
    echo ""
    echo "Cleaned:"
    echo "  • Python cache files"
    echo "  • Log files"
    echo "  • macOS metadata"
    echo "  • Next.js build cache"
    echo "  • Pytest cache"
    echo "  • Coverage files"
fi

echo ""
echo -e "${BLUE}Project size:${NC} $(du -sh . | cut -f1)"
echo ""
