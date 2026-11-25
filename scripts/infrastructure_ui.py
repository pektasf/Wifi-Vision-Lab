from pathlib import Path
import pandas as pd
import streamlit as st


DATA = Path(__file__).resolve().parent.parent / "data" / "processed"


def read_data(filename):
    path = DATA / filename
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return pd.DataFrame()


def find_col(df, candidates):
    for name in candidates:
        if name in df.columns:
            return name
    return None


def assign_identity_keys(combined, ip_col, mac_col):
    """Create stable grouping keys without mismatched boolean-index assignment."""
    result = combined.copy()
    result["_ip_key"] = result[ip_col].astype(str).str.strip()
    result["_mac_key"] = result[mac_col].astype(str).str.strip().str.upper()
    result["_identity"] = result["_ip_key"]

    missing_ip = result["_identity"].eq("")
    result.loc[missing_ip, "_identity"] = result.loc[missing_ip, "_mac_key"]

    missing_identity = result["_identity"].eq("")
    fallback = pd.Series(
        [f"kayit-{index}" for index in result.index[missing_identity]],
        index=result.index[missing_identity],
        dtype="object",
    )
    result.loc[missing_identity, "_identity"] = fallback
    return result


def render():
    inventory = read_data("device_inventory.csv")
    nodes = read_data("topology_nodes.csv")
    classification = read_data("device_classification.csv")
    wifi = read_data("wifi_connection.csv")
    access_points = read_data("wifi_access_points.csv")

    st.title("Ag Altyapisi")
    st.caption(
        "Gateway, router, access point, repeater, switch ve diger ag ekipmanlari"
    )

    if inventory.empty and nodes.empty and classification.empty:
        st.warning("Altyapi envanteri icin henuz veri bulunamadi.")
        return

    frames = []
    for frame in [inventory, nodes, classification]:
        if not frame.empty:
            frames.append(frame.copy())

    # Kayitlari ortak IP/MAC kimligi uzerinden birlestir.
    combined = pd.concat(frames, ignore_index=True, sort=False).fillna("")

    ip_col = find_col(combined, ["ip", "IP", "ip_address"])
    mac_col = find_col(combined, ["mac", "MAC", "mac_address"])
    vendor_col = find_col(combined, ["vendor", "manufacturer", "brand"])
    name_col = find_col(combined, ["hostname", "label", "device_name", "name"])
    type_col = find_col(combined, ["node_type", "device_type", "type"])
    status_col = find_col(combined, ["status", "state"])
    class_col = find_col(combined, ["classification", "device_classification"])
    gateway_col = find_col(combined, ["gateway", "default_gateway"])

    if ip_col is None:
        combined["_ip"] = ""
        ip_col = "_ip"
    if mac_col is None:
        combined["_mac"] = ""
        mac_col = "_mac"
    if vendor_col is None:
        combined["_vendor"] = ""
        vendor_col = "_vendor"
    if name_col is None:
        combined["_name"] = ""
        name_col = "_name"
    if type_col is None:
        combined["_type"] = ""
        type_col = "_type"
    if status_col is None:
        combined["_status"] = ""
        status_col = "_status"
    if class_col is None:
        combined["_classification"] = ""
        class_col = "_classification"

    # Bir IP/MAC icin birden fazla kayit varsa dolu alanlari koru.
    combined = assign_identity_keys(combined, ip_col, mac_col)

    rows = []
    for identity, group in combined.groupby("_identity", sort=False):
        item = {}
        for col in combined.columns:
            values = [
                str(v).strip() for v in group[col].tolist()
                if str(v).strip() and str(v).strip().lower() != "nan"
            ]
            item[col] = values[0] if values else ""
        rows.append(item)

    devices = pd.DataFrame(rows)

    # Kaynak alanlarini birlikte kullan; uretici bilgisi tek basina kesin rol degildir.
    category_col = find_col(devices, ["category"])
    vendor_role_col = find_col(devices, ["vendor_role"])

    def role_for(row):
        values = [
            row.get(type_col, ""),
            row.get(class_col, ""),
            row.get(name_col, ""),
            row.get(category_col, "") if category_col else "",
            row.get(vendor_role_col, "") if vendor_role_col else "",
        ]
        text = " ".join(str(v) for v in values).lower()

        if "gateway" in text:
            return "Gateway"
        if "router" in text:
            return "Router"
        if "access point" in text or "access_point" in text:
            return "Access Point"
        if "repeater" in text or "range extender" in text:
            return "Repeater"
        if "mesh" in text:
            return "Mesh"
        if "switch" in text:
            return "Switch"
        if "controller" in text:
            return "Controller"

        if "network equipment" in text or "network_device" in text:
            return "Ag ekipmani adayi"

        vendor = str(row.get(vendor_col, "")).lower()
        if vendor and any(x in vendor for x in [
            "ruijie", "tp-link", "ubiquiti", "mikrotik", "cisco", "huawei"
        ]):
            return "Ag ekipmani adayi"

        return "Diger / Belirsiz"

    devices["Altyapi rolu"] = devices.apply(role_for, axis=1)

    def evidence_for(row):
        role = row["Altyapi rolu"]
        category = str(
            row.get(category_col, "") if category_col else ""
        ).lower()
        classification_value = str(row.get(class_col, "")).lower()

        if role == "Diger / Belirsiz":
            return "Siniflandirilmamis"
        if role == "Ag ekipmani adayi":
            if str(row.get("role_evidence_type", "")).strip() == "vendor_only":
                return "Yalnizca uretici bilgisi; cihaz rolu dogrulanmadi"
            return "Uretici veya tahmini siniflandirma"
        if str(row.get("role_evidence_type", "")).strip() == "hostname_role_hint":
            return "Hostname ipucuna dayali tahmin"
        if str(row.get("role_evidence_type", "")).strip() == "hostname_model_family_inference":
            return "Model ailesi ipucuna dayali tahmin"
        if "manufacturer-based inference" in category or "inferred" in classification_value:
            return "Tahmini siniflandirma"
        return "Kayitli siniflandirma"

    devices["KanIt durumu"] = devices.apply(evidence_for, axis=1)

    total = len(devices)
    infrastructure = devices[
        devices["Altyapi rolu"] != "Diger / Belirsiz"
    ]
    candidates = devices[
        devices["Altyapi rolu"] == "Ag ekipmani adayi"
    ]

    a, b, c, d = st.columns(4)
    a.metric("Toplam cihaz", f"{total:,}")
    b.metric("Altyapi kaydi", f"{len(infrastructure):,}")
    c.metric("Ekipman adayi", f"{len(candidates):,}")
    d.metric("Wi-Fi AP kaydi", f"{len(access_points):,}")

    st.divider()

    overview, inventory_tab, wifi_tab, evidence_tab = st.tabs([
        "Genel Bakis",
        "Cihaz Envanteri",
        "Wi-Fi Baglantisi",
        "KanIt ve Kaynaklar"
    ])

    with overview:
        st.subheader("Altyapi dagilimi")
        counts = (
            devices["Altyapi rolu"]
            .value_counts()
            .rename_axis("Rol")
            .reset_index(name="Cihaz sayisi")
        )

        left, right = st.columns([1, 1])
        with left:
            st.dataframe(counts, width="stretch", hide_index=True)
        with right:
            st.markdown("**Veri kalitesi**")
            evidence_counts = (
                devices["KanIt durumu"]
                .value_counts()
                .rename_axis("KanIt")
                .reset_index(name="Kayit")
            )
            st.dataframe(
                evidence_counts,
                width="stretch",
                hide_index=True
            )

        st.info(
            "Ayni agda gorunen cihazlar otomatik olarak birbirine bagli kabul edilmez. "
            "AP-istemci iliskisi ancak cihaz yonetim arayuzu, SNMP veya desteklenen "
            "bir yonetim API'sinden alinan veriyle dogrulanabilir."
        )

    with inventory_tab:
        st.subheader("Ag ekipmani envanteri")

        search = st.text_input(
            "Envanterde ara",
            placeholder="IP, MAC, marka, model veya cihaz adi"
        )

        role_options = ["Tum roller"] + sorted(
            devices["Altyapi rolu"].dropna().unique().tolist()
        )
        selected_role = st.selectbox("Altyapi rolu", role_options)

        filtered = devices.copy()
        if search.strip():
            mask = filtered.astype(str).apply(
                lambda col: col.str.contains(
                    search.strip(), case=False, na=False
                )
            ).any(axis=1)
            filtered = filtered[mask]

        if selected_role != "Tum roller":
            filtered = filtered[
                filtered["Altyapi rolu"] == selected_role
            ]

        st.caption(f"{len(filtered):,} kayit listeleniyor.")

        preferred = [
            name_col, ip_col, mac_col, vendor_col,
            "model", "firmware", "Altyapi rolu",
            status_col, "KanIt durumu"
        ]
        columns = []
        for col in preferred:
            if col in filtered.columns and col not in columns:
                columns.append(col)

        if columns:
            st.caption(f"{len(filtered):,} cihaz")
            records = list(filtered.iterrows())
            for offset in range(0, len(records), 3):
                card_cols = st.columns(3)
                for card_col, (idx, row) in zip(card_cols, records[offset:offset + 3]):
                    with card_col:
                        with st.container(border=True):
                            st.markdown(f"**{str(row.get(name_col, '') or 'İsimsiz cihaz')}**")
                            st.caption(str(row.get(ip_col, '') or 'IP bilinmiyor'))
                            st.write(str(row.get("Altyapi rolu", "Belirsiz")))
                            st.caption(str(row.get("KanIt durumu", "Bilinmiyor")))

        if not filtered.empty:
            @st.dialog("Altyapı cihazı", width="large")
            def show_infrastructure_device(selected):
                left, right = st.columns(2)
                for column, fields in [
                    (left, [(name_col, "Cihaz adı"), (ip_col, "IP adresi"), (mac_col, "MAC adresi"), (vendor_col, "Üretici")]),
                    (right, [("model", "Model"), ("firmware", "Firmware"), ("ssid", "SSID"), ("channel", "Kanal"), ("frequency", "Frekans"), ("band", "Bant")]),
                ]:
                    with column:
                        for key, label in fields:
                            st.markdown(f"**{label}**")
                            st.write(str(selected.get(key, "") or "Bilinmiyor"))
                st.caption(f"Rol: {selected['Altyapi rolu']} · Kanıt: {selected['KanIt durumu']}")

            selected_index = st.selectbox(
                "Ayrıntılarını aç",
                filtered.index.tolist(),
                format_func=lambda idx: (
                    str(filtered.loc[idx, name_col] or "İsimsiz cihaz")
                    + " · " + str(filtered.loc[idx, ip_col] or "IP yok")
                ),
                key="infrastructure_device_select",
            )
            if st.button("Seçili cihazın detaylarını aç", key="infrastructure_open_detail"):
                show_infrastructure_device(filtered.loc[selected_index])

        if not devices.empty:
            st.download_button(
                "Envanteri CSV indir",
                data=devices.to_csv(index=False).encode("utf-8-sig"),
                file_name="ag_altyapisi_envanteri.csv",
                mime="text/csv"
            )

    with wifi_tab:
        st.subheader("Mevcut Wi-Fi baglantisi")
        if wifi.empty:
            st.info("Wi-Fi baglanti verisi bulunamadi.")
        else:
            st.dataframe(wifi, width="stretch", hide_index=True)

        st.subheader("Kesfedilen erisim noktalari")
        if access_points.empty:
            st.info("Kesfedilmis access point kaydi bulunamadi.")
        else:
            st.dataframe(
                access_points,
                width="stretch",
                hide_index=True
            )

        st.caption(
            "Windows arayuzunden alinan BSSID, bagli olunan kablosuz erisim "
            "noktasinin radyo arayuzu adresidir. Envanterdeki farkli bir MAC "
            "adresinin ayni fiziksel cihaza ait oldugu varsayilmaz."
        )

    with evidence_tab:
        st.subheader("KanIt ve veri kaynaklari")
        st.markdown(
            "- **Kayitli siniflandirma:** Kaynak dosyada cihaz turu veya siniflandirma var.\n"
            "- **Uretici bilgisine dayali aday:** Uretici ag ekipmani markasi olarak taniniyor; rol kesin degil.\n"
            "- **Tahmini siniflandirma:** Siniflandirma kaynagi tahmine dayaniyor.\n"
            "- **Siniflandirilmamis:** Cihaz turu icin yeterli veri yok."
        )

        st.markdown("**Kullanilan yerel veri dosyalari**")
        for filename in [
            "device_inventory.csv",
            "topology_nodes.csv",
            "device_classification.csv",
            "wifi_connection.csv",
            "wifi_access_points.csv"
        ]:
            path = DATA / filename
            st.write(
                f"{filename} ? "
                f"{'Mevcut' if path.exists() else 'Bulunamadi'}"
            )
