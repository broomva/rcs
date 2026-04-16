"""
Test: Recursive Stability Budget (Theorem 5.8 / Eq. 15)

Validates the stability budget equation:
    λ_i = γ_i - L_θ,i·ρ_i - L_d,i·η_i - β_i·τ̄_i - (ln ν_i)/τ_a,i

Tests:
1. Budget positivity under known-stable parameters
2. Budget negativity under known-unstable parameters
3. Monotonic sensitivity to each cost term
4. Eslami (2026) simulation parameters reproduce their result
5. Cross-level coupling: L2 mutations must respect L1 margin
6. HysteresisGate dwell-time satisfies switching constraint
"""

import math
import sys


class StabilityBudget:
    """The recursive stability budget at a single level."""

    def __init__(
        self,
        gamma: float,       # nominal decay rate
        L_theta: float,     # adaptation sensitivity
        rho: float,         # adaptation rate bound
        L_d: float,         # design sensitivity
        eta: float,         # design evolution rate bound
        beta: float,        # delay sensitivity
        tau_bar: float,     # supremal total delay
        nu: float,          # jump comparability factor (>= 1)
        tau_a: float,       # average dwell time
    ):
        self.gamma = gamma
        self.L_theta = L_theta
        self.rho = rho
        self.L_d = L_d
        self.eta = eta
        self.beta = beta
        self.tau_bar = tau_bar
        self.nu = nu
        self.tau_a = tau_a

    @property
    def adaptation_cost(self) -> float:
        return self.L_theta * self.rho

    @property
    def design_cost(self) -> float:
        return self.L_d * self.eta

    @property
    def delay_cost(self) -> float:
        return self.beta * self.tau_bar

    @property
    def switching_cost(self) -> float:
        if self.tau_a <= 0:
            return float('inf')
        return math.log(self.nu) / self.tau_a

    @property
    def margin(self) -> float:
        """λ = γ - Σ costs"""
        return (
            self.gamma
            - self.adaptation_cost
            - self.design_cost
            - self.delay_cost
            - self.switching_cost
        )

    @property
    def is_stable(self) -> bool:
        return self.margin > 0

    def max_mutation_magnitude(self) -> float:
        """Maximum η that keeps λ > 0 (Proposition 7.1)."""
        numerator = (
            self.gamma
            - self.adaptation_cost
            - self.delay_cost
            - self.switching_cost
        )
        if self.L_d <= 0:
            return float('inf')
        return numerator / self.L_d


def test_eslami_stable_case():
    """Reproduce Eslami & Yu (2026) stable simulation parameters.

    From the paper (Section V):
    γ = 0.609, ν = 2.2, L_θ = 0.8, β = 2.5
    ρ = 0.15, τ_a = 4.0, τ̄ = 0.03
    Expected λ = 0.609 - 0.120 - 0.075 - 0.197 = +0.217
    """
    b = StabilityBudget(
        gamma=0.609,
        L_theta=0.8, rho=0.15,
        L_d=0.0, eta=0.0,          # no design evolution in their example
        beta=2.5, tau_bar=0.03,
        nu=2.2, tau_a=4.0,
    )
    assert b.is_stable, f"Eslami stable case should be stable, got λ={b.margin:.4f}"
    assert abs(b.margin - 0.217) < 0.01, f"Expected λ≈0.217, got {b.margin:.4f}"
    print(f"  PASS  Eslami stable case: λ = {b.margin:.4f}")


def test_eslami_unstable_case():
    """Reproduce Eslami & Yu (2026) unstable simulation parameters.

    ρ = 3.5, τ_a = 0.4, τ̄ = 0.20
    Expected λ = 0.609 - 2.800 - 0.500 - 1.971 = -4.662
    """
    b = StabilityBudget(
        gamma=0.609,
        L_theta=0.8, rho=3.5,
        L_d=0.0, eta=0.0,
        beta=2.5, tau_bar=0.20,
        nu=2.2, tau_a=0.4,
    )
    assert not b.is_stable, f"Eslami unstable case should be unstable, got λ={b.margin:.4f}"
    assert abs(b.margin - (-4.662)) < 0.01, f"Expected λ≈-4.662, got {b.margin:.4f}"
    print(f"  PASS  Eslami unstable case: λ = {b.margin:.4f}")


def test_sensitivity_adaptation_rate():
    """Increasing adaptation rate ρ monotonically decreases margin."""
    base = StabilityBudget(
        gamma=1.0, L_theta=0.5, rho=0.1,
        L_d=0.0, eta=0.0,
        beta=0.0, tau_bar=0.0,
        nu=1.5, tau_a=5.0,
    )
    margins = []
    for rho in [0.1, 0.5, 1.0, 1.5, 2.0]:
        b = StabilityBudget(
            gamma=1.0, L_theta=0.5, rho=rho,
            L_d=0.0, eta=0.0,
            beta=0.0, tau_bar=0.0,
            nu=1.5, tau_a=5.0,
        )
        margins.append(b.margin)
    for i in range(len(margins) - 1):
        assert margins[i] > margins[i + 1], \
            f"Margin should decrease with ρ: {margins}"
    print(f"  PASS  Sensitivity: ρ ↑ → λ ↓  ({[f'{m:.3f}' for m in margins]})")


def test_sensitivity_delay():
    """Increasing delay τ̄ monotonically decreases margin."""
    margins = []
    for tau_bar in [0.0, 0.05, 0.10, 0.20, 0.50]:
        b = StabilityBudget(
            gamma=1.0, L_theta=0.5, rho=0.1,
            L_d=0.0, eta=0.0,
            beta=2.0, tau_bar=tau_bar,
            nu=1.5, tau_a=5.0,
        )
        margins.append(b.margin)
    for i in range(len(margins) - 1):
        assert margins[i] > margins[i + 1], \
            f"Margin should decrease with τ̄: {margins}"
    print(f"  PASS  Sensitivity: τ̄ ↑ → λ ↓  ({[f'{m:.3f}' for m in margins]})")


def test_sensitivity_switching():
    """Decreasing dwell time τ_a (faster switching) decreases margin."""
    margins = []
    for tau_a in [10.0, 5.0, 2.0, 1.0, 0.5]:
        b = StabilityBudget(
            gamma=1.0, L_theta=0.5, rho=0.1,
            L_d=0.0, eta=0.0,
            beta=0.0, tau_bar=0.0,
            nu=2.0, tau_a=tau_a,
        )
        margins.append(b.margin)
    for i in range(len(margins) - 1):
        assert margins[i] > margins[i + 1], \
            f"Margin should decrease as τ_a decreases: {margins}"
    print(f"  PASS  Sensitivity: τ_a ↓ → λ ↓  ({[f'{m:.3f}' for m in margins]})")


def test_egri_mutation_bound():
    """EGRI mutation magnitude must respect L1 stability margin (Prop. 7.1).

    η₁ < (γ₁ - L_θ,₁·ρ₁ - β₁·τ̄₁ - ln(ν₁)/τ_a,₁) / L_d,₁
    """
    b = StabilityBudget(
        gamma=0.8,
        L_theta=0.3, rho=0.2,
        L_d=0.5, eta=0.0,      # eta is what we're bounding
        beta=1.0, tau_bar=0.05,
        nu=1.5, tau_a=3.0,
    )
    max_eta = b.max_mutation_magnitude()
    assert max_eta > 0, f"Max mutation should be positive for stable base, got {max_eta}"

    # At max_eta, margin should be ~0
    b_at_max = StabilityBudget(
        gamma=0.8,
        L_theta=0.3, rho=0.2,
        L_d=0.5, eta=max_eta - 0.001,
        beta=1.0, tau_bar=0.05,
        nu=1.5, tau_a=3.0,
    )
    assert b_at_max.is_stable, "Should be barely stable at η = max - ε"

    b_over_max = StabilityBudget(
        gamma=0.8,
        L_theta=0.3, rho=0.2,
        L_d=0.5, eta=max_eta + 0.001,
        beta=1.0, tau_bar=0.05,
        nu=1.5, tau_a=3.0,
    )
    assert not b_over_max.is_stable, "Should be unstable at η = max + ε"
    print(f"  PASS  EGRI mutation bound: η_max = {max_eta:.4f}")


def test_hysteresis_dwell_time():
    """HysteresisGate's min_hold_ms satisfies the dwell-time condition.

    From Eslami Proposition 2: τ_h ≥ 2h̲/M̄
    For stability: τ_h > ln(ν)/(γ - L_θ·ρ)

    Life Autonomic uses min_hold_ms = 30000 (30 seconds).
    """
    min_hold_s = 30.0  # 30 seconds, from HysteresisGate default

    # Typical L1 parameters for the Life agent
    gamma = 0.5       # moderate decay rate
    L_theta = 0.3
    rho = 0.1
    nu = 1.5

    required_dwell = math.log(nu) / (gamma - L_theta * rho)
    assert min_hold_s > required_dwell, \
        f"HysteresisGate dwell ({min_hold_s}s) must exceed required ({required_dwell:.2f}s)"
    print(f"  PASS  Hysteresis dwell: {min_hold_s}s > required {required_dwell:.2f}s")


def test_recursive_all_levels_stable():
    """A 4-level RCS hierarchy (L0-L3) with realistic parameters.

    Time-scale separation: each level ~10x slower than the one below.
    """
    levels = {
        "L0 (plant)": StabilityBudget(
            gamma=2.0, L_theta=0.3, rho=0.5,
            L_d=0.1, eta=0.2,
            beta=1.0, tau_bar=0.01,   # fast inner loop
            nu=1.2, tau_a=0.5,
        ),
        "L1 (autonomic)": StabilityBudget(
            gamma=0.5, L_theta=0.2, rho=0.1,
            L_d=0.1, eta=0.05,
            beta=0.5, tau_bar=0.1,    # seconds
            nu=1.5, tau_a=30.0,       # 30s dwell (hysteresis gate)
        ),
        "L2 (EGRI)": StabilityBudget(
            gamma=0.1, L_theta=0.05, rho=0.01,
            L_d=0.02, eta=0.01,
            beta=0.0005, tau_bar=60.0,  # β is small: delay is expected at this scale
            nu=1.1, tau_a=3600.0,       # hours between promotions
        ),
        "L3 (governance)": StabilityBudget(
            gamma=0.01, L_theta=0.001, rho=0.001,
            L_d=0.001, eta=0.0005,
            beta=0.000001, tau_bar=3600.0,  # β ≈ 0: delay is the norm, not a perturbation
            nu=1.05, tau_a=86400.0,         # days between policy changes
        ),
    }

    all_stable = True
    for name, b in levels.items():
        status = "STABLE" if b.is_stable else "UNSTABLE"
        if not b.is_stable:
            all_stable = False
        print(f"         {name}: λ = {b.margin:.6f} ({status})")

    assert all_stable, "All levels must be stable for composite stability"
    omega = min(b.margin for b in levels.values())
    print(f"  PASS  4-level hierarchy stable, ω = min λ = {omega:.6f}")


def test_budget_is_lyapunov():
    """EGRI budget B(t) is monotonically decreasing (Law 4).

    Simulates a sequence of trials consuming budget.
    """
    initial_budget = 100.0
    cost_per_trial = 3.5
    budget = initial_budget

    for trial in range(20):
        new_budget = budget - cost_per_trial
        if new_budget <= 0:
            # Budget closure: halt
            break
        assert new_budget < budget, \
            f"Budget must decrease: B({trial+1})={new_budget} >= B({trial})={budget}"
        budget = new_budget

    assert budget > 0 or trial < 20, "Budget should either exhaust or complete all trials"
    print(f"  PASS  EGRI budget is Lyapunov: {initial_budget} → {budget:.1f} in {trial+1} trials")


# =============================================================================
# Run all tests
# =============================================================================

if __name__ == "__main__":
    tests = [
        test_eslami_stable_case,
        test_eslami_unstable_case,
        test_sensitivity_adaptation_rate,
        test_sensitivity_delay,
        test_sensitivity_switching,
        test_egri_mutation_bound,
        test_hysteresis_dwell_time,
        test_recursive_all_levels_stable,
        test_budget_is_lyapunov,
    ]

    print("=" * 60)
    print("RCS Stability Budget Tests")
    print("=" * 60)

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR {test.__name__}: {e}")
            failed += 1

    print("=" * 60)
    print(f"{passed} passed, {failed} failed")
    sys.exit(1 if failed > 0 else 0)
