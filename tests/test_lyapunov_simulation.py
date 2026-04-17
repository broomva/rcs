"""
Test: Lyapunov Simulation of Recursive Stability (Theorem 1, Eq. 15)

Numerical witnesses for the recursive stability budget. Each test integrates
a small switched system with delay and compares the measured Lyapunov decay
to what the budget predicts.

Integrator: classical RK4 (4th-order Runge-Kutta). We previously used forward
Euler at dt=1e-3; with eigenvalues near -5 that sits close to Euler's stability
boundary, so "stable" passes could be artifacts of the integrator rather than
the system. RK4 has a comfortably larger stability region and O(dt^4) local
error, so the witnesses reflect the system.

Dependencies: standard library only (math, sys, random). Pure-Python RK4 is
~20 lines; adding scipy for one integrator would bloat CI for no gain.

Delay handling: fixed-lag ring buffer. Each RK4 sub-stage uses x(t - tau_bar)
as a piecewise-constant input over the step. Exact for linear delay terms when
dt << tau_bar.

Adaptation note: the original simulation evolved a scalar `theta` but never
fed it back into the plant dynamics. We removed that dead state. `rho` remains
a budget parameter but is not dynamically coupled to x in this minimal
two-dimensional witness; full adaptation-coupled dynamics are validated in
the Life integration harness (see specs/life-integration-harness.md).
"""

import math
import sys


# =============================================================================
# RK4 integrator
# =============================================================================

def rk4_step_2d(f, x, t, dt):
    """One RK4 step for a 2D state with right-hand side f(x, t) -> [dx0, dx1]."""
    k1 = f(x, t)
    x2 = [x[0] + 0.5 * dt * k1[0], x[1] + 0.5 * dt * k1[1]]
    k2 = f(x2, t + 0.5 * dt)
    x3 = [x[0] + 0.5 * dt * k2[0], x[1] + 0.5 * dt * k2[1]]
    k3 = f(x3, t + 0.5 * dt)
    x4 = [x[0] + dt * k3[0], x[1] + dt * k3[1]]
    k4 = f(x4, t + dt)
    return [
        x[0] + dt * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0]) / 6.0,
        x[1] + dt * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1]) / 6.0,
    ]


def simulate_switched_system(
    A_modes: list,          # list of 2x2 matrices, one per mode
    A_d: list,              # 2x2 delay coupling matrix
    tau_a: float,           # dwell time (periodic switching period)
    tau_bar: float,         # delay horizon
    dt: float = 0.001,
    T: float = 10.0,
    x0: tuple = (1.0, 0.5),
    switch: bool = True,    # if False, stay in mode 0 the whole time
):
    """Integrate x' = A_{sigma(t)} x + A_d x(t - tau_bar) with periodic switching.

    Returns (trajectory, n_switches) where trajectory is a list of
    (t, ||x||, V=||x||^2, mode) tuples.
    """
    steps = int(T / dt)
    delay_steps = max(1, int(tau_bar / dt))

    x_history = [[x0[0], x0[1]]] * (delay_steps + 1)
    x = [x0[0], x0[1]]
    mode = 0
    last_switch_t = 0.0
    n_switches = 0
    n_modes = len(A_modes)

    trajectory = []

    for step in range(steps):
        t = step * dt
        V = x[0] ** 2 + x[1] ** 2
        trajectory.append((t, math.sqrt(V), V, mode))

        if switch and n_modes > 1 and (t - last_switch_t) >= tau_a:
            mode = (mode + 1) % n_modes
            last_switch_t = t
            n_switches += 1

        x_delayed = x_history[0]
        A = A_modes[mode]

        def f(xc, _t, A=A, xd=x_delayed):
            return [
                A[0][0] * xc[0] + A[0][1] * xc[1] + A_d[0][0] * xd[0] + A_d[0][1] * xd[1],
                A[1][0] * xc[0] + A[1][1] * xc[1] + A_d[1][0] * xd[0] + A_d[1][1] * xd[1],
            ]

        x = rk4_step_2d(f, x, t, dt)

        x_history.append([x[0], x[1]])
        x_history.pop(0)

    return trajectory, n_switches


# =============================================================================
# Tests
# =============================================================================

def test_stable_system_decays():
    """Eslami & Yu (2026) stable parameters: V(x) converges to 0.

    Matrices from Section V of Eslami (both individually stable).
    Parameters satisfy the budget: lambda = 0.609 - 0.120 - 0.075 - 0.197 > 0.
    """
    A1 = [[-3.8897, -3.2679], [1.5381, 0.7197]]
    A2 = [[-3.1172, 0.4840], [-5.4957, 0.4516]]
    A_d = [[0.0, 0.0], [0.8, 0.2]]

    traj, switches = simulate_switched_system(
        A_modes=[A1, A2],
        A_d=A_d,
        tau_a=4.0,       # slow switching, respects dwell-time
        tau_bar=0.03,
        dt=0.001,
        T=15.0,
        x0=(1.0, 0.5),
    )

    V_initial = traj[0][2]
    V_final = traj[-1][2]
    decay_ratio = V_final / V_initial

    assert decay_ratio < 0.01, (
        f"V should decay to <1% of initial: V(0)={V_initial:.4f}, "
        f"V(T)={V_final:.6e}, ratio={decay_ratio:.6e}"
    )

    window = len(traj) // 10
    avg_start = sum(t[2] for t in traj[:window]) / window
    avg_end = sum(t[2] for t in traj[-window:]) / window
    assert avg_end < avg_start * 0.1, (
        f"Windowed average should show clear decay: "
        f"start={avg_start:.4f}, end={avg_end:.6e}"
    )

    print(
        f"  PASS  Stable system decays: V(0)={V_initial:.4f} → "
        f"V(T)={V_final:.6e} (ratio={decay_ratio:.3e}, {switches} switches)"
    )


def test_unstable_mode_diverges():
    """Single unstable mode (eigenvalue > 0): V(x) must grow.

    This replaces the prior test_unstable_system_diverges, which simulated
    Eslami's unstable parameter set but (with individually-stable matrices
    and a small initial condition that never tripped the switching deadband)
    actually converged — and the assertion was missing, so it printed PASS
    regardless.

    Here we use one matrix with a positive real eigenvalue, no switching,
    no delay. The initial condition is aligned with the unstable eigenvector
    (second component zero) so the faster decaying mode does not mix into
    V(t) and the measured rate matches the eigenvalue cleanly.
    """
    A_unstable = [[0.5, 0.0], [0.0, -1.0]]  # eigenvalues +0.5, -1.0

    traj, switches = simulate_switched_system(
        A_modes=[A_unstable],
        A_d=[[0.0, 0.0], [0.0, 0.0]],
        tau_a=1000.0,
        tau_bar=0.001,
        dt=0.001,
        T=5.0,
        x0=(0.1, 0.0),   # pure unstable mode
        switch=False,
    )

    V_initial = traj[0][2]
    V_final = traj[-1][2]
    growth_ratio = V_final / V_initial

    assert growth_ratio > 10.0, (
        f"V should grow by >10x with +0.5 eigenvalue over T=5s "
        f"(theory: e^(2*0.5*5) = {math.exp(5.0):.2f}): "
        f"V(0)={V_initial:.4f}, V(T)={V_final:.4f}, ratio={growth_ratio:.2f}"
    )

    measured_rate = math.log(growth_ratio) / (2 * traj[-1][0])
    expected_rate = 0.5
    rel_error = abs(measured_rate - expected_rate) / expected_rate
    assert rel_error < 0.01, (
        f"Measured growth rate {measured_rate:.4f} should match "
        f"max eigenvalue {expected_rate} (error={rel_error:.2%})"
    )

    assert switches == 0, f"switch=False should produce 0 switches, got {switches}"
    print(
        f"  PASS  Unstable mode diverges: V(0)={V_initial:.4f} → "
        f"V(T)={V_final:.4f} (ratio={growth_ratio:.2f}, rate={measured_rate:.4f})"
    )


def test_exponential_decay_rate():
    """Single stable mode, no switching, no delay: measured decay matches gamma.

    V(t) = ||x(t)||^2 decays as e^{-2*gamma*t} for a diagonalizable A with
    eigenvalue -gamma along the excited eigenvector. Initial condition is
    aligned with the slower mode (-1.5) so no faster mode contributes to V.
    """
    A = [[-2.0, 0.0], [0.0, -1.5]]
    gamma = 1.5

    traj, _ = simulate_switched_system(
        A_modes=[A],
        A_d=[[0.0, 0.0], [0.0, 0.0]],
        tau_a=1000.0,
        tau_bar=0.001,
        dt=0.001,
        T=5.0,
        x0=(0.0, 1.0),   # pure slow-mode eigenvector
        switch=False,
    )

    V_0 = traj[0][2]
    V_T = traj[-1][2]
    T = traj[-1][0]

    assert V_T > 0, f"V should not underflow; got V(T)={V_T}"
    measured_rate = -math.log(V_T / V_0) / (2 * T)
    relative_error = abs(measured_rate - gamma) / gamma
    assert relative_error < 0.01, (
        f"Measured decay rate {measured_rate:.4f} should be close to "
        f"gamma={gamma} (error={relative_error:.2%})"
    )
    print(
        f"  PASS  Exponential rate: measured ω={measured_rate:.4f}, "
        f"predicted γ={gamma} (error={relative_error:.2%})"
    )


def test_homeostatic_drive_decreases():
    """Homeostatic drive D(x) = ||x - x*||^2 is a Lyapunov function (Prop. 4.2).

    With setpoint at origin, D(x) = V(x) = ||x||^2. The per-step monotonicity
    check below relies on dV/dt = x^T (A + A^T) x <= 0 — i.e., the SYMMETRIC
    part of A is negative semidefinite, not just that A is Hurwitz. A matrix
    can be Hurwitz (all eigenvalues have negative real parts) while A + A^T
    has a positive eigenvalue, in which case V can *transiently* grow even
    though x eventually converges (e.g., A = [[-1, 5], [-5, -1]]).

    We therefore explicitly guard on A + A^T being negative definite at the
    top of the test, so a future matrix change fails fast here instead of
    producing a confusing non-monotonicity error.
    """
    A = [[-1.0, 0.3], [-0.3, -1.2]]

    # Guard: A + A^T must be negative definite for V(x)=||x||^2 to be
    # monotone under x' = A x. For 2x2, this is equivalent to
    # S_00 < 0 and det(S) > 0, where S = A + A^T.
    s00 = 2 * A[0][0]
    s01 = A[0][1] + A[1][0]
    s11 = 2 * A[1][1]
    det_s = s00 * s11 - s01 * s01
    assert s00 < 0 and det_s > 0, (
        f"A + A^T must be negative definite for this test's monotonicity "
        f"assertion: A + A^T = [[{s00}, {s01}], [{s01}, {s11}]], "
        f"det={det_s}. If you changed A, pick one with a symmetric part "
        f"that is negative definite, or relax the per-step monotonicity "
        f"check to a windowed-average check."
    )

    traj, _ = simulate_switched_system(
        A_modes=[A],
        A_d=[[0.0, 0.0], [0.0, 0.0]],
        tau_a=1000.0,
        tau_bar=0.001,
        dt=0.001,
        T=10.0,
        x0=(2.0, -1.5),
        switch=False,
    )

    D_initial = traj[0][2]
    D_final = traj[-1][2]

    assert D_final < D_initial * 0.001, (
        f"Drive should decrease by >1000x: D(0)={D_initial:.4f}, "
        f"D(T)={D_final:.6e}"
    )

    for i in range(1, len(traj)):
        assert traj[i][2] <= traj[i - 1][2] + 1e-9, (
            f"Drive is non-monotone at step {i}: "
            f"D(t-)={traj[i-1][2]:.6e}, D(t)={traj[i][2]:.6e}"
        )

    total_reward = D_initial - D_final
    assert total_reward > 0, f"Total reward should be positive: {total_reward}"

    print(
        f"  PASS  Homeostatic drive decreases monotonically: "
        f"D(0)={D_initial:.4f} → D(T)={D_final:.6e}, reward={total_reward:.4f}"
    )


# =============================================================================
# Run all tests
# =============================================================================

if __name__ == "__main__":
    tests = [
        test_stable_system_decays,
        test_unstable_mode_diverges,
        test_exponential_decay_rate,
        test_homeostatic_drive_decreases,
    ]

    print("=" * 60)
    print("RCS Lyapunov Simulation Tests (RK4 integrator)")
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
