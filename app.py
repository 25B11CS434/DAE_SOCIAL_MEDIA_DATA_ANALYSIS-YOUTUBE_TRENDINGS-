"""YouTube Trending Analytics - cleaning + dashboard in ONE file.
Run:  python app.py        (or:  python -m streamlit run app.py)
Every run cleans youtube_large_dataset.xlsx and saves cleaned_youtube_data.csv / .xlsx
in this same folder, then opens the dashboard.
"""
#python -m streamlit run DAEN/app.py

import subprocess, sys
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit.runtime.scriptrunner import get_script_run_ctx

# `python app.py` -> start Streamlit automatically with the light theme
if get_script_run_ctx(suppress_warning=True) is None:
    subprocess.run([sys.executable, "-m", "streamlit", "run", __file__,
                    "--theme.base=light", "--theme.primaryColor=#2563eb",
                    "--theme.backgroundColor=#f5f7fb", "--theme.secondaryBackgroundColor=#ffffff",
                    "--theme.textColor=#1e293b"])
    sys.exit()

st.set_page_config(page_title="YouTube Trending Analytics", page_icon="📺", layout="wide")

# =============== PART 1: DATA CLEANING ===============
FOLDER = Path(__file__).parent
RAW_FILE = FOLDER / "youtube_large_dataset.xlsx"
NUM_COLS = ["days_to_trend", "duration_min", "views", "likes", "dislikes", "comment_count"]
DATE_COLS = ["publish_date", "trending_date"]


def clean(raw_path=RAW_FILE, save=True):
    df = pd.read_excel(raw_path, sheet_name="Data")
    log = {"rows_raw": len(df), "cols_raw": df.shape[1]}

    # 1. standardise column names, drop empty / unnamed columns (e.g. "Column1")
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
    df = df.dropna(axis=1, how="all")
    df = df.loc[:, ~df.columns.str.startswith("unnamed")]

    # 2. remove duplicates
    df = df.drop_duplicates().drop_duplicates(subset="video_id")

    # 3. fix data types
    for c in NUM_COLS:
        df[c] = pd.to_numeric(df[c], errors="coerce")
        df.loc[df[c] < 0, c] = np.nan                      # negative counts are invalid
    for c in DATE_COLS:
        df[c] = pd.to_datetime(df[c], errors="coerce")

    # 4. handle missing values
    log["missing_before"] = int(df.isna().sum().sum())
    for c in NUM_COLS:
        df[c] = df[c].fillna(df[c].median())                # numbers -> median
    text_cols = df.select_dtypes(exclude=["number", "datetime"]).columns
    for c in text_cols:
        df[c] = df[c].astype(str).str.strip().replace({"": np.nan, "nan": np.nan}).fillna("Unknown")
    df["channel_tier"] = df["channel_tier"].str.lower()
    df = df.dropna(subset=DATE_COLS)                        # dates cannot be guessed
    df = df[df["views"] > 0]
    log["missing_after"] = int(df.isna().sum().sum())

    # 5. logical fixes: likes/comments can never exceed views; trending can't precede publish
    for c in ["likes", "dislikes", "comment_count"]:
        df[c] = df[c].clip(upper=df["views"])
    df = df[df["trending_date"] >= df["publish_date"]]

    # 6. new columns used by the dashboard
    df["engagement_rate"] = ((df["likes"] + df["comment_count"]) / df["views"] * 100).round(2)
    df["like_rate"] = (df["likes"] / df["views"] * 100).round(2)
    df["log10_views"] = np.log10(df["views"]).round(3)
    df["trend_month"] = df["trending_date"].dt.to_period("M").dt.to_timestamp()

    df = df.reset_index(drop=True)
    log["rows_clean"] = len(df)

    if save:                                                # cleaned file in the same folder
        df.to_csv(FOLDER / "cleaned_youtube_data.csv", index=False)
        df.to_excel(FOLDER / "cleaned_youtube_data.xlsx", index=False)
    return df, log


# =============== PART 2: DASHBOARD ===============
NAVY, BLUE, ORANGE, SLATE = "#0f2a5c", "#2563eb", "#f97316", "#475569"
TIERS = ["Small", "Mid", "Large", "Mega"]
TIER_COLORS = {"Small": "#93c5fd", "Mid": "#3b82f6", "Large": "#1e3a8a", "Mega": ORANGE}

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, .stApp {font-family:'Inter',sans-serif;}
.stApp {background:#f5f7fb;}
.block-container {padding-top:1.4rem; max-width:1300px;}
section[data-testid="stSidebar"] {background:#ffffff; border-right:1px solid #e2e8f0;}
.hero {background:linear-gradient(120deg,#0f2a5c,#1e40af); border-radius:16px;
       padding:26px 32px; margin-bottom:20px;}
.hero h1 {color:#fff !important; font-size:1.9rem; font-weight:700; margin:0; padding:0;}
.hero p {color:#bfdbfe !important; margin:6px 0 0; font-size:.95rem;}
.steps {margin-top:14px;}
.steps span {display:inline-block; background:rgba(255,255,255,.14); color:#fff; padding:4px 12px;
             border-radius:999px; font-size:.72rem; font-weight:600; margin:0 6px 4px 0;}
.kpi, .ins {background:#fff; border:1px solid #e2e8f0; border-left:4px solid #2563eb;
            border-radius:12px; padding:14px 18px;}
.ins {border-left-color:#f97316;}
.kpi .l, .ins .l {font-size:.72rem; color:#64748b; text-transform:uppercase; letter-spacing:.06em; font-weight:600;}
.kpi .v {font-size:1.65rem; font-weight:700; color:#0f2a5c; line-height:1.3;}
.ins .v {font-size:1.25rem; font-weight:700; color:#0f2a5c; line-height:1.4;}
.ins .s {font-size:.8rem; color:#64748b;}
div[data-testid="stVerticalBlockBorderWrapper"] {background:#fff; border-radius:14px;}
.stTabs [data-baseweb="tab"] {font-weight:600; font-size:.95rem;}
.foot {text-align:center; color:#94a3b8; font-size:.78rem; margin-top:28px;}
</style>""", unsafe_allow_html=True)


@st.cache_data
def load():
    df, _ = clean()                       # cleans the raw file AND saves the cleaned files
    df["Channel type"] = df["channel_tier"].str.title()
    return df


def style(fig, title, h=360):
    fig.update_layout(title=dict(text=title, font=dict(size=15, color=NAVY)), template="plotly_white",
                      height=h, margin=dict(l=10, r=10, t=55, b=10), legend_title_text="",
                      font=dict(family="Inter, sans-serif", color=SLATE),
                      paper_bgcolor="#ffffff", plot_bgcolor="#ffffff")
    fig.update_xaxes(gridcolor="#eef2f7")
    fig.update_yaxes(gridcolor="#eef2f7")
    return fig


def show(fig):
    with st.container(border=True):
        st.plotly_chart(fig)


df = load()

# ---------- sidebar: filters and sorting ----------
st.sidebar.subheader("Filters")
search = st.sidebar.text_input("Search title or channel")
tiers = st.sidebar.multiselect("Channel type (tier)", TIERS, default=TIERS)
cats = st.sidebar.multiselect("Category", sorted(df.category.unique()))
countries = st.sidebar.multiselect("Country", sorted(df.country.unique()))
min_views = st.sidebar.number_input("Min views (reach)", 0, int(df.views.max()), 0, step=1000)
max_views = st.sidebar.number_input("Max views (reach)", 0, int(df.views.max()), int(df.views.max()), step=1000)

st.sidebar.subheader("Sort data")
SORT_OPTIONS = {"Views": "views", "Likes": "likes", "Comments": "comment_count",
                "Engagement rate": "engagement_rate", "Duration (min)": "duration_min",
                "Days to trend": "days_to_trend"}
sort_col = SORT_OPTIONS[st.sidebar.selectbox("Sort by", list(SORT_OPTIONS))]
ascending = st.sidebar.radio("Order", ["Highest first", "Lowest first"]) == "Lowest first"
top_n = st.sidebar.number_input("Show top N rows", 5, 1000, 20, step=5)

# ---------- apply filters ----------
f = df[df["Channel type"].isin(tiers) & df.views.between(min_views, max_views)]
if cats:
    f = f[f.category.isin(cats)]
if countries:
    f = f[f.country.isin(countries)]
if search:
    f = f[f.title.str.contains(search, case=False) | f.channel_title.str.contains(search, case=False)]

# ---------- header ----------
st.markdown("""
<div class="hero">
  <h1>YouTube Trending Analytics</h1>
  <p>Social Media Data Analysis System: explore what drives videos to trend by channel type, views and reach.</p>
  <div class="steps"><span>LOAD</span><span>CLEAN</span><span>TRANSFORM</span><span>FILTER</span>
  <span>VISUALIZE</span><span>INSIGHTS</span></div>
</div>""", unsafe_allow_html=True)

if f.empty:
    st.warning("No videos match these filters. Please widen them.")
    st.stop()

# ---------- KPI cards ----------
kpis = [("Videos", f"{len(f):,}"), ("Total views", f"{f.views.sum()/1e6:,.1f}M"),
        ("Avg views", f"{f.views.mean():,.0f}"), ("Avg likes", f"{f.likes.mean():,.0f}"),
        ("Avg engagement", f"{f.engagement_rate.mean():.2f}%")]
for col, (name, val) in zip(st.columns(5), kpis):
    col.markdown(f'<div class="kpi"><div class="l">{name}</div><div class="v">{val}</div></div>',
                 unsafe_allow_html=True)
st.write("")

# ---------- insight cards ----------
bar = f.groupby("category", as_index=False)["views"].sum().sort_values("views")
tier_eng = f.groupby("Channel type").engagement_rate.mean()
country_views = f.groupby("country").views.sum()
insights = [("Top category", bar.iloc[-1]["category"], "Most total views"),
            ("Best-engaging channel type", tier_eng.idxmax(), f"{tier_eng.max():.2f}% average engagement"),
            ("Top country", country_views.idxmax(), f"{country_views.max()/1e6:,.1f}M total views")]
for col, (name, val, sub) in zip(st.columns(3), insights):
    col.markdown(f'<div class="ins"><div class="l">{name}</div><div class="v">{val}</div>'
                 f'<div class="s">{sub}</div></div>', unsafe_allow_html=True)
st.write("")

# ---------- tabs ----------
tab1, tab2, tab3 = st.tabs(["Overview", "Distribution and relationships", "Sorted data"])

with tab1:
    c1, c2 = st.columns(2)
    with c1:
        show(style(px.bar(bar, x="views", y="category", orientation="h",
                          color_discrete_sequence=[BLUE], labels={"views": "Total views", "category": ""}),
                   "Total views by category"))
    with c2:
        fig = px.pie(f, names="Channel type", color="Channel type", hole=0.5,
                     color_discrete_map=TIER_COLORS, category_orders={"Channel type": TIERS})
        fig.update_traces(textinfo="percent", marker=dict(line=dict(color="#ffffff", width=2)))
        show(style(fig, "Videos by channel type"))
    line = f.groupby("trend_month", as_index=False)["views"].sum()
    show(style(px.line(line, x="trend_month", y="views", markers=True, color_discrete_sequence=[BLUE],
                       labels={"trend_month": "Month", "views": "Total views"}),
               "Monthly views of trending videos", h=330))

with tab2:
    c3, c4 = st.columns(2)
    with c3:
        show(style(px.histogram(f, x="log10_views", nbins=40, color_discrete_sequence=[BLUE],
                                labels={"log10_views": "Views (log10 scale)"}),
                   "Distribution of views"))
    with c4:
        fig = px.box(f, x="Channel type", y="engagement_rate", color="Channel type", points=False,
                     color_discrete_map=TIER_COLORS, category_orders={"Channel type": TIERS},
                     labels={"engagement_rate": "Engagement rate (%)", "Channel type": ""})
        fig.update_layout(showlegend=False)
        show(style(fig, "Engagement rate by channel type"))
    sample = f.sample(min(len(f), 3000), random_state=1)
    show(style(px.scatter(sample, x="views", y="likes", color="Channel type", log_x=True, log_y=True,
                          opacity=0.65, hover_name="title", color_discrete_map=TIER_COLORS,
                          category_orders={"Channel type": TIERS}),
               "Views vs likes (log scale)", h=400))

with tab3:
    st.caption(f"Top {int(top_n)} videos, sorted by {sort_col.replace('_', ' ')} "
               f"({'lowest' if ascending else 'highest'} first)")
    table = f.sort_values(sort_col, ascending=ascending).head(int(top_n))
    st.dataframe(table[["video_id", "title", "channel_title", "Channel type", "category", "country",
                        "views", "likes", "comment_count", "engagement_rate"]],
                 hide_index=True,
                 column_config={"video_id": "Video ID", "title": "Title", "channel_title": "Channel",
                                "category": "Category", "country": "Country",
                                "views": st.column_config.NumberColumn("Views", format="%d"),
                                "likes": st.column_config.NumberColumn("Likes", format="%d"),
                                "comment_count": st.column_config.NumberColumn("Comments", format="%d"),
                                "engagement_rate": st.column_config.NumberColumn("Engagement (%)", format="%.2f")})
    st.download_button("Download filtered data (CSV)", f.drop(columns="Channel type").to_csv(index=False),
                       "filtered_data.csv", mime="text/csv")

st.markdown('<div class="foot">DAE Review-2 · Social Media Data Analysis System</div>', unsafe_allow_html=True)
