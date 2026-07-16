"""
Test: Agency-Necessity Lemma — persistent goal-directed behavior under
disturbance requires a strictly positive contraction rate λ>0 (BRO-1923).

Question: does *intelligence* need control/stability? The answer splits:

  * CAPABILITY (raw function-power) does NOT — it is orthogonal to λ
    (compute-stability-budget-orthogonality, 9/9): capability rides the
    compute axis, λ fixes the unbuyable time-scale ratios. Perpendicular.
  * AGENCY (capability harnessed to a persistent goal under disturbance)
    DOES — this file is the witness.

Define AGENCY as: ultimate-boundedness of the goal error ‖x − x*‖ to an
ε-ball, for EVERY disturbance signal bounded by D̄>0, over a horizon H.
That is the converse-ISS-Lyapunov necessity (Sontag–Wang) plus a sharp
OPEN-LOOP ESCAPE CLAUSE that says exactly when feedback is dispensable.

Canonical plant — the single integrator (a neutrally-stable / drift-prone
plant, the interesting case; a naturally-contracting plant needs no help):

    ẋ = u + d,   goal x* = 0,   |d(t)| ≤ D̄

  * OPEN-LOOP  u = r(t) = 0   (reference: "stay at 0", no state feedback)
      ẋ = d ⟹ worst-case x(t) = x0 + D̄·t → UNBOUNDED.
      Exits the ε-ball at H* = (ε − |x0|)/D̄. Persistence fails past a
      finite horizon.
  * CLOSED-LOOP  u = −k·x   (feedback, contraction rate λ = k > 0)
      ẋ = −k x + d ⟹ x(t) → ISS ball of radius D̄/k.
      Ultimate bound ε achievable IFF k ≥ D̄/ε. So λ>0 is necessary AND
      its magnitude is bounded below by D̄/ε.
  * λ = 0 boundary: k→0 recovers open-loop (ISS ball D̄/k → ∞).

ESCAPE CLAUSE (the framed contribution — converse-Lyapunov itself is
classical): open-loop suffices IFF H·D̄ < ε (with x0=0, unit disturbance
gain). One-shot / short-horizon capability escapes the requirement;
persistent agency (H→∞, any D̄>0) does not.

Here λ = k is exactly the L0/L1 contraction rate in the RCS stability
budget, so the last test grounds the lemma against the canonical per-level
λ_i in data/parameters.toml (drift net, same convention as
test_stability_budget.py): every stable RCS level clears the agency bar
with a finite ISS ball D̄/λ_i.

Pure stdlib (math + tomllib). Wired into the Makefile `test` target and the
ci.yml `test-proofs` job, so it runs in CI.
"""

import math
import sys
import tomllib
from pathlib import Path

PARAMETERS_TOML = Path(__file__).resolve().parents[1] / "data" / "parameters.toml"

# Canonical scenario constants (dimensionless).
D_BAR = 0.5      # disturbance magnitude bound |d| ≤ D̄
EPS = 0.1        # goal-error tolerance (ε-ball radius)
K_STAR = D_BAR / EPS   # = 5.0, the exact necessity threshold on the contraction rate


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


def open_loop_x(x0, t, d=D_BAR):
    """Open-loop u=0, constant worst-case disturbance: x(t) = x0 + d·t (closed form)."""
    return x0 + d * t


def closed_loop_x(x0, t, k, d=D_BAR):
    """Closed-loop u=−kx, constant worst-case disturbance (closed form):
    x(t) = (x0 − d/k)·e^{−kt} + d/k → d/k as t→∞."""
    return (x0 - d / k) * math.exp(-k * t) + d / k


# =============================================================================

def test_open_loop_error_grows_linearly():
    """Open-loop error is unbounded: |x(H)| = x0 + D̄·H, linear in H."""
    x0, H = 0.0, 10.0
    x_H = open_loop_x(x0, H)
    x_2H = open_loop_x(x0, 2 * H)
    # linear growth: doubling the horizon adds exactly D̄·H more error
    assert abs((x_2H - x_H) - D_BAR * H) < 1e-9, (x_H, x_2H)
    # unbounded: no finite ceiling — error at 100H is 10x error at 10H
    assert open_loop_x(x0, 100 * H) > 10 * x_H
    print(f"  PASS  open-loop error grows linearly & unbounded "
          f"(|x({H})|={x_H:.3f}, |x({2*H})|={x_2H:.3f})")


def test_open_loop_crossover_horizon():
    """Open-loop exits the ε-ball at exactly H* = (ε − |x0|)/D̄."""
    x0 = 0.02
    H_star = (EPS - x0) / D_BAR
    # just before: inside; just after: outside
    assert open_loop_x(x0, H_star * 0.99) < EPS
    assert open_loop_x(x0, H_star * 1.01) > EPS
    # numeric crossing matches analytic H*
    ts, xs = integrate(lambda _t, _x: D_BAR, x0, H_star * 2)
    t_cross = next(t for t, x in zip(ts, xs) if x >= EPS)
    assert abs(t_cross - H_star) < 2e-3, (t_cross, H_star)
    print(f"  PASS  open-loop crossover horizon H* = (ε−x0)/D̄ = {H_star:.4f} "
          f"(numeric {t_cross:.4f})")


def test_closed_loop_iss_ball_is_D_over_k():
    """Closed-loop converges to the ISS ball of radius D̄/k (constant worst-case)."""
    x0, k = 3.0, K_STAR
    x_ss = closed_loop_x(x0, 50.0, k)          # long horizon → steady state
    assert abs(x_ss - D_BAR / k) < 1e-6, (x_ss, D_BAR / k)
    print(f"  PASS  closed-loop ISS ball = D̄/k = {D_BAR/k:.4f} (x_ss={x_ss:.6f})")


def test_contraction_rate_necessity_threshold():
    """Ultimate bound ≤ ε IFF k ≥ D̄/ε. k*=D̄/ε is the exact threshold."""
    # at threshold: steady-state error == ε (boundary)
    assert abs(closed_loop_x(0.0, 100.0, K_STAR) - EPS) < 1e-6
    # below threshold (weaker contraction): ultimate bound EXCEEDS ε → agency fails
    k_weak = K_STAR * 0.5
    assert closed_loop_x(0.0, 100.0, k_weak) > EPS
    # above threshold: ultimate bound strictly inside ε → agency holds
    k_strong = K_STAR * 2.0
    assert closed_loop_x(0.0, 100.0, k_strong) < EPS
    print(f"  PASS  necessity threshold k* = D̄/ε = {K_STAR:.3f} "
          f"(k<k*→fail, k>k*→hold)")


def test_lambda_zero_recovers_open_loop():
    """As k→0⁺ the ISS ball D̄/k → ∞: no feedback == unbounded == open-loop.
    λ>0 is therefore STRICTLY necessary for a finite ultimate bound."""
    balls = [(k, D_BAR / k) for k in (5.0, 1.0, 0.1, 0.01, 0.001)]
    # monotone increasing as k decreases; diverges as k→0
    for i in range(len(balls) - 1):
        assert balls[i][1] < balls[i + 1][1]
    assert balls[-1][1] > 100.0   # k=1e-3 → ball 500, already unbounded-scale
    print(f"  PASS  λ→0 ⟹ ISS ball → ∞  (D̄/k: "
          f"{', '.join(f'{b:.1f}' for _, b in balls)})")


def test_closed_loop_transient_matches_closed_form():
    """The numerically integrated closed-loop TRANSIENT matches the analytic
    x(t) = (x0−D̄/k)e^{−kt} + D̄/k at every sampled time — a genuine
    ODE-vs-closed-form check (not just the steady state), which would fail if
    the closed form used elsewhere were wrong."""
    x0, k = 3.0, K_STAR
    def f(_t, x):
        return -k * x + D_BAR
    ts, xs = integrate(f, x0, 2.0, dt=1e-4)
    max_err = max(abs(x - closed_loop_x(x0, t, k)) for t, x in zip(ts, xs))
    assert max_err < 1e-5, max_err
    print(f"  PASS  closed-loop transient matches (x0−D̄/k)e^(−kt)+D̄/k "
          f"(max err {max_err:.1e})")


def test_ultimate_bound_under_time_varying_disturbance():
    """The ISS ball D̄/k bounds the error under a genuinely TIME-VARYING
    disturbance — an exogenous square wave d(t) = D̄·sign(sin ωt) that forces the
    state both directions — while the constant, sign-aligned disturbance is
    EXTREMAL (it alone achieves D̄/k). Necessity is over the whole |d|≤D̄ class.

    (A sign-aligned adversary d=D̄·sign(x) degenerates to constant +D̄ once the
    state settles at the far edge and never switches, so it does NOT exercise
    time variation — a square wave does, and lands strictly inside the extremal
    ball because fast switching gives the plant less time to drift.)"""
    k, omega = K_STAR, 20.0
    def f(t, x):
        return -k * x + D_BAR * (1.0 if math.sin(omega * t) >= 0 else -1.0)
    ts, xs = integrate(f, 0.0, 30.0)
    ultimate = max(abs(x) for t, x in zip(ts, xs) if t > 15.0)   # tail
    # time-varying disturbance stays within — and strictly inside — the extremal ball
    assert ultimate <= D_BAR / k + 1e-9, (ultimate, D_BAR / k)
    assert ultimate < D_BAR / k, "switching d must land strictly inside the constant-d extremal ball"
    # the constant, sign-aligned disturbance ACHIEVES the extremal bound D̄/k
    assert abs(closed_loop_x(3.0, 50.0, k) - D_BAR / k) < 1e-6
    print(f"  PASS  time-varying square-wave d strictly inside extremal ball "
          f"D̄/k={D_BAR/k:.4f} (ultimate={ultimate:.4f}); constant d achieves it")


def test_open_loop_escape_clause():
    """Open-loop (no λ) SUFFICES iff H·D̄ < ε (x0=0). Below the horizon
    threshold, capability without feedback is fine; above it, only λ>0 keeps
    the error bounded. This is the precise boundary between one-shot
    capability and persistent agency."""
    H_thresh = EPS / D_BAR                      # = 0.2
    assert open_loop_x(0.0, 0.9 * H_thresh) < EPS   # short horizon → open-loop OK
    assert open_loop_x(0.0, 1.1 * H_thresh) > EPS   # past it → open-loop fails
    # closed-loop with k≥k* holds for an UNBOUNDED horizon (contrast)
    assert closed_loop_x(0.0, 1000.0, K_STAR) <= EPS + 1e-6
    print(f"  PASS  escape clause: open-loop ok iff H < ε/D̄ = {H_thresh:.3f}; "
          f"closed-loop holds ∀H")


def test_canonical_lambda_drift_guard_and_grounding():
    """Drift guard + grounding (NOT independent lemma validation): every stable
    RCS level in data/parameters.toml has λ_i>0 (recomputed, matching the cached
    [derived.lambda]) so its agency ISS ball D̄/λ_i is finite. The finiteness is
    a trivial corollary of λ_i>0 — the substantive assertion here is the
    parameter-cache consistency (same drift-net convention as
    test_stability_budget.py::test_recursive_all_levels_stable). It exists to
    (a) catch parameter drift and (b) ground the lemma's λ in the canonical
    per-level contraction rates; the lemma itself is witnessed by the tests
    above, not by this one."""
    with PARAMETERS_TOML.open("rb") as fh:
        cfg = tomllib.load(fh)
    assert cfg["schema_version"] == 1, (
        f"unsupported schema_version {cfg['schema_version']}: written for v1"
    )

    def lam(l):
        # λ_i = γ − L_θρ − L_dη − βτ̄ − ln(ν)/τ_a  (Eq. 15)
        return (l["gamma"] - l["L_theta"] * l["rho"] - l["L_d"] * l["eta"]
                - l["beta"] * l["tau_bar"] - math.log(l["nu"]) / l["tau_a"])

    cached = cfg["derived"]["lambda"]
    recomputed = {l["id"]: lam(l) for l in cfg["levels"]}
    assert set(recomputed) == {"L0", "L1", "L2", "L3"}, sorted(recomputed)
    for lid, val in recomputed.items():
        assert abs(val - cached[lid]) < 1e-6, (
            f"drift: [derived.lambda].{lid}={cached[lid]} vs recomputed {val:.9f}. "
            f"Run scripts/gen_parameters_tex.py."
        )
        assert val > 0.0, f"level {lid} has λ={val} ≤ 0 — cannot sustain agency"
        iss_ball = D_BAR / val
        assert math.isfinite(iss_ball) and iss_ball > 0
    worst = max(recomputed, key=lambda k: D_BAR / recomputed[k])   # smallest λ → biggest ball
    print(f"  PASS  all 4 RCS levels clear the agency bar (λ_i>0, finite D̄/λ_i); "
          f"tightest at {worst} (λ={recomputed[worst]:.6f}, ball={D_BAR/recomputed[worst]:.2f})")


# =============================================================================

if __name__ == "__main__":
    tests = [
        test_open_loop_error_grows_linearly,
        test_open_loop_crossover_horizon,
        test_closed_loop_iss_ball_is_D_over_k,
        test_contraction_rate_necessity_threshold,
        test_lambda_zero_recovers_open_loop,
        test_closed_loop_transient_matches_closed_form,
        test_ultimate_bound_under_time_varying_disturbance,
        test_open_loop_escape_clause,
        test_canonical_lambda_drift_guard_and_grounding,
    ]

    print("=" * 66)
    print("Agency-necessity: persistent goal-directed behavior needs λ>0")
    print("=" * 66)

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

    print("=" * 66)
    print(f"{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
