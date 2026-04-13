import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from stats import df, sectransfer_df, sec_deltas_df, playerStats

LINE_EXCLUDED_METRICS = {"srs", "sos", "minutes"}
CHANGE_EXCLUDED_METRICS = LINE_EXCLUDED_METRICS | {"obpm", "dbpm", "bpm"}
CHANGE_COLOR_SCALE = [
    [0.0, "#b2182b"],
    [0.5, "#f7f7f7"],
    [1.0, "#1a9850"],
]


def _safe_key(text):
    return str(text).replace(" ", "_").replace(",", "_")


def _valid_metrics(metrics, available_cols, excluded):
    return [m for m in metrics if m in available_cols and m.lower() not in excluded]


def _apply_line_layout(fig, y_title="Value"):
    fig.update_layout(
        xaxis_title="Metric",
        yaxis_title=y_title,
        xaxis_tickangle=-45,
        height=520,
        margin=dict(l=20, r=20, t=30, b=120),
        legend=dict(orientation="h", y=1.05, x=0),
    )

st.set_page_config(
    page_title="Basketball Transfer Dashboard",
    page_icon=":bar_chart:",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
    <style>
    /* --- Sidebar --- */
    [data-testid="stSidebar"] { background-color: #660000; }
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] span:not([data-baseweb="tag"] span) { color: #ffffff !important; }
    [data-testid="stSidebar"] [data-baseweb="select"] [data-testid="stMarkdownContainer"],
    [data-testid="stSidebar"] [data-baseweb="select"] div[class*="placeholder"],
    [data-testid="stSidebar"] [data-baseweb="select"] div[class*="singleValue"] { color: #660000 !important; }
    [data-testid="stSidebar"] span[data-baseweb="tag"] { background-color: #660000 !important; color: #ffffff !important; }

    /* --- Top filter banner (main content radio) --- */
    section[data-testid="stMain"] div[data-testid="stRadio"] {
        background-color: #660000;
        border-radius: 10px;
        padding: 14px 22px 10px 22px;
        margin-bottom: 16px;
    }
    /* Radio group label ("Filter by") */
    section[data-testid="stMain"] div[data-testid="stRadio"] > label p {
        color: #ffffff !important;
        font-size: 1.15rem !important;
        font-weight: 700 !important;
        letter-spacing: 0.02em;
    }
    /* Individual option labels and all nested text/spans */
    section[data-testid="stMain"] div[data-testid="stRadio"] label,
    section[data-testid="stMain"] div[data-testid="stRadio"] label span,
    section[data-testid="stMain"] div[data-testid="stRadio"] label p,
    section[data-testid="stMain"] div[data-testid="stRadio"] div,
    section[data-testid="stMain"] div[data-testid="stRadio"] span {
        color: #ffffff !important;
        font-size: 1.1rem !important;
        font-weight: 500 !important;
    }
    /* Radio button circles */
    section[data-testid="stMain"] div[data-testid="stRadio"] input[type="radio"] {
        accent-color: #ffffff;
    }
    </style>
""", unsafe_allow_html=True)


def build_chart_df(transfer_df, metrics):
    if transfer_df.empty or "Conf" not in transfer_df.columns:
        return pd.DataFrame()
    valid = _valid_metrics(metrics, transfer_df.columns, LINE_EXCLUDED_METRICS)
    if not valid:
        return pd.DataFrame()
    sec_mask = transfer_df["Conf"].eq("SEC")
    non_sec_mean = transfer_df.loc[~sec_mask, valid].mean(numeric_only=True)
    sec_mean = transfer_df.loc[sec_mask, valid].mean(numeric_only=True)
    return pd.DataFrame({
        "metric": valid,
        "Non-SEC": [non_sec_mean.get(m, np.nan) for m in valid],
        "SEC": [sec_mean.get(m, np.nan) for m in valid],
    })


def plot_charts(transfer_df, metrics, selected_confs, subject, selected_players, is_all):
    if transfer_df.empty or "Conf" not in transfer_df.columns:
        st.info("No transfer data available for plotting.")
        return

    # Player-selected mode: one non-SEC line per player + shared SEC average line.
    if not is_all and selected_players:
        valid = _valid_metrics(metrics, transfer_df.columns, LINE_EXCLUDED_METRICS)
        if not valid:
            st.info("No metric data available for plotting.")
            return

        sec_mean = transfer_df.loc[transfer_df["Conf"].eq("SEC"), valid].mean(numeric_only=True)
        fig = go.Figure()

        for player in selected_players:
            player_non_sec = transfer_df[(transfer_df["full_name"] == player) & (transfer_df["Conf"] != "SEC")]
            if player_non_sec.empty:
                continue
            # Use the latest non-SEC row for each player
            player_row = player_non_sec.sort_values("Year").tail(1).iloc[0]
            fig.add_trace(go.Scatter(
                x=valid,
                y=[player_row.get(m, np.nan) for m in valid],
                mode="lines+markers",
                name=player,
            ))

        if not fig.data:
            st.info("No player non-SEC data available for plotting.")
            return

        fig.add_trace(go.Scatter(
            x=valid,
            y=[sec_mean.get(m, np.nan) for m in valid],
            mode="lines+markers",
            name="SEC",
            line=dict(width=3),
        ))

        st.subheader(f"{subject} vs SEC by Metric")
        _apply_line_layout(fig)
        st.plotly_chart(fig, use_container_width=True, key=f"chart_{_safe_key(subject)}_players")
        return

    non_sec_available = sorted(c for c in transfer_df["Conf"].dropna().unique() if c != "SEC")
    confs_to_plot = [c for c in selected_confs if c in non_sec_available] if selected_confs else non_sec_available
    if not confs_to_plot:
        st.info("No non-SEC conferences available to compare against SEC.")
        return
    # If multiple conferences are selected, plot all conference lines + SEC on one chart.
    if len(confs_to_plot) > 1:
        fig = go.Figure()
        sec_added = False

        for conf in confs_to_plot:
            chart_df = build_chart_df(transfer_df[transfer_df["Conf"].isin([conf, "SEC"])], metrics)
            if chart_df.empty:
                continue

            fig.add_trace(go.Scatter(
                x=chart_df["metric"],
                y=chart_df["Non-SEC"],
                mode="lines+markers",
                name=conf,
            ))

            if not sec_added:
                fig.add_trace(go.Scatter(
                    x=chart_df["metric"],
                    y=chart_df["SEC"],
                    mode="lines+markers",
                    name="SEC",
                    line=dict(width=3),
                ))
                sec_added = True

        if not fig.data:
            st.info("No data for selected conferences.")
            return

        st.subheader(f"{subject} — Selected conferences vs SEC by Metric")
        _apply_line_layout(fig)
        st.plotly_chart(fig, use_container_width=True, key=f"chart_{_safe_key(subject)}_multi_conf")
        return

    # Single selected conference: keep one conference vs SEC chart.
    conf = confs_to_plot[0]
    chart_df = build_chart_df(transfer_df[transfer_df["Conf"].isin([conf, "SEC"])], metrics)
    st.subheader(f"{subject} — {conf} vs SEC by Metric")
    if chart_df.empty:
        st.info(f"No data for {conf}.")
        return

    fig = go.Figure([
        go.Scatter(x=chart_df["metric"], y=chart_df["Non-SEC"], mode="lines+markers", name=conf),
        go.Scatter(x=chart_df["metric"], y=chart_df["SEC"], mode="lines+markers", name="SEC"),
    ])
    _apply_line_layout(fig)
    st.plotly_chart(fig, use_container_width=True, key=f"chart_{_safe_key(subject)}_{_safe_key(conf)}")


def conference_average(df_in, conf_col="Conf"):
    if df_in.empty or conf_col not in df_in.columns:
        return df_in
    numeric_cols = df_in.select_dtypes(include="number").columns.tolist()
    if not numeric_cols:
        return df_in[[conf_col]].drop_duplicates()
    return df_in.groupby(conf_col, as_index=False)[numeric_cols].mean()


def style_numeric(df_in):
    def color(val):
        if isinstance(val, (int, float, np.number)):
            if val < 0: return "background-color: #ffdddd; color: #900000;"
            if val > 0: return "background-color: #ddffdd; color: #006400;"
        return ""
    numeric_cols = df_in.select_dtypes(include="number").columns
    return df_in.style.map(color, subset=numeric_cols) if len(numeric_cols) else df_in


def get_delta_only_df(delta_df):
    keep_cols = [c for c in ["full_name", "Conf_Non_SEC", "Conf"] if c in delta_df.columns]
    delta_cols = [c for c in delta_df.columns if c.endswith("_Delta")]
    return delta_df[keep_cols + delta_cols].copy() if delta_cols else delta_df.copy()


def build_change_chart_df(delta_df, metrics, change_kind="pct", aggregate=True):
    if delta_df.empty:
        return pd.DataFrame()
    valid_metrics = [m for m in metrics if m.lower() not in CHANGE_EXCLUDED_METRICS]
    if not valid_metrics:
        return pd.DataFrame()

    suffix = "_Pct_Change" if change_kind == "pct" else "_Delta"
    rows = []
    for metric in valid_metrics:
        col = f"{metric}{suffix}"
        if col not in delta_df.columns:
            continue
        value = delta_df[col].mean() if aggregate else delta_df[col].iloc[-1]
        rows.append({"metric": metric, "change": value})

    return pd.DataFrame(rows)


def _render_change_bar(chart_df, title, y_title, key):
    chart_df = chart_df.sort_values("change", ascending=False)
    max_abs = max(abs(chart_df["change"].min()), abs(chart_df["change"].max())) if not chart_df.empty else 1
    max_abs = max(max_abs, 1e-9)
    st.subheader(title)
    fig = go.Figure([
        go.Bar(
            x=chart_df["metric"],
            y=chart_df["change"],
            marker=dict(
                color=chart_df["change"],
                colorscale=CHANGE_COLOR_SCALE,
                cmin=-max_abs,
                cmax=max_abs,
            ),
            name="Change",
        )
    ])
    fig.add_hline(y=0, line_dash="dash", line_color="#666")
    fig.update_layout(
        xaxis_title="Metric",
        yaxis_title=y_title,
        xaxis_tickangle=-45,
        height=520,
        margin=dict(l=20, r=20, t=30, b=120),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True, key=_safe_key(key))


def _render_delta_pct_pair(base_df, metrics, title_prefix, key_prefix, aggregate):
    delta_chart_df = build_change_chart_df(base_df, metrics, change_kind="delta", aggregate=aggregate)
    pct_chart_df = build_change_chart_df(base_df, metrics, change_kind="pct", aggregate=aggregate)

    col1, col2 = st.columns(2)
    with col1:
        if not delta_chart_df.empty:
            _render_change_bar(
                delta_chart_df,
                f"{title_prefix} delta",
                "SEC - Non-SEC",
                f"delta_{key_prefix}",
            )
        else:
            st.info("No delta data available.")

    with col2:
        if not pct_chart_df.empty:
            _render_change_bar(
                pct_chart_df,
                f"{title_prefix} % change",
                "% change (SEC vs Non-SEC)",
                f"pct_{key_prefix}",
            )
        else:
            st.info("No % change data available.")


def plot_change_bars(delta_df, metrics, subject, is_all, selected_players):
    if delta_df.empty:
        st.info("No SEC delta data available for plotting.")
        return

    if is_all and "Conf_Non_SEC" in delta_df.columns:
        confs = sorted(delta_df["Conf_Non_SEC"].dropna().unique().tolist())
        if not confs:
            st.info("No conference delta data available for plotting.")
            return

        if len(confs) > 1:
            tabs = st.tabs(confs)
            for tab, conf in zip(tabs, confs):
                with tab:
                    _render_delta_pct_pair(
                        delta_df[delta_df["Conf_Non_SEC"] == conf],
                        metrics,
                        f"{conf} -> SEC",
                        f"conf_{conf}",
                        aggregate=True,
                    )
            return

        conf = confs[0]
        _render_delta_pct_pair(
            delta_df[delta_df["Conf_Non_SEC"] == conf],
            metrics,
            f"{conf} -> SEC",
            f"conf_{conf}",
            aggregate=True,
        )
        return

    if "full_name" in delta_df.columns and selected_players:
        if len(selected_players) > 1:
            tabs = st.tabs(selected_players)
            for tab, player in zip(tabs, selected_players):
                with tab:
                    player_df = delta_df[delta_df["full_name"] == player]
                    if player_df.empty:
                        st.info("No SEC delta data available for this player.")
                        continue
                    _render_delta_pct_pair(
                        player_df,
                        metrics,
                        player,
                        f"player_{player}",
                        aggregate=False,
                    )
            return

        player = selected_players[0]
        player_df = delta_df[delta_df["full_name"] == player]
        if player_df.empty:
            st.info("No SEC delta data available for this player.")
            return
        _render_delta_pct_pair(
            player_df,
            metrics,
            player,
            f"player_{player}",
            aggregate=False,
        )
        return

    # Fallback combined view
    _render_delta_pct_pair(
        delta_df,
        metrics,
        f"{subject} SEC metric",
        f"combined_{subject}",
        aggregate=True,
    )


def _plot_school_line_chart(transfer_df, metrics, school):
    """Single Non-SEC avg vs SEC avg line chart for a school's incoming transfers."""
    chart_df = build_chart_df(transfer_df, metrics)
    if chart_df.empty:
        st.info("No transfer data available for this school.")
        return
    fig = go.Figure([
        go.Scatter(x=chart_df["metric"], y=chart_df["Non-SEC"], mode="lines+markers", name="Pre-Transfer (avg)"),
        go.Scatter(x=chart_df["metric"], y=chart_df["SEC"], mode="lines+markers", name=f"{school} (avg)",
                   line=dict(width=3)),
    ])
    st.subheader(f"{school} — Pre-Transfer vs SEC Avg by Metric")
    _apply_line_layout(fig)
    st.plotly_chart(fig, use_container_width=True, key=f"school_line_{_safe_key(school)}")


def plot_sec_school_tabs(schools, all_transfer_df, all_delta_df, metrics):
    """Render line + bar chart tabs for each SEC school."""
    if not schools:
        st.info("No SEC schools found.")
        return
    tabs = st.tabs(schools)
    for tab, school in zip(tabs, schools):
        with tab:
            school_players = sorted(
                all_transfer_df.loc[
                    (all_transfer_df["Conf"] == "SEC") & (all_transfer_df["Tm"] == school),
                    "full_name",
                ].dropna().unique().tolist()
            )
            if not school_players:
                st.info(f"No transfer data for {school}.")
                continue
            school_transfer = all_transfer_df[all_transfer_df["full_name"].isin(school_players)]
            school_delta = all_delta_df[all_delta_df["full_name"].isin(school_players)]
            _plot_school_line_chart(school_transfer, metrics, school)
            _render_delta_pct_pair(
                school_delta, metrics, school, f"school_{_safe_key(school)}", aggregate=True
            )


# --- App ---
st.title("Basketball Transfer Dashboard :bar_chart::basketball:")
with st.expander("About this Dashboard"):
    st.header("About the Dataset")
    st.write("This dashboard analyzes basketball transfer data, including player performance metrics such as SRS "
             "and SOS. The dataset includes information on player transfers, their previous and new teams, and "
             "their performance statistics.")
    st.dataframe(df.head(10))

filter_mode = st.radio(
    "Filter by",
    options=["Conference", "SEC school", "Player"],
    index=0,
    horizontal=True,
)

# --- Sidebar ---
conference_options = sorted(df["Conf"].dropna().unique().tolist())
non_sec_only = sectransfer_df[sectransfer_df["Conf"] != "SEC"]
all_player_options = sorted(non_sec_only["full_name"].dropna().unique().tolist())
sec_school_options = sorted(
    sectransfer_df.loc[sectransfer_df["Conf"] == "SEC", "Tm"].dropna().unique().tolist()
)

selected_confs = []
selected_players = []
conf_filter_active = False
selected_sec_school = None

st.sidebar.header("Filters")

if filter_mode == "Conference":
    def _sync_selected_confs_to_players():
        selected = st.session_state.get("selected_players_conf", [])
        if not selected:
            return
        player_confs = sorted(
            non_sec_only.loc[non_sec_only["full_name"].isin(selected), "Conf"]
            .dropna()
            .unique()
            .tolist()
        )
        st.session_state["selected_confs"] = player_confs

    selected_confs = st.sidebar.multiselect(
        "Select conference(s)",
        options=conference_options,
        default=conference_options,
        key="selected_confs",
    )

    available_players = (
        sorted(non_sec_only.loc[non_sec_only["Conf"].isin(selected_confs), "full_name"].dropna().unique().tolist())
        if selected_confs else []
    )
    selected_players = st.sidebar.multiselect(
        "Select player(s) from selected conference(s) (optional)",
        options=available_players,
        default=[],
        key="selected_players_conf",
        on_change=_sync_selected_confs_to_players,
    )

    if selected_players:
        players_in_scope = selected_players
    else:
        players_in_scope = available_players
    conf_filter_active = bool(selected_confs)

elif filter_mode == "SEC school":
    selected_sec_school = st.sidebar.selectbox(
        "Select SEC school",
        options=["(All SEC schools)"] + sec_school_options,
        index=0,
    )

    if selected_sec_school == "(All SEC schools)":
        selected_players = []
        players_in_scope = all_player_options
    else:
        school_players = sorted(
            sectransfer_df.loc[
                (sectransfer_df["Conf"] == "SEC") & (sectransfer_df["Tm"] == selected_sec_school),
                "full_name",
            ]
            .dropna()
            .unique()
            .tolist()
        )
        selected_players = st.sidebar.multiselect(
            f"Select player(s) from {selected_sec_school} (optional)",
            options=school_players,
            default=[],
            key="selected_players_school",
        )
        players_in_scope = selected_players or school_players
        st.sidebar.caption(f"Showing players who transferred to {selected_sec_school}.")
    conf_filter_active = False

else:  # Player
    selected_players = st.sidebar.multiselect("Select player(s)", options=all_player_options, default=[])
    st.sidebar.caption("Conference filter is disabled while player selection is active.")

    players_in_scope = selected_players or all_player_options
    conf_filter_active = False

if not players_in_scope:
    if filter_mode == "Conference" and not selected_confs:
        st.warning("Select at least one conference to populate player options.")
    elif filter_mode == "SEC school":
        st.warning("No players found for the selected SEC school.")
    else:
        st.warning("No players found for the current filter selection.")
    st.stop()

# sectransfer_conf: 1 matching non-SEC row per player + their SEC row
if conf_filter_active:
    matched_non_sec = (
        sectransfer_df[sectransfer_df["full_name"].isin(players_in_scope) & sectransfer_df["Conf"].isin(selected_confs)]
        .sort_values("Year").groupby("full_name").tail(1)
    )
    sec_rows = sectransfer_df[sectransfer_df["full_name"].isin(players_in_scope) & (sectransfer_df["Conf"] == "SEC")]
    sectransfer_conf = pd.concat([matched_non_sec, sec_rows]).sort_values(["full_name", "Year"])
else:
    sectransfer_conf = sectransfer_df[sectransfer_df["full_name"].isin(players_in_scope)].copy()

df_conf = df[df["full_name"].isin(players_in_scope)].copy()

# --- Filter data ---
is_all = len(selected_players) == 0
subject = (
    f"{selected_sec_school} transfers"
    if selected_sec_school and selected_sec_school != "(All SEC schools)"
    else ("All players" if is_all else ", ".join(selected_players))
)
# Show graphs when conference filter is set OR when one/more players are explicitly selected.
# Keeps no-conference/all-players view as dataframe-only.
show_conf_graphs = len(selected_confs) > 0 or len(selected_players) > 0
player_data = df_conf if is_all else df_conf[df_conf["full_name"].isin(selected_players)]
transfer_data = sectransfer_conf if is_all else sectransfer_conf[sectransfer_conf["full_name"].isin(selected_players)]
delta_data = sec_deltas_df.copy() if is_all else sec_deltas_df[sec_deltas_df["full_name"].isin(selected_players)]
if "Conf_Non_SEC" in delta_data.columns and conf_filter_active:
    delta_data = delta_data[delta_data["Conf_Non_SEC"].isin(selected_confs)]

# --- Display ---
if is_all:
    avg_confs = selected_confs + ["SEC"] if selected_confs else player_data["Conf"].dropna().unique().tolist()
    st.subheader("Conference averages (all players)")
    st.dataframe(conference_average(player_data[player_data["Conf"].isin(avg_confs)], "Conf"), use_container_width=True)
    st.subheader("Transfer rows (conference averages)")
    st.dataframe(conference_average(transfer_data, "Conf"), use_container_width=True)
    if show_conf_graphs:
        plot_charts(transfer_data, playerStats, selected_confs, subject, selected_players, is_all)
    st.subheader("SEC deltas (conference averages)")
    agg_col = "Conf_Non_SEC" if "Conf_Non_SEC" in delta_data.columns else "Conf"
    delta_only_data = get_delta_only_df(delta_data)
    st.dataframe(style_numeric(conference_average(delta_only_data, agg_col)), use_container_width=True)
    if show_conf_graphs:
        plot_change_bars(delta_data, playerStats, subject, is_all, selected_players)
else:
    st.subheader(f"Stats until SEC transfer for {subject}")
    st.dataframe(player_data, use_container_width=True)
    st.subheader("Transfer rows")
    st.dataframe(transfer_data, use_container_width=True)
    if show_conf_graphs:
        plot_charts(transfer_data, playerStats, selected_confs, subject, selected_players, is_all)
    st.subheader("SEC deltas")
    delta_only_data = get_delta_only_df(delta_data)
    st.dataframe(style_numeric(delta_only_data), use_container_width=True)
    if show_conf_graphs:
        plot_change_bars(delta_data, playerStats, subject, is_all, selected_players)

# --- SEC school charts (tabbed by school) ---
if filter_mode == "SEC school":
    st.markdown("---")
    st.subheader("Charts by SEC School")
    if selected_sec_school == "(All SEC schools)":
        plot_sec_school_tabs(sec_school_options, sectransfer_df, sec_deltas_df, playerStats)
    else:
        # All players who transferred to this school (regardless of optional player sub-filter)
        school_all_players = sorted(
            sectransfer_df.loc[
                (sectransfer_df["Conf"] == "SEC") & (sectransfer_df["Tm"] == selected_sec_school),
                "full_name",
            ].dropna().unique().tolist()
        )
        if school_all_players:
            school_transfer = sectransfer_df[sectransfer_df["full_name"].isin(school_all_players)]
            school_delta = sec_deltas_df[sec_deltas_df["full_name"].isin(school_all_players)]
            _plot_school_line_chart(school_transfer, playerStats, selected_sec_school)
            _render_delta_pct_pair(
                school_delta, playerStats, selected_sec_school,
                f"school_{_safe_key(selected_sec_school)}", aggregate=True,
            )
        else:
            st.info(f"No transfer data found for {selected_sec_school}.")
