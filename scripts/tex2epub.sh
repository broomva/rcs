#!/usr/bin/env bash
# =============================================================================
# tex2epub.sh — Convert an RCS paper main.tex into an EPUB3 readable in
# iOS Books (Apple Books) and other reflowable EPUB readers.
#
# Why this exists
# ---------------
# The canonical paper format is LaTeX → PDF (tectonic). PDFs are fixed-
# layout and become painful to read on phone-sized screens: text gets
# tiny, scroll is column-per-column, and font size can't be adjusted.
#
# EPUB3 is reflowable and Apple Books renders MathML natively, so
# equation-heavy control-theory content stays sharp while the reader
# controls font size, theme, and typeface.
#
# Pipeline
# --------
#   1. Apply a minimal sed pre-filter:
#        \taua[i]  →  \tau_{a,i}
#      The canonical \taua macro (preamble.tex line 87) uses \ifx\\#1\\
#      which pandoc's math parser can't tokenise. The substitution is
#      lossless — inlines what LaTeX would expand to — and only touches
#      the indexed form.
#
#   2. Run pandoc 3.x with:
#        --from latex --to epub3
#        --mathml                 : MathML, not PNG images (sharp + user-scalable)
#        --citeproc               : resolve \cite against references.bib
#        --toc --toc-depth=2      : Books shows a proper section outline
#        --metadata-file          : title / author / series / ISBN-equivalent
#        --css                    : iOS Books readability overrides
#
#   3. Run from the paper directory so relative \input paths resolve
#      (\def\SHAREDLATEX{../../latex}; \input{\SHAREDLATEX/preamble}).
#
# Usage
# -----
#   scripts/tex2epub.sh <input.tex> <output.epub> <metadata.yaml>
#
# Example:
#   scripts/tex2epub.sh papers/p0-foundations/main.tex \
#                       papers/p0-foundations/main.epub \
#                       epub/metadata-p0.yaml
#
# Requirements: pandoc 3.x (tested on 3.9).
# =============================================================================

set -euo pipefail

if [[ $# -lt 3 ]]; then
  cat >&2 <<USAGE
Usage: $0 <input.tex> <output.epub> <metadata.yaml>

  <input.tex>      Paper source (e.g. papers/p0-foundations/main.tex)
  <output.epub>    Output path (e.g. papers/p0-foundations/main.epub)
  <metadata.yaml>  Pandoc metadata (title/author/series/etc.)
USAGE
  exit 2
fi

INPUT_TEX="$1"
OUTPUT_EPUB="$2"
METADATA_YAML="$3"

# Resolve everything against the repo root so relative paths in the
# script are stable regardless of where the caller invoked it from.
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Input paths: accept either repo-relative or absolute.
[[ "$INPUT_TEX" != /* ]]     && INPUT_TEX="$REPO_ROOT/$INPUT_TEX"
[[ "$OUTPUT_EPUB" != /* ]]   && OUTPUT_EPUB="$REPO_ROOT/$OUTPUT_EPUB"
[[ "$METADATA_YAML" != /* ]] && METADATA_YAML="$REPO_ROOT/$METADATA_YAML"

BIB="$REPO_ROOT/latex/references.bib"
CSS="$REPO_ROOT/epub/styles.css"

# Sanity checks
for f in "$INPUT_TEX" "$METADATA_YAML" "$BIB" "$CSS"; do
  if [[ ! -f "$f" ]]; then
    echo "error: missing required file: $f" >&2
    exit 1
  fi
done

PAPER_DIR="$(dirname "$INPUT_TEX")"
BASENAME="$(basename "$INPUT_TEX")"

# Pre-filter: inline \taua at call sites so pandoc never has to expand
# the \newcommand body (which uses \ifx — unsupported by pandoc's math
# parser).
#
#   \taua[i]   →  \tau_{a,i}       (indexed form)
#   \taua      →  \tau_{a}         (bare form — no trailing comma)
#
# Order matters: the indexed rule must run first. After it, no \taua[
# remains, so the bare rule only catches the no-arg usages.
TMP_TEX="$PAPER_DIR/.epub-tmp-${BASENAME}"
cleanup() { rm -f "$TMP_TEX"; }
trap cleanup EXIT

sed -E \
  -e 's/\\taua\[([^][]*)\]/\\tau_{a,\1}/g' \
  -e 's/\\taua([^[:alnum:]])/\\tau_{a}\1/g' \
  -e 's/\\author\{[^}]*\}//g' \
  "$INPUT_TEX" > "$TMP_TEX"

# Rationale for stripping \author{}:
#   Pandoc otherwise emits the author TWICE on the title page — once
#   from the LaTeX \author{} block and once from the YAML creator:
#   metadata. Stripping it from the pandoc input leaves the YAML as
#   the single source of truth for EPUB author metadata while the
#   tectonic PDF pipeline still sees \author{} untouched (this script
#   edits a per-build temp copy, never the source tex).

# Run pandoc from the paper directory so \input{../../latex/...} works.
cd "$PAPER_DIR"

pandoc "$(basename "$TMP_TEX")" \
  --from latex \
  --to epub3 \
  --output "$OUTPUT_EPUB" \
  --mathml \
  --toc \
  --toc-depth=2 \
  --citeproc \
  --bibliography="$BIB" \
  --css="$CSS" \
  --metadata-file="$METADATA_YAML" \
  --standalone

# Emit a quick summary so the caller can see what was produced.
SIZE=$(du -h "$OUTPUT_EPUB" | awk '{print $1}')
echo "built: $OUTPUT_EPUB ($SIZE)"
