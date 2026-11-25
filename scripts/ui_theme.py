import streamlit as st


THEMES = {
    "dark": {
        "bg": "#0B1220", "surface": "#111C2E", "surface_soft": "#16243A",
        "border": "#26364E", "text": "#E8EEF7", "muted": "#9AAAC0",
        "accent": "#4A9BFF", "accent_soft": "#1C3556", "sidebar": "#08111F",
        "sidebar_muted": "#91A1B8", "hover": "#1B2A41", "input": "#101B2D",
        "header": "rgba(11, 18, 32, .94)", "shadow": "rgba(0, 0, 0, .18)",
    },
    "light": {
        "bg": "#F4F7FB", "surface": "#FFFFFF", "surface_soft": "#F8FAFD",
        "border": "#E4EAF2", "text": "#17243A", "muted": "#718096",
        "accent": "#2878E8", "accent_soft": "#EAF2FF", "sidebar": "#101B2D",
        "sidebar_muted": "#91A1B8", "hover": "#1B2A41", "input": "#FFFFFF",
        "header": "rgba(244, 247, 251, .94)", "shadow": "rgba(25, 48, 82, .06)",
    },
}


def get_theme_palette(theme):
    """Return the palette for a supported theme name."""
    return THEMES.get(str(theme).lower(), THEMES["dark"]).copy()


def apply_theme(theme="dark"):
    """Apply the selected WiFi Vision Lab visual system."""
    palette = get_theme_palette(theme)
    variables = "\n".join(
        f"    --wv-{name.replace('_', '-')}: {value};"
        for name, value in palette.items()
    )
    color_scheme = "dark" if str(theme).lower() == "dark" else "light"
    st.markdown(
        f"""
        <style>
        :root {{
{variables}
            color-scheme: {color_scheme};
        }}
        .stApp, [data-testid="stAppViewContainer"] {{ background: var(--wv-bg); color: var(--wv-text); }}
        .block-container {{ max-width: 1680px; padding: 1.7rem 2.25rem 3rem; }}
        [data-testid="stHeader"] {{ background: var(--wv-header); border-bottom: 1px solid var(--wv-border); }}
        [data-testid="stSidebar"], [data-testid="stSidebar"] > div:first-child {{ background: var(--wv-sidebar); border-right: 1px solid var(--wv-border); }}
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {{ color: var(--wv-sidebar-muted); }}
        h1, h2, h3, h4, p, label, li {{ color: var(--wv-text); }}
        h1, h2, h3, h4 {{ letter-spacing: -.035em; font-weight: 720 !important; }}
        h1 {{ font-size: 1.9rem !important; }} h2 {{ font-size: 1.35rem !important; }} h3 {{ font-size: 1.08rem !important; }}
        [data-testid="stCaptionContainer"], [data-testid="stWidgetLabel"] p, [data-testid="stMarkdownContainer"] small {{ color: var(--wv-muted) !important; }}
        [data-testid="stMetric"], [data-testid="stDataFrame"], [data-testid="stTable"], [data-testid="stExpander"], [data-testid="stForm"] {{
            background: var(--wv-surface); border: 1px solid var(--wv-border); border-radius: 14px; box-shadow: 0 5px 18px var(--wv-shadow);
        }}
        [data-testid="stMetric"] {{ padding: 17px 19px; transition: border-color .16s ease, box-shadow .16s ease, transform .16s ease; }}
        [data-testid="stMetric"]:hover {{ border-color: var(--wv-accent); transform: translateY(-1px); }}
        [data-testid="stMetricLabel"] {{ color: var(--wv-muted) !important; font-size: .8rem !important; font-weight: 650 !important; }}
        [data-testid="stMetricValue"] {{ color: var(--wv-text) !important; font-size: 1.75rem !important; font-weight: 780 !important; letter-spacing: -.04em; }}
        [data-testid="stDataFrame"], [data-testid="stTable"] {{ overflow: hidden; }}
        [data-testid="stDataFrame"] [role="columnheader"] {{ font-weight: 700 !important; }}
        [data-baseweb="input"] > div, [data-baseweb="select"] > div, [data-baseweb="textarea"],
        [data-testid="stTextInput"] input, [data-testid="stNumberInput"] input, [data-testid="stTextArea"] textarea {{
            background: var(--wv-input) !important; color: var(--wv-text) !important; border: 1px solid var(--wv-border) !important; border-radius: 9px; box-shadow: none;
        }}
        [data-baseweb="input"] > div:focus-within, [data-baseweb="select"] > div:focus-within, [data-baseweb="textarea"]:focus-within {{ border-color: var(--wv-accent) !important; box-shadow: 0 0 0 1px var(--wv-accent); }}
        [data-testid="stButton"] button, [data-testid="stDownloadButton"] button {{ min-height: 2.45rem; border-radius: 9px; font-weight: 650; transition: background .15s ease, border-color .15s ease, box-shadow .15s ease; }}
        [data-testid="stButton"] button[kind="primary"] {{ background: var(--wv-accent); border-color: var(--wv-accent); color: #FFFFFF; box-shadow: 0 3px 9px var(--wv-shadow); }}
        [data-testid="stButton"] button[kind="primary"]:hover {{ filter: brightness(1.08); }}
        [data-testid="stButton"] button[kind="secondary"], [data-testid="stDownloadButton"] button {{ background: var(--wv-surface); color: var(--wv-text); border-color: var(--wv-border); }}
        [data-testid="stButton"] button[kind="secondary"]:hover, [data-testid="stDownloadButton"] button:hover {{ border-color: var(--wv-accent); color: var(--wv-accent); }}
        [data-testid="stTabs"] [role="tablist"] {{ gap: 7px; border-bottom: 1px solid var(--wv-border); }}
        [data-testid="stTabs"] button[role="tab"] {{ padding: 10px 14px; color: var(--wv-muted); font-weight: 650; }}
        [data-testid="stTabs"] button[aria-selected="true"] {{ color: var(--wv-accent) !important; border-bottom: 2px solid var(--wv-accent); }}
        [data-testid="stAlert"] {{ border-radius: 10px; }}
        [data-testid="stMarkdownContainer"] code {{ background: var(--wv-surface-soft); color: var(--wv-accent); border-radius: 5px; }}
        .wv-page-header {{ padding: 0 0 1.1rem; margin: 0 0 1.25rem; border-bottom: 1px solid var(--wv-border); }}
        .wv-page-header h1 {{ margin: 0 0 .35rem !important; color: var(--wv-text) !important; font-size: 1.9rem !important; font-weight: 760 !important; letter-spacing: -.045em !important; }}
        .wv-page-header p {{ margin: 0 !important; color: var(--wv-muted) !important; font-size: .92rem !important; line-height: 1.55; }}
        hr {{ border-color: var(--wv-border) !important; }} #MainMenu, footer {{ visibility: hidden; }}
        @media (max-width: 900px) {{ .block-container {{ padding: 1.25rem 1rem 2rem; }} }}
        @media (max-width: 700px) {{ .wv-page-header h1, h1 {{ font-size: 1.5rem !important; }} .block-container {{ padding-left: .8rem; padding-right: .8rem; }} [data-testid="stMetricValue"] {{ font-size: 1.35rem !important; }} }}
        </style>
        """,
        unsafe_allow_html=True,
    )
