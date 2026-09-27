"""
Test: Non-Stationary-Objective Theorem — internalizing the verifier makes the
terminal objective non-stationary or world-decoupled (BRO-1924).

Question: what are the impacts of RSI in an UNCONTROLLED realm? "Uncontrolled"
has a precise meaning here (from endogenous-reference-contamination /
anthropic-rsi-as-control-problem): the independent verifier is removed, so the
reference the controller tracks is INTERNALIZED — r = g(x), the verifier grades
the very state it reads. This file makes those dynamics explicit and testable.

Model — one parametric family with an INTERNALIZATION FRACTION μ ∈ [0,1]:

    ẋ = −k (x − r),   r = (1−μ)·r₀ + μ·g(x),   g(x) = a·x + b

  * μ = 0  →  exogenous reference r = r₀ (standard control): the world sets the
             goal. Attractor x* = r₀; ∂x*/∂r₀ = 1 (world-coupled, stationary).
  * μ = 1  →  fully internalized r = g(x): the verifier reads its own state.

Fixed point of the blended loop:  x* = [(1−μ)r₀ + μb] / (1 − μa),
so the COUPLING SENSITIVITY (a static sensitivity of the fixed point — related
to, not identical with, the trajectory-conserved independence h⟂U) is

    h_coupling(μ) ≔ ∂x*/∂r₀ = (1−μ)/(1−μa)  :  1 (μ=0)  →  0 (μ=1).

Consequences at μ = 1 (verifier fully internalized):
  1. EXISTENCE DICHOTOMY — g(x)=x+c (a=1, c≠0) has NO fixed point ⟹ ẋ = kc,
     unbounded drift (incoherent-drift sub-case); or a<1 ⟹ unique x*=b/(1−a).
  2. DECOUPLING — at any fixed point ∂x*/∂r₀ = 0: the terminal objective is
     causally independent of the exogenous task (the reward-hack / wirehead
     fixed point). h_coupling collapses 1 → 0.
  3. NON-STATIONARY TRANSIENT — the tracked target g(x(t)) co-moves with the
     state: d/dt[g(x)] = a·ẋ ≠ 0 off equilibrium. The reference is a function
     of the tracked variable.
  4. STABILITY — the fixed point is stable iff (1−μa) > 0. For a>1 a fixed
     point exists formally but repels ⟹ divergence.

Corollary (AI-risk translation): uncontrolled RSI does NOT yield "the wrong
fixed goal pursued with superhuman competence" (Bostrom stable-terminal-goal +
instrumental convergence). It yields either (a) drift with no stable terminal
goal, or (b) convergence to a fixed point of its own evaluation map, decoupled
from the world. "Monomaniacal coherent optimizer" is neither.

Cross-link to the agency lemma (BRO-1923): at μ=1, a<1 the closed loop is
still CONTRACTING — effective rate λ = k(1−a) > 0 clears the agency-necessity
bar — yet its goal is world-decoupled. λ>0 buys CONVERGENCE, not CORRECTNESS.

Pure stdlib (math only). Wired into the Makefile `test` target and the ci.yml
`test-proofs` job, so it runs in CI.
"""

import math
import sys

K = 1.0   # controller gain (a valid contraction rate; agency-necessity, BRO-1923)


def integrate(f, x0, t_end, dt=1e-3):
    """RK4 integration of ẋ = f(t, x). Returns (t_grid, x_grid)."""
    n = int(round(t_end / dt))
    t, x = 0.0, x0
    ts, xs = [0.0], [x0]
    for _ in range(n):
        k1 = f(t, x)
        k2 = f(t + dt / 2, x + dt / 2 * k1)
        k3 = f(t + dt / 2, x + dt / 2 * k2)
        k4 = f(t + dt, x + dt * k3)
        x += dt / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
        t += dt
        ts.append(t)
        xs.append(x)
    return ts, xs


def dynamics(mu, a, b, r0):
    """ẋ = −k(x − r), r = (1−μ)r₀ + μ(ax+b). Returns f(t, x)."""
    def f(_t, x):
        r = (1 - mu) * r0 + mu * (a * x + b)
        return -K * (x - r)
    return f


def steady_state(mu, a, b, r0, x0=0.0, t_end=200.0):
    """Integrate to (near-)equilibrium and return the terminal state."""
    _ts, xs = integrate(dynamics(mu, a, b, r0), x0, t_end)
    return xs[-1]


def fixed_point_analytic(mu, a, b, r0):
    """x* = [(1−μ)r₀ + μb]/(1−μa)  (defined iff 1−μa ≠ 0)."""
    denom = 1 - mu * a
    return ((1 - mu) * r0 + mu * b) / denom


def h_coupling_analytic(mu, a):
    """Independence quantity h = ∂x*/∂r₀ = (1−μ)/(1−μa)."""
    return (1 - mu) / (1 - mu * a)


def h_coupling_numeric(mu, a, b, r0=1.0, dr=0.25):
    """Finite-difference ∂x*/∂r₀ from two integrated steady states."""
    return (steady_state(mu, a, b, r0 + dr) - steady_state(mu, a, b, r0 - dr)) / (2 * dr)


# =============================================================================

def test_exogenous_objective_stationary_and_world_coupled():
    """μ=0: exogenous reference. Attractor x*=r₀ and ∂x*/∂r₀=1 — the world
    determines the goal (stationary, world-coupled)."""
    a, b = 0.5, 3.0
    for r0 in (2.0, -1.0, 5.0):
        assert abs(steady_state(0.0, a, b, r0) - r0) < 1e-6, r0
    assert abs(h_coupling_numeric(0.0, a, b) - 1.0) < 1e-3
    print("  PASS  μ=0 exogenous: x*→r₀, ∂x*/∂r₀=1 (world-coupled, stationary)")


def test_endogenous_contraction_map_converges():
    """μ=1, a<1: internalized verifier with a contraction map has a unique
    fixed point x*=b/(1−a)."""
    a, b = 0.5, 3.0
    x_star = steady_state(1.0, a, b, r0=99.0)     # r0 arbitrary — should not matter
    assert abs(x_star - b / (1 - a)) < 1e-6, (x_star, b / (1 - a))
    print(f"  PASS  μ=1, a={a}: converges to g's fixed point b/(1−a) = {b/(1-a):.3f}")


def test_endogenous_objective_decoupled_from_world():
    """μ=1, a<1: the terminal objective is causally independent of the
    exogenous task — ∂x*/∂r₀ = 0. The reward-hack / wirehead fixed point."""
    a, b = 0.5, 3.0
    # x* is identical across wildly different "world tasks" r₀
    xs = [steady_state(1.0, a, b, r0) for r0 in (-50.0, 0.0, 50.0)]
    assert max(xs) - min(xs) < 1e-6, xs
    assert abs(h_coupling_numeric(1.0, a, b)) < 1e-3
    print(f"  PASS  μ=1: ∂x*/∂r₀=0 — goal decoupled from world (x*={xs[0]:.3f} ∀r₀)")


def test_endogenous_no_fixed_point_drifts():
    """μ=1, a=1, c≠0 (g(x)=x+c): no fixed point ⟹ ẋ=kc, unbounded linear drift.
    The incoherent-drift sub-case — the objective is never satisfied."""
    c = 0.7
    ts, xs = integrate(dynamics(1.0, 1.0, c, r0=0.0), 0.0, 20.0)
    # constant drift ẋ = k·c ⟹ x(t) = k·c·t (linear, unbounded)
    assert abs(xs[-1] - K * c * ts[-1]) < 1e-6, (xs[-1], K * c * ts[-1])
    assert xs[-1] > 10.0   # unbounded-scale, no equilibrium
    # no fixed point: 1−μa = 0
    assert abs(1 - 1.0 * 1.0) < 1e-12
    print(f"  PASS  μ=1, a=1, c={c}: no fixed point, ẋ=kc drift → x({ts[-1]:.0f})={xs[-1]:.2f}")


def test_endogenous_unstable_fixed_point_diverges():
    """μ=1, a>1: a fixed point x*=b/(1−a) exists FORMALLY but is a repeller
    (effective gain −k(1−a) > 0). The deviation grows as init·e^{k(a−1)t}; we
    assert the exponential RATE k(a−1), not merely ">100× growth" (BRO-1937). A
    half-exponent model e^{½k(a−1)t} still clears 100× at t=20 (e^5≈148), so the
    magnitude-only check does NOT pin the rate that §7 lists as validated."""
    a, b = 1.5, 3.0
    k_rate = K * (a - 1.0)                              # analytic exponent = 0.5
    x_fp = b / (1 - a)   # = -6.0, exists analytically
    init_dev = 0.01
    t_end = 20.0
    # start just off the fixed point → run AWAY from it (repeller), not toward
    ts, xs = integrate(dynamics(1.0, a, b, r0=0.0), x_fp + init_dev, t_end)
    final_dev = abs(xs[-1] - x_fp)
    assert final_dev > 100 * init_dev, (final_dev, init_dev)     # repelled at all
    assert (1 - 1.0 * a) < 0                                     # unstable condition 1−μa<0
    # (1) endpoint magnitude matches init·e^{k(a−1)·t_end} within 1%
    expected = init_dev * math.exp(k_rate * t_end)
    assert abs(final_dev / expected - 1.0) < 1e-2, (final_dev, expected)
    # (2) INTERIOR rate fitted from the trajectory itself between t=10 and t=20 —
    #     a genuine per-t exponent, not just the endpoint; excludes e^{½k(a−1)t}
    i_mid = len(ts) // 2                               # t≈10 (dt=1e-3 ⟹ exact)
    dev_mid = abs(xs[i_mid] - x_fp)
    rate_fit = math.log(final_dev / dev_mid) / (ts[-1] - ts[i_mid])
    assert abs(rate_fit - k_rate) < 1e-2, (rate_fit, k_rate)
    print(f"  PASS  μ=1, a={a}: repeller — deviation grew {final_dev/init_dev:.0f}× "
          f"(fitted rate {rate_fit:.4f} ≈ k(a−1)={k_rate:.3f}; e^{{½·}} model excluded)")


def test_transient_target_is_nonstationary():
    """μ=1, a≠0 (0<|a|<1 here): the tracked target g(x(t))=a·x(t)+b is TIME-VARYING
    while the state moves (d/dt[g(x)]=a·ẋ≠0). The reference co-moves with the
    tracked variable — the defining non-stationarity. a≠0 is REQUIRED: at a=0 the
    map g(x)=b is constant, so the target is stationary (and decoupled) — the
    non-stationarity is an a≠0 phenomenon (BRO-1937)."""
    a, b = 0.5, 3.0
    # effective rate λ=k(1−a)=0.5 → time constant 2s; run 30s (~15 τ) to settle
    _ts, xs = integrate(dynamics(1.0, a, b, r0=0.0), x0=0.0, t_end=30.0)
    targets = [a * x + b for x in xs]
    # target genuinely moves early (off equilibrium) and settles late
    early_delta = abs(targets[200] - targets[0])         # ~0.2s in
    late_delta = abs(targets[-1] - targets[-200])        # near equilibrium
    assert early_delta > 1e-3, early_delta
    assert late_delta < 1e-4, late_delta
    # a=0 BOUNDARY witness: g(x)=a·x+b with a=0 is constant (=b), so the target is
    # STATIONARY even though the STATE sweeps a large range. The state-movement
    # assertion is the non-vacuous anchor (it fails if the integrator is broken or
    # the state is stuck — without it the `0.0·x` would make the target check pass
    # for any trajectory); the target then being pinned at b witnesses
    # d/dt[g(x)]=a·ẋ=0 at a=0 — decoupled AND stationary (BRO-1937 part-3 boundary).
    a0 = 0.0
    _ts0, xs0 = integrate(dynamics(1.0, a0, b, r0=0.0), x0=0.0, t_end=30.0)
    state_range0 = max(xs0) - min(xs0)
    assert state_range0 > 1.0, state_range0                  # state genuinely moves (0→b=3)
    targets0 = [a0 * x + b for x in xs0]
    assert max(targets0) - min(targets0) < 1e-12, targets0   # yet target constant (a0=0)
    print(f"  PASS  μ=1: target g(x(t)) non-stationary off-equilibrium for a={a}≠0 "
          f"(Δearly={early_delta:.3f}, Δlate={late_delta:.1e}); a=0 target constant "
          f"while state swept {state_range0:.2f}")


def test_independence_quantity_collapse():
    """Sweeping μ:0→1, the coupling sensitivity h=∂x*/∂r₀ collapses monotonically
    from 1 (world-anchored) to 0 (self-anchored). "Removing the verifier" is the
    continuous operation that empties world-coupling — the fixed-point signature
    of the trajectory-level h⟂U → 0 event (endogenous-reference-contamination)."""
    a, b = 0.5, 3.0
    prev = 2.0
    for mu in (0.0, 0.25, 0.5, 0.75, 1.0):
        h_an = h_coupling_analytic(mu, a)
        h_nu = h_coupling_numeric(mu, a, b)
        assert abs(h_an - h_nu) < 1e-3, (mu, h_an, h_nu)   # analytic == integrated
        assert h_an < prev, (mu, h_an, prev)               # strictly decreasing
        prev = h_an
        # ALSO pin the general blended fixed-point formula against integration
        # (not just the μ=0/μ=1 special cases) so a constant/sign error in
        # fixed_point_analytic is caught, for r₀ that genuinely matters (μ<1)
        for r0 in (-2.0, 5.0):
            xa = fixed_point_analytic(mu, a, b, r0)
            xn = steady_state(mu, a, b, r0)
            assert abs(xa - xn) < 1e-6, (mu, r0, xa, xn)
    assert abs(h_coupling_analytic(0.0, a) - 1.0) < 1e-12
    assert abs(h_coupling_analytic(1.0, a) - 0.0) < 1e-12
    print("  PASS  coupling sensitivity h=∂x*/∂r₀ collapses 1→0 as μ:0→1 "
          "(analytic==numeric; general x* formula pinned to integration)")


def test_a_gt_1_sweep_is_not_a_smooth_collapse():
    """§3 caveat witness: for a>1 the coupling sensitivity h(μ)=(1−μ)/(1−μa) is
    NOT a smooth 1→0 collapse — it has a POLE at μ=1/a (exactly where the fixed
    point loses stability, 1−μa=0), rising toward +∞ then flipping sign before
    returning to 0 at μ=1. The smooth-knob reading holds only in the contraction
    regime a<1; the endpoints survive, the path between does not."""
    a = 1.5
    mu_pole = 1.0 / a                      # 0.667
    h_below = h_coupling_analytic(mu_pole - 0.02, a)   # → large +
    h_above = h_coupling_analytic(mu_pole + 0.02, a)   # → negative (sign flip)
    assert h_below > 10.0, h_below
    assert h_above < 0.0, h_above
    # endpoints still 1 and 0 despite the discontinuous interior
    assert abs(h_coupling_analytic(0.0, a) - 1.0) < 1e-12
    assert abs(h_coupling_analytic(1.0, a) - 0.0) < 1e-12
    # DYNAMICAL witness (BRO-1937): the pole/sign-flip above are pure formula
    # self-consistency (h_coupling_analytic checked against itself). Pin the
    # pre-pole RISE to actual RK integration on the STABLE side μ<1/a (1−μa>0, so
    # the fixed point is a real attractor): the integrated ∂x*/∂r₀ must match the
    # large analytic value, and the blended fixed point must match integration.
    mu_stable = 0.6                        # < 1/a=0.667 ⟹ 1−μa=0.1>0 (stable)
    h_an_stable = h_coupling_analytic(mu_stable, a)    # = (1−0.6)/0.1 = 4.0
    h_nu_stable = h_coupling_numeric(mu_stable, a, b=3.0)
    assert abs(h_an_stable - 4.0) < 1e-9, h_an_stable
    assert abs(h_an_stable - h_nu_stable) < 1e-3, (h_an_stable, h_nu_stable)
    for r0 in (-2.0, 5.0):
        assert abs(fixed_point_analytic(mu_stable, a, 3.0, r0)
                   - steady_state(mu_stable, a, 3.0, r0)) < 1e-6, (r0,)
    print(f"  PASS  a={a}>1: h(μ) poles at μ=1/a={mu_pole:.3f} "
          f"(below={h_below:.1f}, above={h_above:.1f}) — collapse NOT smooth; "
          f"pre-pole rise pinned to integration (h(0.6)={h_nu_stable:.3f}≈4.0)")


def test_stable_but_decoupled_lambda_buys_convergence_not_correctness():
    """Cross-link to the agency lemma (BRO-1923): at μ=1, a<1 the closed loop
    is CONTRACTING — effective rate λ = k(1−a) > 0 clears the agency-necessity
    bar (BRO-1923) — YET the goal it converges to is world-decoupled
    (∂x*/∂r₀=0). Stability buys CONVERGENCE, not CORRECTNESS: an uncontrolled
    RSI system can be perfectly homeostatic about the wrong, self-defined goal."""
    a, b = 0.5, 3.0
    lam_eff = K * (1 - a)                 # effective closed-loop contraction rate
    assert lam_eff > 0, lam_eff           # clears BRO-1923 agency bar
    # converges (agency) …
    x_star = steady_state(1.0, a, b, r0=42.0)
    assert abs(x_star - b / (1 - a)) < 1e-6
    # … but to a world-decoupled goal (∂x*/∂r₀ = 0)
    assert abs(h_coupling_analytic(1.0, a)) < 1e-12
    print(f"  PASS  λ_eff={lam_eff:.3f}>0 (converges) but ∂x*/∂r₀=0 (decoupled): "
          f"stability ≠ correctness")


# =============================================================================

if __name__ == "__main__":
    tests = [
        test_exogenous_objective_stationary_and_world_coupled,
        test_endogenous_contraction_map_converges,
        test_endogenous_objective_decoupled_from_world,
        test_endogenous_no_fixed_point_drifts,
        test_endogenous_unstable_fixed_point_diverges,
        test_transient_target_is_nonstationary,
        test_independence_quantity_collapse,
        test_a_gt_1_sweep_is_not_a_smooth_collapse,
        test_stable_but_decoupled_lambda_buys_convergence_not_correctness,
    ]

    print("=" * 68)
    print("Non-stationary objective: internalizing the verifier decouples the goal")
    print("=" * 68)

    passed = failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {t.__name__}: {e}")
            failed += 1
        except Exception as e:  # noqa: BLE001
            print(f"  ERROR {t.__name__}: {e}")
            failed += 1

    print("=" * 68)
    print(f"{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
