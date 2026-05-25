# 🔑 Dira Behagrala — Lottery Optimizer

Maximize your chances of winning an apartment in the Israeli Ministry of Housing lottery (דירה בהגרלה).

## What it does

The Israeli housing lottery lets young couples apply to **3 cities**, entering all available raffles within each. This tool helps you pick the **best 3 cities** by calculating your real probability of winning at least one raffle — accounting for:

- **General-pool apartments only** — reserved units for local residents (בני המקום), handicapped applicants, and military reservists are excluded from your pool
- **Your city preferences** — balance between best odds and where you actually want to live
- **Probability trends over time** — see how registration numbers change as the deadline approaches

## How to use

Open the app, set your city preferences using the sliders, and get your personalized top-3 recommendation.

👉 **[Launch Dira Behagrala](https://ronelias-dira-lottery-streamlit-app-bpxpgu.streamlit.app/)**

### Scoring

The app uses an **additive utility model** to rank cities:

```
score = α × P(win) + (1-α) × (preference / 10)
```

Adjust **α** in Advanced Settings — from *City first* (location matters most) to *Best odds* (maximize your win probability).

## Built by

[Ron Elias](https://www.linkedin.com/in/ronelias7/)
