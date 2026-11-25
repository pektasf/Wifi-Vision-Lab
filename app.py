from pathlib import Path
import os
import subprocess
import sys

import pandas as pd
import streamlit as st
from scripts.ui_theme import apply_theme

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "processed"




st.set_page_config(
    page_title="WiFi Vision Lab",
    page_icon="W",
    layout="wide",
    initial_sidebar_state="expanded"
)

apply_theme()



def apply_design():
    st.markdown("""
    <style>
    :root {
        --wv-bg: #F3F6FB;
        --wv-surface: #FFFFFF;
        --wv-border: #E2E8F0;
        --wv-text: #17243A;
        --wv-muted: #64748B;
        --wv-primary: #2563EB;
        --wv-primary-soft: #EFF6FF;
    }

    .stApp {
        background: var(--wv-bg);
        color: var(--wv-text);
    }

    .block-container {
        max-width: 1600px;
        padding-top: 1.5rem;
        padding-bottom: 3rem;
    }

    [data-testid="stSidebar"] {
        background: #FFFFFF;
        border-right: 1px solid var(--wv-border);
    }

    [data-testid="stSidebar"] > div:first-child {
        padding-top: 1.2rem;
    }

    [data-testid="stSidebar"] h1 {
        color: #14213D;
        font-size: 1.35rem;
        font-weight: 800;
        letter-spacing: -0.5px;
    }

    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
        color: var(--wv-muted);
        font-size: 0.78rem;
    }

    [data-testid="stSidebar"] [role="radiogroup"] {
        gap: 5px;
    }

    [data-testid="stSidebar"] [role="radiogroup"] label {
        padding: 9px 12px;
        border-radius: 9px;
        transition: background .15s ease;
        border: 1px solid transparent;
    }

    [data-testid="stSidebar"] [role="radiogroup"] label:hover {
        background: #F1F5F9;
    }

    [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
        background: var(--wv-primary-soft);
        border-color: #BFDBFE;
        color: #1D4ED8;
        font-weight: 700;
    }

    h1, h2, h3 {
        color: #17243A !important;
        letter-spacing: -0.35px;
    }

    h1 {
        font-size: 1.9rem !important;
        font-weight: 800 !important;
    }

    h2 {
        font-size: 1.35rem !important;
        font-weight: 750 !important;
    }

    h3 {
        font-size: 1.05rem !important;
        font-weight: 700 !important;
    }

    p, label, span, div {
        text-rendering: optimizeLegibility;
    }

    [data-testid="stMetric"] {
        background: #FFFFFF;
        border: 1px solid var(--wv-border);
        border-radius: 12px;
        padding: 16px 18px;
        box-shadow: 0 2px 5px rgba(15, 23, 42, .025);
    }

    [data-testid="stMetricLabel"] {
        color: #64748B !important;
        font-size: .82rem !important;
        font-weight: 600 !important;
    }

    [data-testid="stMetricValue"] {
        color: #17243A !important;
        font-size: 1.7rem !important;
        font-weight: 800 !important;
    }

    [data-testid="stDataFrame"],
    [data-testid="stTable"] {
        border: 1px solid var(--wv-border);
        border-radius: 10px;
        overflow: hidden;
        background: #FFFFFF;
    }

    [data-testid="stTextInput"] input,
    [data-testid="stNumberInput"] input,
    [data-testid="stSelectbox"] div[data-baseweb="select"] > div {
        border-radius: 8px;
        border-color: #CBD5E1;
        background: #FFFFFF;
    }

    [data-testid="stButton"] button,
    [data-testid="stDownloadButton"] button {
        border-radius: 8px;
        font-weight: 650;
        min-height: 40px;
        transition: all .15s ease;
    }

    [data-testid="stButton"] button[kind="primary"] {
        background: var(--wv-primary);
        border-color: var(--wv-primary);
        color: #FFFFFF;
    }

    [data-testid="stButton"] button:hover,
    [data-testid="stDownloadButton"] button:hover {
        border-color: var(--wv-primary);
        color: var(--wv-primary);
    }

    [data-testid="stTabs"] [role="tab"] {
        font-weight: 650;
        padding: 10px 15px;
    }

    [data-testid="stExpander"] {
        background: #FFFFFF;
        border: 1px solid var(--wv-border);
        border-radius: 10px;
    }

    hr {
        border-color: var(--wv-border);
    }

    [data-testid="stAlert"] {
        border-radius: 10px;
    }

    @media (max-width: 768px) {
        .block-container {
            padding: 1rem .8rem 2rem .8rem;
        }

        h1 {
            font-size: 1.55rem !important;
        }

        [data-testid="stMetricValue"] {
            font-size: 1.35rem !important;
        }
    }
    
    /* Sidebar: ekran yuksekligine uyumlu, kompakt navigasyon */
    [data-testid="stSidebar"] > div:first-child {
        padding-top: 0.35rem !important;
        padding-bottom: 0.5rem !important;
    }

    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
        gap: 0.45rem;
    }

    [data-testid="stSidebar"] h1 {
        font-size: 1.15rem !important;
        line-height: 1.25 !important;
        margin-bottom: 0 !important;
    }

    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
        margin-bottom: 0.25rem !important;
        font-size: 0.72rem !important;
    }

    [data-testid="stSidebar"] [role="radiogroup"] {
        gap: 2px !important;
    }

    [data-testid="stSidebar"] [role="radiogroup"] label {
        min-height: 0 !important;
        padding: 5px 9px !important;
        margin: 0 !important;
        border-radius: 7px !important;
        font-size: 0.86rem !important;
        line-height: 1.2 !important;
    }

    [data-testid="stSidebar"] [role="radiogroup"] label p {
        margin: 0 !important;
        line-height: 1.2 !important;
    }

    [data-testid="stSidebar"] [data-testid="stButton"] button {
        min-height: 36px !important;
        padding: 5px 10px !important;
        font-size: 0.84rem !important;
    }

    [data-testid="stSidebar"] hr {
        margin: 0.35rem 0 !important;
    }

    @media (max-height: 850px) {
        [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
            gap: 0.25rem !important;
        }

        [data-testid="stSidebar"] [role="radiogroup"] label {
            padding-top: 3px !important;
            padding-bottom: 3px !important;
        }
    }

    @media (max-height: 700px) {
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
            font-size: 0.68rem !important;
        }

        [data-testid="stSidebar"] [role="radiogroup"] label {
            font-size: 0.81rem !important;
        }
    }

    </style>
    """, unsafe_allow_html=True)




def load(filename):
    path = DATA / filename
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return pd.DataFrame()


def page_header(title, description=""):
    import html

    safe_title = html.escape(str(title))
    safe_description = html.escape(str(description))

    st.markdown(
        f"""
        <div class="wv-page-header">
            <h1>{safe_title}</h1>
            {"<p>" + safe_description + "</p>" if description else ""}
        </div>
        """,
        unsafe_allow_html=True
    )



def run_scan():
    main_file = ROOT / "main.py"

    if not main_file.exists():
        st.error("main.py bulunamadı. Tarama başlatılamadı.")
        return

    custom_cidr = str(st.session_state.get("scan_cidr", "")).strip()
    approved = bool(st.session_state.get("scan_approved", False))
    confirmation = str(st.session_state.get("scan_confirmation", "")).strip()

    if custom_cidr and not approved:
        st.error("Özel ağ taraması için yetki onayını işaretlemelisiniz.")
        return
    if custom_cidr and confirmation != custom_cidr:
        st.error("Onay alanına özel CIDR değerini aynen tekrar yazmalısınız.")
        return

    scan_env = os.environ.copy()
    for key in (
        "WIFI_VISION_SCAN_CIDR",
        "WIFI_VISION_SCAN_APPROVED",
        "WIFI_VISION_SCAN_CONFIRMATION",
    ):
        scan_env.pop(key, None)

    if custom_cidr:
        scan_env["WIFI_VISION_SCAN_CIDR"] = custom_cidr
        scan_env["WIFI_VISION_SCAN_APPROVED"] = "1"
        scan_env["WIFI_VISION_SCAN_CONFIRMATION"] = confirmation

    with st.spinner("Ağ taraması ve analiz çalışıyor..."):
        try:
            result = subprocess.run(
                [sys.executable, str(main_file)],
                cwd=ROOT,
                env=scan_env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace"
            )
        except FileNotFoundError:
            st.error("Python çalıştırıcısı bulunamadı. Uygulama ortamını kontrol edin.")
            return
        except subprocess.TimeoutExpired:
            st.error("Tarama işlemi zaman aşımına uğradı.")
            return
        except OSError as exc:
            st.error(f"Tarama işlemi başlatılamadı: {exc}")
            return

    if result.returncode == 0:
        st.success("Tarama ve analiz tamamlandı.")
    else:
        st.error("Tarama sırasında hata oluştu. Ayrıntılar aşağıda.")

    if result.stdout:
        with st.expander("İşlem çıktıları"):
            st.code(result.stdout)

    if result.stderr:
        with st.expander("Hata ayrıntıları"):
            st.code(result.stderr)

    st.rerun()


def show_table(data, height=450):
    if data is None or data.empty:
        st.info("Gosterilecek veri bulunamadi.")
        return

    row_count = len(data)
    table_height = max(180, min(int(height), 520))

    st.dataframe(
        data,
        width="stretch",
        hide_index=True,
        height=table_height
    )



def filtered_table(data, key, allow_status=True):
    if data is None or data.empty:
        st.info("Bu bolumde henuz veri bulunmuyor.")
        return

    st.caption(f"Toplam {len(data):,} kayit")

    c1, c2 = st.columns([2.2, 1])

    with c1:
        search = st.text_input(
            "Kayitlarda ara",
            placeholder="IP, MAC, cihaz adi veya anahtar kelime",
            key=key + "_search"
        )

    with c2:
        status_values = []
        if allow_status and "status" in data.columns:
            status_values = sorted(
                value for value in data["status"].astype(str).unique()
                if value.strip()
            )

        if status_values:
            status_options = ["Tum durumlar"] + status_values
            selected_status = st.selectbox(
                "Durum filtresi",
                status_options,
                key=key + "_status"
            )
        else:
            selected_status = "Tum durumlar"

    result = data.copy()

    if search.strip():
        mask = result.astype(str).apply(
            lambda col: col.str.contains(
                search.strip(),
                case=False,
                na=False,
                regex=False
            )
        ).any(axis=1)
        result = result[mask]

    if selected_status != "Tum durumlar" and "status" in result.columns:
        result = result[result["status"].astype(str) == selected_status]

    st.caption(f"{len(result):,} kayit gosteriliyor.")

    if result.empty:
        st.warning("Aramanizla eslesen kayit bulunamadi.")
        return

    show_table(result)

    st.download_button(
        "Filtrelenmis CSV indir",
        result.to_csv(index=False).encode("utf-8-sig"),
        file_name=key + ".csv",
        mime="text/csv",
        key=key + "_download"
    )



def dashboard_page():
    inventory = load("device_inventory.csv")
    profiles = load("device_profiles.csv")
    events = load("device_events.csv")
    classification = load("device_classification.csv")

    st.markdown(
        "<div style='color:#38bdf8;font-size:12px;font-weight:700;"
        "letter-spacing:1.5px;margin-bottom:8px'>NETWORK OPERATIONS</div>",
        unsafe_allow_html=True
    )
    st.title("Ag Kontrol Merkezi")
    st.caption("Yerel ag envanteri, cihaz durumu ve kesif ozeti")

    total = len(inventory)
    responding = 0
    if "status" in inventory.columns:
        responding = int(
            inventory["status"].astype(str).str.lower()
            .isin(["responding", "online", "active"]).sum()
        )

    offline = max(total - responding, 0)
    profile_count = len(profiles)
    event_count = len(events)

    st.markdown("### Ag genel bakis")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Toplam cihaz", f"{total:,}")
    c2.metric("Yan\u0131t veren", f"{responding:,}")
    c3.metric("Cihaz profili", f"{profile_count:,}")
    c4.metric("Kayitli olay", f"{event_count:,}")

    st.markdown("---")
    left, right = st.columns([1.15, 1])

    with left:
        st.markdown("### Cihaz durum dagilimi")
        if "status" in inventory.columns and not inventory.empty:
            status_data = (
                inventory["status"].replace("", "Bilinmiyor")
                .value_counts().rename_axis("Durum")
                .reset_index(name="Cihaz")
                .set_index("Durum")
            )
            st.bar_chart(status_data, height=250)
        else:
            st.info("Durum dagilimi icin yeterli veri yok.")

    with right:
        st.markdown("### Ag kesif bilgisi")
        if not inventory.empty:
            if "adapter" in inventory.columns:
                adapter_count = inventory["adapter"].replace(
                    "", "Bilinmiyor"
                ).nunique()
                st.metric("Kesifte gorulen ag arayuzu", adapter_count)
            if "subnet" in inventory.columns:
                subnet_count = inventory["subnet"].replace(
                    "", "Bilinmiyor"
                ).nunique()
                st.metric("Gorulen alt ag", subnet_count)
            if "gateway" in inventory.columns:
                gateways = inventory["gateway"].replace("", "-").unique()
                st.write("**Varsayilan ag gecidi**")
                st.code(", ".join(gateways[:5]))
        else:
            st.info("Henuz cihaz envanteri bulunmuyor.")

    st.markdown("---")
    st.markdown("### Uretici dagilimi")
    if "vendor" in classification.columns and not classification.empty:
        vendor_data = (
            classification["vendor"].replace("", "Bilinmiyor")
            .value_counts().head(8).rename_axis("Uretici")
            .reset_index(name="Cihaz")
            .set_index("Uretici")
        )
        st.bar_chart(vendor_data, height=240)
    elif "vendor" in inventory.columns and not inventory.empty:
        vendor_data = (
            inventory["vendor"].replace("", "Bilinmiyor")
            .value_counts().head(8).rename_axis("Uretici")
            .reset_index(name="Cihaz")
            .set_index("Uretici")
        )
        st.bar_chart(vendor_data, height=240)
    else:
        st.info("Uretici dagilimi icin siniflandirma verisi bulunamadi.")

    st.markdown("---")
    st.markdown("### Son kesfedilen cihazlar")
    if not inventory.empty:
        recent = inventory.copy()
        if "timestamp" in recent.columns:
            recent = recent.sort_values("timestamp", ascending=False)

        preferred = [
            "timestamp", "ip", "hostname", "mac",
            "status", "gateway", "adapter"
        ]
        visible = [col for col in preferred if col in recent.columns]
        if not visible:
            visible = list(recent.columns[:7])

        st.dataframe(
            recent[visible].head(12),
            width="stretch",
            hide_index=True
        )
    else:
        st.info("Henuz envanter kaydi yok. Yeni kesif baslatabilirsiniz.")


def devices_page():
    inventory = load("device_inventory.csv")

    st.title("Cihaz Envanteri")
    st.caption("Kesfedilen ag cihazlarini ara, filtrele ve incele.")

    if inventory.empty:
        st.info("Henuz cihaz kaydi bulunmuyor. Once ag kesfi yapin.")
        return

    data = inventory.copy()

    for col in ["ip", "mac", "hostname", "status", "gateway", "adapter", "subnet"]:
        if col not in data.columns:
            data[col] = ""

    data["status"] = data["status"].replace("", "Bilinmiyor")

    total = len(data)
    responding = int(
        data["status"].astype(str).str.lower()
        .isin(["responding", "online", "active"]).sum()
    )
    other = total - responding

    a, b, c = st.columns(3)
    a.metric("Toplam cihaz", f"{total:,}")
    b.metric("Yan\u0131t veren", f"{responding:,}")
    c.metric("Di\u011fer / bilinmiyor", f"{other:,}")

    st.markdown("---")
    st.markdown("### Filtreler")

    f1, f2 = st.columns([2, 1])
    with f1:
        search = st.text_input(
            "Cihaz ara",
            placeholder="IP, MAC adresi, cihaz adi veya gateway..."
        )
    with f2:
        statuses = ["Tum durumlar"] + sorted(
            data["status"].astype(str).unique().tolist()
        )
        selected_status = st.selectbox("Durum", statuses)

    filtered = data.copy()

    if selected_status != "Tum durumlar":
        filtered = filtered[
            filtered["status"].astype(str) == selected_status
        ]

    if search.strip():
        term = search.strip().lower()
        mask = filtered.astype(str).apply(
            lambda col: col.str.lower().str.contains(term, regex=False)
        ).any(axis=1)
        filtered = filtered[mask]

    st.markdown(
        f"**{len(filtered):,}** cihaz listeleniyor",
    )

    preferred = [
        "ip", "hostname", "mac", "status",
        "gateway", "adapter", "subnet", "timestamp"
    ]
    visible = [col for col in preferred if col in filtered.columns]

    st.dataframe(
        filtered[visible],
        width="stretch",
        hide_index=True,
        height=420
    )

    st.markdown("---")
    st.markdown("### Cihaz detaylari")

    device_options = filtered["ip"].astype(str).tolist()
    device_options = [x for x in device_options if x.strip()]

    if not device_options:
        st.info("Secilen filtrelere uygun cihaz bulunamadi.")
        return

    selected_ip = st.selectbox("Incelenecek cihaz", device_options)
    selected_rows = data[data["ip"].astype(str) == selected_ip]

    if not selected_rows.empty:
        device = selected_rows.iloc[0]

        d1, d2, d3 = st.columns(3)
        d1.metric("IP adresi", str(device.get("ip", "-")) or "-")
        d2.metric("MAC adresi", str(device.get("mac", "-")) or "-")
        d3.metric("Durum", str(device.get("status", "-")) or "-")

        left, right = st.columns(2)
        with left:
            st.markdown("**Ag bilgileri**")
            st.write("Gateway:", device.get("gateway", "-") or "-")
            st.write("Ag arayuzu:", device.get("adapter", "-") or "-")
            st.write("Alt ag:", device.get("subnet", "-") or "-")

        with right:
            st.markdown("**Cihaz kimligi**")
            st.write("Cihaz adi:", device.get("hostname", "-") or "-")
            st.write("Son kayit:", device.get("timestamp", "-") or "-")

def history_page():
    page_header(
        "Cihaz Ge\u00e7mi\u015fi",
        "Cihazlar\u0131n zaman i\u00e7indeki g\u00f6zlem ve de\u011fi\u015fim kay\u0131tlar\u0131"
    )

    history = load("device_history.csv")
    profiles = load("device_profiles.csv")

    if history.empty:
        st.info("Hen\u00fcz cihaz ge\u00e7mi\u015fi kayd\u0131 bulunmuyor.")
        return

    history = history.copy()

    if "observed_at" in history.columns:
        history["_parsed_time"] = pd.to_datetime(
            history["observed_at"], errors="coerce"
        )
        history = history.sort_values(
            "_parsed_time", ascending=False, na_position="last"
        )

    total_devices = (
        history["identity_key"].nunique()
        if "identity_key" in history.columns else 0
    )

    latest = (
        history["observed_at"].iloc[0]
        if "observed_at" in history.columns and len(history) else "-"
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Toplam g\u00f6zlem", f"{len(history):,}")
    c2.metric("G\u00f6zlemlenen cihaz", f"{total_devices:,}")
    c3.metric("Son g\u00f6zlem", str(latest)[:19])

    st.divider()

    left, right = st.columns([2, 1])

    with left:
        search = st.text_input(
            "Ge\u00e7mi\u015f kay\u0131tlar\u0131nda ara",
            placeholder="IP, MAC veya cihaz ad\u0131",
            key="history_search_v2"
        )

    with right:
        identities = ["T\u00fcm cihazlar"]
        if "identity_key" in history.columns:
            identities += sorted(
                history["identity_key"].astype(str).unique().tolist()
            )
        selected = st.selectbox(
            "Cihaz filtresi", identities, key="history_device_v2"
        )

    result = history.copy()

    if selected != "T\u00fcm cihazlar" and "identity_key" in result.columns:
        result = result[result["identity_key"].astype(str) == selected]

    if search.strip():
        mask = result.astype(str).apply(
            lambda col: col.str.contains(search.strip(), case=False, na=False)
        ).any(axis=1)
        result = result[mask]

    if "_parsed_time" in result.columns:
        result = result.drop(columns=["_parsed_time"])

    st.caption(f"{len(result):,} kay\u0131t listeleniyor")
    st.dataframe(
        result,
        width="stretch",
        hide_index=True,
        height=520
    )

    st.download_button(
        "Ge\u00e7mi\u015f kay\u0131tlar\u0131n\u0131 CSV indir",
        result.to_csv(index=False).encode("utf-8-sig"),
        file_name="cihaz_gecmisi.csv",
        mime="text/csv",
        key="history_export_v2"
    )



def detail_page():
    page_header(
        "Cihaz Detay\u0131",
        "Cihaz kimli\u011fi, s\u0131n\u0131fland\u0131rma, olaylar ve g\u00f6zlem ge\u00e7mi\u015fi"
    )

    profiles = load("device_profiles.csv")
    history = load("device_history.csv")
    events = load("device_events.csv")
    classification = load("device_classification.csv")

    if profiles.empty or "identity_key" not in profiles.columns:
        st.info("Cihaz profili bulunamad\u0131. \u00d6nce cihaz taramas\u0131 yap\u0131n.")
        return

    profiles = profiles.copy()
    profiles["identity_key"] = profiles["identity_key"].astype(str)

    def device_label(identity):
        row = profiles[profiles["identity_key"] == identity].iloc[0]
        parts = [
            str(row.get("current_ip", "")),
            str(row.get("mac", "")),
            str(row.get("hostname", ""))
        ]
        return " | ".join(x for x in parts if x)

    identities = profiles["identity_key"].drop_duplicates().tolist()

    selected = st.selectbox(
        "Cihaz se\u00e7",
        identities,
        format_func=device_label,
        key="detail_device_v2"
    )

    selected_rows = profiles[profiles["identity_key"] == selected]
    if selected_rows.empty:
        st.warning("Se\u00e7ilen cihaz profili bulunamad\u0131.")
        return

    device = selected_rows.iloc[0]

    st.divider()

    a, b, c, d = st.columns(4)
    a.metric("IP adresi", str(device.get("current_ip", "-")) or "-")
    b.metric("MAC adresi", str(device.get("mac", "-")) or "-")
    c.metric("G\u00f6zlem say\u0131s\u0131", str(device.get("observation_count", "0")) or "0")
    d.metric("IP de\u011fi\u015fimi", str(device.get("ip_change_count", "0")) or "0")

    st.subheader("Cihaz kimli\u011fi")

    identity_data = {
        "Alan": [
            "Cihaz ad\u0131", "\u00dcretici", "S\u0131n\u0131fland\u0131rma",
            "Durum", "\u0130lk g\u00f6r\u00fclme", "Son g\u00f6r\u00fclme", "IP ge\u00e7mi\u015fi"
        ],
        "De\u011fer": [
            device.get("hostname", ""),
            device.get("vendor", ""),
            device.get("classification", ""),
            device.get("status", ""),
            device.get("first_seen", ""),
            device.get("last_seen", ""),
            device.get("ip_history", "")
        ]
    }
    st.dataframe(
        pd.DataFrame(identity_data),
        width="stretch",
        hide_index=True
    )

    ip = str(device.get("current_ip", ""))

    if not classification.empty and "ip" in classification.columns:
        class_rows = classification[
            classification["ip"].astype(str) == ip
        ]
    else:
        class_rows = pd.DataFrame()

    if not class_rows.empty:
        st.subheader("S\u0131n\u0131fland\u0131rma ve kan\u0131t")
        st.dataframe(
            class_rows.tail(5),
            width="stretch",
            hide_index=True
        )

    tab_history, tab_events = st.tabs(["G\u00f6zlem ge\u00e7mi\u015fi", "Cihaz olaylar\u0131"])

    with tab_history:
        if "identity_key" in history.columns:
            device_history = history[
                history["identity_key"].astype(str) == selected
            ].copy()
        else:
            device_history = pd.DataFrame()

        if not device_history.empty:
            if "observed_at" in device_history.columns:
                device_history = device_history.sort_values(
                    "observed_at", ascending=False
                )
            st.caption(f"{len(device_history)} g\u00f6zlem kayd\u0131")
            st.dataframe(
                device_history,
                width="stretch",
                hide_index=True,
                height=350
            )
        else:
            st.info("Bu cihaz i\u00e7in g\u00f6zlem ge\u00e7mi\u015fi bulunamad\u0131.")

    with tab_events:
        if "identity_key" in events.columns:
            device_events = events[
                events["identity_key"].astype(str) == selected
            ].copy()
        else:
            device_events = pd.DataFrame()

        if not device_events.empty:
            if "event_time" in device_events.columns:
                device_events = device_events.sort_values(
                    "event_time", ascending=False
                )
            st.caption(f"{len(device_events)} olay kayd\u0131")
            st.dataframe(
                device_events,
                width="stretch",
                hide_index=True,
                height=350
            )
        else:
            st.info("Bu cihaz i\u00e7in olay kayd\u0131 bulunamad\u0131.")




def events_page():
    st.title("Ag Olaylari")
    st.caption("Ag ve cihaz olaylarini tek ekranda inceleyin.")

    sources = [
        ("Cihaz olaylari", "device_events.csv"),
        ("Ag olaylari", "network_events.csv"),
    ]

    frames = []
    for label, filename in sources:
        frame = load(filename)
        if not frame.empty:
            frame = frame.copy()
            frame["record_source"] = label
            frames.append(frame)

    if not frames:
        st.info("Henuz olay kaydi bulunmuyor.")
        return

    data = pd.concat(frames, ignore_index=True, sort=False).fillna("")

    c1, c2 = st.columns(2)
    c1.metric("Toplam olay kaydi", f"{len(data):,}")
    c2.metric("Olay kaynagi", f"{len(frames)}")

    st.markdown("---")
    st.markdown("### Olay filtreleri")

    f1, f2 = st.columns([2, 1])
    with f1:
        term = st.text_input(
            "Olay ara",
            placeholder="IP, MAC, olay turu veya aciklama..."
        )
    with f2:
        source_values = ["Tum kaynaklar"] + sorted(
            data["record_source"].astype(str).unique().tolist()
        )
        selected_source = st.selectbox("Kaynak", source_values)

    filtered = data.copy()

    if selected_source != "Tum kaynaklar":
        filtered = filtered[
            filtered["record_source"].astype(str) == selected_source
        ]

    if term.strip():
        term = term.strip().lower()
        mask = filtered.astype(str).apply(
            lambda col: col.str.lower().str.contains(term, regex=False)
        ).any(axis=1)
        filtered = filtered[mask]

    st.markdown(f"**{len(filtered):,}** olay gosteriliyor")

    # Varsa olay turu veya durum alanina gore ek filtre sun.
    type_col = next(
        (c for c in ["event_type", "event", "type", "event_name"]
         if c in filtered.columns),
        None
    )

    if type_col and not filtered.empty:
        types = ["Tum olay turleri"] + sorted(
            x for x in filtered[type_col].astype(str).unique() if x.strip()
        )
        selected_type = st.selectbox("Olay turu", types)
        if selected_type != "Tum olay turleri":
            filtered = filtered[
                filtered[type_col].astype(str) == selected_type
            ]

    preferred = [
        "timestamp", "event_time", "ip", "mac", "hostname",
        "event_type", "event", "type", "description",
        "message", "status", "severity", "record_source"
    ]
    visible = [c for c in preferred if c in filtered.columns]
    if not visible:
        visible = list(filtered.columns)

    st.dataframe(
        filtered[visible],
        width="stretch",
        hide_index=True,
        height=470
    )

    with st.expander("Tum olay alanlarini goster"):
        st.write(", ".join(data.columns.astype(str)))


def behavior_page():
    st.title("Davranis Analizi")
    st.caption("Cihaz davranis bulgulari ve mevcut cihaz zekasi kayitlari.")

    findings = load("behavior_findings.csv")
    intelligence = load("device_intelligence.csv")

    if findings.empty and intelligence.empty:
        st.info("Henuz davranis analizi kaydi bulunmuyor.")
        return

    a, b = st.columns(2)
    a.metric("Davranis bulgusu", f"{len(findings):,}")
    b.metric("Cihaz zekasi kaydi", f"{len(intelligence):,}")

    st.markdown("---")

    if not findings.empty:
        st.markdown("### Davranis bulgulari")

        data = findings.copy()
        term = st.text_input(
            "Bulgularda ara",
            placeholder="Cihaz, IP veya bulgu aciklamasi..."
        )

        if term.strip():
            term = term.strip().lower()
            mask = data.astype(str).apply(
                lambda col: col.str.lower().str.contains(term, regex=False)
            ).any(axis=1)
            data = data[mask]

        st.markdown(f"**{len(data):,}** bulgu kaydi")
        st.dataframe(
            data,
            width="stretch",
            hide_index=True,
            height=350
        )
    else:
        st.info("Davranis bulgusu dosyasi henuz bos.")

    st.markdown("---")

    if not intelligence.empty:
        st.markdown("### Cihaz zekasi")
        st.dataframe(
            intelligence,
            width="stretch",
            hide_index=True,
            height=350
        )
    else:
        st.info("Cihaz zekasi kaydi bulunmuyor.")


def live_page():
    st.title("Canli Izleme")
    st.caption("Ag envanteri ve mevcut izleme kayitlarinin durumu.")

    monitor = load("network_monitor.csv")
    inventory = load("device_inventory.csv")

    total = len(inventory)
    responding = 0
    if not inventory.empty and "status" in inventory.columns:
        responding = int(
            inventory["status"].astype(str).str.lower()
            .isin(["responding", "online", "active"]).sum()
        )

    c1, c2, c3 = st.columns(3)
    c1.metric("Envanter kaydi", f"{total:,}")
    c2.metric("Yan\u0131t veren cihaz", f"{responding:,}")
    c3.metric("Izleme kaydi", f"{len(monitor):,}")

    st.markdown("---")
    left, right = st.columns([1, 1])

    with left:
        st.markdown("### Izleme verisi")
        if monitor.empty:
            st.info("network_monitor.csv dosyasinda izleme kaydi bulunmuyor.")
        else:
            st.success("Izleme kayitlari mevcut.")
            st.dataframe(
                monitor,
                width="stretch",
                hide_index=True,
                height=300
            )

    with right:
        st.markdown("### Son envanter")
        if inventory.empty:
            st.info("Cihaz envanteri henuz olusturulmamis.")
        else:
            timestamp_col = next(
                (c for c in ["timestamp", "observed_at", "last_seen"]
                 if c in inventory.columns),
                None
            )
            if timestamp_col:
                latest = inventory[timestamp_col].astype(str).max()
                st.write("Son kayit:", latest or "Bilinmiyor")
            st.write("Kaynak: data/processed/device_inventory.csv")
            st.write("Bu ekran kayitli verileri gosterir; kendi basina surekli tarama yapmaz.")

    st.markdown("---")
    st.markdown("### Cihaz durumu")
    if not inventory.empty:
        if "status" in inventory.columns:
            status = (
                inventory["status"].replace("", "Bilinmiyor")
                .value_counts().rename_axis("Durum")
                .reset_index(name="Cihaz sayisi")
                .set_index("Durum")
            )
            st.bar_chart(status, height=250)

        preferred = [
            "timestamp", "ip", "hostname", "mac", "status"
        ]
        columns = [c for c in preferred if c in inventory.columns]
        if columns:
            st.dataframe(
                inventory[columns].head(20),
                width="stretch",
                hide_index=True
            )

    if st.button("Envanter taramasını başlat", key="live_scan_button"):
        run_scan()




def signal_page():
    st.title("Wi-Fi Sinyali")
    st.caption("Mevcut Wi-Fi baglantisi ve kesfedilen erisim noktalari.")

    connection = load("wifi_connection.csv")
    access_points = load("wifi_access_points.csv")

    st.markdown("### Mevcut baglanti")

    if not connection.empty:
        current = connection.iloc[-1]

        a, b, c, d = st.columns(4)
        a.metric("SSID", str(current.get("ssid", "-")) or "-")
        b.metric("Sinyal", str(current.get("signal", "-")) or "-")
        c.metric("Kanal", str(current.get("channel", "-")) or "-")
        d.metric("Radyo tipi", str(current.get("radio_type", "-")) or "-")

        st.markdown("#### Baglanti ayrintilari")
        left, right = st.columns(2)
        with left:
            st.write("**BSSID**")
            st.code(str(current.get("bssid", "-")) or "-")
            st.write("**Veri kaynagi**")
            st.write(str(current.get("bssid_source", "-")) or "-")
        with right:
            st.write("**Olcum zamani**")
            st.write(str(current.get("observed_at", "-")) or "-")
            st.write("**Baglanti durumu**")
            st.success("Baglanti kaydi mevcut")
    else:
        st.info("Wi-Fi baglanti kaydi bulunamadi. Once Wi-Fi kesfini calistirin.")

    st.markdown("---")
    st.markdown("### Kesfedilen erisim noktalari")

    if not access_points.empty:
        st.metric("Kesfedilen AP kaydi", f"{len(access_points):,}")

        if "signal" in access_points.columns:
            signal_values = (
                access_points["signal"].astype(str)
                .str.replace("%", "", regex=False)
            )
            numeric_signal = pd.to_numeric(signal_values, errors="coerce")
            chart_data = access_points.copy()
            chart_data["Sinyal (%)"] = numeric_signal
            label_col = next(
                (c for c in ["ssid", "bssid"] if c in chart_data.columns),
                None
            )
            if label_col:
                chart_data = chart_data.dropna(subset=["Sinyal (%)"])
                if not chart_data.empty:
                    st.bar_chart(
                        chart_data.set_index(label_col)["Sinyal (%)"],
                        height=240
                    )

        st.dataframe(
            access_points,
            width="stretch",
            hide_index=True,
            height=320
        )
    else:
        st.info("Kesfedilmis erisim noktasi kaydi bulunmuyor.")

    st.caption(
        "Sinyal degerleri kayitli olcumleri yansitir. "
        "Fiziksel mesafe, yalnizca sinyal yuzdesinden dogrudan hesaplanamaz."
    )

    if st.button("Wi-Fi verisini yeniden tara", key="wifi_scan_button"):
        run_scan()



def reports_page():
    page_header(
        "Raporlar",
        "Envanter ve ag gozlem verilerini disa aktarin"
    )

    inventory = load("device_inventory.csv")
    profiles = load("device_profiles.csv")
    events = load("device_events.csv")
    history = load("device_history.csv")

    a, b, c, d = st.columns(4)
    a.metric("Envanter", len(inventory))
    b.metric("Profiller", len(profiles))
    c.metric("Olaylar", len(events))
    d.metric("Gecmis kaydi", len(history))

    st.divider()
    st.subheader("Veri disa aktarma")

    datasets = {
        "Cihaz envanteri": inventory,
        "Cihaz profilleri": profiles,
        "Ag olaylari": events,
        "Cihaz gecmisi": history
    }

    for label, data in datasets.items():
        if data.empty:
            continue

        safe_name = (
            label.lower()
            .replace(" ", "_")
            .replace("ag", "network")
        )

        st.download_button(
            label + " CSV indir",
            data.to_csv(index=False).encode("utf-8-sig"),
            file_name=safe_name + ".csv",
            mime="text/csv",
            key="report_" + safe_name
        )


def topology_page():
    from scripts.topology_ui import render
    render()


def infrastructure_page():
    from scripts.infrastructure_ui import render
    render()



def U(value):
    return value.encode("ascii").decode("unicode_escape")



PAGES = [
    "Dashboard",
    "Cihazlar",
    "Cihaz Ge\u00e7mi\u015fi",
    "Cihaz Detay\u0131",
    "A\u011f Olaylar\u0131",
    "Davran\u0131\u015f Analizi",
    "A\u011f Topolojisi",
    "Canl\u0131 \u0130zleme",
    "Wi-Fi Sinyali",
    "A\u011f Altyap\u0131s\u0131",
    "Raporlar"
]

NAV_GROUPS = [
    ("GENEL BAKI\u015e", [PAGES[0]]),
    ("C\u0130HAZ Y\u00d6NET\u0130M\u0130", PAGES[1:4]),
    ("A\u011e ANAL\u0130Z\u0130", PAGES[4:10]),
    ("S\u0130STEM", [PAGES[10]])
]


with st.sidebar:
    st.markdown("""
    <style>
    [data-testid="stSidebar"] {
        min-width: 270px;
        max-width: 270px;
    }

    [data-testid="stSidebar"] > div:first-child {
        height: 100vh;
        box-sizing: border-box;
        overflow-y: auto;
        padding: 8px 13px 8px 13px;
    }

    [data-testid="stSidebar"] .brand-name {
        font-size: 1.28rem;
        font-weight: 800;
        letter-spacing: -0.5px;
        color: #17243A;
        margin: 0 0 2px 0;
    }

    [data-testid="stSidebar"] .brand-description {
        font-size: 0.64rem;
        line-height: 1.5;
        font-weight: 750;
        letter-spacing: 0.8px;
        color: #8491A5;
        margin-bottom: 13px;
    }

    [data-testid="stSidebar"] .nav-heading {
        color: #8793A5;
        font-size: 0.66rem;
        font-weight: 800;
        letter-spacing: 0.85px;
        margin: 11px 0 4px 9px;
    }

    [data-testid="stSidebar"] div.stButton {
        margin: 0;
        padding: 0;
    }

    [data-testid="stSidebar"] div.stButton > button {
        width: 100%;
        min-height: 34px;
        height: 34px;
        padding: 4px 10px;
        margin: 0;
        border-radius: 6px;
        box-shadow: none;
        text-align: left;
        justify-content: flex-start;
        font-size: 0.87rem;
        font-weight: 500;
        transition: background 120ms ease, color 120ms ease;
    }

    [data-testid="stSidebar"] div.stButton > button[kind="secondary"] {
        background: transparent;
        border: 1px solid transparent;
        color: #46566D;
    }

    [data-testid="stSidebar"] div.stButton > button[kind="secondary"]:hover {
        background: #F0F3F8;
        border-color: transparent;
        color: #174EA6;
    }

    [data-testid="stSidebar"] div.stButton > button[kind="primary"] {
        background: #EAF1FF;
        border: 0;
        border-left: 3px solid #3478E5;
        color: #174EA6;
        font-weight: 700;
        padding-left: 7px;
    }

    [data-testid="stSidebar"] hr {
        margin: 9px 0;
        border-color: #E7EBF1;
    }

    [data-testid="stSidebar"] .sidebar-footer {
        font-size: 0.72rem;
        line-height: 1.6;
        color: #8793A5;
    }

    @media (max-height: 800px) {
        [data-testid="stSidebar"] .nav-heading {
            margin-top: 7px;
            margin-bottom: 2px;
        }
        [data-testid="stSidebar"] div.stButton > button {
            min-height: 31px;
            height: 31px;
        }
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown(
        '<div class="brand-name">WiFi Vision Lab</div>'
        '<div class="brand-description">A\u011e G\u00d6ZLEM VE \u0130ST\u0130HBARAT PLATFORMU</div>',
        unsafe_allow_html=True
    )

    if "active_page" not in st.session_state:
        st.session_state.active_page = PAGES[0]

    for group_index, (section, items) in enumerate(NAV_GROUPS):
        st.markdown(
            f'<div class="nav-heading">{section}</div>',
            unsafe_allow_html=True
        )

        for item_index, item in enumerate(items):
            active = st.session_state.active_page == item
            if st.button(
                item,
                key=f"fixed_nav_{group_index}_{item_index}",
                type="primary" if active else "secondary",
                width="stretch"
            ):
                st.session_state.active_page = item
                st.rerun()

    page = st.session_state.active_page

    st.divider()
    with st.expander("Tarama kapsamı", expanded=False):
        st.caption("Boş bırakılırsa yalnızca bağlı olduğunuz aktif özel ağ taranır.")
        st.text_input(
            "Özel IPv4 CIDR (isteğe bağlı)",
            key="scan_cidr",
            placeholder="Örn. 192.168.10.0/24"
        )
        st.checkbox(
            "Bu özel ağı taramaya yetkili olduğumu onaylıyorum",
            key="scan_approved"
        )
        st.text_input(
            "Onay için CIDR değerini tekrar yazın",
            key="scan_confirmation",
            placeholder="CIDR ile birebir aynı olmalı"
        )
    if st.button("A\u011f taramas\u0131n\u0131 ba\u015flat", key="fixed_nav_scan", width="stretch"):
        run_scan()

    st.markdown(
        '<div class="sidebar-footer">Yerel veri depolama<br>WiFi Vision Lab | Local Edition</div>',
        unsafe_allow_html=True
    )


PAGE_RENDERERS = {
    PAGES[0]: dashboard_page,
    PAGES[1]: devices_page,
    PAGES[2]: history_page,
    PAGES[3]: detail_page,
    PAGES[4]: events_page,
    PAGES[5]: behavior_page,
    PAGES[6]: topology_page,
    PAGES[7]: live_page,
    PAGES[8]: signal_page,
    PAGES[9]: infrastructure_page,
    PAGES[10]: reports_page,
}

renderer = PAGE_RENDERERS.get(page)

if renderer is not None:
    renderer()
else:
    st.error("Sayfa bulunamad\u0131.")

