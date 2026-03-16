# Animated Simulations

Visual representations of how the **Regime Volatility Arbitrage Engine** works.

## Contents

| File | Description |
|------|-------------|
| **index.html** | Interactive animated architecture: data flow from IBKR → ConnectionManager → Orchestrator → PricingEngine / RegimeFilter → Signal → ExecutionHandler. Flow dots show live direction; speed and pause controls. |
| **decision-flow.html** | Animated decision logic tree: how the strategy chooses ENTER_LONG, HOLD, DELTA_HEDGE, or CLOSE_ALL from regime and IV spread. |

## How to view

Open in a browser (no server required):

```bash
open "animated simulations/index.html"
# or
open "animated simulations/decision-flow.html"
```

Or double-click the HTML files in Finder.

## Tech

- Self-contained HTML/CSS/JS; no build step.
- Fonts loaded from Google Fonts (JetBrains Mono, Outfit) when online.
