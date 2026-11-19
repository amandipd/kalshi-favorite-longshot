# Local backtest: sizing grid for the bot's own rule (Oct 14, 2026)

**Setup**
- Script: local_backtest_grid.py (beside this file), on research/kalshi_15min/strategies_backtest.py.
- Rule: version 4 of the live bot. It buys the favourite at the end of minute 8 when its ask is 92-99.9¢, across crypto, metals and energy. It skips spreads of 2¢ or more, and "late" favourites (50¢ or under at minute 6 or 7, or up 10¢+ in minute 8). Whole contracts, Fed-decision windows skipped.
- Start: $2,000 on Dec 10, 2025. The history runs to about Oct 8, 2026.
- Sizing: "bet" = % of bankroll per bet; "window" = cap on the sum of a 15-minute window's bets (each bet = min(bet%, window% / n bets)).

**Two fill models**
- **full:** every order fills in full at the recorded ask + 0.4¢ (live-like).
- **tape:** each order fills only as far as Kalshi's public trade tape says the book had (liquidity.py). Live check: the model predicted 126 contracts against 130 real on 76 orders.

| fills | bet | window | end from $2k | max drop | worst 24h | worst 15 min | Dec10-Jul17 | Jul18-on |
|---|---|---|---|---|---|---|---|---|
| full | 1% | 20% | $7,826 | 23% | −13.7% | −4.9% | +30% | +201% |
| full | 2% | 20% | $27,966 | 41% | −25.8% | −10.0% | +63% | +756% |
| full | 3% | 20% | $69,859 | 56% | −35.7% | −15.0% | +89% | +1752% |
| full | 4% | 20% | $133,310 | 68% | −42.8% | −20.0% | +93% | +3348% |
| full | 5% | 20% | $201,261 | 76% | −46.6% | −20.1% | +68% | +5900% |
| full | 3% | 10% | $35,454 | 55% | −27.4% | −10.0% | +57% | +1031% |
| full | 3% | 30% | $83,922 | 56% | −36.8% | −15.0% | +90% | +2112% |
| tape | 1% | 20% | $3,065 | 18% | −8.3% | −4.7% | +4% | +47% |
| tape | 2% | 10% | $3,306 | 33% | −15.6% | −6.5% | −6% | +76% |
| tape | 2% | 20% | $3,518 | 33% | −15.4% | −8.2% | −5% | +85% |
| tape | 3% | 10% | $3,266 | 44% | −18.6% | −7.3% | −17% | +96% |
| tape | 3% | 20% | $3,605 | 45% | −21.2% | −10.9% | −13% | +107% |
| tape | 3% | 30% | $3,715 | 46% | −21.2% | −11.4% | −13% | +113% |
| tape | 4% | 20% | $3,442 | 57% | −26.8% | −11.8% | −24% | +127% |
| tape | 5% | 20% | $3,274 | 66% | −32.4% | −14.7% | −37% | +161% |

**Readings**
- **With realistic (tape) fills, profit is almost flat in bet size** ($3.1-3.7k from $2k), while the max drawdown climbs from 18% (1%) to 45% (3%) and 66% (5%).
  - Book depth caps the profit.
  - Bigger orders mainly add exposure on the fills they do get, which are adversely selected.
- **2%/20% keeps about 97% of 3%/20%'s realistic profit** ($3,518 vs $3,605), with a max drop of 33% instead of 45% and a worst 24h of −15% instead of −21%.
- **1%/20%** keeps about two-thirds of the profit with an 18% max drop.
- **The window cap matters little at 2-3%** (10% vs 20% vs 30%).
- **The full-fill line scales without limit and is unrealistic**, given about 60% live fill rates.
- **Live context**
  - 1,070 live bets since Sep 28: 47 lost against 51.5 implied.
  - 92¢+: 876 bets, 18 lost against 33.5 implied (edge about 1.3-1.8 pt over price).
  - Live fill share is about 60% of contracts asked.
  - Fast entry (orders at minute 8 + 0.3 s) went live Oct 14, 21:04 UTC.
