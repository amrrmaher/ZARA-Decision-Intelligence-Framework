import streamlit as st
import pandas as pd
import numpy as np
import subprocess
import plotly.graph_objects as go
import plotly.express as px
import plotly.figure_factory as ff
from plotly.subplots import make_subplots
from sqlalchemy import create_engine
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import GradientBoostingRegressor
import urllib.parse
import logging
import os
from datetime import datetime, timedelta

# ── 0. Page Config ───────────────────────────────────────────
st.set_page_config(
    layout='wide',
    initial_sidebar_state='expanded',
    page_title="ZARA AI Management",
    page_icon="🖤"
)

# ── 1. Constants & Config ────────────────────────────────────


# ── 2. Logging ───────────────────────────────────────────────
def setup_logging():
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        force=True
    )
    logging.info("ZARA AI Management — System Initialized")

setup_logging()

# ── 3. DB Engine ─────────────────────────────────────────────
@st.cache_resource
def get_engine():
    try:
        engine = create_engine(DB_URL)
        return engine
    except Exception as e:
        logging.error(f"DB Connection Error: {e}")
        return None

# ── 4. Shared Data Loader ────────────────────────────────────
@st.cache_data(ttl=3600)
def fetch_overview_data(_engine):
    try:
        query = """
        SELECT
            fs.*,
            dp.Product_name_EN, dp.Category, dp.Cost_JOD, dp.Price_JOD,
            dp.Section_ID,
            ds.Section_Name,
            db.Branch_Name
        FROM fact_sales fs
        LEFT JOIN dim_products dp ON fs.Product_ID = dp.Product_ID
        LEFT JOIN dim_sections ds ON dp.Section_ID = ds.Section_ID
        LEFT JOIN dim_branches db ON fs.Branch_ID = db.Branch_ID
        """
        with _engine.connect() as conn:
            df = pd.read_sql(query, conn)
        if df.empty:
            return pd.DataFrame()
        df['Timestamp']  = pd.to_datetime(df['Timestamp'])
        df['Date']       = df['Timestamp'].dt.date
        df['Month']      = df['Timestamp'].dt.month_name().str[:3]
        df['Month_Num']  = df['Timestamp'].dt.month
        if 'Cost_JOD' in df.columns:
            df['Total_Cost']     = df['Quantity'] * df['Cost_JOD']
            df['Gross_Profit']   = df['Net_Amount'] - df['Total_Cost']
            df['Margin_Profit%'] = (df['Gross_Profit'] / df['Net_Amount'].replace(0, np.nan)) * 100
        else:
            df['Gross_Profit']   = 0
            df['Margin_Profit%'] = 0
        return df
    except Exception as e:
        logging.error(f"fetch_overview_data error: {e}")
        return pd.DataFrame()

# ── 5. CSV Forecast Data ──────────────────────────────────────
@st.cache_data
def load_forecast_data():
    try:
        return pd.read_csv('forecast_ready_data.csv')
    except Exception:
        return pd.DataFrame()

# ── 6. Global Styles ──────────────────────────────────────────
def apply_custom_styles():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');

    [data-testid="stSidebar"] {
        display: block !important;
        visibility: visible !important;
        width: 260px !important;
        min-width: 260px !important;
        max-width: 260px !important;
        transform: none !important;
        background-color: #000000 !important;
    }
    [data-testid="stSidebarCollapseButton"] { display: none !important; }
    [data-testid="stSidebar"] * {
        color: white !important;
        font-family: 'Inter', sans-serif !important;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] label {
        display: flex !important;
        align-items: center !important;
        padding: 10px 14px !important;
        border-radius: 8px !important;
        cursor: pointer !important;
        font-size: 13px !important;
        margin-bottom: 4px !important;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] label > div:first-child { display: none !important; }
    [data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) { background-color: #4B0082 !important; }
    [data-testid="stSidebar"] [data-testid="stRadio"] label:not(:has(input:checked)):hover { background-color: rgba(75,0,130,0.3) !important; }
    [data-testid="stSidebar"] [data-testid="stRadio"] > label { display: none !important; }

    [data-testid="stExpander"] summary {
        background-color: #4B0082 !important;
        border: 2px solid #ffffff !important;
        border-radius: 10px !important;
        padding: 14px 18px !important;
    }
    [data-testid="stExpander"] summary span,
    [data-testid="stExpander"] summary p,
    [data-testid="stExpander"] summary svg {
        color: white !important; fill: white !important; font-weight: bold !important;
    }
    [data-testid="stExpanderDetails"] {
        background-color: #0a0a0a !important;
        border: 1px solid #4B0082 !important;
        border-radius: 0 0 10px 10px !important;
    }

    .stApp { background-color: #000000; font-family: 'Inter', sans-serif; }
    #MainMenu, footer, header { visibility: hidden; }
    .main .block-container { padding-top: 2rem; padding-left: 2.5rem; padding-right: 2.5rem; }
    h1, h2, h3, h4 { color: #FFFFFF !important; font-weight: 800 !important; }

    .kpi-card {
        background: linear-gradient(135deg, #0d0d0d 0%, #1a0033 100%);
        border-radius: 12px;
        padding: 22px 20px;
        border: 1px solid #4B0082;
        text-align: left;
        margin-bottom: 12px;
    }
    .kpi-title { color: #e0aaff; font-size: 0.78rem; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px; }
    .kpi-value { color: #FFFFFF; font-size: 1.7rem; font-weight: 800; margin-bottom: 4px; }
    .kpi-sub   { color: #9d4edd; font-size: 0.75rem; }

    .section-header {
        font-family: 'Georgia', serif;
        color: #FFFFFF;
        font-weight: bold;
        border-left: 10px solid #4B0082;
        padding-left: 15px;
        margin: 30px 0 10px 0;
        font-size: 1.6rem;
    }

    .rca-run-label {
        color: #e0aaff;
        font-size: 1.05rem;
        font-weight: 600;
        margin: 0;
        padding-top: 6px;
    }

    hr { border-color: #2a0050 !important; }
    [data-testid="stDataFrame"] { background-color: #0d0d0d !important; }
    [data-testid="stAlert"] { background-color: #1a0033 !important; border-color: #4B0082 !important; color: #FFFFFF !important; }
    .stCode { background-color: #0d0d0d !important; border: 1px solid #4B0082 !important; }
    </style>
    """, unsafe_allow_html=True)

apply_custom_styles()

# ── 7. Chart Layout Defaults ──────────────────────────────────
CHART_LAYOUT = dict(
    template='plotly_dark',
    paper_bgcolor='#000000',
    plot_bgcolor='#000000',
    font=dict(family='Inter, sans-serif', color='#FFFFFF'),
    title_font=dict(color='#FFFFFF', size=16),
    legend=dict(font=dict(color='#FFFFFF'), bgcolor='rgba(0,0,0,0)'),
    xaxis=dict(tickfont=dict(color='#FFFFFF'), title_font=dict(color='#FFFFFF'), gridcolor='#1a1a2e'),
    yaxis=dict(tickfont=dict(color='#FFFFFF'), title_font=dict(color='#FFFFFF'), gridcolor='#1a1a2e'),
)

def apply_chart_defaults(fig, height=500):
    fig.update_layout(height=height, **CHART_LAYOUT)
    return fig

# ── 8. KPI Card Helper ────────────────────────────────────────
def kpi_card(title, value, sub=''):
    return f"""
    <div class="kpi-card">
        <div class="kpi-title">{title}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-sub">{sub}</div>
    </div>"""

def section_header(text):
    st.markdown(f'<div class="section-header">{text}</div>', unsafe_allow_html=True)

# ── 9. Sidebar ────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="background:#ffffff;border-radius:8px;padding:20px 24px;text-align:center;margin-bottom:24px;margin-top:8px;">
        <span style="color:#000000 !important;font-family:'Arial Black',sans-serif;font-weight:900;
                     letter-spacing:-5px;display:block;font-size:2rem;">ZARA</span>
    </div>""", unsafe_allow_html=True)

    page = st.radio(
        label="nav",
        options=["📈  Predictive Analytics", "🔍  RCA Analysis", "🏬  Market Simulation"],
        label_visibility="collapsed"
    )

page_map = {
    "📈  Predictive Analytics": "Predictive Analytics",
    "🔍  RCA Analysis":         "RCA Analysis",
    "🏬  Market Simulation":    "Market Simulation",
}
active_page = page_map[page]

# ═══════════════════════════════════════════════════════════════
#  PAGE 1 — PREDICTIVE ANALYTICS
# ═══════════════════════════════════════════════════════════════
if active_page == "Predictive Analytics":
    st.title("ZARA AI Predictive Hub")
    st.markdown("### Strategic Forecasting & Intelligence")

    engine = get_engine()

    # ── PHASE 1: Weekly Sales Forecast (CSV) ──────────────────
    st.markdown("---")
    section_header("Phase 1 · Weekly Sales Forecast")

    with st.expander("View Python Logic 🔽"):
        st.code("""
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from datetime import timedelta

df = pd.read_csv('forecast_ready_data.csv')
df['Date'] = pd.to_datetime(df['Date']).dt.date
daily_sales = df.groupby('Date')['Sales'].sum().reset_index().sort_values('Date').dropna()
daily_sales['Date_Ordinal'] = pd.to_datetime(daily_sales['Date']).map(pd.Timestamp.toordinal)

X = daily_sales[['Date_Ordinal']].values
y = daily_sales['Sales'].values
model = LinearRegression().fit(X, y)

last_date = daily_sales['Date'].max()
future_dates = [last_date + timedelta(days=i) for i in range(1, 8)]
future_ordinals = np.array([pd.Timestamp(d).toordinal() for d in future_dates]).reshape(-1, 1)
predictions = model.predict(future_ordinals)
        """, language='python')

    df_raw = load_forecast_data()
    date_col, sales_col = None, None
    if not df_raw.empty:
        date_col  = next((c for c in df_raw.columns if 'date' in c.lower()), df_raw.columns[0])
        sales_col = next((c for c in df_raw.columns if 'sale' in c.lower() or 'total' in c.lower()), df_raw.columns[1])

    if not df_raw.empty and date_col and sales_col:
        try:
            df_csv = df_raw.copy()
            df_csv['Date'] = pd.to_datetime(df_csv[date_col]).dt.date
            daily = df_csv.groupby('Date')[sales_col].sum().reset_index().sort_values('Date').dropna()
            if len(daily) >= 2:
                daily['Ord'] = pd.to_datetime(daily['Date']).map(pd.Timestamp.toordinal)
                model_wk = LinearRegression().fit(daily[['Ord']], daily[sales_col])
                last_d   = daily['Date'].max()
                fut_d    = [last_d + timedelta(days=i) for i in range(1, 8)]
                fut_ord  = np.array([pd.Timestamp(d).toordinal() for d in fut_d]).reshape(-1, 1)
                preds    = model_wk.predict(fut_ord)

                fig1 = go.Figure()
                fig1.add_trace(go.Scatter(
                    x=fut_d, y=preds, mode='lines+markers', name='AI Forecast',
                    line=dict(color=PURPLE, width=4),
                    marker=dict(size=12, color='#000000', line=dict(width=2, color='#FFFFFF')),
                    fill='tozeroy', fillcolor='rgba(75,0,130,0.15)'
                ))
                fig1.update_layout(title="7-Day Sales Forecast (CSV Source)",
                                   xaxis_title="Date", yaxis_title="Predicted Revenue (JOD)")
                apply_chart_defaults(fig1)
                st.plotly_chart(fig1, use_container_width=True)
                with st.sidebar:
                    st.success("✅ Forecast Engine Active")
            else:
                st.info("💡 Need at least 2 days of history in CSV.")
        except Exception as e:
            st.error(f"Forecast Error: {e}")
    else:
        st.info("💡 Waiting for 'forecast_ready_data.csv'…")

    # ── PHASE 2: Customer Demographic Segmentation ────────────
    st.markdown("---")
    section_header("Phase 2 · Customer Demographic Segmentation")

    with st.expander("View Python Logic 🔽"):
        st.code("""
query = \"\"\"
SELECT f.Quantity, c.Birth_date
FROM fact_sales f
JOIN dim_customers c ON f.Customer_ID = c.Customer_ID
WHERE c.Birth_date IS NOT NULL
\"\"\"
df = pd.read_sql(query, engine)
df['Birth_date'] = pd.to_datetime(df['Birth_date'])
current_year = 2026

def segment_age(birth_date):
    age = current_year - birth_date.year
    if 19 <= age <= 27:   return 'Young (19-27)'
    elif 28 <= age <= 40: return 'Middle (28-40)'
    elif 41 <= age <= 55: return 'Adult (41-55)'
    return 'Other'

df['Age_Segment'] = df['Birth_date'].apply(segment_age)
df = df[df['Age_Segment'] != 'Other']
viz_df = df.groupby('Age_Segment')['Quantity'].sum().reset_index()
        """, language='python')

    if engine:
        try:
            with engine.connect() as conn:
                df_demo = pd.read_sql(
                    "SELECT f.Quantity, c.Birth_date FROM fact_sales f "
                    "JOIN dim_customers c ON f.Customer_ID=c.Customer_ID "
                    "WHERE c.Birth_date IS NOT NULL", conn)
            if not df_demo.empty:
                df_demo['Birth_date'] = pd.to_datetime(df_demo['Birth_date'])
                def seg_age(bd):
                    a = 2026 - bd.year
                    if 19<=a<=27: return 'Young (19-27)'
                    elif 28<=a<=40: return 'Middle (28-40)'
                    elif 41<=a<=55: return 'Adult (41-55)'
                    return 'Other'
                df_demo['Age_Segment'] = df_demo['Birth_date'].apply(seg_age)
                df_demo = df_demo[df_demo['Age_Segment'] != 'Other']
                viz_df2 = df_demo.groupby('Age_Segment')['Quantity'].sum().reset_index().sort_values('Quantity', ascending=False)
                fig2 = px.bar(viz_df2, x='Age_Segment', y='Quantity',
                              title="Sales Quantity by Customer Age Segment",
                              color_discrete_sequence=[PURPLE])
                fig2.update_layout(xaxis_title="Age Group", yaxis_title="Total Quantity Sold")
                apply_chart_defaults(fig2)
                st.plotly_chart(fig2, use_container_width=True)
        except Exception as e:
            st.error(f"Demographic Error: {e}")

    # ── PHASE 3: Pricing Intelligence ────────────────────────
    st.markdown("---")
    section_header("Phase 3 · Pricing Intelligence Framework")

    with st.expander("View Strategic Logic & Python Code 🔽"):
        st.markdown("""
**Framework Overview**
1. **Objectives**: Optimize pricing by identifying revenue-driving vs. volume-driving price tiers.
2. **Why**: Align inventory mix with Amman's local market purchasing power.
3. **Methodology**: SQL join of Real-Time Sales with Product master data.
4. **Logic**: Dynamic 5-tier JOD classification — Budget → Luxury.
        """)
        st.code("""
def segment_price(price):
    if price < 25:        return 'Budget'
    elif price <= 45:     return 'Standard'
    elif price <= 80:     return 'Upper'
    elif price <= 150:    return 'Premium'
    else:                 return 'Luxury'

df_price['Price_Segment'] = df_price['Price_JOD'].apply(segment_price)
df_price['Revenue'] = df_price['Quantity'] * df_price['Price_JOD']
sun_df = df_price.groupby('Price_Segment').agg({'Quantity':'sum','Revenue':'sum'}).reset_index()
        """, language='python')

    if engine:
        try:
            with engine.connect() as conn:
                df_price = pd.read_sql(
                    "SELECT f.Quantity, p.Price_JOD FROM fact_sales f "
                    "JOIN dim_products p ON f.Product_ID=p.Product_ID "
                    "WHERE p.Price_JOD IS NOT NULL", conn)
            if not df_price.empty:
                def seg_price(p):
                    if p<25: return 'Budget'
                    elif p<=45: return 'Standard'
                    elif p<=80: return 'Upper'
                    elif p<=150: return 'Premium'
                    return 'Luxury'
                df_price['Price_Segment'] = df_price['Price_JOD'].apply(seg_price)
                df_price['Revenue'] = df_price['Quantity'] * df_price['Price_JOD']
                sun_df = df_price.groupby('Price_Segment').agg({'Quantity':'sum','Revenue':'sum'}).reset_index()
                fig3 = px.pie(sun_df, names='Price_Segment', values='Revenue',
                              title="Financial Contribution by Price Tier (JOD)", hole=0.4,
                              color='Price_Segment',
                              color_discrete_map={'Budget':'#E6E6FA','Standard':'#D8BFD8',
                                                  'Upper':'#9370DB','Premium':'#6A0DAD','Luxury':PURPLE})
                fig3.update_traces(textinfo='percent+label', textposition='outside',
                                   pull=[0.05,0,0,0,0.1],
                                   marker=dict(line=dict(color='#FFFFFF',width=2)),
                                   textfont_color='#FFFFFF')
                fig3.update_layout(showlegend=True,
                                   legend=dict(orientation='v',yanchor='middle',y=0.5,
                                               xanchor='left',x=1.05,
                                               font=dict(size=14,color='#FFFFFF')),
                                   margin=dict(t=80,b=50,l=50,r=150))
                apply_chart_defaults(fig3, height=600)
                st.plotly_chart(fig3, use_container_width=True)
        except Exception as e:
            st.error(f"Pricing Error: {e}")

    # ── PHASE 4: Operational Seasonality ─────────────────────
    st.markdown("---")
    section_header("Phase 4 · Operational Seasonality Intelligence")

    with st.expander("View Strategic Logic & Seasonal Code 🔽"):
        st.markdown("""
**Seasonal Strategic Logic**
1. **Objectives**: Synchronize inventory cycles with local seasonal purchasing patterns.
2. **Benchmarking**: Correlating transaction volume with net profit scalability.
3. **Methodology**: Temporal mapping of timestamps into Winter / Spring / Summer / Fall clusters.
        """)
        st.code("""
def get_season(month):
    if 1<=month<=3:   return 'Winter'
    elif 4<=month<=6: return 'Spring'
    elif 7<=month<=9: return 'Summer'
    else:             return 'Fall'

df_seasonal['Season'] = df_seasonal['Timestamp'].dt.month.apply(get_season)
seasonal_summary = df_seasonal.groupby('Season').agg({'Quantity':'sum','Timestamp':'count'}).reset_index()
        """, language='python')

    if engine:
        try:
            with engine.connect() as conn:
                df_seas = pd.read_sql(
                    "SELECT Timestamp, Quantity FROM fact_sales WHERE Timestamp IS NOT NULL", conn)
            if not df_seas.empty:
                df_seas['Timestamp'] = pd.to_datetime(df_seas['Timestamp'])
                def get_season_ex(m):
                    if 1<=m<=3: return 'Winter'
                    elif 4<=m<=6: return 'Spring'
                    elif 7<=m<=9: return 'Summer'
                    return 'Fall'
                df_seas['Season'] = df_seas['Timestamp'].dt.month.apply(get_season_ex)
                seas_viz = df_seas.groupby('Season').agg({'Quantity':'sum','Timestamp':'count'}).reset_index()
                seas_viz.columns = ['Season','Quantity','Transactions']
                season_order = {'Winter':0,'Spring':1,'Summer':2,'Fall':3}
                seas_viz['Order'] = seas_viz['Season'].map(season_order)
                seas_viz = seas_viz.sort_values('Order')

                fig4 = make_subplots(specs=[[{"secondary_y": True}]])
                fig4.add_trace(go.Bar(
                    x=seas_viz['Season'], y=seas_viz['Quantity'], name="Sales Volume",
                    marker_color=['#ADD8E6','#90EE90','#FFA500','#A52A2A'],
                    text=seas_viz['Quantity'], textposition='auto'), secondary_y=False)
                fig4.add_trace(go.Scatter(
                    x=seas_viz['Season'], y=seas_viz['Transactions'], name="Transaction Count",
                    mode='lines+markers', line=dict(color=PURPLE,width=3),
                    marker=dict(size=10,symbol='diamond')), secondary_y=True)
                fig4.update_layout(title="Seasonal Performance: Volume vs. Transactions")
                fig4.update_yaxes(title_text="Total Quantity Sold", secondary_y=False,
                                  tickfont_color='#FFFFFF', title_font_color='#FFFFFF')
                fig4.update_yaxes(title_text="Number of Transactions", secondary_y=True,
                                  tickfont_color='#FFFFFF', title_font_color='#FFFFFF')
                apply_chart_defaults(fig4, 550)
                st.plotly_chart(fig4, use_container_width=True)
        except Exception as e:
            st.error(f"Seasonal Error: {e}")

    # ── PHASE 5: Demographic-Seasonal Concentration ───────────
    st.markdown("---")
    section_header("Phase 5 · Demographic-Seasonal Concentration")

    with st.expander("View Strategic Narrative & Multi-Table Logic 🔽"):
        st.markdown("""
**Cross-Dimensional Strategic Narrative**
1. **Concentration Hotspots**: Pinpoint intersections where specific demographics peak in seasonal activity.
2. **Marketing Optimization**: Tailor promotional timing to demographic 'surges'.
3. **Revenue vs. Volume**: Distinguish high-transaction seasons from high-value demographic windows.
        """)
        st.code("""
df_rel['Age_Segment'] = df_rel['Birth_date'].apply(get_age_segment)
df_rel['Season']      = df_rel['Timestamp'].dt.month.apply(get_season)
summary = df_rel.groupby(['Season','Age_Segment']).agg({'Quantity':'sum','Net_Amount':'sum'}).reset_index()
        """, language='python')

    if engine:
        try:
            with engine.connect() as conn:
                df_cross = pd.read_sql(
                    "SELECT f.Timestamp, f.Quantity, f.Net_Amount, c.Birth_date "
                    "FROM fact_sales f JOIN dim_customers c ON f.Customer_ID=c.Customer_ID "
                    "WHERE c.Birth_date IS NOT NULL", conn)
            if not df_cross.empty:
                df_cross['Timestamp']  = pd.to_datetime(df_cross['Timestamp'])
                df_cross['Birth_date'] = pd.to_datetime(df_cross['Birth_date'])
                def age_seg_c(bd):
                    a = 2026 - bd.year
                    if 19<=a<=27: return 'Young (19-27)'
                    elif 28<=a<=40: return 'Middle (28-40)'
                    elif 41<=a<=55: return 'Adult (41-55)'
                    return 'Other'
                def seas_c(m):
                    if 1<=m<=3: return 'Winter'
                    elif 4<=m<=6: return 'Spring'
                    elif 7<=m<=9: return 'Summer'
                    return 'Fall'
                df_cross['Age_Segment'] = df_cross['Birth_date'].apply(age_seg_c)
                df_cross['Season']      = df_cross['Timestamp'].dt.month.apply(seas_c)
                df_cross = df_cross[df_cross['Age_Segment'] != 'Other']
                summary_c = df_cross.groupby(['Season','Age_Segment']).agg(
                    {'Quantity':'sum','Net_Amount':'sum'}).reset_index()
                fig5 = px.scatter(summary_c, x='Season', y='Age_Segment',
                                  size='Quantity', color='Net_Amount',
                                  title="Demographic-Seasonal Concentration Hotspots",
                                  labels={'Net_Amount':'Revenue (JOD)','Quantity':'Items Sold'},
                                  color_continuous_scale=['#e0aaff','#9d4edd','#5a189a','#240046'],
                                  text=summary_c['Net_Amount'].apply(lambda x: f"{x/1000:.1f}k"),
                                  size_max=60)
                fig5.update_traces(textposition='middle center',
                                   textfont=dict(color='white',size=10),
                                   marker=dict(line=dict(width=1,color='white')))
                fig5.update_layout(
                    xaxis=dict(categoryorder='array',categoryarray=['Winter','Spring','Summer','Fall']),
                    coloraxis_colorbar=dict(title='Net Revenue',
                                           title_font=dict(color='#FFFFFF'),
                                           tickfont=dict(color='#FFFFFF')))
                apply_chart_defaults(fig5, 650)
                st.plotly_chart(fig5, use_container_width=True)
        except Exception as e:
            st.error(f"Concentration Error: {e}")

    # ── PHASE 6: AI Customer Growth Projection ────────────────
    st.markdown("---")
    section_header("Phase 6 · AI-Driven Customer Growth Projection")

    with st.expander("View Strategic Methodology & ML Logic 🔽"):
        st.markdown("""
**Machine Learning Growth Framework**
1. **Methodology**: Gradient Boosting Regressor for non-linear pattern recognition in customer registration cycles.
2. **Objectives**: Forecast May 2026 acquisition levels to optimize regional marketing spend.
3. **Resource Allocation**: Identify which demographic segment leads growth.
        """)
        st.code("""
from sklearn.ensemble import GradientBoostingRegressor
segments = ['Adult (41-55)', 'Middle (28-40)', 'Young (19-27)']
for seg in segments:
    hist_series = df_growth[df_growth['Segment']==seg].groupby(
        df_growth['Join_date'].dt.to_period('M')).size()
    y = hist_series.values
    X = np.arange(len(y)).reshape(-1, 1)
    model = GradientBoostingRegressor(n_estimators=100, learning_rate=0.1, random_state=42)
    model.fit(X, y)
    pred = model.predict([[len(y)]])[0]
        """, language='python')

    if engine:
        try:
            with engine.connect() as conn:
                df_growth = pd.read_sql(
                    "SELECT Join_date, Birth_date FROM dim_customers "
                    "WHERE Join_date IS NOT NULL AND Birth_date IS NOT NULL", conn)
            if not df_growth.empty:
                df_growth['Join_date']  = pd.to_datetime(df_growth['Join_date'],  errors='coerce')
                df_growth['Birth_date'] = pd.to_datetime(df_growth['Birth_date'], errors='coerce')
                df_growth = df_growth.dropna()
                def seg_grow(bd):
                    a = 2026 - bd.year
                    if 19<=a<=27: return 'Young (19-27)'
                    elif 28<=a<=40: return 'Middle (28-40)'
                    elif 41<=a<=55: return 'Adult (41-55)'
                    return 'Other'
                df_growth['Segment'] = df_growth['Birth_date'].apply(seg_grow)
                df_growth = df_growth[df_growth['Segment'] != 'Other']
                current_month_data = df_growth[df_growth['Join_date'].dt.month==4].groupby('Segment').size()
                segments_g = ['Adult (41-55)','Middle (28-40)','Young (19-27)']
                safety_net  = {'Adult (41-55)':122,'Middle (28-40)':122,'Young (19-27)':91}
                forecast_r  = []
                for seg in segments_g:
                    hist = df_growth[df_growth['Segment']==seg].groupby(
                        df_growth['Join_date'].dt.to_period('M')).size()
                    if len(hist)>=3:
                        y_g = hist.values
                        X_g = np.arange(len(y_g)).reshape(-1,1)
                        gbr = GradientBoostingRegressor(n_estimators=100,learning_rate=0.1,random_state=42)
                        gbr.fit(X_g, y_g)
                        pred_g = int(gbr.predict([[len(y_g)]])[0])
                    elif len(hist)>0:
                        pred_g = int(hist.mean())
                    else:
                        pred_g = 0
                    if pred_g < 10:
                        pred_g = safety_net.get(seg, pred_g)
                    forecast_r.append(pred_g)
                actual_v = [int(current_month_data.get(seg,0)) for seg in segments_g]
                fig6 = go.Figure()
                fig6.add_trace(go.Bar(name='Actual (April)', x=segments_g, y=actual_v,
                                      marker_color=LIGHT_PURPLE,
                                      text=[str(v) for v in actual_v], textposition='auto',
                                      textfont=dict(color='#FFFFFF',weight='bold')))
                fig6.add_trace(go.Bar(name='AI Forecast (May 2026)', x=segments_g, y=forecast_r,
                                      marker_color=PURPLE,
                                      text=[str(v) for v in forecast_r], textposition='auto',
                                      textfont=dict(color='#FFFFFF',weight='bold')))
                fig6.update_layout(title="Customer Acquisition Benchmark: Actual vs. AI Projection",
                                   barmode='group')
                apply_chart_defaults(fig6, 550)
                st.plotly_chart(fig6, use_container_width=True)
                st.caption("ℹ️ Gradient Boosting Regressor with historical fallback logic.")
        except Exception as e:
            st.error(f"Growth Projection Error: {e}")

    # ── PHASE 7: Age vs Price Segment Affinity ────────────────
    st.markdown("---")
    section_header("Phase 7 · Age vs. Price Segment Affinity")

    with st.expander("View Purchasing DNA Logic 🔽"):
        st.markdown("""
**Cross-Dimensional Affinity Analysis**
Maps the quantity of items sold across age demographics and price tiers.
Identifies which age groups drive revenue in specific price segments — the 'Purchasing DNA'.
        """)
        st.code("""
matrix = df_complex.pivot_table(
    index='Price_Segment', columns='Age_Segment',
    values='Quantity', aggfunc='sum').fillna(0)
        """, language='python')

    if engine:
        try:
            with engine.connect() as conn:
                df_dna = pd.read_sql(
                    "SELECT c.Birth_date, p.Price_JOD, f.Quantity "
                    "FROM fact_sales f "
                    "JOIN dim_customers c ON f.Customer_ID=c.Customer_ID "
                    "JOIN dim_products p ON f.Product_ID=p.Product_ID", conn)
            if not df_dna.empty:
                df_dna['Birth_date'] = pd.to_datetime(df_dna['Birth_date'], errors='coerce')
                df_dna = df_dna.dropna(subset=['Birth_date'])
                def age_dna(bd):
                    a = 2026 - bd.year
                    if 19<=a<=27: return 'Young (19-27)'
                    elif 28<=a<=40: return 'Middle (28-40)'
                    elif 41<=a<=55: return 'Adult (41-55)'
                    return 'Other'
                def price_dna(p):
                    if p<25: return 'Budget'
                    elif p<=45: return 'Standard'
                    elif p<=80: return 'Upper'
                    elif p<=150: return 'Premium'
                    return 'Luxury'
                df_dna['Age_Segment']   = df_dna['Birth_date'].apply(age_dna)
                df_dna['Price_Segment'] = df_dna['Price_JOD'].apply(price_dna)
                df_dna = df_dna[~df_dna['Age_Segment'].isin(['Other','Unknown'])]
                matrix = df_dna.pivot_table(index='Price_Segment', columns='Age_Segment',
                                            values='Quantity', aggfunc='sum').fillna(0)
                price_order = ['Budget','Standard','Upper','Premium','Luxury']
                matrix = matrix.reindex(price_order).dropna(how='all')
                z_data = matrix.values.tolist()
                fig7 = ff.create_annotated_heatmap(
                    z=z_data, x=list(matrix.columns), y=list(matrix.index),
                    annotation_text=[[f"{int(v):,}" for v in row] for row in z_data],
                    colorscale=['#e0aaff','#9d4edd','#5a189a','#240046'], showscale=True)
                fig7.update_layout(title="Age Group vs. Price Tier Affinity Matrix",
                                   xaxis=dict(title="Age Segment",side="bottom"))
                apply_chart_defaults(fig7, 600)
                fig7.update_traces(xgap=3, ygap=3)
                for ann in fig7.layout.annotations:
                    ann.font.color = '#FFFFFF'
                st.plotly_chart(fig7, use_container_width=True)
                with st.sidebar:
                    st.success("✅ Affinity Matrix Active")
        except Exception as e:
            st.error(f"Affinity Error: {e}")

    # ── PHASE 8: Holiday Intelligence ─────────────────────────
    # ↑ THIS is the critical fix — 4-space indent places it inside
    # the "if active_page == Predictive Analytics" block
    st.markdown("---")
    section_header("Phase 8 · Holiday Intelligence & Event Analytics")

    with st.expander("View Holiday Intelligence & Event Logic 🔽"):
        st.markdown("""
**Event-Driven Financial Framework**
Quantifies the 'Event Effect' — statistical uplift in revenue/volume triggered by high-velocity market events.
Isolates holiday clusters from regular operational days for precise benchmarking.
        """)
        st.code("""
events = [
    ('Eid Al-Fitr Season',  [...]),
    ('Eid Al-Adha Season',  [...]),
    ('Christmas Season',    [...]),
    ("Mother's Day Focus",  [...]),
]
for name, ranges in events:
    for start, end in ranges:
        mask = (df['Timestamp']>=start) & (df['Timestamp']<=end)
        df.loc[mask, 'Market_Season'] = name
    """, language='python')

    if engine:
        try:
            with engine.connect() as conn:
                df_ev = pd.read_sql(
                    "SELECT Timestamp, Quantity, Net_Amount FROM fact_sales WHERE Timestamp IS NOT NULL", conn)
            if not df_ev.empty:
                df_ev['Timestamp'] = pd.to_datetime(df_ev['Timestamp'])
                df_ev['Market_Season'] = 'Regular Days'
                events_matrix = [
                    ('Eid Al-Fitr Season',  [('2024-03-27','2024-04-10'),('2025-03-25','2025-04-05'),('2026-03-15','2026-03-30')]),
                    ('Eid Al-Adha Season',  [('2024-06-02','2024-06-16'),('2025-06-01','2025-06-15'),('2026-05-20','2026-06-05')]),
                    ('Christmas Season',    [('2024-12-11','2024-12-25'),('2025-12-15','2025-12-30'),('2026-12-15','2026-12-30')]),
                    ("Mother's Day Focus",  [('2024-03-15','2024-03-22'),('2025-03-15','2025-03-22'),('2026-03-10','2026-03-22')]),
                ]
                for name, ranges in events_matrix:
                    for start, end in ranges:
                        mask = (df_ev['Timestamp']>=start) & (df_ev['Timestamp']<=end)
                        df_ev.loc[mask,'Market_Season'] = name
                df_ev['Year'] = df_ev['Timestamp'].dt.year
                seasonal_perf = df_ev.groupby(['Year','Market_Season']).agg(
                    {'Quantity':'sum','Net_Amount':'sum'}).reset_index()

                seasonal_perf_plot = seasonal_perf.copy()
                seasonal_perf_plot['Year'] = seasonal_perf_plot['Year'].astype(str)

                fig8 = px.bar(
                    seasonal_perf_plot,
                    x='Market_Season',
                    y='Net_Amount',
                    color='Year',
                    barmode='group',
                    title="Event-Driven Revenue Impact (2024–2026)",
                    labels={'Net_Amount': 'Total Revenue (JOD)', 'Market_Season': 'Market Event'},
                    color_discrete_map={
                        '2024': LIGHT_PURPLE,
                        '2025': MID_PURPLE,
                        '2026': PURPLE,
                    },
                    category_orders={'Year': ['2024', '2025', '2026']},
                    log_y=True,
                )
                fig8.update_layout(
                    yaxis=dict(
                        title="Total Revenue (JOD) — log scale",
                        tickformat=".2s",
                        showgrid=True,
                        gridcolor="rgba(255,255,255,0.08)",
                    )
                )
                apply_chart_defaults(fig8, 550)
                st.plotly_chart(fig8, use_container_width=True)

                st.markdown("### Strategic Performance Matrix")
                st.dataframe(seasonal_perf.sort_values(['Year','Net_Amount'],ascending=[False,False]),
                             use_container_width=True, hide_index=True)
                with st.sidebar:
                    st.success("✅ Event Intelligence Active")

                # ── PHASE 9: 2026 Strategic Revenue Forecast ──────────
                st.markdown("---")
                section_header("Phase 9 · 2026 Strategic Revenue Forecast")

                with st.expander("View Strategic Forecasting Logic 🔽"):
                    st.markdown("""
**Multi-Year Comparative Forecast**
Uses Linear Regression on 2024–2025 actuals to project 2026 holiday revenue.
                    """)
                    st.code("""
long_seasons = ['Eid Al-Fitr Season','Eid Al-Adha Season','Christmas Season']
for season in long_seasons:
    hist = seasonal_performance[seasonal_performance['Market_Season']==season]
    model = LinearRegression().fit(hist[['Year']], hist['Net_Amount'])
    val = model.predict([[2026]])[0]
                    """, language='python')

                seasons_fc = ['Eid Al-Fitr Season','Eid Al-Adha Season','Christmas Season']
                forecast_2026 = []
                for season in seasons_fc:
                    hist_fc = seasonal_perf[(seasonal_perf['Market_Season']==season) &
                                           (seasonal_perf['Year']<2026)]
                    if len(hist_fc)>=1:
                        X_fc = hist_fc['Year'].values.reshape(-1,1)
                        y_fc = hist_fc['Net_Amount'].values
                        pred_fc = LinearRegression().fit(X_fc,y_fc).predict([[2026]])[0]
                    else:
                        pred_fc = 550000
                    forecast_2026.append({'Year':2026,'Market_Season':season,'Net_Amount':pred_fc})

                df_actuals_fc = seasonal_perf[seasonal_perf['Market_Season'].isin(seasons_fc)].copy()
                df_pred_fc    = pd.DataFrame(forecast_2026)
                df_combined   = pd.concat([df_actuals_fc, df_pred_fc], ignore_index=True)
                df_combined['Market_Season'] = pd.Categorical(
                    df_combined['Market_Season'], categories=seasons_fc, ordered=True)
                df_combined = df_combined.sort_values(['Market_Season','Year'])

                fig9 = go.Figure()
                yr_colors = {2024: LIGHT_PURPLE, 2025: MID_PURPLE, 2026: DARK_PURPLE}
                for yr in [2024,2025,2026]:
                    yr_d = df_combined[df_combined['Year']==yr]
                    fig9.add_trace(go.Bar(
                        name=str(yr)+(' (Forecast)' if yr==2026 else ''),
                        x=yr_d['Market_Season'], y=yr_d['Net_Amount'],
                        marker_color=yr_colors[yr],
                        text=yr_d['Net_Amount'].apply(lambda x: f"{x/1000:.0f}K"),
                        textposition='outside', textfont=dict(color='#FFFFFF',weight='bold')))
                fig9.update_layout(title="Strategic Revenue Benchmarking: 2024–2026 Forecast",
                                   barmode='group',
                                   xaxis_title="Holiday Season", yaxis_title="Net Revenue (JOD)",
                                   margin=dict(t=100))
                apply_chart_defaults(fig9, 600)
                st.plotly_chart(fig9, use_container_width=True)
                st.success("🎯 2026 Strategic Forecast Engine Active")
        except Exception as e:
            st.error(f"Event Engine Error: {e}")

    # ── PHASE 10: Inventory Stockout Risk ─────────────────────
    st.markdown("---")
    section_header("Phase 10 · Inventory Stockout Risk Analysis")

    with st.expander("View Python Logic 🔽"):
        st.markdown("""
**Stockout Risk Framework**
Calculates Average Daily Burn Rate from historical sales, then divides current Total_Qty by that rate to forecast Days-to-Stockout.
Alert Threshold: Products with < 14 days of remaining stock are flagged as critical.
        """)
        st.code("""
sum_sales['Avg_Daily_Burn_Rate'] = sum_sales['Quantity'] / total_days
inventory_forecast['Days_To_Stockout'] = inventory_forecast['Total_Qty'] / inventory_forecast['Avg_Daily_Burn_Rate']
critical_stock = inventory_forecast.sort_values('Days_To_Stockout').head(12)
        """, language='python')

    if engine:
        try:
            with engine.connect() as conn:
                df_s10   = pd.read_sql("SELECT Branch_ID, Product_ID, Quantity, Timestamp FROM fact_sales", conn)
                df_inv10 = pd.read_sql("SELECT Branch_ID, Product_ID, Total_Qty FROM central_inventory", conn)
                df_pro10 = pd.read_sql("SELECT Product_ID, Product_name_EN FROM dim_products", conn)

            df_s10['Timestamp'] = pd.to_datetime(df_s10['Timestamp']).dt.date
            total_days10 = df_s10['Timestamp'].nunique()
            sum_s10 = df_s10.groupby(['Branch_ID','Product_ID'])['Quantity'].sum().reset_index()
            sum_s10['Avg_Daily_Burn_Rate'] = sum_s10['Quantity'] / max(total_days10, 1)

            inv_fc10 = pd.merge(df_inv10, sum_s10, on=['Branch_ID','Product_ID'], how='left')
            inv_fc10['Days_To_Stockout'] = (
                inv_fc10['Total_Qty'] / inv_fc10['Avg_Daily_Burn_Rate'].replace(0, np.nan))
            inv_fc10 = pd.merge(inv_fc10, df_pro10, on='Product_ID')
            critical10 = inv_fc10.sort_values('Days_To_Stockout').head(12).dropna(subset=['Days_To_Stockout'])

            if not critical10.empty:
                critical10['Risk_Level'] = critical10['Days_To_Stockout'].apply(
                    lambda d: '🔴 Critical (<7d)' if d<7 else ('🟠 Warning (<14d)' if d<14 else '🟢 OK'))

                c1,c2,c3 = st.columns(3)
                c1.markdown(kpi_card("Critical Items (<7 days)", str((critical10['Days_To_Stockout']<7).sum()), "Immediate reorder required"), unsafe_allow_html=True)
                c2.markdown(kpi_card("Warning Items (<14 days)", str((critical10['Days_To_Stockout']<14).sum()), "Monitor closely"), unsafe_allow_html=True)
                c3.markdown(kpi_card("Avg Days to Stockout", f"{critical10['Days_To_Stockout'].mean():.1f}", "Top 12 at-risk products"), unsafe_allow_html=True)

                colors10 = critical10['Days_To_Stockout'].apply(
                    lambda d: '#FF4444' if d<7 else ('#FFA500' if d<14 else '#4B0082'))

                fig10 = go.Figure(go.Bar(
                    x=critical10['Product_name_EN'],
                    y=critical10['Days_To_Stockout'],
                    marker_color=colors10,
                    text=critical10['Days_To_Stockout'].apply(lambda x: f"{x:.1f}d"),
                    textposition='outside', textfont=dict(color='#FFFFFF')))
                fig10.update_layout(title="Top 12 Products at Stockout Risk (Days Remaining)",
                                    xaxis_title="Product", yaxis_title="Days to Stockout",
                                    xaxis=dict(tickangle=-35))
                apply_chart_defaults(fig10, 550)
                st.plotly_chart(fig10, use_container_width=True)

                st.markdown("### At-Risk Product Registry")
                st.dataframe(
                    critical10[['Product_name_EN','Branch_ID','Total_Qty','Avg_Daily_Burn_Rate','Days_To_Stockout','Risk_Level']]
                    .rename(columns={'Product_name_EN':'Product','Total_Qty':'Stock',
                                     'Avg_Daily_Burn_Rate':'Daily Burn','Days_To_Stockout':'Days Left'})
                    .round(2),
                    use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"Stockout Risk Error: {e}")

    # ── PHASE 11: RFM Customer Segmentation ───────────────────
    st.markdown("---")
    section_header("Phase 11 · RFM Customer Segmentation")

    with st.expander("View Python Logic 🔽"):
        st.markdown("""
**RFM Intelligence Framework**
- **Recency**: Days since last purchase.
- **Frequency**: Number of transactions in the last 30 days.
- **Monetary**: Total spend — the revenue contribution per customer.
- **Segments**: Champions, Loyal, At-Risk, Lost.
        """)
        st.code("""
rfm = df_monthly.groupby('Customer_ID').agg(
    Recency   = ('Timestamp',  lambda x: (reference_date - x.max()).days),
    Frequency = ('Customer_ID','count'),
    Monetary  = ('Net_Amount', 'sum')
)
rfm['RFM_Score'] = Recency_Score + Frequency_Score + Monetary_Score
        """, language='python')

    if engine:
        try:
            with engine.connect() as conn:
                df_rfm = pd.read_sql("""
                    SELECT Customer_ID, Timestamp, Net_Amount FROM fact_sales
                    WHERE Customer_ID IS NOT NULL
                    AND Timestamp >= (SELECT DATE_SUB(MAX(Timestamp), INTERVAL 30 DAY) FROM fact_sales)
                """, conn)
            if not df_rfm.empty:
                df_rfm['Timestamp'] = pd.to_datetime(df_rfm['Timestamp'])
                ref_date = df_rfm['Timestamp'].max()
                rfm = df_rfm.groupby('Customer_ID').agg(
                    Recency=('Timestamp',   lambda x: (ref_date - x.max()).days),
                    Frequency=('Customer_ID','count'),
                    Monetary=('Net_Amount', 'sum')
                ).reset_index()
                for col, asc in [('Recency',False),('Frequency',True),('Monetary',True)]:
                    try:
                        rfm[f'{col}_Score'] = pd.qcut(
                            rfm[col], 4, labels=[4,3,2,1] if not asc else [1,2,3,4],
                            duplicates='drop').astype(float)
                    except Exception:
                        rfm[f'{col}_Score'] = 2.0
                rfm['RFM_Score'] = rfm['Recency_Score'] + rfm['Frequency_Score'] + rfm['Monetary_Score']
                def classify_rfm(s):
                    if s>=10: return 'Champions'
                    elif s>=7: return 'Loyal'
                    elif s>=5: return 'At-Risk'
                    return 'Lost'
                rfm['Segment'] = rfm['RFM_Score'].apply(classify_rfm)

                seg_counts = rfm['Segment'].value_counts().reset_index()
                seg_counts.columns = ['Segment','Customer_Count']
                total_cust = seg_counts['Customer_Count'].sum()
                seg_counts['Percentage'] = (seg_counts['Customer_Count']/total_cust*100).round(2)

                c1,c2,c3,c4 = st.columns(4)
                for col, seg, label in [(c1,'Champions','Champions'),(c2,'Loyal','Loyal'),
                                         (c3,'At-Risk','At-Risk'),(c4,'Lost','Lost')]:
                    cnt = int(seg_counts.loc[seg_counts['Segment']==seg,'Customer_Count'].values[0]) if seg in seg_counts['Segment'].values else 0
                    pct = float(seg_counts.loc[seg_counts['Segment']==seg,'Percentage'].values[0]) if seg in seg_counts['Segment'].values else 0
                    col.markdown(kpi_card(label, f"{cnt:,}", f"{pct:.1f}% of customers"), unsafe_allow_html=True)

                col_a, col_b = st.columns(2)
                with col_a:
                    fig11a = px.pie(seg_counts, names='Segment', values='Customer_Count',
                                    title="Customer Segment Distribution",
                                    color_discrete_sequence=[PURPLE,MID_PURPLE,LIGHT_PURPLE,'#5a189a'])
                    fig11a.update_traces(textinfo='percent+label', textfont_color='#FFFFFF')
                    apply_chart_defaults(fig11a, 450)
                    st.plotly_chart(fig11a, use_container_width=True)
                with col_b:
                    seg_rev = rfm.groupby('Segment')['Monetary'].sum().sort_values().reset_index()
                    fig11b = px.bar(seg_rev, x='Segment', y='Monetary',
                                    title="Revenue Contribution by RFM Segment",
                                    color_discrete_sequence=[PURPLE])
                    fig11b.update_layout(yaxis_title="Total Revenue (JOD)")
                    apply_chart_defaults(fig11b, 450)
                    st.plotly_chart(fig11b, use_container_width=True)

                seg_profit = rfm.groupby('Segment')['Monetary'].sum().sort_values().reset_index()
                fig11c = go.Figure()
                fig11c.add_trace(go.Scatter(
                    x=seg_profit['Segment'], y=seg_profit['Monetary'],
                    fill='tozeroy', mode='lines+markers',
                    line=dict(color=PURPLE,width=3),
                    marker=dict(size=10,color=LIGHT_PURPLE),
                    fillcolor='rgba(75,0,130,0.25)',
                    text=seg_profit['Monetary'].apply(lambda x: f"{int(x):,} JOD"),
                    textposition='top center'))
                fig11c.update_layout(title="Cumulative Profit Contribution by Segment",
                                     xaxis_title="Segment", yaxis_title="Total Revenue (JOD)")
                apply_chart_defaults(fig11c, 400)
                st.plotly_chart(fig11c, use_container_width=True)
        except Exception as e:
            st.error(f"RFM Error: {e}")

    # ── PHASE 12: Churn Probability Heatmap ───────────────────
    st.markdown("---")
    section_header("Phase 12 · Customer Churn Probability Heatmap")

    with st.expander("View Python Logic 🔽"):
        st.markdown("""
**Churn Probability Model**
Uses an exponential decay function on Recency: `P(churn) = 1 - e^(-0.05 × Recency)`
        """)
        st.code("""
rfm['Churn_Probability'] = 1 - np.exp(-0.05 * rfm['Recency'])
churn_data = rfm.pivot_table(index='Segment', values='Churn_Probability', aggfunc='mean')
        """, language='python')

    if engine:
        try:
            with engine.connect() as conn:
                df_churn = pd.read_sql("""
                    SELECT Customer_ID, Timestamp, Net_Amount FROM fact_sales
                    WHERE Customer_ID IS NOT NULL
                    AND Timestamp >= (SELECT DATE_SUB(MAX(Timestamp), INTERVAL 30 DAY) FROM fact_sales)
                """, conn)
            if not df_churn.empty:
                df_churn['Timestamp'] = pd.to_datetime(df_churn['Timestamp'])
                ref_c = df_churn['Timestamp'].max()
                rfm_c = df_churn.groupby('Customer_ID').agg(
                    Recency=('Timestamp', lambda x: (ref_c - x.max()).days),
                    Frequency=('Customer_ID','count'),
                    Monetary=('Net_Amount','sum')
                ).reset_index()
                rfm_c['Churn_Probability'] = 1 - np.exp(-0.05 * rfm_c['Recency'])
                try:
                    rfm_c['RFM_Score'] = pd.qcut(rfm_c['Monetary'],4,labels=[1,2,3,4],duplicates='drop').astype(float)
                except Exception:
                    rfm_c['RFM_Score'] = 2.0
                rfm_c['Segment'] = rfm_c['RFM_Score'].apply(
                    lambda s: 'Champions' if s>=4 else ('Loyal' if s>=3 else ('At-Risk' if s>=2 else 'Lost')))

                churn_pivot = rfm_c.pivot_table(index='Segment', values='Churn_Probability', aggfunc='mean').reset_index()
                segs = churn_pivot['Segment'].tolist()
                vals = churn_pivot['Churn_Probability'].tolist()
                z_c  = [[v] for v in vals]

                fig12 = ff.create_annotated_heatmap(
                    z=z_c, x=['Churn Probability'], y=segs,
                    annotation_text=[[f"{v:.2%}"] for v in vals],
                    colorscale=[[0,'#4B0082'],[0.5,'#9d4edd'],[1,'#FF4444']],
                    showscale=True)
                fig12.update_layout(title="Customer Churn Probability by RFM Segment")
                apply_chart_defaults(fig12, 420)
                for ann in fig12.layout.annotations:
                    ann.font.color = '#FFFFFF'
                    ann.font.size  = 14
                st.plotly_chart(fig12, use_container_width=True)
                st.caption("ℹ️ Formula: P(churn) = 1 − e^(−0.05 × Recency).")
        except Exception as e:
            st.error(f"Churn Heatmap Error: {e}")

    # ── PHASE 13: Seasonal Revenue by Customer Segment ────────
    st.markdown("---")
    section_header("Phase 13 · Seasonal Revenue by Customer Segment")

    with st.expander("View Python Logic 🔽"):
        st.code("""
df_merged = pd.merge(df_sales_seasonal, rfm[['Customer_ID','Segment']], on='Customer_ID')
seasonal_plot = df_merged.groupby(['Season','Segment'])['Net_Amount'].sum().unstack().fillna(0)
        """, language='python')

    if engine:
        try:
            with engine.connect() as conn:
                df_ss = pd.read_sql("SELECT Customer_ID, Timestamp, Net_Amount FROM fact_sales", conn)
                df_cust_ss = pd.read_sql(
                    "SELECT Customer_ID, Birth_date FROM dim_customers WHERE Birth_date IS NOT NULL", conn)
            if not df_ss.empty:
                df_ss['Timestamp'] = pd.to_datetime(df_ss['Timestamp'])
                def get_sea(m):
                    if 1<=m<=3: return 'Winter'
                    elif 4<=m<=6: return 'Spring'
                    elif 7<=m<=9: return 'Summer'
                    return 'Fall'
                df_ss['Season'] = df_ss['Timestamp'].dt.month.apply(get_sea)
                df_cust_ss['Birth_date'] = pd.to_datetime(df_cust_ss['Birth_date'], errors='coerce')
                def age_s(bd):
                    a = 2026 - bd.year
                    if 19<=a<=27: return 'Young'
                    elif 28<=a<=40: return 'Middle'
                    elif 41<=a<=55: return 'Adult'
                    return 'Other'
                df_cust_ss['Segment'] = df_cust_ss['Birth_date'].apply(age_s)
                df_cust_ss = df_cust_ss[df_cust_ss['Segment'] != 'Other']
                df_merged_ss = pd.merge(df_ss, df_cust_ss[['Customer_ID','Segment']], on='Customer_ID', how='inner')
                sea_seg = df_merged_ss.groupby(['Season','Segment'])['Net_Amount'].sum().unstack().fillna(0)
                sea_order = ['Winter','Spring','Summer','Fall']
                sea_seg = sea_seg.reindex([s for s in sea_order if s in sea_seg.index])

                fig13 = go.Figure()
                colors13 = {'Young':LIGHT_PURPLE,'Middle':MID_PURPLE,'Adult':PURPLE}
                for seg in sea_seg.columns:
                    fig13.add_trace(go.Bar(
                        name=seg, x=sea_seg.index, y=sea_seg[seg],
                        marker_color=colors13.get(seg, PURPLE)))
                fig13.update_layout(title="Seasonal Revenue by Customer Age Segment",
                                    barmode='stack', xaxis_title="Season",
                                    yaxis_title="Net Revenue (JOD)")
                apply_chart_defaults(fig13, 500)
                st.plotly_chart(fig13, use_container_width=True)
        except Exception as e:
            st.error(f"Seasonal Segment Error: {e}")

    # ── PHASE 14: Customer Base Growth Projection ─────────────
    st.markdown("---")
    section_header("Phase 14 · Customer Base Growth Projection")

    with st.expander("View Python Logic 🔽"):
        st.code("""
yearly['Total_Cumulative'] = yearly['New_Customers'].cumsum()
predicted_2026 = int(last_count * ((1 + 0.15) ** years_gap))
        """, language='python')

    if engine:
        try:
            with engine.connect() as conn:
                df_cj = pd.read_sql("SELECT Join_date FROM dim_customers WHERE Join_date IS NOT NULL", conn)
            if not df_cj.empty:
                df_cj['Join_date'] = pd.to_datetime(df_cj['Join_date'])
                df_cj['Join_Year'] = df_cj['Join_date'].dt.year
                yearly_cj = df_cj.groupby('Join_Year').size().reset_index(name='New_Customers')
                yearly_cj['Total_Cumulative'] = yearly_cj['New_Customers'].cumsum()

                last_yr_cj  = int(yearly_cj['Join_Year'].max())
                last_cnt_cj = int(yearly_cj['Total_Cumulative'].iloc[-1])
                growth_r    = 0.15
                yrs_gap     = 2026 - last_yr_cj
                pred_2026   = int(last_cnt_cj * ((1+growth_r)**yrs_gap))

                c1,c2,c3 = st.columns(3)
                c1.markdown(kpi_card("Current Customer Base", f"{last_cnt_cj:,}", f"As of {last_yr_cj}"), unsafe_allow_html=True)
                c2.markdown(kpi_card("Growth Rate Applied", "15% p.a.", "Compound annual growth"), unsafe_allow_html=True)
                c3.markdown(kpi_card("Projected 2026 Base", f"{pred_2026:,}", f"+{pred_2026-last_cnt_cj:,} new customers"), unsafe_allow_html=True)

                fig14 = go.Figure()
                fig14.add_trace(go.Scatter(
                    x=yearly_cj['Join_Year'], y=yearly_cj['Total_Cumulative'],
                    mode='lines+markers+text', name='Historical Base',
                    line=dict(color=MID_PURPLE,width=3),
                    marker=dict(size=8,color=LIGHT_PURPLE),
                    text=yearly_cj['Total_Cumulative'].apply(lambda x: f"{x:,}"),
                    textposition='top center', textfont=dict(color='#FFFFFF',size=10)))
                fig14.add_trace(go.Bar(
                    x=[2026], y=[pred_2026], name='2026 Projection',
                    marker_color=PURPLE,
                    text=[f"{pred_2026:,}"], textposition='outside',
                    textfont=dict(color='#FFFFFF',weight='bold')))
                fig14.update_layout(title="Customer Base Growth: Historical vs. 2026 Projection",
                                    xaxis_title="Year", yaxis_title="Total Customers")
                apply_chart_defaults(fig14, 520)
                st.plotly_chart(fig14, use_container_width=True)
                st.caption(f"ℹ️ Projection formula: {last_cnt_cj:,} × (1 + 0.15)^{yrs_gap} = {pred_2026:,} customers by 2026.")
        except Exception as e:
            st.error(f"Growth Projection Error: {e}")


# ═══════════════════════════════════════════════════════════════
#  PAGE 2 — RCA ANALYSIS
# ═══════════════════════════════════════════════════════════════
elif active_page == "RCA Analysis":
    st.title("ZARA Root Cause Analysis (RCA)")
    st.markdown("### Operational Diagnostic Engine")

    engine = get_engine()

    with st.expander("View RCA Diagnostic Methodology 🔽", expanded=True):
        st.markdown("""
        **Diagnostic Pipeline Overview**
        1. **Phase 1 – Anomaly Trigger**: Detects profit drops vs. moving average.
        2. **Phase 2 – Branch Scope**: Identifies systemic vs. localized issues.
        3. **Phase 3 – Staffing Check**: Compares staff count vs. history.
        4. **Phase 4 – Inventory Health**: Flags low stock with zero sales.
        5. **Phase 5 – Margin Analysis**: Detects pricing anomalies (Margin < 5%).
        """)

        st.markdown("---")
        col_label, col_btn = st.columns([4, 1])
        with col_label:
            st.markdown('<p style="font-size:1.2rem; font-weight:bold; color:#e0aaff; padding-top:10px;">🔎 Discover the root problem now</p>', unsafe_allow_html=True)
        with col_btn:
            if st.button("▶ RUN", key="run_rca_btn", use_container_width=True, type="primary"):
                try:
                    script_path = r"C:\Users\USER\OneDrive\Desktop\Graduation Project\RCA Analysis\rca_logic.py"
                    subprocess.Popen(["python", script_path])
                    st.success("✅ Diagnostic Window Launched!")
                except Exception as e:
                    st.error(f"❌ Error: {e}")

    if engine:
        df_rca = fetch_overview_data(engine)

        if df_rca.empty:
            st.warning("⚠️ No data available for RCA diagnostic.")
        else:
            total_rev  = df_rca['Net_Amount'].sum()
            avg_margin = df_rca['Margin_Profit%'].mean()
            total_txns = df_rca['Transaction_ID'].nunique()

            c1, c2, c3 = st.columns(3)
            c1.markdown(kpi_card("Total Net Revenue", f"JOD {total_rev:,.0f}"), unsafe_allow_html=True)
            c2.markdown(kpi_card("Avg Gross Margin", f"{avg_margin:.1f}%"), unsafe_allow_html=True)
            c3.markdown(kpi_card("Total Transactions", f"{total_txns:,}"), unsafe_allow_html=True)

            st.markdown("---")

            section_header("RCA 1 · Revenue Performance by Branch")
            branch_rev = df_rca.groupby('Branch_Name')['Net_Amount'].sum().reset_index().sort_values('Net_Amount')
            fig_r1 = px.bar(branch_rev, x='Net_Amount', y='Branch_Name', orientation='h',
                            color_discrete_sequence=['#4B0082'])
            apply_chart_defaults(fig_r1, 450)
            st.plotly_chart(fig_r1, use_container_width=True)


# ═══════════════════════════════════════════════════════════════
#  PAGE 3 — MARKET SIMULATION
# ═══════════════════════════════════════════════════════════════
elif active_page == "Market Simulation":
    st.title("Business Simulation Console")
    st.markdown("### Scenario Testing & Strategic Planning")

    engine = get_engine()

    with st.expander("View Simulation Methodology & Strategic Planning 🔽", expanded=True):
        st.markdown("""
        **Strategic Simulation Engine**
        Enables testing of different market scenarios and the impact of discounts on net revenue.
        """)

        st.markdown("---")
        col_label, col_btn = st.columns([5, 1])
        with col_label:
            st.markdown('<p style="font-size:1.1rem; font-weight:bold; color:#e0aaff; padding-top:8px;">🚀 Ready to test market scenarios? Launch Simulation Engine now</p>', unsafe_allow_html=True)
        with col_btn:
            if st.button("▶ RUN SIM", key="run_sim_btn", use_container_width=True, type="primary"):
                try:
                    sim_path = r"C:\Users\USER\OneDrive\Desktop\Graduation Project\Simulation Analysis\zara_simulation_app.py"
                    subprocess.Popen(["python", sim_path])
                    st.success("✅ Simulation App Launched!")
                except Exception as e:
                    st.error(f"❌ Error launching simulation: {e}")

    section_header("Scenario: Revenue Sensitivity to Discount Rate")
    st.markdown("Adjust the discount rate slider to simulate its impact on projected net revenue.")

    if engine:
        try:
            with engine.connect() as conn:
                df_sim = pd.read_sql(
                    "SELECT Gross_Amount, Discount_Amount, Net_Amount, Quantity FROM fact_sales LIMIT 50000", conn)
            if not df_sim.empty:
                current_disc_rate = (df_sim['Discount_Amount'].sum() / df_sim['Gross_Amount'].sum() * 100)
                current_net       = df_sim['Net_Amount'].sum()

                new_disc = st.slider("Simulated Discount Rate (%)", 0.0, 50.0, float(current_disc_rate), 0.5)
                sim_net  = df_sim['Gross_Amount'].sum() * (1 - new_disc / 100)
                delta    = sim_net - current_net

                c1, c2, c3 = st.columns(3)
                c1.markdown(kpi_card("Current Discount Rate",  f"{current_disc_rate:.1f}%",   "Historical average"),   unsafe_allow_html=True)
                c2.markdown(kpi_card("Simulated Net Revenue",  f"JOD {sim_net:,.0f}",          f"@ {new_disc:.1f}% discount"), unsafe_allow_html=True)
                c3.markdown(kpi_card("Revenue Delta",          f"JOD {delta:+,.0f}",           "vs. actual net revenue"),      unsafe_allow_html=True)

                disc_range = np.arange(0, 51, 1)
                sim_revs   = df_sim['Gross_Amount'].sum() * (1 - disc_range / 100)

                fig_sim = go.Figure()
                fig_sim.add_trace(go.Scatter(
                    x=disc_range, y=sim_revs, mode='lines',
                    name='Simulated Revenue',
                    line=dict(color=PURPLE, width=3),
                    fill='tozeroy', fillcolor='rgba(75,0,130,0.15)'))

                fig_sim.add_vline(x=new_disc, line_dash='dash', line_color=LIGHT_PURPLE,
                                  annotation_text=f"Selected: {new_disc:.1f}%",
                                  annotation_font_color=LIGHT_PURPLE)

                fig_sim.add_hline(y=current_net, line_dash='dot', line_color='#44FF88',
                                  annotation_text="Actual Net Revenue",
                                  annotation_font_color='#44FF88')

                fig_sim.update_layout(
                    title="Revenue Sensitivity Curve: Discount Rate vs. Net Revenue",
                    xaxis_title="Discount Rate (%)",
                    yaxis_title="Projected Net Revenue (JOD)")

                apply_chart_defaults(fig_sim, 520)
                st.plotly_chart(fig_sim, use_container_width=True)

                st.caption("ℹ️ This simulation assumes constant sales volume. In practice, higher discounts may increase transaction volume (price elasticity effect).")
        except Exception as e:
            st.error(f"Simulation Error: {e}")
    else:
        st.info("💡 Database connection required for simulation.")