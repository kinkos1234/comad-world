#!/bin/zsh
# Unified crawl orchestrator — runs all crawlers and enrichment pipeline.
#
# Usage:
#   ./scripts/crawl-all.sh              # Run all crawlers
#   ./scripts/crawl-all.sh --enrich     # Run crawlers + enrichment pipeline
#   ./scripts/crawl-all.sh --only blogs # Run only blog crawler
#   ./scripts/crawl-all.sh --only arxiv # Run only arxiv crawler

export PATH="$HOME/.local/bin:$HOME/.bun/bin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
TODAY=$(date +%Y-%m-%d)
ENRICH=false
ONLY=""

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --enrich) ENRICH=true; shift ;;
    --only) ONLY="$2"; shift 2 ;;
    *) shift ;;
  esac
done

echo "============================================"
echo "Knowledge Ontology Crawler — $TODAY"
echo "============================================"

CRAWL_START=$(date +%s)

# Run crawlers
if [[ -z "$ONLY" || "$ONLY" == "blogs" ]]; then
  echo ""
  "$SCRIPT_DIR/crawl-blogs.sh"
fi

if [[ -z "$ONLY" || "$ONLY" == "arxiv" ]]; then
  echo ""
  "$SCRIPT_DIR/crawl-arxiv.sh"
fi

if [[ -z "$ONLY" || "$ONLY" == "github" ]]; then
  echo ""
  "$SCRIPT_DIR/crawl-github.sh"
fi

if [[ -z "$ONLY" || "$ONLY" == "geeknews" ]]; then
  echo ""
  "$SCRIPT_DIR/ingest-geeknews.sh"
fi

CRAWL_END=$(date +%s)
CRAWL_DURATION=$((CRAWL_END - CRAWL_START))

echo ""
echo "--------------------------------------------"
echo "Crawling done in ${CRAWL_DURATION}s"

# Run enrichment pipeline if requested
if [[ "$ENRICH" == "true" ]]; then
  echo ""
  echo "Running enrichment pipeline..."
  cd "$PROJECT_DIR" && bun run packages/core/src/setup-schema.ts --enrich
fi

echo ""
echo "============================================"
echo "All done! $(date)"
echo "============================================"
