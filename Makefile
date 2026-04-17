# =============================================================================
# RCS — Build & Test
# =============================================================================

.PHONY: all build build-p0 build-p0-article build-p0-ieee test params params-check clean

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

build: build-p0

build-p0: build-p0-article build-p0-ieee

build-p0-article: params
	cd papers/p0-foundations && tectonic main.tex

build-p0-ieee: params
	cd papers/p0-foundations && tectonic main-ieee.tex

# --- Test ---

test: params-check
	python3 tests/test_stability_budget.py
	python3 tests/test_lyapunov_simulation.py

# --- Clean ---

clean:
	find papers -name '*.aux' -delete 2>/dev/null || true
	find papers -name '*.bbl' -delete 2>/dev/null || true
	find papers -name '*.blg' -delete 2>/dev/null || true
	find papers -name '*.log' -delete 2>/dev/null || true
	find papers -name '*.out' -delete 2>/dev/null || true
	find papers -name '*.toc' -delete 2>/dev/null || true
	find papers -name '*.synctex.gz' -delete 2>/dev/null || true
