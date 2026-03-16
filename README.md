# Regime Volatility Arbitrage Engine

Systematic volatility arbitrage in short-dated equity-index options, combining rough-volatility pricing with real-time regime detection and live execution on Interactive Brokers.

---

### Overview

This repository implements **Project Rough‑Regime**: an event‑driven volatility arbitrage system designed for short‑dated index options (e.g. SPY). The core thesis is empirical:

- Realised variance of equity indices is **rough**, with Hurst exponent \(H \approx 0.07\) (Gatheral–Jaisson–Rosenbaum, 2018), not \(H = 0.5\) as assumed by classical diffusion models (Black–Scholes, Heston, SABR).
- Standard desks still price options off smooth models; this mismatch is most visible in the **short‑dated ATM skew**. A model that correctly captures roughness can systematically identify mispriced volatility.

The engine operationalises this in three layers:

- **Mathematical layer (`pricing_engine.py`)** — Monte Carlo pricer for a stochastic Volterra variance process (rough Bergomi–style) using the **Hybrid Scheme** with Numba JIT. Outputs model prices and *model implied volatility*.
- **Risk layer (`regime_filter.py`)** — two‑state **Gaussian Hidden Markov Model** (Calm / Turbulent) on daily log‑returns, fitted via Baum–Welch EM. The forward‑filtered \(P(\text{Turbulent}\mid r_{1:t})\) gates risk.
- **Execution layer (`connection_manager.py`, `execution_handler.py`, `orchestrator.py`)** — asynchronous IBKR TWS connectivity, tick ingestion into HDF5, event‑driven orchestrator, and a passive **chase algorithm** for order execution.

The central constraint is explicit:

> **Only trade when the market is Calm and the model says volatility is cheap.**  
>  
> Formally, **enter long volatility** only if  
> \[
> \text{Regime} = \text{Calm}
> \quad\text{and}\quad
> \sigma_{\text{model}} - \sigma_{\text{market}} > \Delta_{\text{entry}},
> \]
> and **exit / hedge** when the regime flips to Turbulent, when the spread compresses, or when stop‑loss / holding‑time limits are hit.

---

### Paper

The theoretical framework, methodology, and empirical results are documented in the accompanying paper:

**“Rough Volatility Arbitrage under Markov Regime: Volterra Process Approach with Double Exponential”**  
Mitchell Scott, Ph.D. & Felipe Cardozo — Emory University

- LaTeX source: `paper/main.tex`  
- Compiled PDF (if built locally): `paper/main.pdf`

---

### Architecture

High‑level data flow:

```text
┌─────────────┐     ticks        ┌──────────────────────┐
│  IBKR TWS   │ ───────────────▶ │  ConnectionManager   │
│ (market data│                  │  tick_queue → HDF5   │
└─────────────┘                  └──────────┬───────────┘
                                           │ MarketState
                                           ▼
                                  ┌──────────────────────┐
                                  │  StrategyOrchestrator│
                                  │  10ms tick loop      │
                                  │  5s signal loop      │
                                  └───┬────────┬────────┘
                                      │        │
                         ┌────────────┘        └─────────────┐
                         ▼                                   ▼
                ┌────────────────┐                 ┌────────────────┐
                │  PricingEngine │                 │  RegimeFilter  │
                │ (Volterra MC)  │                 │ (Gaussian HMM) │
                └────────┬───────┘                 └────────┬───────┘
                         │  OptionResult (price, IV)        │ RegimeSignal
                         └───────────────┬──────────────────┘
                                         ▼
                              ┌──────────────────────┐
                              │   Signal Generator   │
                              │  (logic tree + PnL)  │
                              └──────────┬───────────┘
                                         │ TradeSignal
                                         ▼
                              ┌──────────────────────┐
                              │  ExecutionHandler    │
                              │  (IBKR orders +      │
                              │   chase algorithm)   │
                              └──────────┬───────────┘
                                         │ orders / mods
                                         ▼
                                     IBKR TWS
```

**Layers:**

- **Infrastructure (`connection_manager.py`)**:  
  Dual‑inheritance `ConnectionManager(EWrapper, EClient)` runs `EClient.run()` on a dedicated daemon thread, fans out ticks into a bounded `tick_queue` and a batched **HDF5 writer** (`tick_data.h5`), and handles reconnects + subscription replay.
- **Strategy (`orchestrator.py`)**:  
  10 ms loop drains `tick_queue` into `MarketState`. Every 5 s it:
  1. Queries the HMM (`RegimeFilter.current_signal()`).
  2. Prices the ATM straddle via rough‑vol MC (`PricingEngine.price_straddle()`).
  3. Inverts the Black–Scholes straddle to a model IV.
  4. Runs a **priority‑ordered decision tree** (stop‑loss, time exit, regime, spread, entry).
  Signals are logged to `trade_log.csv`.
- **Execution (`execution_handler.py`)**:  
  Separate IBKR client (own `clientId`) for order management, with a tick‑aware **chase**:
  - Start at mid‑price.
  - Every `τ_chase` seconds, move one tick toward aggressive side, up to `n_chase` steps.
  - Optionally convert to market on timeout.  
  Order lifecycle and fills are recorded to `fills.csv`.
- **Health (`main.py` → `SystemHealthMonitor`)**:  
  Periodic heartbeat to `heartbeat.log` (uptime %, ticks/minute, queue occupancy, reconnect count, signal count).

For a full module‑by‑module breakdown, see `PROJECT_ARCHITECTURE.md`.

---

### Mathematical Core

#### Rough volatility — stochastic Volterra variance

Variance is driven by a **fractional kernel** with Hurst \(H < 0.5\):

$$
v_t = v_0 + \frac{1}{\Gamma\!\bigl(H + \tfrac{1}{2}\bigr)}
      \int_0^t (t-s)^{H - 1/2}\,\lambda(v_s)\,\mathrm{d}W_s^v,
\qquad \lambda(v) = \nu \sqrt{v},
$$

while spot follows

$$
\mathrm{d}\log S_t = \left(r - \tfrac{1}{2} v_t\right) \mathrm{d}t
                     + \sqrt{v_t}\,\mathrm{d}W_t^S,
\quad \mathrm{Corr}(\mathrm{d}W^S, \mathrm{d}W^v) = \rho.
$$

Direct Euler–Maruyama is inconsistent when \(H < 0.5\) (error \(O(n^H)\)). The engine uses the **Hybrid Scheme** (Bennedsen–Lunde–Pakkanen, 2017):

- Near‑field kernel over first \(\kappa\) lags integrated exactly (power‑law weights).
- Far‑field replaced by a geometric **exponential sum** \(\sum_{l=1}^J c_l e^{-\gamma_l (t-s)}\), maintained via low‑dimensional state \(x_l\).

This reduces the convolution cost from \(O(N^2)\) to \(O(N\kappa + N J)\), and is Numba‑JIT‑compiled for sub‑millisecond per‑path throughput.

#### Gaussian HMM — regime filter

Daily log‑returns \(r_t\) are generated by a two‑state Markov chain \(S_t \in \{0,1\}\) (Calm, Turbulent):

$$
r_t \mid S_t = k \sim \mathcal{N}(\mu_k, \sigma_k^2), \quad k \in \{0,1\},
$$

with transition matrix \(A_{jk} = P(S_{t+1}=k \mid S_t=j)\) and initial distribution \(\pi\).

The forward (scaled) filter evolves

$$
\alpha_0(k) \propto \pi_k\,\mathcal{N}(r_0;\mu_k,\sigma_k^2),\qquad
\alpha_t(k) \propto \mathcal{N}(r_t;\mu_k,\sigma_k^2)\sum_j \alpha_{t-1}(j) A_{jk},
$$

and the **traffic‑light** rule is

- \(P(\text{Turbulent}) \le 0.60\): **Trade** (full Kelly size permitted).
- \(0.60 < P(\text{Turbulent}) \le 0.80\): **Delta hedge / no new entries**.
- \(P(\text{Turbulent}) > 0.80\): **Close all** and stay flat.

Calibration uses Baum–Welch EM with multiple random restarts and vectorised forward–backward passes.

#### Kelly criterion — position sizing

Given rolling excess‑return estimate \(\hat{\mu}\) and variance \(\hat{\sigma}^2\), the Kelly fraction is

$$
f^* = \frac{\hat{\mu} - r_f}{\hat{\sigma}^2},
$$

with a **half‑Kelly cap** \(f^*_{\text{cap}} = \min(f^*, 0.5)\) for robustness. The regime filter gates \(f^*\) to zero in Turbulent states.

---

### Key Results (from the paper)

Five‑year synthetic study comparing a naive always‑on long‑vol strategy to the **regime‑adjusted** strategy:

| Metric              | Naive Long‑Vol | Regime‑Adjusted |
|---------------------|----------------|-----------------|
| Annualised Return   | 5.1%           | 7.3%            |
| Annualised Sharpe   | 0.87           | 1.38            |
| Maximum Drawdown    | −22.4%         | −12.7%          |
| Calmar Ratio        | 0.23           | 0.57            |

In broad terms:

- The rough‑vol pricer is empirically verified to converge at \(O(N^{-1/2})\) and cross‑checks against Black–Scholes in the \(H=0.5, \nu \to 0\) limit.
- The G‑HMM reliably flags synthetic crisis regimes with lead time and high classification accuracy.
- Most of the performance improvement is attributable to the **HMM traffic‑light** preventing long‑vol exposure during Turbulent regimes.

---

### Decision Logic

Signals are generated by a strict priority order (first match wins):

1. **Hard stop‑loss** — if position open and unrealised PnL < \(-\text{max\_loss\_pct} \times\) entry cost → `STOP_LOSS` (`CLOSE_ALL`).
2. **Time exit** — if holding period > `max_hold_days` → `CLOSE_ALL`.
3. **High turbulence** — if \(P(\text{Turbulent}) > 0.80\):
   - Position open → `CLOSE_ALL`.
   - Flat → `HOLD` (stay flat).
4. **Moderate turbulence** — if \(0.60 < P(\text{Turbulent}) \le 0.80\):
   - Position open → `DELTA_HEDGE`.
   - Flat → `HOLD` (no entry).
5. **Spread compression** — if position open and IV spread < exit threshold → `CLOSE_ALL` (alpha gone).
6. **Entry** — if Regime = Calm, IV spread > entry threshold, and position FLAT → `ENTER_LONG` (open ATM straddle).
7. **Default** — `HOLD`.

See `orchestrator.py` and `PROJECT_ARCHITECTURE.md` (§5) for the exact logic tree.

---

### Project Structure

After cleanup, the intended layout is:

```text
Regime-Volatility-Arbitrage-Engine/
├── main.py                  # Entry point (--mode research|validate|test|paper|live)
├── config.py                # Central configuration (pricing, regime, IBKR, storage)
├── pricing_engine.py        # Rough-vol Volterra MC pricer (Hybrid Scheme, Numba)
├── regime_filter.py         # 2-state Gaussian HMM (Baum–Welch, Viterbi, online update)
├── orchestrator.py          # Strategy loop, decision logic, position management
├── connection_manager.py    # IBKR TWS connectivity, tick ingestion, HDF5 storage
├── execution_handler.py     # Order execution, chase algorithm, fill logging
├── validation_suite.py      # MC convergence + regime stability tests
├── examples_stochastic_processes.py  # One example per stochastic process
├── stochastic_processes_reference.md # Equations and derivations used in the code
├── tests/
│   ├── test_pricing_engine.py
│   ├── test_orchestrator.py
│   ├── test_execution_handler.py
│   └── test_validation_suite.py
├── paper/
│   └── main.tex             # Academic paper (PDF built locally as paper/main.pdf)
├── notebooks/               # Research notebooks (analysis, validation) — planned
├── figures/                 # Generated plots (roughness, regimes, equity, convergence, costs)
├── animated simulations/    # HTML animations (architecture + decision flow)
├── PROJECT_ARCHITECTURE.md  # Detailed architecture and implementation reference
├── requirements.txt         # Python dependencies
├── LICENSE                  # MIT License
└── README.md                # This file
```

Runtime data and logs (`tick_data.h5`, `trade_log.csv`, `fills.csv`, `heartbeat.log`) are intentionally **not** tracked by git (see `.gitignore`).

---

### Quickstart

```bash
git clone https://github.com/FelipeCardozo0/Regime-Volatility-Arbitrage-Engine.git
cd Regime-Volatility-Arbitrage-Engine

# Install dependencies
pip install -r requirements.txt

# Research mode: fits HMM, runs MC pricing, generates plots
python main.py --mode research

# Validation suite: MC convergence + regime stability (CI-friendly)
python main.py --mode validate

# Run unit tests
pytest tests/ -v

# Paper trading (requires IBKR TWS running on port 7497)
python main.py --mode paper

# Live trading (port 7496) — only after validation + paper trading certification
python main.py --mode live
```

Modes:

| Mode      | Description                                               | IBKR required |
|----------|-----------------------------------------------------------|---------------|
| `research` | HMM calibration, rough‑vol pricing, and plots            | No            |
| `validate` | MC convergence + regime stability checks                 | No            |
| `test`     | Smoke test of all layers                                 | No            |
| `paper`    | Full system on IBKR paper trading (port 7497)           | Yes           |
| `live`     | Live trading (port 7496), gated by validation + review  | Yes           |

---

### Configuration

All operational parameters live in `config.py`. Key ones:

- **Pricing engine**:
  - `HURST_EXPONENT` (default `0.07`)
  - `V0` (initial variance, default `0.04`)
  - `LAMBDA_VOL_OF_VOL` (vol‑of‑vol)
  - `MC_PATHS` (number of Monte Carlo paths)
  - `MC_STEPS_PER_DAY` (time resolution)
  - `RISK_FREE_RATE`
- **Regime filter**:
  - `HMM_N_STATES` (default `2`)
  - `HMM_TICKER` (default `"SPY"`)
  - `HMM_HISTORY_YEARS` (training window)
  - `TURBULENCE_THRESHOLD` (baseline 0.6)
- **IBKR connectivity**:
  - `TWS_HOST`, `TWS_PAPER_PORT`, `TWS_LIVE_PORT`
  - `TWS_CLIENT_ID` (market data; execution uses `client_id + 1`)
- **Storage**:
  - `HDF5_TICK_STORE` (`tick_data.h5`)

No parameters are hard‑coded in the strategy logic; all go through `config.py`.

---

### Limitations and Future Work

As discussed in the paper:

- **Gaussian emissions** in the HMM understate tails; Student‑\(t\) or skewed emissions would better capture crisis dynamics.
- **Fixed Hurst exponent** \(H\) ignores regime‑dependent roughness; a regime‑conditional \(H\) is a natural extension.
- Current backtests are primarily **synthetic**; a full historical SPY options study is the next step before deployment.
- The paper outlines future extensions:
  - Three‑state HMM (Calm / Trending / Turbulent).
  - Joint modelling of the **VIX term structure** as an additional observation.
  - Intraday calibration using a high‑frequency options data provider (e.g. Polygon.io).
  - Two‑tier **HMM–Hawkes** architecture where a regime‑conditional Hawkes process quantifies contagion within Turbulent regimes.

---

### References

A non‑exhaustive subset of the references implemented in this codebase:

1. J. Gatheral, T. Jaisson, M. Rosenbaum — *Volatility is rough* (Quantitative Finance, 2018).  
2. M. Bennedsen, A. Lunde, M. S. Pakkanen — *Hybrid scheme for Brownian semistationary processes* (Finance & Stochastics, 2017).  
3. C. Bayer, P. Friz, J. Gatheral — *Pricing under rough volatility* (Quantitative Finance, 2016).  
4. O. El Euch, M. Rosenbaum — *The characteristic function of rough Heston models* (Mathematical Finance, 2019).  
5. S. L. Heston — *A closed-form solution for options with stochastic volatility* (RFS, 1993).  
6. P. Hagan et al. — *Managing smile risk* (Wilmott Magazine, 2002).  
7. L. R. Rabiner — *A tutorial on hidden Markov models* (Proc. IEEE, 1989).  
8. J. D. Hamilton — *A new approach to the economic analysis of nonstationary time series* (Econometrica, 1989).  
9. E. O. Thorp — *The Kelly criterion in blackjack, sports betting, and the stock market* (in *The Kelly Capital Growth Investment Criterion*, 2011).

---

### Authors

- **Felipe Cardozo** — Mathematics & Computer Science, Emory University  
- **Mitchell Scott, Ph.D.** — Department of Mathematics, Emory University

