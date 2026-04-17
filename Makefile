# =============================================================================
# RCS — Build & Test
# =============================================================================

.PHONY: all build build-article build-ieee test params params-check clean

# --- Parameters ---
# latex/parameters.toml is the single source of truth for all stability
# budget parameters. latex/parameters.tex is regenerated from it and must
# be kept in sync — CI enforces this via `make params-check`.

params: latex/parameters.tex

latex/parameters.tex: latex/parameters.toml scripts/gen_parameters_tex.py
	python3 scripts/gen_parameters_tex.py

params-check:
	python3 scripts/gen_parameters_tex.py --check

# --- Build ---

all: build test

build: params build-article build-ieee

build-article: params
	cd latex && tectonic rcs-definitions.tex

build-ieee: params
	cd latex && tectonic rcs-definitions-ieee.tex

# --- Test ---
# Numerical validation of the stability budget theorem
# and algebraic property checks

test: params-check
	python3 tests/test_stability_budget.py
	python3 tests/test_lyapunov_simulation.py

# --- Clean ---

clean:
	cd latex && rm -f *.aux *.bbl *.blg *.log *.out *.toc *.nav *.snm *.vrb *.synctex.gz
