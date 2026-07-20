"""
Test: Persistent-Excitation Dither restores IDENTIFIABILITY — the stochastic arm
of the verifiable pause (BRO-1930, followup to BRO-1924).

`endogenous-reference-contamination` proves the exogenous set that survives an
internalized verifier has exactly two members: a frozen `r₀` (the `μ<1` fraction,
BRO-1924) and a manufactured **persistent-excitation (PE) dither**. This file is
the dither arm.

THE HONEST CRUX (no overclaim). At `μ=1` the internalized loop `ẋ=−k(x−g(x))` has
`∂x*/∂r₀=0` for ANY zero-mean dither — the mean fixed point stays `g`'s fixed
point, and a probe you add and average out cannot move it. So PE dither does NOT
restore coupling by itself. What it restores is **IDENTIFIABILITY**: it makes the
hidden world-target `r₀` *separately* recoverable from the dithered response, so a
measure-only corrector (the "second Boss") can estimate `r̂₀` and re-inject it. THEN
the corrected loop steers `r₀` *without contaminating it* with the internal nuisance
(`∂x*/∂ν→0`). Dither is *necessary* (no PE ⟹ the corrector cannot separate `r₀` from
`ν`) and *insufficient* (you also need the corrector). That is exactly why the
verifiable pause needs BOTH exogenous members.

The classical fact doing the work is PE ⟺ parameter identifiability
(Åström–Wittenmark, adaptive control): a probe is persistently exciting of order n
iff the windowed information matrix `∫φφᵀ ≥ αI` with `α>0`, and then a standard
least-squares estimator recovers the true parameters; a rank-deficient (non-PE)
probe leaves them unidentifiable.

Concrete identification model (2 hidden parameters θ*=[r₀, ν], so PE of order 2 is
required — a constant, or two COLLINEAR regressor channels w₁=w₂, is NOT enough.
A single sinusoid is not inherently non-PE: sampled into two DISTINCT lagged
regressors it is already persistently exciting of order 2 (Åström–Wittenmark). The
witness's non-PE cases fail by DESIGNED channel collinearity w₁=w₂, not by having
too few frequencies):

    y(t) = φ(t)·θ*  =  w₁(t)·r₀ + w₂(t)·ν       (dithered, measured response)
    θ̂    = (Σ φφᵀ)⁻¹ (Σ φ y)                     (least squares)

  * PE probe (w₁,w₂ at DISTINCT frequencies) ⟹ Σφφᵀ full rank ⟹ θ̂ = θ* exactly.
  * COLLINEAR channels (w₁=w₂: a shared constant OR a shared sinusoid) ⟹ Σφφᵀ
    singular (rank 1) ⟹ r₀ not separable from ν ⟹ unidentifiable.

Restored coupling, given the corrector `ẋ = −k(x−g(x)) − k_c(x − r̂₀)`:

    x* = (k·b + k_c·r̂₀) / (k(1−a) + k_c),
    ∂x*/∂r₀ = [k_c / (k(1−a)+k_c)] · (∂r̂₀/∂r₀),

so the restored coupling is the correction gain fraction TIMES the estimate
sensitivity `∂r̂₀/∂θ*`. That sensitivity is IDENTITY under PE (r₀ steered alone,
∂x*/∂ν=0 — clean) and the ½(r₀+ν) BLEND without PE (∂r̂₀/∂r₀=0.5, ∂r̂₀/∂ν=0.5, so
∂x*/∂ν=∂x*/∂r₀ — contaminated). SEPARABILITY, not zero-vs-nonzero coupling, is the
switch: without PE the coupling is nonzero (0.292) but inseparable from the nuisance.

Excitation threshold (reduced-order coupling dynamics; the two terms are each
grounded — `−ρh` is verifier-independence-depletes-under-optimization, `+βσ²` is
the correction that identification enables):

    ḣ = −ρ·h + β·σ²·(h_max − h),   h* = β σ² h_max / (ρ + β σ²).

  * σ²=0 ⟹ h*=0 (recovers BRO-1924: no dither ⟹ decoupled).
  * h* ≥ h_min ⟺ σ² ≥ ρ·h_min / (β(h_max − h_min))  — the minimum excitation to
    win the identification-vs-internalization race (the PE analog of α*=2−p).

Pure stdlib (math only; hand-coded 2×2 linear algebra — CI has no numpy).
Wired into the Makefile `test` target and the ci.yml `test-proofs` job.
"""

import math
import sys

# --- hidden ground truth (unknown to the internalized loop) ---
R0_TRUE = 2.0     # the world target r₀ we want to keep identifiable
NU_TRUE = -1.0    # a nuisance parameter mixed into the response
THETA_TRUE = (R0_TRUE, NU_TRUE)

# --- plant / corrector constants ---
K, A, B, KC = 1.0, 0.5, 3.0, 0.7   # ẋ=−k(x−(ax+b)) − k_c(x−r̂₀)


# ---------- hand-coded 2x2 symmetric linear algebra (stdlib only) ----------

def accumulate(phis, ys):
    """Return (M, c): M = Σ φφᵀ (2x2 symmetric as [m00,m01,m11]), c = Σ φ y."""
    m00 = m01 = m11 = c0 = c1 = 0.0
    for (p0, p1), y in zip(phis, ys):
        m00 += p0 * p0
        m01 += p0 * p1
        m11 += p1 * p1
        c0 += p0 * y
        c1 += p1 * y
    return (m00, m01, m11), (c0, c1)


def min_eig_sym2(M):
    """Smaller eigenvalue of symmetric [[m00,m01],[m01,m11]]."""
    m00, m01, m11 = M
    tr2 = (m00 + m11) / 2.0
    rad = math.sqrt(((m00 - m11) / 2.0) ** 2 + m01 * m01)
    return tr2 - rad


def solve_sym2(M, c, ridge=0.0):
    """Solve (M+ridge·I)θ=c. Returns (θ0,θ1) or None if singular."""
    m00, m01, m11 = M[0] + ridge, M[1], M[2] + ridge
    det = m00 * m11 - m01 * m01
    if abs(det) < 1e-12:
        return None
    c0, c1 = c
    return ((m11 * c0 - m01 * c1) / det, (-m01 * c0 + m00 * c1) / det)


# ---------- probes ----------

def probe(kind, theta=THETA_TRUE, n=2000, dt=0.01, amp=1.0):
    """Return (phis, ys) for a measurement y=φ·θ under the named probe.

    'pe'       — w₁=amp·sin(t), w₂=amp·sin(2t): distinct freqs, full-rank regressor.
    'constant' — w₁=w₂=amp: collinear (identical) channels ⟹ rank-1, NOT PE.
    'single'   — w₁=w₂=amp·sin(t): collinear channels again ⟹ rank-1.
    'none'     — w₁=w₂=0: no probe at all (μ=1 with the dither off).
    """
    phis, ys = [], []
    for i in range(n):
        t = i * dt
        if kind == "pe":
            p0, p1 = amp * math.sin(t), amp * math.sin(2.0 * t)
        elif kind == "constant":
            p0, p1 = amp, amp
        elif kind == "single":
            s = amp * math.sin(t)
            p0, p1 = s, s
        elif kind == "none":
            p0, p1 = 0.0, 0.0
        else:
            raise ValueError(kind)
        phis.append((p0, p1))
        ys.append(p0 * theta[0] + p1 * theta[1])
    return phis, ys


def identify(kind, theta=THETA_TRUE, n=2000, dt=0.01, amp=1.0, noise_amp=0.0):
    """Run least-squares identification under a probe; return (theta_hat, alpha)
    where alpha is the normalized PE bound (min eigenvalue of Σφφᵀ / n)."""
    phis, ys = probe(kind, theta, n, dt, amp)
    if noise_amp:
        # deterministic, reproducible "noise" (fixed sinusoid at 1.3 rad/s — a
        # frequency BETWEEN the probe's, so it projects onto the regressors and
        # yields a genuine, α-dependent error rather than averaging to dust) — no RNG
        ys = [y + noise_amp * math.sin(1.3 * i * dt + 0.5) for i, y in enumerate(ys)]
    M, c = accumulate(phis, ys)
    # Normalize to the AVERAGE information matrix (1/n)Σφφᵀ — O(1) scale. Same
    # least-squares solution, but avoids catastrophic cancellation in det for the
    # rank-deficient (non-PE) probes, where raw sums are ~n·(matrix) ≈ millions.
    Mn = (M[0] / n, M[1] / n, M[2] / n)
    cn = (c[0] / n, c[1] / n)
    alpha = min_eig_sym2(Mn)                    # normalized PE bound = min eig of (1/n)Σφφᵀ
    theta_hat = solve_sym2(Mn, cn, ridge=1e-9)  # tiny ridge so singular cases still return a value
    return theta_hat, alpha


def correction_fraction():
    """k_c/(k(1−a)+k_c) — the corrector's gain fraction in ∂x*/∂r̂₀."""
    return KC / (K * (1 - A) + KC)


def corrector_steady_state(r_hat, x0=0.0, t_end=200.0, dt=1e-2):
    """RK4-integrate the CORRECTED loop ẋ = −k(x−g(x)) − k_c(x−r̂₀), g(x)=ax+b,
    to its fixed point. Pure numerical integration of the ODE — it does NOT read
    the closed-form fixed point, so comparing its result against
    (k·b + k_c·r̂₀)/(k(1−a)+k_c) is a genuine DYNAMICAL witness (a wrong ODE, e.g.
    a dropped k_c term, diverges from the algebra), not a formula-self-consistency
    check. Effective rate k(1−a)+k_c = 1.2 > 0 ⟹ stable attractor, integral
    converges to the fixed point to machine precision (RK4's discrete fixed point
    equals the ODE's for a linear system)."""
    def f(x):
        return -K * (x - (A * x + B)) - KC * (x - r_hat)
    x, n = x0, int(t_end / dt)
    for _ in range(n):
        k1 = f(x); k2 = f(x + dt/2 * k1); k3 = f(x + dt/2 * k2); k4 = f(x + dt * k3)
        x += dt/6 * (k1 + 2 * k2 + 2 * k3 + k4)
    return x


def integrated_world_sensitivity(kind, which):
    """End-to-end ∂x*/∂θ*[which] finite-differenced THROUGH the integrated
    corrector fixed point: perturb the TRUE parameter, re-run the least-squares
    estimator under `kind` to get r̂₀, RK-integrate the corrector ODE to x*, and
    measure the slope of the *integrated* x*. which=0 → ∂x*/∂r₀ (world steering),
    which=1 → ∂x*/∂ν (nuisance contamination). This composes the REAL estimator
    with the REAL integrated fixed point — the witness the 0.583 / 0.292 table
    entries were missing (before, only the estimator Jacobian was differenced and
    the corrector gain was a bare closed-form constant)."""
    eps = 1e-3

    def x_star_of(theta):
        r_hat = identify(kind, theta=theta)[0][0]     # estimator's r̂₀ under the probe
        return corrector_steady_state(r_hat)          # integrated corrected fixed point

    hi = list(THETA_TRUE); hi[which] += eps
    lo = list(THETA_TRUE); lo[which] -= eps
    return (x_star_of(tuple(hi)) - x_star_of(tuple(lo))) / (2 * eps)


def estimator_jacobian(kind):
    """Finite-difference ∂θ̂/∂θ*: how the LS estimate of [r₀, ν] responds to each
    TRUE parameter. Returns [[∂r̂₀/∂r₀, ∂r̂₀/∂ν], [∂ν̂/∂r₀, ∂ν̂/∂ν]].

    PE ⟹ ≈ identity (each estimate tracks its own parameter — SEPARABLE).
    non-PE ⟹ rows of 0.5 (r̂₀ = ½(r₀+ν): the estimate is a blend — INSEPARABLE)."""
    r0, nu = THETA_TRUE
    eps = 1e-3
    base = identify(kind, theta=(r0, nu))[0]
    d_r0 = identify(kind, theta=(r0 + eps, nu))[0]     # perturb r₀
    d_nu = identify(kind, theta=(r0, nu + eps))[0]     # perturb ν
    assert base is not None and d_r0 is not None and d_nu is not None
    return [
        [(d_r0[0] - base[0]) / eps, (d_nu[0] - base[0]) / eps],
        [(d_r0[1] - base[1]) / eps, (d_nu[1] - base[1]) / eps],
    ]


# ---------- macro coupling dynamics ----------

RHO, BETA, H_MAX = 0.30, 1.0, 1.0   # depletion rate, correction gain, max coupling


def coupling_steady_state(sigma2):
    """h* = βσ²h_max/(ρ+βσ²) — analytic steady state of ḣ=−ρh+βσ²(h_max−h)."""
    return BETA * sigma2 * H_MAX / (RHO + BETA * sigma2)


def coupling_integrate(sigma2, h0=0.0, t_end=200.0, dt=1e-2):
    """Integrate ḣ=−ρh+βσ²(h_max−h) to steady state (RK4)."""
    def f(h):
        return -RHO * h + BETA * sigma2 * (H_MAX - h)
    h, n = h0, int(t_end / dt)
    for _ in range(n):
        k1 = f(h); k2 = f(h + dt/2*k1); k3 = f(h + dt/2*k2); k4 = f(h + dt*k3)
        h += dt/6 * (k1 + 2*k2 + 2*k3 + k4)
    return h


def excitation_threshold(h_min):
    """σ*² = ρ·h_min/(β(h_max−h_min)) — min excitation for h*≥h_min.

    Well-posed only for 0 < h_min < h_max and β, ρ > 0. Since
    h* = βσ²h_max/(ρ+βσ²) < h_max for every finite σ², a target h_min ≥ h_max is
    unreachable at ANY excitation and the formula divides by ≤0 — undefined. The
    precondition was implicit in §5; BRO-1937 states it and enforces it here.
    Raised as ValueError (not assert) so the guard survives `python -O`."""
    if not (RHO > 0 and BETA > 0):
        raise ValueError(f"threshold requires β, ρ > 0, got ρ={RHO}, β={BETA}")
    if not (0 < h_min < H_MAX):
        raise ValueError(f"threshold requires 0 < h_min < h_max={H_MAX}, got {h_min}")
    return RHO * h_min / (BETA * (H_MAX - h_min))


# =============================================================================

def test_pe_probe_identifies_world_target():
    """PE probe (2 distinct freqs) ⟹ full-rank information matrix (α>0) ⟹ LS
    recovers BOTH hidden parameters exactly, including r₀."""
    theta_hat, alpha = identify("pe")
    assert alpha > 1e-3, alpha                       # persistently exciting
    assert theta_hat is not None
    assert abs(theta_hat[0] - R0_TRUE) < 1e-6, theta_hat
    assert abs(theta_hat[1] - NU_TRUE) < 1e-6, theta_hat
    print(f"  PASS  PE probe identifies r₀={theta_hat[0]:.6f}, ν={theta_hat[1]:.6f} "
          f"(α={alpha:.4f}>0)")


def test_constant_probe_is_not_persistently_exciting():
    """A CONSTANT dither (w₁=w₂) has a rank-1 information matrix (α≈0): r₀ is NOT
    separable from the nuisance ⟹ unidentifiable. Not any dither works."""
    theta_hat, alpha = identify("constant")
    assert alpha < 1e-9, alpha                       # rank-deficient → not PE
    # the ridge-regularized solve cannot recover r₀ (splits the r₀+ν sum)
    assert theta_hat is None or abs(theta_hat[0] - R0_TRUE) > 0.5, theta_hat
    print(f"  PASS  constant probe NOT persistently exciting (α={alpha:.2e}≈0) → r₀ hidden")


def test_collinear_channel_probe_fails_for_two_parameters():
    """A probe whose two regressor channels are IDENTICAL (w₁=w₂=sin t) gives a
    rank-1 information matrix (α≈0): the channels are linearly dependent, so r₀
    cannot be separated from ν regardless of the sinusoid's spectral content. Two
    unknowns need two linearly-independent channels."""
    _theta_hat, alpha = identify("single")
    assert alpha < 1e-9, alpha
    print(f"  PASS  collinear channels (w₁=w₂) ⟹ rank-1, α={alpha:.2e}≈0 → r₀ not separable")


def test_no_probe_leaves_world_fully_hidden():
    """μ=1 with the dither OFF: zero regressor, α=0, r₀ completely unobservable —
    the BRO-1924 decoupled baseline this arm is trying to rescue."""
    theta_hat, alpha = identify("none")
    assert alpha == 0.0, alpha
    assert theta_hat is None                          # 0·θ=0, no information
    print("  PASS  no probe ⟹ α=0, r₀ fully hidden (the BRO-1924 baseline)")


def test_pe_bound_governs_estimation_error():
    """A DETERMINISTIC off-frequency disturbance (a fixed 1.3 rad/s sinusoid, not
    RNG — see identify()) projects onto the regressors and induces an estimation
    BIAS whose MAGNITUDE ∝ 1/amp ∝ 1/√α (α∝amp²): doubling the probe amplitude
    halves the error. Honest labelling (BRO-1937): the *classical* PE result is
    that estimator **variance** ∝ 1/α under STOCHASTIC noise ⟹ error magnitude ∝
    1/√α; here we witness the same 1/√α *exponent* deterministically, so what we
    measure is a projection **bias**, not a variance (the code injects a fixed
    sinusoid, not a random one — same conditioning story, correct name). A
    higher-excitation probe gives a smaller error; the PE bound α is the concrete
    conditioning that controls accuracy. This pins the exponent — a genuine 1/√α,
    refuting a naive 1/α reading."""
    rows = []
    for amp in (0.5, 1.0, 2.0):
        theta_hat, alpha = identify("pe", amp=amp, noise_amp=0.05)
        assert theta_hat is not None
        err = abs(theta_hat[0] - R0_TRUE)
        rows.append((amp, alpha, err))
    assert all(e > 1e-6 for _, _, e in rows), rows        # genuinely nonzero, not dust
    for i in range(len(rows) - 1):
        assert rows[i][1] < rows[i + 1][1], rows          # α increasing with amp
        # error·amp is invariant ⟹ error ∝ 1/amp ∝ 1/√α (NOT 1/α)
        p0 = rows[i][2] * rows[i][0]
        p1 = rows[i + 1][2] * rows[i + 1][0]
        assert abs(p0 - p1) / p0 < 0.05, (p0, p1)         # err·amp constant within 5%
    print(f"  PASS  error ∝ 1/√α ∝ 1/amp under noise "
          f"(amp/err: {', '.join(f'{a}/{e:.4f}' for a, _, e in rows)}; err·amp const)")


def test_pe_gives_separable_world_steering():
    """The real switch is SEPARABILITY, not zero-vs-nonzero coupling. Re-injecting
    the estimate r̂₀ restores coupling to r₀ in BOTH cases (a non-PE estimator is
    NOT zero — it returns r̂₀=½(r₀+ν), so ∂r̂₀/∂r₀=0.5). What PE buys is that r₀ is
    recovered ALONE: the corrected loop steers the world-target with ∂x*/∂ν≈0
    (clean). Without PE, r₀ is inseparable from the nuisance ν, so correcting
    "toward the world" drags ν in equally (∂x*/∂ν = ∂x*/∂r₀). Contamination, not
    decoupling — exactly the endogenous-reference-contamination story."""
    frac = correction_fraction()          # 0.5833; ∂x*/∂(estimate)
    J_pe = estimator_jacobian("pe")
    J_const = estimator_jacobian("constant")
    # PE: estimator Jacobian ≈ identity (r̂₀ tracks r₀ alone)
    assert abs(J_pe[0][0] - 1.0) < 1e-2 and abs(J_pe[0][1]) < 1e-2, J_pe
    # non-PE: r̂₀ = ½(r₀+ν) → row [0.5, 0.5] (inseparable blend)
    assert abs(J_const[0][0] - 0.5) < 1e-2 and abs(J_const[0][1] - 0.5) < 1e-2, J_const
    # restored coupling to r₀ is NONZERO in BOTH ("0 without PE" was wrong)
    coup_pe, coup_const = frac * J_pe[0][0], frac * J_const[0][0]
    assert coup_pe > 0 and coup_const > 0, (coup_pe, coup_const)
    # pin the MAGNITUDES to the doc §4 table (0.583 / 0.292) so frac's VALUE is
    # load-bearing here, not just its sign (BRO-1937 anti-vacuity); the INTEGRATED
    # witness lives in test_integrated_corrector_pins_correction_fraction below
    assert abs(coup_pe - 0.583) < 1e-2, coup_pe
    assert abs(coup_const - 0.292) < 1e-2, coup_const
    # the SWITCH is contamination = coupling to the nuisance ν
    contam_pe, contam_const = frac * J_pe[0][1], frac * J_const[0][1]
    assert abs(contam_pe) < 1e-2, contam_pe                        # PE: clean steering
    assert abs(contam_const - coup_const) < 1e-2, (contam_const, coup_const)  # non-PE: fully contaminated
    print(f"  PASS  PE gives SEPARABLE steering (∂x*/∂ν={contam_pe:.3f}≈0); non-PE "
          f"contaminates (∂x*/∂ν={contam_const:.3f} = ∂x*/∂r₀={coup_const:.3f})")


def test_integrated_corrector_pins_correction_fraction():
    """MAJOR witness (BRO-1937): validate correction_fraction() and the 0.583 /
    0.292 world-coupling sensitivities against an INTEGRATED corrector ODE, not
    just the closed form. Before this, correction_fraction() was a bare algebraic
    constant that no assertion depended on (every use pinned only the SIGN), so
    the doc §4 table's 0.583/0.292 were asserted, not witnessed. Three checks:

      (1) the RK-integrated fixed point of ẋ=−k(x−g(x))−k_c(x−r̂₀) equals the
          closed form (k·b+k_c·r̂₀)/(k(1−a)+k_c) across several r̂₀ — a dynamical
          witness that the ODE's attractor matches the algebra;
      (2) ∂x*/∂r̂₀ finite-differenced THROUGH that integration equals
          correction_fraction() (=0.583) — pins the gain fraction to the ODE, so
          a wrong correction_fraction() now fails a test;
      (3) the end-to-end world sensitivities, composing the REAL least-squares
          estimator with the integrated fixed point, reproduce the §4 table:
          ∂x*/∂r₀ = 0.583 (PE) vs 0.292 (non-PE), and the contamination
          ∂x*/∂ν = 0 (PE) vs 0.292 (non-PE). Now computed, not assumed."""
    denom = K * (1 - A) + KC
    # (1) integrated fixed point == closed form (genuine ODE attractor)
    for r_hat in (-2.0, 0.5, 2.0, 5.0):
        x_int = corrector_steady_state(r_hat)
        x_cf = (K * B + KC * r_hat) / denom
        assert abs(x_int - x_cf) < 1e-9, (r_hat, x_int, x_cf)
    # (2) ∂x*/∂r̂₀ through integration == correction_fraction() (== 0.583)
    eps = 1e-3
    dxdr_hat = (corrector_steady_state(1.0 + eps)
                - corrector_steady_state(1.0 - eps)) / (2 * eps)
    frac = correction_fraction()
    assert abs(frac - 0.583) < 1e-3, frac                       # the doc §4 value
    assert abs(dxdr_hat - frac) < 1e-6, (dxdr_hat, frac)        # integrated == closed form
    # (3) end-to-end world coupling through estimator + integrated fixed point
    coup_pe = integrated_world_sensitivity("pe", 0)             # ∂x*/∂r₀ under PE
    coup_np = integrated_world_sensitivity("constant", 0)       # ∂x*/∂r₀ under non-PE
    contam_pe = integrated_world_sensitivity("pe", 1)           # ∂x*/∂ν under PE
    contam_np = integrated_world_sensitivity("constant", 1)     # ∂x*/∂ν under non-PE
    assert abs(coup_pe - 0.583) < 1e-2, coup_pe                 # PE steers r₀ at frac·1
    assert abs(coup_np - 0.292) < 5e-3, coup_np                 # non-PE at frac·0.5
    assert abs(contam_pe) < 1e-2, contam_pe                     # PE: clean (∂x*/∂ν≈0)
    assert abs(contam_np - 0.292) < 5e-3, contam_np             # non-PE: fully contaminated
    print(f"  PASS  integrated corrector pins correction_fraction={frac:.4f} "
          f"(∂x*/∂r̂₀_int={dxdr_hat:.4f}); world coupling PE={coup_pe:.3f}/"
          f"non-PE={coup_np:.3f}, contamination PE={contam_pe:.3f}/non-PE={contam_np:.3f}")


def test_threshold_macro_dynamics():
    """Reduced-order coupling ḣ=−ρh+βσ²(h_max−h): steady state h*(σ²) matches the
    analytic form (integrated==closed-form), σ²=0 recovers BRO-1924 (h*=0), and
    h*≥h_min exactly at the excitation threshold σ*²=ρh_min/(β(h_max−h_min))."""
    # analytic == integrated across excitation levels
    for sigma2 in (0.0, 0.1, 0.5, 1.0):
        assert abs(coupling_integrate(sigma2) - coupling_steady_state(sigma2)) < 1e-6
    # no dither ⟹ decoupled (recovers BRO-1924)
    assert coupling_steady_state(0.0) == 0.0
    assert coupling_steady_state(0.5) > 0.0
    # threshold: at σ*², h*==h_min; just below fails, just above holds
    h_min = 0.5
    s_star = excitation_threshold(h_min)
    assert abs(coupling_steady_state(s_star) - h_min) < 1e-9
    assert coupling_steady_state(0.99 * s_star) < h_min
    assert coupling_steady_state(1.01 * s_star) > h_min
    # well-posedness precondition (BRO-1937): h* < h_max at every finite σ², so a
    # target h_min ≥ h_max is unreachable and the threshold formula is undefined
    assert coupling_steady_state(1e6) < H_MAX                   # h*→h_max⁻, never reaches
    for bad in (H_MAX, 1.5 * H_MAX):
        try:
            excitation_threshold(bad)
            raise AssertionError(f"expected precondition failure for h_min={bad}")
        except ValueError as e:
            assert "threshold requires" in str(e), e            # our guard fired
    print(f"  PASS  threshold σ*²={s_star:.3f} for h_min={h_min} "
          f"(σ²=0→h*=0 recovers BRO-1924; analytic==integrated; h_min<h_max enforced)")


def test_dither_absorbed_below_threshold():
    """If internalization depletes faster (ρ↑) the restored coupling h* drops
    toward 0 — the dither gets absorbed before it can identify
    (verifier-independence-depletes-under-optimization). h* is monotone
    decreasing in ρ and → 0 as ρ → ∞."""
    sigma2 = 0.5
    def h_star(rho):
        return BETA * sigma2 * H_MAX / (rho + BETA * sigma2)
    hs = [h_star(r) for r in (0.1, 0.5, 2.0, 10.0, 100.0)]
    for i in range(len(hs) - 1):
        assert hs[i] > hs[i + 1], hs                  # decreasing in ρ
    assert hs[-1] < 0.01                              # ρ=100 → dither absorbed
    print(f"  PASS  faster internalization absorbs the dither "
          f"(h* vs ρ: {', '.join(f'{h:.3f}' for h in hs)})")


# =============================================================================

if __name__ == "__main__":
    tests = [
        test_pe_probe_identifies_world_target,
        test_constant_probe_is_not_persistently_exciting,
        test_collinear_channel_probe_fails_for_two_parameters,
        test_no_probe_leaves_world_fully_hidden,
        test_pe_bound_governs_estimation_error,
        test_pe_gives_separable_world_steering,
        test_integrated_corrector_pins_correction_fraction,
        test_threshold_macro_dynamics,
        test_dither_absorbed_below_threshold,
    ]

    print("=" * 70)
    print("Persistent-excitation dither: identifiability restores world-coupling")
    print("=" * 70)

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

    print("=" * 70)
    print(f"{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
