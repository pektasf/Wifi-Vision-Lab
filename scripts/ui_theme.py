import streamlit as st


LIGHT_PALETTE = {
    "bg": "#F5F7FA", "surface": "#FFFFFF", "surface_soft": "#F8FAFC",
    "border": "#E6EAF0", "text": "#182230", "muted": "#687586",
    "accent": "#3478D4", "accent_soft": "#EAF2FF", "sidebar": "#FFFFFF",
    "sidebar_muted": "#718096", "hover": "#F1F5F9", "input": "#FFFFFF",
    "header": "rgba(255, 255, 255, .92)", "shadow": "rgba(15, 23, 42, .035)",
}


def get_theme_palette(theme="light"):
    """Return the single supported light palette as a copy."""
    return LIGHT_PALETTE.copy()


def apply_theme(theme="light"):
    """Apply the restrained, light-only WiFi Vision Lab design system."""
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
        }}
        .stApp, [data-testid="stAppViewContainer"] {{ background: var(--wv-bg); color: var(--wv-text); }}
        .block-container {{ max-width: 1480px; padding: 1.5rem 2rem 3rem; }}
        [data-testid="stHeader"] {{ background: var(--wv-header); border-bottom: 1px solid var(--wv-border); }}
        [data-testid="stSidebar"], [data-testid="stSidebar"] > div:first-child {{ background: #FFFFFF; border-right: 1px solid var(--wv-border); }}
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {{ color: var(--wv-muted); }}
        h1, h2, h3, h4, p, label, li {{ color: var(--wv-text); }}
        h1, h2, h3, h4 {{ letter-spacing: -.025em; font-weight: 700 !important; }}
        h1 {{ font-size: 1.8rem !important; }} h2 {{ font-size: 1.3rem !important; }} h3 {{ font-size: 1.05rem !important; }}
        [data-testid="stCaptionContainer"], [data-testid="stWidgetLabel"] p, [data-testid="stMarkdownContainer"] small {{ color: var(--wv-muted) !important; }}
        [data-testid="stMetric"], [data-testid="stExpander"], [data-testid="stForm"] {{ background: #FFFFFF; border: 1px solid var(--wv-border); border-radius: 12px; box-shadow: 0 2px 8px var(--wv-shadow); }}
        [data-testid="stMetric"] {{ padding: 14px 16px; }}
        [data-testid="stMetricLabel"] {{ color: var(--wv-muted) !important; font-size: .8rem !important; font-weight: 600 !important; }}
        [data-testid="stMetricValue"] {{ color: var(--wv-text) !important; font-size: 1.55rem !important; font-weight: 720 !important; letter-spacing: -.03em; }}
        [data-testid="stDataFrame"], [data-testid="stTable"] {{ border: 1px solid var(--wv-border); border-radius: 10px; overflow: hidden; }}
        [data-baseweb="input"] > div, [data-baseweb="select"] > div, [data-baseweb="textarea"], [data-testid="stTextInput"] input, [data-testid="stNumberInput"] input, [data-testid="stTextArea"] textarea {{ background: #FFFFFF !important; color: var(--wv-text) !important; border: 1px solid #D9E0E8 !important; border-radius: 8px; box-shadow: none; }}
        [data-baseweb="input"] > div:focus-within, [data-baseweb="select"] > div:focus-within, [data-baseweb="textarea"]:focus-within {{ border-color: var(--wv-accent) !important; box-shadow: 0 0 0 1px var(--wv-accent); }}
        [data-testid="stButton"] button, [data-testid="stDownloadButton"] button {{ min-height: 2.35rem; border-radius: 8px; font-weight: 600; }}
        [data-testid="stButton"] button[kind="primary"] {{ background: var(--wv-accent); border-color: var(--wv-accent); color: #FFFFFF; }}
        [data-testid="stButton"] button[kind="secondary"], [data-testid="stDownloadButton"] button {{ background: #FFFFFF; color: var(--wv-text); border-color: var(--wv-border); }}
        [data-testid="stButton"] button[kind="secondary"]:hover, [data-testid="stDownloadButton"] button:hover {{ border-color: var(--wv-accent); color: var(--wv-accent); }}
        [data-testid="stTabs"] [role="tablist"] {{ gap: 4px; border-bottom: 1px solid var(--wv-border); }}
        [data-testid="stTabs"] button[role="tab"] {{ padding: 9px 12px; color: var(--wv-muted); font-weight: 600; }}
        [data-testid="stTabs"] button[aria-selected="true"] {{ color: var(--wv-accent) !important; border-bottom: 2px solid var(--wv-accent); }}
        [data-testid="stAlert"] {{ border-radius: 9px; }}
        [data-testid="stMarkdownContainer"] code {{ background: var(--wv-surface-soft); color: var(--wv-accent); border-radius: 4px; }}
        .wv-page-header {{ padding: 0 0 .9rem; margin: 0 0 1.1rem; border-bottom: 1px solid var(--wv-border); }}
        .wv-page-header h1 {{ margin: 0 0 .3rem !important; color: var(--wv-text) !important; font-size: 1.8rem !important; font-weight: 740 !important; }}
        .wv-page-header p {{ margin: 0 !important; color: var(--wv-muted) !important; font-size: .9rem !important; }}
        [data-testid="stVerticalBlockBorderWrapper"] {{ border-color: var(--wv-border) !important; border-radius: 12px !important; }}
        hr {{ border-color: var(--wv-border) !important; }} #MainMenu, footer {{ visibility: hidden; }}
        @media (max-width: 900px) {{ .block-container {{ padding: 1rem 1rem 2rem; }} }}
        @media (max-width: 700px) {{ .wv-page-header h1, h1 {{ font-size: 1.5rem !important; }} .block-container {{ padding-left: .75rem; padding-right: .75rem; }} [data-testid="stMetricValue"] {{ font-size: 1.25rem !important; }} }}
        </style>
        """, unsafe_allow_html=True,
    )
