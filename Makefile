# =============================================================================
# RCS — Build & Test
# =============================================================================

.PHONY: all build build-article build-ieee test clean

# --- Build ---

all: build test

build: build-article build-ieee

build-article:
	cd latex && tectonic rcs-definitions.tex

build-ieee:
	cd latex && tectonic rcs-definitions-ieee.tex

# --- Test ---
# Numerical validation of the stability budget theorem
# and algebraic property checks

test:
	python3 tests/test_stability_budget.py
	python3 tests/test_lyapunov_simulation.py

# --- Clean ---

clean:
	cd latex && rm -f *.aux *.bbl *.blg *.log *.out *.toc *.nav *.snm *.vrb *.synctex.gz
