import streamlit as st


def apply_theme():
    """Apply the shared WiFi Vision Lab visual system."""
    st.markdown(
        """
        <style>
        :root {
            --wv-bg: #F4F7FB;
            --wv-surface: #FFFFFF;
            --wv-surface-soft: #F8FAFD;
            --wv-border: #E4EAF2;
            --wv-text: #17243A;
            --wv-muted: #718096;
            --wv-accent: #2878E8;
            --wv-accent-soft: #EAF2FF;
            --wv-sidebar: #101B2D;
            --wv-sidebar-muted: #91A1B8;
        }

        .stApp {
            background: var(--wv-bg);
            color: var(--wv-text);
        }

        .block-container {
            max-width: 1680px;
            padding: 1.7rem 2.25rem 3rem;
        }

        [data-testid="stHeader"] {
            background: rgba(244, 247, 251, .94);
            border-bottom: 1px solid rgba(228, 234, 242, .8);
        }

        [data-testid="stSidebar"] {
            background: var(--wv-sidebar);
            border-right: 1px solid #1C2A40;
        }

        [data-testid="stSidebar"] > div:first-child {
            background: var(--wv-sidebar);
        }

        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
            color: var(--wv-sidebar-muted);
        }

        h1, h2, h3, h4 {
            color: var(--wv-text) !important;
            letter-spacing: -.035em;
            font-weight: 720 !important;
        }

        h1 { font-size: 1.9rem !important; }
        h2 { font-size: 1.35rem !important; }
        h3 { font-size: 1.08rem !important; }

        [data-testid="stCaptionContainer"],
        [data-testid="stWidgetLabel"] p {
            color: var(--wv-muted) !important;
        }

        [data-testid="stMetric"] {
            background: var(--wv-surface);
            border: 1px solid var(--wv-border);
            border-radius: 14px;
            padding: 17px 19px;
            box-shadow: 0 5px 18px rgba(25, 48, 82, .045);
            transition: border-color .16s ease, box-shadow .16s ease,
                        transform .16s ease;
        }

        [data-testid="stMetric"]:hover {
            border-color: #C9D9F0;
            box-shadow: 0 8px 22px rgba(25, 48, 82, .075);
            transform: translateY(-1px);
        }

        [data-testid="stMetricLabel"] {
            color: var(--wv-muted) !important;
            font-size: .8rem !important;
            font-weight: 650 !important;
        }

        [data-testid="stMetricValue"] {
            color: var(--wv-text) !important;
            font-size: 1.75rem !important;
            font-weight: 780 !important;
            letter-spacing: -.04em;
        }

        [data-testid="stDataFrame"],
        [data-testid="stTable"] {
            background: var(--wv-surface);
            border: 1px solid var(--wv-border);
            border-radius: 12px;
            overflow: hidden;
        }

        [data-testid="stDataFrame"] [role="columnheader"] {
            font-weight: 700 !important;
        }

        [data-testid="stDataFrame"] [role="row"]:hover {
            background: #F3F7FD;
        }

        [data-baseweb="input"] > div,
        [data-baseweb="select"] > div,
        [data-baseweb="textarea"] {
            background: #FFFFFF;
            border: 1px solid #D6DFEB;
            border-radius: 9px;
            box-shadow: none;
        }

        [data-baseweb="input"] > div:focus-within,
        [data-baseweb="select"] > div:focus-within,
        [data-baseweb="textarea"]:focus-within {
            border-color: var(--wv-accent);
            box-shadow: 0 0 0 1px var(--wv-accent);
        }

        .stButton > button,
        .stDownloadButton > button {
            min-height: 2.45rem;
            border-radius: 9px;
            font-weight: 650;
            transition: background .15s ease, border-color .15s ease,
                        box-shadow .15s ease;
        }

        .stButton > button[kind="primary"] {
            background: var(--wv-accent);
            border-color: var(--wv-accent);
            color: #FFFFFF;
            box-shadow: 0 3px 9px rgba(40, 120, 232, .18);
        }

        .stButton > button[kind="primary"]:hover {
            background: #1F67CD;
            border-color: #1F67CD;
            color: #FFFFFF;
            box-shadow: 0 5px 14px rgba(40, 120, 232, .23);
        }

        .stButton > button[kind="secondary"]:hover,
        .stDownloadButton > button:hover {
            border-color: #9CB9E2;
            color: #1F67CD;
            background: #F3F7FD;
        }

        [data-testid="stTabs"] [role="tablist"] {
            gap: 7px;
            border-bottom: 1px solid var(--wv-border);
        }

        [data-testid="stTabs"] button[role="tab"] {
            padding: 10px 14px;
            color: var(--wv-muted);
            font-weight: 650;
        }

        [data-testid="stTabs"] button[aria-selected="true"] {
            color: var(--wv-accent) !important;
            border-bottom: 2px solid var(--wv-accent);
        }

        [data-testid="stExpander"] {
            background: var(--wv-surface);
            border: 1px solid var(--wv-border);
            border-radius: 12px;
        }

        [data-testid="stAlert"] {
            border-radius: 10px;
        }

        [data-testid="stMarkdownContainer"] code {
            background: #EAF0F8;
            color: #205EAD;
            border-radius: 5px;
        }

        .wv-page-header {
            padding: 0 0 1.1rem;
            margin: 0 0 1.25rem;
            border-bottom: 1px solid var(--wv-border);
        }

        .wv-page-header h1 {
            margin: 0 0 .35rem !important;
            color: var(--wv-text) !important;
            font-size: 1.9rem !important;
            font-weight: 760 !important;
            letter-spacing: -.045em !important;
        }

        .wv-page-header p {
            margin: 0 !important;
            color: var(--wv-muted) !important;
            font-size: .92rem !important;
            line-height: 1.55;
        }

        [data-testid="stVerticalBlock"] {
            gap: .85rem;
        }

        hr {
            border-color: var(--wv-border) !important;
        }

        #MainMenu, footer {
            visibility: hidden;
        }

        @media (max-width: 900px) {
            .block-container {
                padding: 1.25rem 1rem 2rem;
            }
        }

        @media (max-width: 700px) {
            .wv-page-header h1, h1 {
                font-size: 1.5rem !important;
            }
            .block-container {
                padding-left: .8rem;
                padding-right: .8rem;
            }
            [data-testid="stMetricValue"] {
                font-size: 1.35rem !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
