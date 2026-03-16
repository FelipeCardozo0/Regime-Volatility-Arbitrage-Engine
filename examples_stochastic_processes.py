#!/usr/bin/env python3
"""
One working example for each stochastic process used in the project.

Run from repo root:
    python examples_stochastic_processes.py

Processes:
  1. Rough volatility (Volterra) — variance + spot
  2. Geometric Brownian motion (Black–Scholes) — IV roundtrip
  3. Gaussian Hidden Markov Model — regime from synthetic returns
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
from pricing_engine import PricingEngine, OptionResult
from regime_filter import RegimeFilter, CALM, TURBULENT
from orchestrator import implied_vol_from_price, _bs_straddle_price


# ════════════════════════════════════════════════════════════════════
# 1. Rough volatility (Volterra) — one example
# ════════════════════════════════════════════════════════════════════

def example_rough_volatility() -> None:
    """
    Process: v_t = v_0 + (1/Γ(H+1/2)) ∫₀ᵗ (t−s)^{H−1/2} λ(v_s) dW_s^v
             d log S_t = (r − ½ v_t) dt + √v_t dW^S_t,  corr(dW^S, dW^v) = ρ.
    """
    print("=" * 60)
    print("1. ROUGH VOLATILITY (Volterra + spot)")
    print("=" * 60)

    engine = PricingEngine(
        H=0.07,
        v0=0.04,
        nu=0.30,
        S0=100.0,
        r=0.05,
        rho=-0.7,
        n_paths=2_000,
        steps_per_day=24,
        kappa=12,
        J=6,
        seed=42,
    )

    # Simulate paths
    S_T, v_T = engine.simulate(T_days=5)
    print(f"  Simulated {len(S_T)} paths over 5 days.")
    print(f"  S_T: mean = {S_T.mean():.4f}, std = {S_T.std():.4f}")
    print(f"  v_T: mean = {v_T.mean():.6f}, min = {v_T.min():.6f}, max = {v_T.max():.6f}")

    # Price ATM straddle
    K = 100.0
    res = engine.price_straddle(K=K, T_days=5)
    print(f"  ATM straddle (K={K}): price = {res.price:.4f}, SE = {res.std_error:.4f}")

    # Model IV via inversion (uses GBM/BS on the next process)
    T_years = 5 / 252.0
    iv = implied_vol_from_price(res.price, 100.0, K, T_years, 0.05)
    print(f"  Model implied vol (from straddle): σ = {iv:.4f}" if iv else "  IV inversion: N/A")
    print()


# ════════════════════════════════════════════════════════════════════
# 2. Geometric Brownian motion (Black–Scholes) — one example
# ════════════════════════════════════════════════════════════════════

def example_black_scholes_gbm() -> None:
    """
    Process: dS_t = S_t (r dt + σ dW_t)  →  analytical C, P, straddle.
    Example: roundtrip IV — price straddle at σ_true, then invert to recover σ.
    """
    print("=" * 60)
    print("2. GEOMETRIC BROWNIAN MOTION (Black–Scholes)")
    print("=" * 60)

    S, K, T, r = 100.0, 100.0, 5 / 252.0, 0.05
    sigma_true = 0.22

    call = PricingEngine.black_scholes_call(S, K, T, r, sigma_true)
    put = PricingEngine.black_scholes_put(S, K, T, r, sigma_true)
    straddle_price = _bs_straddle_price(S, K, T, r, sigma_true)
    print(f"  S={S}, K={K}, T={T:.6f}, r={r}, σ={sigma_true}")
    print(f"  Call = {call:.4f}, Put = {put:.4f}, Straddle = {straddle_price:.4f}")

    # IV roundtrip
    sigma_recovered = implied_vol_from_price(straddle_price, S, K, T, r)
    print(f"  IV from straddle price: σ = {sigma_recovered:.6f}  (error = {abs(sigma_recovered - sigma_true):.2e})")
    print()


# ════════════════════════════════════════════════════════════════════
# 3. Gaussian HMM — one example
# ════════════════════════════════════════════════════════════════════

def example_gaussian_hmm() -> None:
    """
    Process: S_t ∈ {0,1} Markov; r_t | S_t=k ~ N(μ_k, σ_k²).
    Example: synthetic two-regime returns → fit G-HMM → current_signal + Viterbi.
    """
    print("=" * 60)
    print("3. GAUSSIAN HIDDEN MARKOV MODEL (regime filter)")
    print("=" * 60)

    rng = np.random.default_rng(42)
    n = 400
    # Synthetic: first half Calm (low vol), second half Turbulent (high vol)
    states_true = np.zeros(n, dtype=int)
    states_true[n // 2:] = 1
    mu_true = [0.0005, -0.001]
    sigma_true = [0.008, 0.025]
    obs = np.array([
        rng.normal(mu_true[s], sigma_true[s]) for s in states_true
    ])
    dates = np.arange(n)

    rf = RegimeFilter(n_states=2, turbulence_threshold=0.6)
    rf.log_returns = obs
    rf.dates = dates
    rf.fit(obs, n_restarts=4)

    p = rf.params
    print(f"  Fitted μ (Calm, Turb): ({p.mu[0]:.5f}, {p.mu[1]:.5f})")
    print(f"  Fitted σ (Calm, Turb): ({p.sigma[0]:.5f}, {p.sigma[1]:.5f})")
    print(f"  π = {p.pi}, A = \n{p.A}")

    signal = rf.current_signal(obs)
    print(f"  current_signal(): state={signal.state} ({'Turbulent' if signal.state == TURBULENT else 'Calm'}), "
          f"P(Turb)={signal.prob_turbulent:.3f}, action={signal.action}")

    vit = rf.viterbi(obs)
    agreement = (vit == states_true).mean()
    print(f"  Viterbi vs true state: {agreement:.1%} agreement")
    print()


# ════════════════════════════════════════════════════════════════════
# Run all
# ════════════════════════════════════════════════════════════════════

def main() -> None:
    example_rough_volatility()
    example_black_scholes_gbm()
    example_gaussian_hmm()
    print("Done. See stochastic_processes_reference.md for equations and development.")


if __name__ == "__main__":
    main()
