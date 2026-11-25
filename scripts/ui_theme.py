
import streamlit as st

def apply_theme():
    st.markdown("""
    <style>
    :root {
        --bg: #F3F6FB;
        --surface: #FFFFFF;
        --surface-hover: #F1F5FC;
        --border: #DCE4EF;
        --text: #17243A;
        --muted: #63738A;
        --accent: #2563EB;
        --accent-soft: #EFF6FF;
    }

    .stApp {
        background: var(--bg) !important;
        color: var(--text) !important;
    }

    .block-container {
        max-width: 1500px;
        padding: 2rem 2.4rem 3rem;
    }

    [data-testid="stHeader"] {
        background: rgba(243,246,251,.96) !important;
        border-bottom: 1px solid var(--border);
    }

    [data-testid="stSidebar"] {
        background: #FFFFFF !important;
        border-right: 1px solid var(--border);
    }

    [data-testid="stSidebar"] * {
        color: #26364D;
    }

    [data-testid="stSidebar"] [role="radiogroup"] {
        gap: 5px;
    }

    [data-testid="stSidebar"] [role="radiogroup"] label {
        border-radius: 8px;
        border: 1px solid transparent;
        padding: 9px 11px;
        transition: background .15s ease, border-color .15s ease;
    }

    [data-testid="stSidebar"] [role="radiogroup"] label:hover {
        background: #EFF5FF;
        border-color: #D8E5F7;
    }

    [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
        background: #EAF2FF;
        border-color: #C9DCFF;
    }

    h1, h2, h3, h4 {
        color: #17243A !important;
        letter-spacing: -.025em;
        font-weight: 650 !important;
    }

    h1 { font-size: 1.9rem !important; }
    h2 { font-size: 1.35rem !important; }
    h3 { font-size: 1.08rem !important; }

    p, label, [data-testid="stMarkdownContainer"] {
        color: #26364D;
    }

    [data-testid="stCaptionContainer"],
    [data-testid="stWidgetLabel"] p {
        color: #63738A !important;
    }

    [data-testid="stMetric"] {
        background: #FFFFFF !important;
        border: 1px solid #DCE4EF !important;
        border-radius: 12px;
        padding: 17px 18px;
        box-shadow: 0 2px 7px rgba(20,40,70,.035);
    }

    [data-testid="stMetricLabel"] {
        color: #63738A !important;
        font-size: .82rem !important;
        font-weight: 600 !important;
    }

    [data-testid="stMetricValue"] {
        color: #17243A !important;
        font-size: 1.8rem !important;
        font-weight: 700 !important;
    }

    [data-testid="stDataFrame"],
    [data-testid="stTable"] {
        background: #FFFFFF !important;
        border: 1px solid #DCE4EF !important;
        border-radius: 10px;
        overflow: hidden;
    }

    [data-testid="stDataFrame"] canvas {
        background: #FFFFFF !important;
    }

    [data-testid="stDataFrame"] [role="grid"],
    [data-testid="stDataFrame"] [role="gridcell"] {
        color: #26364D !important;
    }

    [data-testid="stDataFrame"] [role="columnheader"] {
        background: #EDF2F8 !important;
        color: #26364D !important;
        font-weight: 700 !important;
    }

    [data-testid="stDataFrame"] [role="row"]:hover [role="gridcell"] {
        background: #F0F5FC !important;
    }

    .stButton > button,
    .stDownloadButton > button {
        background: #FFFFFF !important;
        color: #1D4ED8 !important;
        border: 1px solid #B9CBE3 !important;
        border-radius: 8px;
        font-weight: 600;
        box-shadow: none;
        transition: background .15s ease, border-color .15s ease;
    }

    .stButton > button:hover,
    .stDownloadButton > button:hover {
        background: #EFF6FF !important;
        color: #1D4ED8 !important;
        border-color: #6B9BE8 !important;
        box-shadow: 0 2px 7px rgba(37,99,235,.09);
        transform: none;
    }

    [data-baseweb="input"] > div,
    [data-baseweb="select"] > div,
    [data-baseweb="textarea"] {
        background: #FFFFFF !important;
        border: 1px solid #C9D5E4 !important;
        border-radius: 8px !important;
        color: #17243A !important;
        box-shadow: none !important;
    }

    [data-baseweb="input"] input,
    [data-baseweb="select"] input,
    [data-baseweb="textarea"] textarea {
        color: #17243A !important;
        -webkit-text-fill-color: #17243A !important;
    }

    [data-baseweb="input"] > div:focus-within,
    [data-baseweb="select"] > div:focus-within,
    [data-baseweb="textarea"]:focus-within {
        border-color: #2563EB !important;
        box-shadow: 0 0 0 1px #2563EB !important;
    }

    [data-testid="stTabs"] [role="tablist"] {
        gap: 6px;
        border-bottom: 1px solid var(--border);
    }

    [data-testid="stTabs"] button[role="tab"] {
        color: #63738A;
        border-radius: 7px 7px 0 0;
    }

    [data-testid="stTabs"] button[role="tab"]:hover {
        background: #EAF2FF;
        color: #1D4ED8;
    }

    [data-testid="stTabs"] button[aria-selected="true"] {
        color: #1D4ED8 !important;
        border-bottom: 2px solid #2563EB;
    }

    [data-testid="stExpander"] {
        background: #FFFFFF;
        border: 1px solid #DCE4EF;
        border-radius: 10px;
    }

    [data-testid="stAlert"] {
        border-radius: 9px;
    }

    hr {
        border-color: #DCE4EF !important;
    }

    [data-testid="stMarkdownContainer"] code {
        background: #EDF2F8;
        color: #1D4ED8;
        border-radius: 5px;
    }

    #MainMenu, footer {
        visibility: hidden;
    }

    @media (max-width: 900px) {
        .block-container {
            padding: 1.3rem 1rem 2rem;
        }
    }
    
    /* WiFi Vision Lab - ortak sayfa duzeni */
    .wv-page-header {
        padding: 0 0 1.15rem 0;
        margin: 0 0 1.35rem 0;
        border-bottom: 1px solid #DCE4EF;
    }

    .wv-page-header h1 {
        margin: 0 0 .35rem 0 !important;
        color: #17243A !important;
        font-size: 1.85rem !important;
        font-weight: 720 !important;
        letter-spacing: -.04em !important;
    }

    .wv-page-header p {
        margin: 0 !important;
        color: #63738A !important;
        font-size: .92rem !important;
        line-height: 1.5;
    }

    [data-testid="stVerticalBlock"] {
        gap: .85rem;
    }

    [data-testid="stDataFrame"] {
        border: 1px solid #DCE4EF !important;
        border-radius: 10px !important;
    }

    [data-testid="stDataFrame"] [role="columnheader"] {
        font-size: .82rem !important;
    }

    .stButton > button,
    .stDownloadButton > button {
        min-height: 2.45rem;
        padding: .45rem .9rem;
    }

    [data-testid="stAlert"] p {
        line-height: 1.5;
    }

    @media (max-width: 700px) {
        .wv-page-header h1 {
            font-size: 1.5rem !important;
        }

        .block-container {
            padding-left: .8rem;
            padding-right: .8rem;
        }
    }

    </style>
    """, unsafe_allow_html=True)
