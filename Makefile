# =============================================================================
# RCS — Build & Test
# =============================================================================

.PHONY: all build build-p0 build-p0-article build-p0-ieee build-p1 build-p1-article build-p1-ieee epub epub-p0 epub-p1 test test-microrcs swe-smoke swe-smoke-dry swe-pilot swe-clean params params-check clean

# --- Parameters ---
# data/parameters.toml is the single source of truth for all stability
# budget parameters. latex/parameters.tex is regenerated from it and must
# be kept in sync — CI enforces this via `make params-check`.

params: latex/parameters.tex

latex/parameters.tex: data/parameters.toml scripts/gen_parameters_tex.py
	python3 scripts/gen_parameters_tex.py

params-check:
	python3 scripts/gen_parameters_tex.py --check

# --- Build ---

all: build test

build: build-p0 build-p1

build-p0: build-p0-article build-p0-ieee

build-p0-article: params
	cd papers/p0-foundations && tectonic main.tex

build-p0-ieee: params
	cd papers/p0-foundations && tectonic main-ieee.tex

build-p1: build-p1-article build-p1-ieee

build-p1-article: params
	cd papers/p1-stability && tectonic main.tex

build-p1-ieee: params
	cd papers/p1-stability && tectonic main-ieee.tex

# --- EPUB (iOS Books / reflowable readers) ---
# pandoc 3.x required; see scripts/tex2epub.sh for pipeline details.

epub: epub-p0 epub-p1

epub-p0: papers/p0-foundations/main.epub

papers/p0-foundations/main.epub: \
		papers/p0-foundations/main.tex \
		latex/references.bib \
		latex/preamble.tex \
		latex/parameters.tex \
		epub/styles.css \
		epub/metadata-p0.yaml \
		scripts/tex2epub.sh
	bash scripts/tex2epub.sh \
		papers/p0-foundations/main.tex \
		papers/p0-foundations/main.epub \
		epub/metadata-p0.yaml

epub-p1: papers/p1-stability/main.epub

papers/p1-stability/main.epub: \
		papers/p1-stability/main.tex \
		latex/references.bib \
		latex/preamble.tex \
		latex/parameters.tex \
		epub/styles.css \
		epub/metadata-p1.yaml \
		scripts/tex2epub.sh
	bash scripts/tex2epub.sh \
		papers/p1-stability/main.tex \
		papers/p1-stability/main.epub \
		epub/metadata-p1.yaml

# --- Test ---

test: params-check test-microrcs
	python3 tests/test_stability_budget.py
	python3 tests/test_lyapunov_simulation.py

# microrcs/ — single-file LLM-controller RCS baseline (P0/P1 empirical witness)
test-microrcs:
	cd microrcs && python3 -m pytest tests/ -v

# --- SWE-bench-Lite smoke (BRO-946) ---
# Smoke test: 2 hand-picked instances × Haiku × flat-only. Validates the
# adapter pipeline end-to-end (HF dataset → repo clone → venv → agent loop →
# patch verify). Live API call required; ~$1–5 cost. See
# microrcs/adapters/AGENTS.md for caching, instance curation, and isolation.
swe-smoke:
	cd microrcs && python3 -m scripts.swe_smoke

# Dry-run path: provisions workspaces, exercises adapter wiring, no LLM calls.
swe-smoke-dry:
	cd microrcs && python3 -m scripts.swe_smoke --dry-run

# BRO-946 pilot: 5 instances × 4 conditions × 1 seed at Haiku × Sonnet meta.
# Tests whether recursion produces a directional signal on SWE-bench-Lite
# before committing to the full bench. ~$30-50 cost, ~1.5-2.5h wall.
swe-pilot:
	cd microrcs && python3 -m scripts.swe_pilot

# Wipe the SWE smoke + pilot cache (canonical clones + venvs + workspaces).
swe-clean:
	rm -rf ~/.cache/microrcs-swe

# --- Clean ---

clean:
	find papers -name '*.aux' -delete 2>/dev/null || true
	find papers -name '*.bbl' -delete 2>/dev/null || true
	find papers -name '*.blg' -delete 2>/dev/null || true
	find papers -name '*.log' -delete 2>/dev/null || true
	find papers -name '*.out' -delete 2>/dev/null || true
	find papers -name '*.toc' -delete 2>/dev/null || true
	find papers -name '*.synctex.gz' -delete 2>/dev/null || true
	find papers -name '.epub-tmp-*' -delete 2>/dev/null || true
