"""Dira B'Hagral — Lottery Probability Tool (Streamlit app)."""

import os
import glob
import json
from datetime import datetime, timedelta

import requests
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from scraper import (
    fetch_projects,
    save_data,
    compute_city_probabilities,
    compute_city_probabilities_over_time,
    DATA_DIR,
)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Dira Edge — Beat the Lottery",
    page_icon="🔑",
    layout="wide",
)

# ── Helpers ───────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def load_latest_data() -> pd.DataFrame:
    """Load data from disk if fresh enough, otherwise fetch from API."""
    latest_path = os.path.join(DATA_DIR, "latest.csv")
    if os.path.exists(latest_path):
        df = pd.read_csv(latest_path, encoding="utf-8-sig")
        if "scraped_at" in df.columns:
            scraped_at = pd.to_datetime(df["scraped_at"].iloc[0])
            if datetime.now() - scraped_at < timedelta(hours=1):
                return df
    # Fetch fresh
    df = fetch_projects()
    if not df.empty:
        save_data(df)
    return df


def get_latest_timestamp() -> str:
    latest_path = os.path.join(DATA_DIR, "latest.csv")
    if os.path.exists(latest_path):
        try:
            df = pd.read_csv(latest_path, encoding="utf-8-sig", nrows=1)
            if "scraped_at" in df.columns:
                return df["scraped_at"].iloc[0]
        except Exception:
            pass
    return "unknown"


def compute_joint_p(p_values: list) -> float:
    p_lose = 1.0
    for p in p_values:
        p_lose *= (1.0 - p)
    return 1.0 - p_lose


def n_snapshots() -> int:
    """Count unique time snapshots — prefers history.csv (works on Streamlit Cloud)."""
    history_path = os.path.join(DATA_DIR, "history.csv")
    if os.path.exists(history_path):
        try:
            df = pd.read_csv(history_path, encoding="utf-8-sig", usecols=["snapshot_time"])
            return df["snapshot_time"].nunique()
        except Exception:
            pass
    return len(glob.glob(os.path.join(DATA_DIR, "scraped_*.csv")))


COUNTER_URL = "https://api.counterapi.dev/v1/dira-lottery/visits"


def get_visit_count(increment: bool = False):
    """Read (and optionally increment) the visitor counter. Returns None on failure."""
    url = COUNTER_URL + ("/up" if increment else "")
    for timeout in (5, 10):  # retry once with longer timeout
        try:
            r = requests.get(url, timeout=timeout)
            if r.status_code == 200:
                return r.json().get("count")
        except Exception:
            continue
    return None


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🔑 Dira Edge")
    st.caption("דירה בהגרלה — Lottery Optimizer")
    st.divider()

    _last_refresh = st.session_state.get("last_refresh_time")
    _cooldown = 60  # seconds between refreshes
    _wait = max(0, _cooldown - (datetime.now() - _last_refresh).total_seconds()) if _last_refresh else 0

    col1, col2 = st.columns([2, 1])
    with col1:
        refresh_clicked = st.button(
            "🔄 Refresh Data",
            width="stretch",
            disabled=_wait > 0,
        )
    with col2:
        if _wait > 0:
            st.success("Updated ✓")
        else:
            ts = get_latest_timestamp()
            st.caption(f"Last:\n{ts[:10] if ts != 'unknown' else '—'}")

    if refresh_clicked and _wait == 0:
        st.session_state["last_refresh_time"] = datetime.now()
        load_latest_data.clear()  # only clear this function's cache, not all users'
        st.rerun()

    st.divider()
    st.subheader("Your City Preferences")
    st.caption("Rate each city 0–10. Higher = more preferred.")

    # ── Save / Load preferences ──
    profile_name = st.text_input("Profile name (optional)", placeholder="e.g. Ron & Marine")

    uploaded = st.file_uploader(
        "Load saved preferences (.json or .csv)",
        type=["json", "csv"],
        label_visibility="collapsed",
    )
    if uploaded is not None:
        if uploaded.size > 200 * 1024:  # 200 KB hard cap
            st.error("File is too large.")
        else:
            try:
                if uploaded.name.endswith(".csv"):
                    prefs_csv = pd.read_csv(uploaded, encoding="utf-8-sig")
                    loaded_prefs = {}
                    for _, row in prefs_csv.iterrows():
                        city = str(row.get("city_english") or row.get("city_hebrew") or "")[:80]
                        rank = row.get("preference_rank")
                        if city and pd.notna(rank):
                            try:
                                loaded_prefs[city] = max(0, min(10, int(float(rank))))
                            except (ValueError, TypeError):
                                pass
                    for city, val in loaded_prefs.items():
                        st.session_state[f"pref_{city}"] = val
                    st.success(f"Loaded {len(loaded_prefs)} city preferences")
                else:
                    loaded = json.load(uploaded)
                    if not isinstance(loaded, dict):
                        raise ValueError("Invalid format")
                    for city, val in loaded.get("preferences", {}).items():
                        if isinstance(city, str) and len(city) <= 80:
                            try:
                                st.session_state[f"pref_{city}"] = max(0, min(10, int(val)))
                            except (ValueError, TypeError):
                                pass
                    name = loaded.get("name", "")
                    if isinstance(name, str) and name:
                        st.session_state["profile_name"] = name[:60]
                    st.success(f"Loaded: {name or 'preferences'}")
            except Exception:
                st.error("Could not read file. Please upload a valid preferences file.")

    if st.session_state.get("profile_name") and not profile_name:
        profile_name = st.session_state["profile_name"]

# ── Load data ─────────────────────────────────────────────────────────────────
with st.spinner("Loading lottery data..."):
    raw_df = load_latest_data()

if raw_df.empty:
    st.error("No data available. Click **Refresh Data** in the sidebar.")
    st.stop()

city_probs = compute_city_probabilities(raw_df)
all_cities = city_probs["city_english"].tolist()
scraped_at = get_latest_timestamp()

# ── City preference sliders (sidebar continued) ───────────────────────────────
with st.sidebar:
    preferences = {}
    for city_eng in sorted(all_cities):
        heb = city_probs.loc[city_probs["city_english"] == city_eng, "city_hebrew"].values
        label = f"{city_eng}  ({heb[0] if len(heb) > 0 else ''})"
        preferences[city_eng] = st.slider(label, 0, 10, 5, key=f"pref_{city_eng}")

    st.divider()
    # ── Save preferences button ──
    prefs_json = json.dumps(
        {"name": profile_name or "My Preferences", "preferences": preferences},
        ensure_ascii=False,
        indent=2,
    )
    safe_name = (profile_name or "preferences").replace(" ", "_").replace("/", "-")
    st.download_button(
        label="💾 Save Preferences",
        data=prefs_json.encode("utf-8"),
        file_name=f"dira_prefs_{safe_name}.json",
        mime="application/json",
        width="stretch",
    )

# ── Count this visit (once per session) ──────────────────────────────────────
if "visit_counted" not in st.session_state:
    visit_count = get_visit_count(increment=True)
    st.session_state["visit_counted"] = True
    st.session_state["visit_count"] = visit_count
else:
    visit_count = st.session_state.get("visit_count")

# ── Sidebar: Advanced Settings + LinkedIn ─────────────────────────────────────
with st.sidebar:
    st.divider()

    with st.expander("⚙️ Advanced Settings"):
        st.caption("What matters more to you — best odds or best location?")

        alpha = st.slider(
            "odds_vs_location",
            min_value=0.0, max_value=1.0, value=0.5, step=0.05,
            key="alpha", label_visibility="collapsed",
        )
        st.markdown(
            "<div style='display:flex;justify-content:space-between;"
            "font-size:0.75rem;color:#888;margin-top:-10px;padding:0 2px'>"
            "<span>🏙️ City first</span><span>Best odds 📊</span></div>",
            unsafe_allow_html=True,
        )

        # Persona card based on alpha
        if alpha >= 0.85:
            persona, color, desc = (
                "🎯 Odds Hunter",
                "#1a6b3c",
                "You're playing the numbers game — every percent counts. The city is a bonus.",
            )
        elif alpha >= 0.65:
            persona, color, desc = (
                "📈 Smart Player",
                "#1a5276",
                "You lean toward the best odds, but you still care where you land.",
            )
        elif alpha >= 0.35:
            persona, color, desc = (
                "⚖️ The Balancer",
                "#6c3483",
                "You want a real shot at winning AND a city you'll actually love.",
            )
        elif alpha >= 0.15:
            persona, color, desc = (
                "🏡 Location-First",
                "#784212",
                "You know where you want to live — odds are a tiebreaker.",
            )
        else:
            persona, color, desc = (
                "❤️ Dream Chaser",
                "#922b21",
                "Your heart leads. The city has to be right — odds are secondary.",
            )

        st.markdown(
            f"""<div style="background:{'rgba(26,107,60,0.08)' if color == '#1a6b3c' else 'rgba(100,100,200,0.07)'};
                border-left:3px solid {color}; border-radius:6px;
                padding:10px 12px; margin:6px 0 10px 0;">
                <strong style="color:{color}">{persona}</strong><br>
                <span style="font-size:0.83rem;color:#555">{desc}</span>
            </div>""",
            unsafe_allow_html=True,
        )

        st.caption(
            f"❤️ {1-alpha:.0%} location weight · 🎯 {alpha:.0%} probability weight  \n"
            f"score = {alpha:.2f} × P(win) + {1-alpha:.2f} × (pref / 10)"
        )

    st.markdown(
        """
        <div style="text-align:center; padding: 12px 0 4px 0;">
            <a href="https://www.linkedin.com/in/ronelias7/" target="_blank"
               style="text-decoration:none; color:#0077B5; font-size:0.82rem;">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16"
                     fill="#0077B5" viewBox="0 0 16 16" style="vertical-align:-2px; margin-right:4px;">
                  <path d="M0 1.146C0 .513.526 0 1.175 0h13.65C15.474 0 16 .513 16 1.146v13.708c0 .633-.526 1.146-1.175 1.146H1.175C.526 16 0 15.487 0 14.854zm4.943 12.248V6.169H2.542v7.225zm-1.2-8.212c.837 0 1.358-.554 1.358-1.248-.015-.709-.52-1.248-1.342-1.248S2.4 3.226 2.4 3.934c0 .694.521 1.248 1.327 1.248zm4.908 8.212V9.359c0-.216.016-.432.08-.586.173-.431.568-.878 1.232-.878.869 0 1.216.662 1.216 1.634v3.865h2.401V9.25c0-2.22-1.184-3.252-2.764-3.252-1.274 0-1.845.7-2.165 1.193v.025h-.016l.016-.025V6.169h-2.4c.03.678 0 7.225 0 7.225z"/>
                </svg>
                Built by Ron Elias
            </a>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ── Main content ──────────────────────────────────────────────────────────────
title_col, counter_col = st.columns([5, 1])
with title_col:
    st.title("🔑 Dira Edge — Find Your Winning Cities")
    st.caption(
        f"Data as of {scraped_at} · "
        f"{len(raw_df)} raffles across {len(city_probs)} cities · "
        f"Target: Young Couple (זוג צעיר)"
    )
with counter_col:
    if visit_count is not None:
        st.markdown(
            f"""
            <div style="text-align:center; padding:16px 0 0 0;">
                <div style="font-size:1.5rem; font-weight:700; line-height:1;">{visit_count:,}</div>
                <div style="font-size:0.7rem; color:#888; margin-top:3px;">👥 visitors</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
st.info(
    "**Rules:** Choose 3 cities. Enter all available raffles within those cities. "
    "Goal: maximize P(winning at least one apartment)."
)

tabs = st.tabs(["📊 Recommendations", "📈 Time Series", "📋 Raw Data"])

# ─────────────────────────────────────────────────────────────────────────────
# Tab 1: Recommendations
# ─────────────────────────────────────────────────────────────────────────────
with tabs[0]:
    # Merge preferences and compute MAUT additive score
    # score = α × P(win) + (1-α) × (pref / 10)
    # Both components normalized to [0,1]. α comes from the sidebar slider.
    prefs_df = pd.DataFrame(
        [{"city_english": c, "preference": v} for c, v in preferences.items()]
    )
    merged = city_probs.merge(prefs_df, on="city_english", how="left")
    merged["preference"] = merged["preference"].fillna(5)
    merged["pref_norm"] = merged["preference"] / 10.0
    merged["maut_score"] = alpha * merged["p_win"] + (1 - alpha) * merged["pref_norm"]

    # ── Top 3 columns ──
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Option A — Best Probability")
        st.caption("Top 3 by P(win) only — maximizes your joint win chance")
        top3_prob = merged.nlargest(3, "p_win")
        jp_prob = compute_joint_p(top3_prob["p_win"].tolist())

        for rank, (_, row) in enumerate(top3_prob.iterrows(), 1):
            with st.container(border=True):
                st.markdown(f"**{rank}. {row['city_english']}** &nbsp; {row['city_hebrew']}")
                c1, c2, c3 = st.columns(3)
                c1.metric("P(win)", f"{row['p_win']:.1%}")
                c2.metric("Raffles", int(row["raffles"]))
                c3.metric("Apts", int(row["general_apartments"] if "general_apartments" in row else row["total_apartments"]))

        st.success(f"**Joint P(winning at least one city): {jp_prob:.1%}**")

    with col_b:
        st.subheader("Option B — Your Balanced Score")
        st.caption(
            f"Top 3 by MAUT score = **{alpha:.0%}** × P(win) + **{1-alpha:.0%}** × preference  "
            f"*(α = {alpha:.2f})*"
        )
        top3_weighted = merged.nlargest(3, "maut_score")
        jp_weighted = compute_joint_p(top3_weighted["p_win"].tolist())

        for rank, (_, row) in enumerate(top3_weighted.iterrows(), 1):
            with st.container(border=True):
                st.markdown(f"**{rank}. {row['city_english']}** &nbsp; {row['city_hebrew']}")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("P(win)", f"{row['p_win']:.1%}")
                c2.metric("Pref", f"{int(row['preference'])}/10")
                c3.metric("Score", f"{row['maut_score']:.3f}")
                c4.metric("Raffles", int(row["raffles"]))

        st.success(f"**Joint P(winning at least one city): {jp_weighted:.1%}**")

    st.divider()

    # ── Full rankings table ──
    st.subheader("All Cities — Full Rankings Table")
    st.caption(
        "P(win) = general pool only (excludes handicapped/reservist/local reserved units).  "
        f"MAUT Score = {alpha:.0%} × P(win) + {1-alpha:.0%} × (pref/10)"
    )
    table = merged.copy()
    table["rank_prob"] = table["p_win"].rank(ascending=False, method="min").astype(int)
    table["rank_maut"] = table["maut_score"].rank(ascending=False, method="min").astype(int)

    gen_apts_col = "general_apartments" if "general_apartments" in table.columns else "total_apartments"
    gen_reg_col  = "general_registered"  if "general_registered"  in table.columns else "total_registered"

    display_table = table[[
        "rank_prob", "city_english", "city_hebrew",
        "raffles", gen_apts_col, gen_reg_col,
        "p_win", "preference", "maut_score", "rank_maut"
    ]].sort_values("rank_prob").reset_index(drop=True)
    display_table.columns = [
        "#", "City (EN)", "City (HE)",
        "Raffles", "Gen. Apts", "Gen. Registered",
        "P(win)", "Pref (0-10)", "MAUT Score", "MAUT #"
    ]
    display_table["P(win)"] = display_table["P(win)"].map("{:.2%}".format)
    display_table["MAUT Score"] = display_table["MAUT Score"].round(3)

    st.dataframe(display_table, width="stretch", hide_index=True)

    st.divider()

    # ── Bar chart: P(win) per city ──
    st.subheader("P(Win) per City")
    top3_names = set(top3_prob["city_english"].values)
    bar_df = merged.sort_values("p_win", ascending=False).copy()
    bar_df["color"] = bar_df["city_english"].apply(
        lambda c: "Top 3" if c in top3_names else "Other"
    )

    fig_bar = px.bar(
        bar_df,
        x="city_english",
        y="p_win",
        color="color",
        color_discrete_map={"Top 3": "#2ecc71", "Other": "#3498db"},
        labels={"p_win": "P(win)", "city_english": "City", "color": ""},
        text=bar_df["p_win"].map("{:.1%}".format),
        hover_data={"city_hebrew": True, "raffles": True,
                    "total_apartments": True, "total_registered": True},
    )
    fig_bar.update_traces(textposition="outside")
    fig_bar.update_layout(
        yaxis_tickformat=".0%",
        xaxis_tickangle=-35,
        showlegend=True,
        height=480,
        margin=dict(t=20, b=10),
    )
    st.plotly_chart(fig_bar)

    # ── Bar chart: MAUT score ──
    st.subheader(f"MAUT Score per City  (α={alpha:.2f} · {alpha:.0%} probability + {1-alpha:.0%} preference)")
    top3w_names = set(top3_weighted["city_english"].values)
    bar_df["color_w"] = bar_df["city_english"].apply(
        lambda c: "Top 3 (balanced)" if c in top3w_names else "Other"
    )
    bar_df_sorted = bar_df.sort_values("maut_score", ascending=False)
    fig_weighted = px.bar(
        bar_df_sorted,
        x="city_english",
        y="maut_score",
        color="color_w",
        color_discrete_map={"Top 3 (balanced)": "#e74c3c", "Other": "#e67e22"},
        labels={"maut_score": "MAUT Score (0–1)", "city_english": "City", "color_w": ""},
        text=bar_df_sorted["maut_score"].round(3),
    )
    fig_weighted.update_traces(textposition="outside")
    fig_weighted.update_layout(
        xaxis_tickangle=-35,
        yaxis_range=[0, 1.05],
        height=480,
        margin=dict(t=20, b=10),
    )
    st.plotly_chart(fig_weighted)


# ─────────────────────────────────────────────────────────────────────────────
# Tab 2: Time Series
# ─────────────────────────────────────────────────────────────────────────────
with tabs[1]:
    st.subheader("P(Win) Over Time")

    num_snapshots = n_snapshots()
    st.metric("Data points", num_snapshots)

    if num_snapshots < 2:
        st.info("Not enough data points yet to display the trend. Check back soon.")
    else:
        with st.spinner("Loading historical data..."):
            hist = compute_city_probabilities_over_time(DATA_DIR)

        if hist.empty:
            st.warning("Could not load historical data.")
        else:
            # City filter — default to top 10 by latest P(win)
            default_cities = city_probs.head(10)["city_english"].tolist()
            selected_cities = st.multiselect(
                "Select cities to display",
                options=sorted(all_cities),
                default=default_cities,
            )

            ts_filtered = hist[hist["city_english"].isin(selected_cities)].copy()
            ts_filtered["p_win_pct"] = ts_filtered["p_win"] * 100

            fig_ts = px.line(
                ts_filtered,
                x="snapshot_time",
                y="p_win_pct",
                color="city_english",
                markers=True,
                labels={
                    "p_win_pct": "P(win) %",
                    "snapshot_time": "Date",
                    "city_english": "City",
                },
                hover_data={"city_hebrew": True, "raffles": True,
                            "total_apartments": True, "total_registered": True},
            )
            fig_ts.update_layout(
                yaxis_ticksuffix="%",
                height=520,
                legend=dict(orientation="v", x=1.02, y=1),
                margin=dict(t=20),
            )
            st.plotly_chart(fig_ts)

            # Table view
            with st.expander("Show raw time-series data"):
                pivot = ts_filtered.pivot_table(
                    index="snapshot_time",
                    columns="city_english",
                    values="p_win",
                    aggfunc="first",
                )
                pivot.index = pd.to_datetime(pivot.index).strftime("%Y-%m-%d %H:%M")
                pivot = pivot.map(lambda x: f"{x:.2%}" if pd.notna(x) else "")
                st.dataframe(pivot, width="stretch")


# ─────────────────────────────────────────────────────────────────────────────
# Tab 3: Raw Data
# ─────────────────────────────────────────────────────────────────────────────
with tabs[2]:
    st.subheader("Raw Raffle Data")
    st.caption(f"{len(raw_df)} raffle entries · last updated {scraped_at[:10] if scraped_at != 'unknown' else '—'}")

    # City filter
    city_filter = st.multiselect(
        "Filter by city",
        options=sorted(raw_df["city_english"].unique()),
        default=[],
        placeholder="Show all cities",
    )
    filtered = raw_df[raw_df["city_english"].isin(city_filter)] if city_filter else raw_df

    # Add per-raffle p(win) column for display (using general pool)
    disp = filtered.copy()
    has_gen = "general_apartments" in disp.columns and "general_registered" in disp.columns
    def raffle_p(row):
        apts = row["general_apartments"] if has_gen else row["apartments"]
        reg  = row["general_registered"]  if has_gen else row["registered"]
        if reg > 0:
            return f"{min(1.0, apts / reg):.2%}"
        return "100%" if apts > 0 else "0%"
    disp["p_win_general"] = disp.apply(raffle_p, axis=1)

    cols = ["city_english", "city_hebrew", "project_name",
            "apartments", "general_apartments", "registered", "general_registered",
            "p_win_general", "lottery_date", "application_end", "neighborhood", "price_per_unit"]
    show_cols = [c for c in cols if c in disp.columns]
    st.dataframe(disp[show_cols].reset_index(drop=True), width="stretch", hide_index=True)

    # Download button
    csv_bytes = filtered.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button(
        label="Download CSV",
        data=csv_bytes,
        file_name=f"dira_data_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )
