# Stochastic Processes in the Regime Volatility Arbitrage Engine

This document lists every stochastic process used in the project: their equations, development, and one runnable example each. Implementation lives in `pricing_engine.py` and `regime_filter.py`.

---

## 1. Rough volatility (Volterra) — spot variance and spot price

**Role:** Model for spot variance and spot price under rough volatility (H < 0.5). Used to price straddles and obtain *model* implied volatility.

### Equations

**Variance process (stochastic Volterra integral):**

$$v_t = v_0 + \frac{1}{\Gamma(H + 1/2)} \int_0^t (t - s)^{H - 1/2} \, \lambda(v_s) \, dW_s^v$$

with diffusion coefficient $\lambda(v) = \nu \sqrt{v}$ (vol-of-vol $\nu$).

**Spot price (risk-neutral log-normal driver):**

$$dS_t = S_t \bigl( r \, dt + \sqrt{v_t} \, dW_t^S \bigr), \qquad \text{or in log form} \quad d\log S_t = \bigl(r - \tfrac{1}{2}v_t\bigr) dt + \sqrt{v_t} \, dW_t^S.$$

**Correlation:** $\operatorname{Corr}(dW^S, dW^v) = \rho$ (instantaneous; typically $\rho \approx -0.7$).

**Parameters:** $H \in (0, 0.5)$ (Hurst), $v_0$ (initial variance), $\nu$ (vol-of-vol), $r$ (risk-free rate), $\rho$ (spot–vol correlation).

### Development

- The kernel $K(t,s) = (t-s)^{H-1/2}$ is the Mandelbrot–Van Ness fractional kernel; for $H < 0.5$ it is singular as $s \to t^-$, so standard Euler–Maruyama is invalid (error $O(n^H)$).
- **Hybrid Scheme** (Bennedsen–Lunde–Pakkanen, 2017): split the kernel into:
  - **Near-field** (lags $j = 0, \ldots, \kappa-1$): exact power-law weights
    $$w_j = \frac{\bigl((j+1)\Delta t\bigr)^{H+1/2} - (j\Delta t)^{H+1/2}}{(H+1/2)\,\Gamma(H+1/2)}$$
  - **Far-field** ($t > \kappa\Delta t$): approximate $K(t) \approx \sum_{j=1}^J c_j e^{-\gamma_j t}$; state variables $x_j$ evolve as
    $$x_j \leftarrow e^{-\gamma_j \Delta t} x_j + c_j \, \lambda(v) \, dW^v.$$
- Variance update:
  $$v_{n+1} = v_0 + \frac{1}{\Gamma(H+1/2)} \Bigl( \text{near-sum} + \text{far-sum} \Bigr), \qquad v \geq 0 \text{ (absorbing at 0).}$$
- Spot is discretised with log-Euler: $\log S \mathrel{+}= (r - \tfrac{1}{2}v) \Delta t + \sqrt{v} \, dW^S$ with correlated $dW^S$, $dW^v$.

### Code reference

- **Equations / kernel:** `pricing_engine.py` docstring and `_kernel_weights`, `_exp_sum_coefficients`, `_simulate_paths`.
- **Parameters:** `config.py` (`HURST_EXPONENT`, `V0`, `LAMBDA_VOL_OF_VOL`, etc.); `PricingEngine.__init__` and `simulate()`.

### Example (in script below)

- Build `PricingEngine` with $H = 0.07$, $v_0 = 0.04$, $\nu = 0.3$, $\rho = -0.7$.
- Call `simulate(T_days=5)` to get terminal $(S_T, v_T)$.
- Call `price_straddle(K, T_days)` to get model price and (via inversion) model IV.

---

## 2. Geometric Brownian motion (GBM) — Black–Scholes

**Role:** Analytical pricing and **implied volatility inversion**. The MC rough-vol engine produces a *dollar* straddle price; we invert the Black–Scholes straddle formula to get a *model implied volatility* comparable to the market.

### Equations

**Spot under risk-neutral GBM:**

$$dS_t = S_t \bigl( r \, dt + \sigma \, dW_t \bigr), \qquad S_0 \text{ given}.$$

**Solution:** $S_T = S_0 \exp\bigl( (r - \sigma^2/2)T + \sigma W_T \bigr)$, so $\log(S_T/S_0)$ is Gaussian with mean $(r - \sigma^2/2)T$ and variance $\sigma^2 T$.

**European call:**

$$C = S_0 \Phi(d_1) - K e^{-rT} \Phi(d_2), \quad d_1 = \frac{\ln(S_0/K) + (r + \sigma^2/2)T}{\sigma\sqrt{T}}, \quad d_2 = d_1 - \sigma\sqrt{T}.$$

**European put:** $P = K e^{-rT} \Phi(-d_2) - S_0 \Phi(-d_1)$. **Straddle:** $C + P$.

### Development

- GBM is the limit of the rough-vol model when $H \to 0.5$ and $\nu \to 0$ (constant variance $\sigma^2 = v_0$).
- IV inversion: given market or model *straddle price* $\Pi$, solve $\Pi = C_\mathrm{BS}(S,K,T,r,\sigma) + P_\mathrm{BS}(S,K,T,r,\sigma)$ for $\sigma$. The project uses **Brent’s method** (no gradient), implemented in `orchestrator.implied_vol_from_price` and BS formulas in `PricingEngine.black_scholes_*` and `orchestrator._bs_straddle_price`.

### Code reference

- **BS formulas:** `pricing_engine.py`: `black_scholes_call`, `black_scholes_put`, `black_scholes_straddle`; `orchestrator.py`: `_bs_straddle_price`, `implied_vol_from_price`.

### Example (in script below)

- Fix $S, K, T, r, \sigma$.
- Compute BS call, put, straddle; then invert the straddle price to recover $\sigma$ (roundtrip).

---

## 3. Gaussian Hidden Markov Model (HMM) — regime filter

**Role:** Classify the market into **Calm** (state 0) vs **Turbulent** (state 1) using daily log-returns. Outputs $P(S_t = \text{Turbulent} \mid r_{1:t})$ for the decision tree (no look-ahead).

### Equations

**Latent state:** $S_t \in \{0,1\}$, Markov with initial distribution $\pi$ and transition matrix $A_{jk} = P(S_{t+1}=k \mid S_t=j)$.

**Observations (daily log-returns):** $r_t = \log(S_t^{\text{spot}} / S_{t-1}^{\text{spot}})$ with emission

$$r_t \mid S_t = k \sim \mathcal{N}(\mu_k, \sigma_k^2).$$

So the **observed process** $\{r_t\}$ is a discrete-time process driven by the hidden Markov chain: at each $t$, $r_t$ is drawn from $\mathcal{N}(\mu_k, \sigma_k^2)$ where $k = S_t$.

**Forward recursion (causal):** scaled $\alpha_t(k) = P(S_t = k \mid r_{1:t})$:

$$\alpha_0(k) \propto \pi_k \, B_k(r_0), \qquad \alpha_t(k) \propto B_k(r_t) \sum_j \alpha_{t-1}(j) A_{jk}.$$

**Emission:** $B_k(r) = \mathcal{N}(r; \mu_k, \sigma_k^2)$. **Traffic light:**  
$P(\text{Turb}) \le 0.6 \to \text{Trade}$; $0.6 < P \le 0.8 \to \text{Delta Hedge}$; $> 0.8 \to \text{Halt}$.

### Development

- **Baum–Welch (EM):** E-step = forward–backward to get $\gamma_t(k) = P(S_t=k \mid r_{1:T})$, $\xi_t(j,k)$; M-step = closed-form update of $\pi, A, \mu, \sigma$.
- **Viterbi:** most likely state sequence $\arg\max_{S_{1:T}} P(S_{1:T} \mid r_{1:T})$ (used for analysis only; not for live signals).
- **Online:** `update_signal(new_return)` propagates $\alpha_{T-1}$ one step with the new observation (causal).

### Code reference

- **Emission / forward / backward / E-M / Viterbi:** `regime_filter.py`: `_log_emission`, `_forward_scaled`, `_backward_scaled`, `_e_step`, `_m_step`, `viterbi`, `current_signal`, `update_signal`.
- **Parameters:** `HMMParams(pi, A, mu, sigma)`; fitted from data via `RegimeFilter.fit()`.

### Example (in script below)

- Generate or load a short series of log-returns; fit a 2-state G-HMM with `RegimeFilter`; run `current_signal()` and optionally `viterbi(obs)` and plot/summarise.

---

## Summary table

| Process            | Role in project              | Main equation / idea                                      | Implementation        |
|--------------------|------------------------------|-----------------------------------------------------------|------------------------|
| Rough Volterra     | Variance + spot for pricing  | $v_t = v_0 + \frac{1}{\Gamma(H+1/2)}\int_0^t (t-s)^{H-1/2}\lambda(v_s)dW_s^v$; spot log-Euler | `pricing_engine.py`    |
| GBM (Black–Scholes)| IV inversion, validation     | $dS_t = S_t(r\,dt + \sigma\,dW_t)$; $C,P$ formulas       | `pricing_engine.py`, `orchestrator.py` |
| Gaussian HMM       | Regime (Calm/Turbulent)       | $r_t \mid S_t=k \sim \mathcal{N}(\mu_k,\sigma_k^2)$; forward $\alpha_t$ | `regime_filter.py`     |

---

## References

1. Bennedsen, M., Lunde, A. & Pakkanen, M. (2017). *Hybrid scheme for Brownian semistationary processes.* Finance & Stochastics, 21(4), 931–965.
2. Gatheral, J., Jaisson, T. & Rosenbaum, M. (2018). *Volatility is rough.* Quantitative Finance, 18(6), 933–949.
3. Rabiner, L.R. (1989). *A tutorial on hidden Markov models and selected applications in speech recognition.* Proc. IEEE, 77(2), 257–286.
