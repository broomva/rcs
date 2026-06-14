"""
Test: Endogenous-gamma — controllability of recursive capability growth (BRO-1518)

Extends the RCS stability budget to ENDOGENOUS capability: gamma (the nominal
decay = capability) is no longer constant but improves itself,

    d(gamma)/dt = kappa * eta * gamma^alpha        (alpha = returns-to-RSI exponent)

Tracking a self-improving plant costs control effort. Both P0 cost channels scale
with capability:
    switching  (re-tune rate 1/tau_a ~ 1/tau_gamma):   B_s * gamma^(alpha-1)
    adaptation (control effort ~ gamma^p):             B_a * p * gamma^(alpha+p-1)
so the closed-loop effective decay is

    gamma_eff(gamma) = gamma - B_s gamma^(alpha-1) - B_a p gamma^(alpha+p-1)

and the homeostatic Lyapunov function contracts iff gamma_eff > 0.

THEOREM (controllability threshold).  As gamma -> inf the binding exponent is
(alpha + p - 2), so the contraction certificate stays positive iff

        alpha  <  alpha*  =  2 - p .

  p = 0 (capability free to wield) -> alpha* = 2   (recovers the switching-only budget)
  p = 1 (verification cost ~ capability, per the verifier-ceiling) -> alpha* = 1

TWO thresholds, three regimes:
  - alpha = 1 : BLOWUP line.  alpha<=1 infinite-horizon growth; alpha>1 finite-time
                singularity at t* = gamma0^(1-alpha) / ((alpha-1) kappa eta).
  - alpha = 2-p : CONTROL-LOSS line.  below it the certificate stays positive
                (homeostasis survives, ceiling is thermodynamic); above it the
                certificate flips negative before the singularity (control lost).

This file is the runnable witness: pure stdlib (math only) so it runs in CI.
"""

import math
import sys

KAPPA, ETA = 0.10, 0.20
LN_NU, C, L_TH = math.log(1.2), 10.0, 5.0
B_S = LN_NU * C * KAPPA * ETA      # switching-cost coefficient
B_A = L_TH * KAPPA * ETA           # adaptation-cost coefficient


def gamma_eff(gamma: float, alpha: float, p: float) -> float:
    """Closed-loop effective decay rate of the homeostatic Lyapunov function."""
    return gamma - B_S * gamma ** (alpha - 1) - B_A * p * gamma ** (alpha + p - 1)


def certificate_flips_at(alpha: float, p: float, g0: float = 1.0,
                         dt: float = 2e-4, T: float = 400.0, gcap: float = 1e7):
    """Integrate the capability ODE; return the gamma at which gamma_eff first
    goes <= 0 (control lost), or None if it stays positive over the trajectory."""
    g, t = g0, 0.0
    while t < T:
        if gamma_eff(g, alpha, p) <= 0:
            return g
        g += KAPPA * ETA * g ** alpha * dt
        t += dt
        if g >= gcap:
            break
    return None


def blowup_time(alpha: float, g0: float = 1.0, dt: float = 1e-4,
                T: float = 1000.0, gcap: float = 1e9):
    """Numerically integrate to the finite-time singularity (alpha > 1)."""
    g, t = g0, 0.0
    while t < T:
        g += KAPPA * ETA * g ** alpha * dt
        t += dt
        if g >= gcap:
            return t
    return None  # no blowup within horizon


def analytic_tstar(alpha: float, g0: float = 1.0) -> float:
    """t* = gamma0^(1-alpha) / ((alpha-1) kappa eta), alpha > 1."""
    return g0 ** (1 - alpha) / ((alpha - 1) * KAPPA * ETA)


# ─── Tests ───────────────────────────────────────────────────────────────────

def test_control_loss_threshold_is_2_minus_p():
    """The certificate flips negative (control lost) iff alpha > 2 - p, for every p."""
    for p in (0.0, 0.5, 1.0):
        astar = 2 - p
        # below threshold -> certificate must stay positive (control maintained)
        for alpha in (astar - 0.4, astar - 0.1):
            if alpha <= 0:
                continue
            assert certificate_flips_at(alpha, p) is None, (
                f"p={p} alpha={alpha} < {astar}: expected control, certificate flipped"
            )
        # above threshold -> certificate must flip negative (control lost)
        for alpha in (astar + 0.5, astar + 1.5):
            assert certificate_flips_at(alpha, p) is not None, (
                f"p={p} alpha={alpha} > {astar}: expected control-loss, certificate stayed positive"
            )
    print("  PASS  control-loss threshold alpha* = 2 - p (p in {0, 0.5, 1})")


def test_p0_recovers_switching_only_threshold():
    """p=0 (capability free to wield) recovers the switching-only budget: alpha* = 2."""
    assert certificate_flips_at(1.7, 0.0) is None, "alpha=1.7 < 2 must stay controlled"
    assert certificate_flips_at(2.5, 0.0) is not None, "alpha=2.5 > 2 must lose control"
    print("  PASS  p=0 -> alpha* = 2 (consistent with the switching-only stability budget)")


def test_verifier_ceiling_corollary_p1():
    """p=1 (verification cost ~ capability, per the verifier-ceiling literature):
    only SUB-CRITICAL self-improvement (alpha < 1) is controllable."""
    assert certificate_flips_at(0.8, 1.0) is None, "alpha=0.8 < 1 must stay controlled"
    assert certificate_flips_at(1.3, 1.0) is not None, "alpha=1.3 > 1 must lose control"
    print("  PASS  p=1 -> alpha* = 1 (only diminishing-returns RSI is controllable)")


def test_blowup_time_matches_analytic():
    """alpha > 1 -> finite-time singularity at the analytic t* (Bernoulli ODE)."""
    for alpha in (1.5, 2.0, 3.0):
        num = blowup_time(alpha)
        ana = analytic_tstar(alpha)
        assert num is not None, f"alpha={alpha} must blow up in finite time"
        rel = abs(num - ana) / ana
        assert rel < 0.02, f"alpha={alpha}: numeric t*={num:.3f} vs analytic {ana:.3f} (rel {rel:.3%})"
    print("  PASS  finite-time blowup t* = gamma0^(1-alpha)/((alpha-1) kappa eta) (alpha>1)")


def test_subcritical_no_finite_time_blowup():
    """alpha <= 1 -> growth has an infinite time horizon (no finite-time singularity)."""
    for alpha in (0.5, 1.0):
        assert blowup_time(alpha, T=500.0) is None, (
            f"alpha={alpha} <= 1 must NOT blow up in finite time"
        )
    print("  PASS  alpha <= 1: no finite-time blowup (infinite-horizon growth)")


def test_certificate_monotone_in_alpha():
    """Sanity: at fixed large gamma, gamma_eff decreases as alpha increases (more
    aggressive self-improvement costs more control)."""
    g, p = 50.0, 0.5
    effs = [gamma_eff(g, a, p) for a in (1.0, 1.5, 2.0, 2.5)]
    assert all(effs[i] > effs[i + 1] for i in range(len(effs) - 1)), effs
    print("  PASS  gamma_eff decreasing in alpha at fixed capability")


if __name__ == "__main__":
    tests = [
        test_control_loss_threshold_is_2_minus_p,
        test_p0_recovers_switching_only_threshold,
        test_verifier_ceiling_corollary_p1,
        test_blowup_time_matches_analytic,
        test_subcritical_no_finite_time_blowup,
        test_certificate_monotone_in_alpha,
    ]
    print("=" * 64)
    print("Endogenous-gamma: controllability of recursive capability growth")
    print("=" * 64)
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            print(f"  FAIL  {t.__name__}: {e}")
            failed += 1
    print("=" * 64)
    print(f"{len(tests) - failed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
