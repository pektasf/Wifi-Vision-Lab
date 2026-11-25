from pathlib import Path
import os
import subprocess
import sys

import pandas as pd
import streamlit as st
from scripts.ui_theme import apply_theme
from scripts.scan_jobs import scan_jobs

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "processed"




st.set_page_config(
    page_title="WiFi Vision Lab",
    page_icon="W",
    layout="wide",
    initial_sidebar_state="expanded"
)

apply_theme("light")





_STORAGE_READY = False


def load(filename):
    global _STORAGE_READY
    path = DATA / filename
    try:
        from scripts.storage import (
            import_legacy_csvs,
            initialize_database,
            read_dataset,
        )

        if not _STORAGE_READY:
            initialize_database()
            import_legacy_csvs(DATA)
            _STORAGE_READY = True

        rows = read_dataset(filename)
        if rows is not None:
            if not rows and path.exists():
                # Preserve CSV headers for empty datasets without reading their records.
                return pd.read_csv(path, dtype=str, nrows=0).fillna("")
            return pd.DataFrame(rows).fillna("")
    except Exception as exc:
        st.warning(f"SQLite veri deposu okunamadı; CSV yedeği deneniyor: {exc}")

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
    custom_cidr = str(st.session_state.get("scan_cidr", "")).strip()
    approved = bool(st.session_state.get("scan_approved", False))
    confirmation = str(st.session_state.get("scan_confirmation", "")).strip()

    try:
        job_id = scan_jobs.start(
            ROOT,
            scan_cidr=custom_cidr,
            approved=approved,
            confirmation=confirmation,
        )
    except ValueError as exc:
        st.error(str(exc))
        return
    except FileNotFoundError:
        st.error("main.py bulunamadı. Tarama başlatılamadı.")
        return
    except OSError as exc:
        st.error(f"Tarama işi başlatılamadı: {exc}")
        return

    st.session_state["active_scan_job_id"] = job_id
    st.session_state.pop("last_auto_refreshed_scan_job_id", None)
    st.success("Tarama arka planda başlatıldı. Diğer sayfalarda çalışmaya devam edebilirsiniz.")


@st.fragment(run_every="1s")
def render_scan_job():
    job_id = st.session_state.get("active_scan_job_id")
    if not job_id:
        return

    job = scan_jobs.get(job_id)
    if job is None:
        st.session_state.pop("active_scan_job_id", None)
        return

    # Refresh the whole app once when a scan finishes so every page reads the
    # newly persisted datasets without requiring a manual browser refresh.
    if job["status"] == "completed":
        refreshed_job_id = st.session_state.get("last_auto_refreshed_scan_job_id")
        if refreshed_job_id != job_id:
            st.session_state["last_auto_refreshed_scan_job_id"] = job_id
            st.rerun()

    labels = {
        "queued": "Sırada",
        "running": "Çalışıyor",
        "completed": "Tamamlandı",
        "failed": "Hata",
        "cancelled": "İptal edildi",
    }
    with st.expander(
        f"Arka plan taraması — {labels.get(job['status'], job['status'])}",
        expanded=job["status"] in {"queued", "running"},
    ):
        st.caption(f"İş kimliği: {job_id}")
        st.caption(job["stage"])
        if job.get("progress_message"):
            st.caption(job["progress_message"])
        st.progress(float(job["progress"]))
        if job["total_targets"]:
            st.caption(
                f"Hedefler: {job['completed_targets']:,} / {job['total_targets']:,}"
            )
        if job["return_code"] is not None:
            st.caption(f"Çıkış kodu: {job['return_code']}")
        if job["error"]:
            st.error(job["error"])
        if job["output"]:
            st.code("\n".join(job["output"][-80:]), language="text")
        if job["status"] in {"queued", "running"}:
            left, right = st.columns(2)
            with left:
                if st.button("Durumu yenile", key="refresh_scan_job", width="stretch"):
                    st.rerun()
            with right:
                if st.button("Taramayı iptal et", key="cancel_scan_job", width="stretch"):
                    scan_jobs.cancel(job_id)
                    st.rerun()
        elif job["status"] == "completed":
            st.success("Tarama ve analiz tamamlandı. Güncel verileri görmek için sayfayı yenileyin.")
        elif job["status"] == "failed":
            st.error("Tarama işlemi hata ile sonlandı. Çıktıyı kontrol edin.")
        elif job["status"] == "cancelled":
            st.warning("Tarama kullanıcı tarafından iptal edildi.")

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



@st.dialog("Cihaz detayları", width="large")
def show_device_modal(device):
    st.caption("Seçilen cihazın kayıtlı kimlik ve ağ bilgileri")
    fields = [
        ("IP adresi", "ip"), ("MAC adresi", "mac"),
        ("Cihaz adı", "hostname"), ("Durum", "status"),
        ("Üretici", "vendor"), ("Gateway", "gateway"),
        ("Ağ arayüzü", "adapter"), ("Alt ağ", "subnet"),
        ("Son gözlem", "timestamp"), ("İlk görülme", "first_seen"),
        ("Son görülme", "last_seen"), ("Sınıflandırma", "classification"),
    ]
    left, right = st.columns(2)
    for index, (label, key) in enumerate(fields):
        with (left if index % 2 == 0 else right):
            st.markdown(f"**{label}**")
            st.write(str(device.get(key, "") or "Bilinmiyor"))
    known = {key for _, key in fields}
    extras = [key for key in device.index if key not in known and str(device.get(key, "")).strip()]
    if extras:
        with st.expander("Diğer teknik alanlar"):
            for key in extras:
                st.markdown(f"**{str(key).replace('_', ' ').title()}**")
                st.write(str(device.get(key)))


def render_device_cards(data, key_prefix="device"):
    if data.empty:
        st.info("Filtrelerle eşleşen cihaz bulunamadı.")
        return
    st.caption(f"{len(data):,} cihaz")
    items = list(data.iterrows())
    for start in range(0, len(items), 3):
        columns = st.columns(3)
        for column, (index, device) in zip(columns, items[start:start + 3]):
            with column:
                with st.container(border=True):
                    st.markdown(f"**{str(device.get('hostname', '') or 'İsimsiz cihaz')}**")
                    st.caption(str(device.get("ip", "") or "IP bilinmiyor"))
                    st.write(str(device.get("status", "") or "Bilinmiyor"))
                    if st.button("Detayları incele", key=f"{key_prefix}_details_{index}", width="stretch"):
                        show_device_modal(device)


def dashboard_page():
    inventory = load("device_inventory.csv")
    profiles = load("device_profiles.csv")
    events = load("device_events.csv")
    classification = load("device_classification.csv")
    page_header("Ağ kontrol merkezi", "Ağınızdaki cihazları ve son gözlemleri tek bakışta görün.")

    total = len(inventory)
    responding = 0
    if "status" in inventory.columns:
        responding = int(inventory["status"].astype(str).str.lower().isin(
            ["responding", "online", "active"]
        ).sum())
    metrics = st.columns(3)
    metrics[0].metric("Toplam cihaz", f"{total:,}")
    metrics[1].metric("Yanıt veren", f"{responding:,}")
    metrics[2].metric("Diğer / bilinmiyor", f"{max(total - responding, 0):,}")

    latest = "Henüz gözlem yok"
    timestamp_col = next((c for c in ["timestamp", "observed_at", "last_seen"] if c in inventory.columns), None)
    if timestamp_col and not inventory.empty:
        parsed = pd.to_datetime(inventory[timestamp_col], errors="coerce")
        if parsed.notna().any():
            latest = parsed.max().strftime("%d.%m.%Y %H:%M")

    with st.container(border=True):
        st.markdown("**Son veri güncellemesi**")
        st.write(latest)
        left, right = st.columns(2)
        with left:
            if st.button("Yeni tarama", type="primary", width="stretch", key="dashboard_start_scan"):
                run_scan()
        with right:
            if st.button("Cihaz envanterini aç", width="stretch", key="dashboard_open_devices"):
                st.session_state.active_page = PAGES[1]
                st.rerun()

    left, right = st.columns([1.1, 1])
    with left:
        st.subheader("Cihaz durumu")
        if "status" in inventory.columns and not inventory.empty:
            chart = inventory["status"].replace("", "Bilinmiyor").value_counts().rename_axis("Durum").reset_index(name="Cihaz").set_index("Durum")
            st.bar_chart(chart, height=230)
        else:
            st.info("Durum dağılımı için henüz veri yok.")
    with right:
        st.subheader("Envanter özeti")
        st.metric("Cihaz profili", f"{len(profiles):,}")
        st.metric("Kayıtlı olay", f"{len(events):,}")
        st.metric("Üretici kaydı", f"{len(classification):,}")

    st.subheader("Son keşfedilen cihazlar")
    if inventory.empty:
        st.info("Henüz cihaz kaydı yok. Yeni tarama başlatabilirsiniz.")
    else:
        recent = inventory.copy()
        if timestamp_col:
            recent = recent.sort_values(timestamp_col, ascending=False)
        visible = [c for c in ["ip", "hostname", "status", "vendor"] if c in recent.columns]
        render_device_cards(recent[visible].head(6) if visible else recent.head(6), "dashboard")


def devices_page():
    inventory = load("device_inventory.csv")
    page_header("Cihaz envanteri", "Cihazları arayın, filtreleyin ve teknik ayrıntıları gerektiğinde açın.")
    if inventory.empty:
        st.info("Henüz cihaz kaydı bulunmuyor. Önce ağ keşfi yapın.")
        return

    data = inventory.copy()
    for col in ["ip", "mac", "hostname", "status", "gateway", "adapter", "subnet"]:
        if col not in data.columns:
            data[col] = ""
    data["status"] = data["status"].replace("", "Bilinmiyor")

    responding = int(data["status"].astype(str).str.lower().isin(
        ["responding", "online", "active"]
    ).sum())
    summary = st.columns(3)
    summary[0].metric("Toplam cihaz", f"{len(data):,}")
    summary[1].metric("Yanıt veren", f"{responding:,}")
    summary[2].metric("Diğer / bilinmiyor", f"{len(data) - responding:,}")

    filters = st.columns([2, 1])
    with filters[0]:
        search = st.text_input("Cihaz ara", placeholder="IP, MAC veya cihaz adı", key="inventory_search")
    with filters[1]:
        statuses = ["Tüm durumlar"] + sorted(data["status"].astype(str).unique().tolist())
        selected_status = st.selectbox("Durum", statuses, key="inventory_status")

    filtered = data.copy()
    if selected_status != "Tüm durumlar":
        filtered = filtered[filtered["status"].astype(str) == selected_status]
    if search.strip():
        mask = filtered.astype(str).apply(
            lambda col: col.str.contains(search.strip(), case=False, na=False, regex=False)
        ).any(axis=1)
        filtered = filtered[mask]

    st.divider()
    render_device_cards(filtered, "inventory")



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
    st.caption("Aktif bağlantı ölçümü, sinyal kalitesi ve erişim noktası görünümü.")

    connection = load("wifi_connection.csv")
    access_points = load("wifi_access_points.csv")
    signal_history = load("wifi_signal_history.csv")

    st.markdown("### Mevcut bağlantı")
    if not connection.empty:
        current = connection.iloc[-1]
        a, b, c, d = st.columns(4)
        a.metric("SSID", str(current.get("ssid", "-")) or "-")
        b.metric("Sinyal", str(current.get("signal", "-")) or "-")
        c.metric("Kanal", str(current.get("channel", "-")) or "-")
        d.metric("Radyo tipi", str(current.get("radio_type", "-")) or "-")
        left, right = st.columns(2)
        with left:
            st.caption("BSSID")
            st.code(str(current.get("bssid", "-")) or "-")
        with right:
            st.caption("Son keşif zamanı")
            st.write(str(current.get("observed_at", "-")) or "-")
    else:
        st.info("Wi-Fi bağlantı kaydı bulunamadı. Önce Wi-Fi keşfini çalıştırın.")

    st.markdown("---")
    st.markdown("### Sinyal ölçüm geçmişi")
    if not signal_history.empty and "signal_percent" in signal_history.columns:
        history = signal_history.copy()
        history["signal_percent"] = pd.to_numeric(
            history["signal_percent"], errors="coerce"
        )
        history = history.dropna(subset=["signal_percent"])
        if "observed_at" in history.columns:
            history = history.sort_values("observed_at")
        if not history.empty:
            latest = history.iloc[-1]
            a, b, c = st.columns(3)
            a.metric("Son ölçüm", f"{int(latest['signal_percent'])}%")
            b.metric("Kalite", str(latest.get("quality", "-")) or "-")
            change = latest.get("change_percent", "")
            c.metric(
                "Önceki ölçüme göre",
                f"{int(float(change)):+d} puan"
                if str(change).strip() else "İlk ölçüm",
            )
            if "observed_at" in history.columns:
                st.line_chart(
                    history.tail(100).set_index("observed_at")[["signal_percent"]],
                    height=250,
                )
            detail_columns = [
                column for column in [
                    "observed_at", "ssid", "signal_percent", "rssi_dbm",
                    "channel", "receive_mbps", "transmit_mbps", "quality",
                ] if column in history.columns
            ]
            st.dataframe(
                history[detail_columns].tail(20).iloc[::-1],
                width="stretch",
                hide_index=True,
            )
    else:
        st.info("Henüz sinyal geçmişi yok. Bir ağ taraması çalıştırıldığında ölçüm kaydedilir.")

    st.markdown("---")
    st.markdown("### Yakındaki erişim noktaları")
    if not access_points.empty:
        st.metric("Keşfedilen AP kaydı", f"{len(access_points):,}")
        if "signal" in access_points.columns:
            signal_values = (
                access_points["signal"].astype(str)
                .str.replace("%", "", regex=False)
            )
            chart_data = access_points.copy()
            chart_data["Sinyal (%)"] = pd.to_numeric(
                signal_values, errors="coerce"
            )
            label_col = next(
                (column for column in ["ssid", "bssid"] if column in chart_data.columns),
                None,
            )
            if label_col:
                chart_data = chart_data.dropna(subset=["Sinyal (%)"])
                if not chart_data.empty:
                    st.bar_chart(
                        chart_data.set_index(label_col)["Sinyal (%)"],
                        height=240,
                    )
        st.dataframe(
            access_points, width="stretch", hide_index=True, height=320
        )
    else:
        st.info("Keşfedilmiş erişim noktası kaydı bulunmuyor.")

    st.caption(
        "Sinyal yüzdesi bağlantı kalitesini gösterir; tek başına fiziksel mesafe "
        "veya AP-istemci bağlantı topolojisini kanıtlamaz."
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
        font-size: 1.15rem; font-weight: 750; letter-spacing: -0.4px;
        color: #17243A; margin: 0 0 3px 0;
    }
    [data-testid="stSidebar"] .brand-description {
        font-size: .68rem; line-height: 1.45; font-weight: 600;
        letter-spacing: .25px; color: #718096; margin-bottom: 12px;
    }

    [data-testid="stSidebar"] .nav-heading { color: #8995A7; font-size: .68rem; font-weight: 700; letter-spacing: .35px; margin: 13px 0 5px 8px; }

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
        background: transparent; border: 1px solid transparent; color: #526176;
    }
    [data-testid="stSidebar"] div.stButton > button[kind="secondary"]:hover {
        background: #F1F5F9; border-color: #E2E8F0; color: #1D4ED8;
    }
    [data-testid="stSidebar"] div.stButton > button[kind="primary"] {
        background: #EAF2FF; border: 1px solid #D6E6FF; color: #1D4ED8; font-weight: 700;
    }

    [data-testid="stSidebar"] hr {
        margin: 9px 0;
        border-color: var(--wv-border);
    }

    [data-testid="stSidebar"] .sidebar-footer { font-size: .72rem; line-height: 1.6; color: #8995A7; }

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
        '<div class="brand-description">YEREL AĞ GÖZLEM PLATFORMU</div>',
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

    render_scan_job()

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

