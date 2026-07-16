# =============================================================================
# RCS — Build & Test
# =============================================================================

.PHONY: all build build-p0 build-p0-article build-p0-ieee build-p1 build-p1-article build-p1-ieee build-p5-jepa build-p5-jepa-article build-p5-jepa-ieee epub epub-p0 epub-p1 test test-microrcs swe-smoke swe-smoke-dry swe-pilot swe-clean swarm-smoke params params-check clean

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

build: build-p0 build-p1 build-p5-jepa

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

# Paper 5: Online JEPA Composite Stability (sub-epic BRO-955).
# Sibling of dormant papers/p5-categorical-foundations/; see
# papers/p5-online-jepa-stability/PROTOCOL.md \S8 for the naming
# reconciliation note.
build-p5-jepa: build-p5-jepa-article build-p5-jepa-ieee

build-p5-jepa-article: params
	cd papers/p5-online-jepa-stability && tectonic main.tex

build-p5-jepa-ieee: params
	cd papers/p5-online-jepa-stability && tectonic main-ieee.tex

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
	python3 tests/test_endogenous_gamma.py
	python3 tests/test_agency_necessity.py
	python3 tests/test_nonstationary_objective.py

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

# --- Swarm-RCS-L0 smoke (BRO-944 follow-up) ---
# Skeleton smoke: --dry-run by default (mocked Reasoner, no API). Exercises
# the SwarmL0Plant + voting + substrate wiring without spend. Live runs
# (lift --dry-run) are deferred to a follow-up PR per spec
# docs/superpowers/specs/2026-05-05-swarm-rcs-l0-design.md.
swarm-smoke:
	cd microrcs && python3 -m scripts.swarm_run --dry-run \
	    --condition swarm_full --suite reference \
	    --n-peers 3 --k-quorum 2 \
	    --max-steps 5 --max-cost-usd 0.10 \
	    --workspace-root /tmp/microrcs-swarm

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
