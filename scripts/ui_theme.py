import streamlit as st


# Signal Atlas: a calm, evidence-first visual system for network observability.
LIGHT_PALETTE = {
    "bg": "#F2F5F3", "surface": "#FFFFFF", "surface_soft": "#F7F9F8",
    "border": "#DCE5E1", "text": "#182B2A", "muted": "#617370",
    "accent": "#087F78", "accent_strong": "#066A65", "accent_soft": "#E4F3F0",
    "sidebar": "#FBFCFB", "sidebar_muted": "#73827F", "hover": "#EDF4F1",
    "input": "#FFFFFF", "header": "rgba(242, 245, 243, .94)",
    "shadow": "rgba(24, 43, 42, .045)", "success": "#167A55",
    "success_soft": "#E8F4ED", "warning": "#8A5A12", "warning_soft": "#FBF2E3",
    "danger": "#B84040", "danger_soft": "#F9EAEA", "info": "#426C8C",
    "info_soft": "#EAF1F6",
}


def get_theme_palette(theme="light"):
    """Return the supported light palette as a copy."""
    return LIGHT_PALETTE.copy()


def apply_theme(theme="light"):
    """Apply the Signal Atlas light-only design system."""
    variables = "\n".join(
        f"    --wv-{name.replace('_', '-')}: {value};"
        for name, value in LIGHT_PALETTE.items()
    )
    st.markdown(
        f"""
        <style>
        :root {{
{variables}
            color-scheme: light;
            --wv-radius-sm: 7px;
            --wv-radius-md: 10px;
            --wv-radius-lg: 14px;
        }}
        html, body, [class*="css"] {{
            font-family: "Segoe UI Variable", "Segoe UI", Inter, -apple-system,
                         BlinkMacSystemFont, sans-serif;
            font-feature-settings: "ss01" on;
            -webkit-font-smoothing: antialiased;
        }}
        .stApp, [data-testid="stAppViewContainer"] {{
            background: var(--wv-bg); color: var(--wv-text);
        }}
        .block-container {{ max-width: 1480px; padding: 1.7rem 2.25rem 3.4rem; }}
        [data-testid="stHeader"] {{
            background: var(--wv-header); border-bottom: 1px solid var(--wv-border);
            backdrop-filter: blur(12px);
        }}
        [data-testid="stSidebar"], [data-testid="stSidebar"] > div:first-child {{
            background: var(--wv-sidebar); border-right: 1px solid var(--wv-border);
        }}
        [data-testid="stSidebar"] > div:first-child {{ padding: 14px 13px 12px; }}
        h1, h2, h3, h4, p, label, li, span {{ color: var(--wv-text); }}
        h1, h2, h3, h4 {{ letter-spacing: -.025em; font-weight: 650 !important; }}
        h1 {{ font-size: 1.82rem !important; line-height: 1.2 !important; }}
        h2 {{ font-size: 1.32rem !important; line-height: 1.3 !important; }}
        h3 {{ font-size: 1.04rem !important; line-height: 1.4 !important; }}
        p, li, label {{ line-height: 1.62; }}
        [data-testid="stMarkdownContainer"] p,
        [data-testid="stMarkdownContainer"] li {{ font-size: .94rem; }}
        [data-testid="stDataFrame"] {{ font-size: .9rem; }}
        [data-testid="stCaptionContainer"] {{ font-size: .78rem; line-height: 1.5; }}
        [data-testid="stVerticalBlock"] {{ gap: .85rem; }}
        [data-testid="stCaptionContainer"], [data-testid="stWidgetLabel"] p,
        [data-testid="stMarkdownContainer"] small {{ color: var(--wv-muted) !important; }}
        [data-testid="stMetric"], [data-testid="stExpander"], [data-testid="stForm"],
        [data-testid="stVerticalBlockBorderWrapper"] {{
            background: var(--wv-surface); border: 1px solid var(--wv-border);
            border-radius: var(--wv-radius-md); box-shadow: 0 1px 2px var(--wv-shadow);
        }}
        [data-testid="stMetric"] {{
            padding: 15px 16px 16px;
            border-top: 3px solid var(--wv-accent);
            min-height: 108px;
        }}
        [data-testid="stMetricLabel"] {{
            color: var(--wv-muted) !important; font-size: .78rem !important;
            font-weight: 600 !important; letter-spacing: .01em;
        }}
        [data-testid="stMetricValue"] {{
            color: var(--wv-text) !important; font-size: 1.72rem !important;
            font-weight: 680 !important; letter-spacing: -.035em;
            font-variant-numeric: tabular-nums;
        }}
        [data-testid="stMetricDelta"] {{ font-size: .78rem !important; }}
        [data-testid="stDataFrame"], [data-testid="stTable"] {{
            border: 1px solid var(--wv-border); border-radius: var(--wv-radius-md);
            overflow: hidden; background: var(--wv-surface);
        }}
        [data-testid="stDataFrame"] [role="grid"] {{ font-variant-numeric: tabular-nums; }}
        [data-baseweb="input"] > div, [data-baseweb="select"] > div,
        [data-baseweb="textarea"], [data-testid="stTextInput"] input,
        [data-testid="stNumberInput"] input, [data-testid="stTextArea"] textarea {{
            background: var(--wv-input) !important; color: var(--wv-text) !important;
            border: 1px solid #C9D6D1 !important; border-radius: var(--wv-radius-sm);
            box-shadow: none !important;
        }}
        [data-baseweb="input"] > div:focus-within,
        [data-baseweb="select"] > div:focus-within,
        [data-baseweb="textarea"]:focus-within {{
            border-color: var(--wv-accent) !important;
            box-shadow: 0 0 0 2px rgba(8, 127, 120, .14) !important;
        }}
        [data-testid="stButton"] button, [data-testid="stDownloadButton"] button,
        [data-testid="stFormSubmitButton"] button {{
            min-height: 2.45rem; border-radius: var(--wv-radius-sm);
            font-weight: 620; transition: background-color 140ms ease,
            border-color 140ms ease, color 140ms ease, transform 140ms ease;
        }}
        [data-testid="stButton"] button[kind="primary"],
        [data-testid="stFormSubmitButton"] button[kind="primary"] {{
            background: var(--wv-accent); border-color: var(--wv-accent); color: #FFFFFF;
        }}
        [data-testid="stButton"] button[kind="primary"]:hover,
        [data-testid="stFormSubmitButton"] button[kind="primary"]:hover {{
            background: var(--wv-accent-strong); border-color: var(--wv-accent-strong);
        }}
        [data-testid="stButton"] button[kind="secondary"],
        [data-testid="stDownloadButton"] button {{
            background: var(--wv-surface); color: var(--wv-text);
            border-color: var(--wv-border);
        }}
        [data-testid="stButton"] button:focus-visible,
        [data-testid="stDownloadButton"] button:focus-visible {{
            outline: 3px solid rgba(8, 127, 120, .28); outline-offset: 2px;
        }}
        [data-testid="stTabs"] [role="tablist"] {{
            gap: 5px; border-bottom: 1px solid var(--wv-border);
        }}
        [data-testid="stTabs"] button[role="tab"] {{
            padding: 10px 13px; color: var(--wv-muted); font-weight: 600;
        }}
        [data-testid="stTabs"] button[aria-selected="true"] {{
            color: var(--wv-accent-strong) !important;
            border-bottom: 2px solid var(--wv-accent);
        }}
        [data-testid="stAlert"] {{ border-radius: var(--wv-radius-md); }}
        [data-testid="stMarkdownContainer"] code {{
            background: var(--wv-surface-soft); color: var(--wv-accent-strong);
            border: 1px solid var(--wv-border); border-radius: 4px;
        }}
        .wv-page-header {{
            padding: 0 0 1rem; margin: 0 0 1.35rem;
            border-bottom: 1px solid var(--wv-border);
        }}
        .wv-page-header h1 {{
            margin: 0 0 .34rem !important; color: var(--wv-text) !important;
            font-size: 1.82rem !important; font-weight: 680 !important;
            letter-spacing: -.035em;
        }}
        .wv-page-header p {{
            margin: 0 !important; color: var(--wv-muted) !important;
            font-size: .9rem !important; max-width: 76ch;
        }}
        [data-testid="stSidebar"] .wv-brand {{
            padding: 10px 9px 17px; margin-bottom: 10px;
            border-bottom: 1px solid var(--wv-border);
        }}
        [data-testid="stSidebar"] .wv-brand-mark {{
            display: inline-flex; align-items: center; justify-content: center;
            width: 31px; height: 31px; margin-right: 9px;
            border-radius: 9px; background: var(--wv-accent-soft);
            color: var(--wv-accent-strong); font-size: 17px; font-weight: 750;
            vertical-align: middle;
        }}
        [data-testid="stSidebar"] .wv-brand-name {{
            display: inline-block; color: var(--wv-text); font-size: 1.02rem;
            font-weight: 720; letter-spacing: -.025em; vertical-align: middle;
        }}
        [data-testid="stSidebar"] .wv-brand-description {{
            margin: 7px 0 0 41px; color: var(--wv-sidebar-muted);
            font-size: .66rem; font-weight: 650; letter-spacing: .09em;
        }}
        [data-testid="stSidebar"] .nav-heading {{
            color: var(--wv-sidebar-muted); font-size: .66rem;
            font-weight: 750; letter-spacing: .105em; margin: 17px 0 6px 10px;
        }}
        [data-testid="stSidebar"] div.stButton {{ margin: 0; padding: 0; }}
        [data-testid="stSidebar"] div.stButton > button {{
            width: 100%; min-height: 39px; height: 39px; padding: 5px 11px;
            margin: 1px 0; border-radius: 8px; box-shadow: none;
            text-align: left; justify-content: flex-start; font-size: .86rem;
            font-weight: 560; transition: background 120ms ease, color 120ms ease,
            border-color 120ms ease;
        }}
        [data-testid="stSidebar"] div.stButton > button[kind="secondary"] {{
            background: transparent; border: 1px solid transparent; color: #50615E;
        }}
        [data-testid="stSidebar"] div.stButton > button[kind="secondary"]:hover {{
            background: var(--wv-hover); border-color: #DCE8E3;
            color: var(--wv-accent-strong);
        }}
        [data-testid="stSidebar"] div.stButton > button[kind="primary"] {{
            background: var(--wv-accent-soft); border: 1px solid #C7E4DE;
            color: var(--wv-accent-strong); font-weight: 700;
            box-shadow: inset 3px 0 0 var(--wv-accent);
        }}
        [data-testid="stSidebar"] div.stButton > button [data-testid="stIconMaterial"] {{
            font-size: 1.08rem; margin-right: .35rem;
        }}
        [data-testid="stSidebar"] hr {{ margin: 12px 0; border-color: var(--wv-border); }}
        [data-testid="stSidebar"] .sidebar-footer {{
            font-size: .72rem; line-height: 1.65; color: var(--wv-sidebar-muted);
        }}
        hr {{ border-color: var(--wv-border) !important; }}
        #MainMenu, footer {{ visibility: hidden; }}
        @media (max-width: 1100px) {{
            .block-container {{ padding: 1.35rem 1.4rem 2.5rem; }}
        }}
        @media (max-width: 700px) {{
            .wv-page-header h1, h1 {{ font-size: 1.5rem !important; }}
            .block-container {{ padding: 1rem .8rem 2rem; }}
            [data-testid="stMetricValue"] {{ font-size: 1.28rem !important; }}
        }}
        @media (max-height: 800px) {{
            [data-testid="stSidebar"] .nav-heading {{ margin-top: 10px; margin-bottom: 3px; }}
            [data-testid="stSidebar"] div.stButton > button {{ min-height: 33px; height: 33px; }}
        }}
        @media (prefers-reduced-motion: reduce) {{
            *, *::before, *::after {{
                scroll-behavior: auto !important; transition-duration: .01ms !important;
                animation-duration: .01ms !important;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
