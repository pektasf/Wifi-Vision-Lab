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


def build_network_context_summary(frame):
    """Return display-safe values for the latest local adapter snapshot."""
    if frame is None or frame.empty:
        return None

    row = frame.iloc[-1]
    dhcp_state = str(row.get("dhcp_enabled", "")).strip().casefold()
    dhcp_labels = {
        "enabled": "Etkin",
        "disabled": "Devre dışı",
        "unknown": "Bilinmiyor",
    }
    return {
        "captured_at": str(row.get("captured_at", "") or "Bilinmiyor"),
        "adapter": str(row.get("adapter", "") or "Bilinmiyor"),
        "adapter_description": str(row.get("adapter_description", "") or "Bilinmiyor"),
        "adapter_kind": str(row.get("adapter_kind", "") or "unknown"),
        "interface_index": str(row.get("interface_index", "") or "Bilinmiyor"),
        "local_ipv4": str(row.get("local_ipv4", "") or "Bilinmiyor"),
        "network_cidr": str(row.get("network_cidr", "") or "Bilinmiyor"),
        "gateway": str(row.get("gateway", "") or "Yok"),
        "dhcp_status": dhcp_labels.get(dhcp_state, "Bilinmiyor"),
        "dhcp_server": str(row.get("dhcp_server", "") or "Bilinmiyor"),
        "dhcp_lease_obtained": str(
            row.get("dhcp_lease_obtained", "") or "Bilinmiyor"
        ),
        "dhcp_lease_expires": str(
            row.get("dhcp_lease_expires", "") or "Bilinmiyor"
        ),
    }


def render():
    inventory = read_data("device_inventory.csv")
    nodes = read_data("topology_nodes.csv")
    classification = read_data("device_classification.csv")
    wifi = read_data("wifi_connection.csv")
    access_points = read_data("wifi_access_points.csv")
    ap_client_history = read_data("ap_client_relationships.csv")
    network_context = read_data("network_context.csv")

    st.markdown(
        '<div class="wv-page-header"><h1>Ağ altyapısı</h1>'
        '<p>Gateway, router, erişim noktası, repeater, switch ve controller kayıtlarını '
        'kanıt düzeyleriyle birlikte incele.</p></div>',
        unsafe_allow_html=True,
    )

    context = build_network_context_summary(network_context)
    if context:
        st.markdown("### Son seçili ağ adaptörü")
        context_columns = st.columns(4)
        context_columns[0].metric("Adaptör", context["adapter"])
        context_columns[1].metric("Yerel IPv4", context["local_ipv4"])
        context_columns[2].metric("Alt ağ", context["network_cidr"])
        context_columns[3].metric("Ağ geçidi", context["gateway"])
        adapter_kind_labels = {
            "physical": "Fiziksel donanım",
            "virtual_wlan": "Sanal WLAN / Wi-Fi Direct",
            "virtual_or_software": "Sanal / yazılım adaptörü",
            "unknown": "Bilinmiyor",
        }
        st.caption(
            f"Arayüz türü: {adapter_kind_labels.get(context['adapter_kind'], 'Bilinmiyor')} "
            f"· {context['adapter_description']}"
        )
        with st.expander("DHCP ve kiralama ayrıntıları"):
            detail_left, detail_right = st.columns(2)
            with detail_left:
                st.markdown(f"**DHCP durumu:** {context['dhcp_status']}")
                st.markdown(f"**DHCP sunucusu:** {context['dhcp_server']}")
                st.markdown(f"**Arayüz indeksi:** {context['interface_index']}")
            with detail_right:
                st.markdown(
                    f"**Kira başlangıcı:** {context['dhcp_lease_obtained']}"
                )
                st.markdown(
                    f"**Kira bitişi:** {context['dhcp_lease_expires']}"
                )
                st.markdown(f"**Son kayıt:** {context['captured_at']}")
        st.caption(
            "Adaptör sınıflandırması yalnızca taramayı yapan bu bilgisayarın yerel "
            "arayüzünü tanımlar; ağdaki uzak cihazların sanal arayüzlerini kanıtlamaz. "
            "Bu bilgiler bilgisayarın seçili yerel adaptörüne aittir; "
            "router üzerindeki tüm DHCP istemci kayıtlarını temsil etmez."
        )

    try:
        from scripts.device_inventory import list_network_adapters
        local_adapters = list_network_adapters()
    except (OSError, RuntimeError, ValueError) as exc:
        local_adapters = []
        st.caption(f"Yerel adaptör envanteri alınamadı: {exc}")

    if local_adapters:
        st.markdown("### Bu bilgisayardaki tüm ağ adaptörleri")
        adapter_frame = pd.DataFrame(local_adapters)
        virtual_wlan_count = int(
            adapter_frame["adapter_kind"].eq("virtual_wlan").sum()
        )
        virtual_other_count = int(
            adapter_frame["adapter_kind"].eq("virtual_or_software").sum()
        )
        adapter_metrics = st.columns(3)
        adapter_metrics[0].metric("Toplam adaptör", len(adapter_frame))
        adapter_metrics[1].metric("Sanal WLAN", virtual_wlan_count)
        adapter_metrics[2].metric("Diğer sanal/yazılım", virtual_other_count)
        adapter_display = adapter_frame.rename(columns={
            "adapter": "Adaptör",
            "adapter_description": "Donanım açıklaması",
            "mac": "MAC adresi",
            "status": "Durum",
            "adapter_kind": "Tür",
            "hardware_interface": "Donanım arayüzü",
            "media_type": "Medya türü",
            "ndis_physical_medium": "Fiziksel ortam",
            "link_speed": "Bağlantı hızı",
            "interface_index": "Arayüz indeksi",
        })
        st.dataframe(
            adapter_display,
            width="stretch",
            hide_index=True,
            height=min(420, 58 + 35 * min(len(adapter_display), 10)),
        )
        st.caption(
            "Bu liste fiziksel, sanal, devre dışı ve gizli Windows adaptörlerini "
            "kapsayabilir. Yalnızca tarama bilgisayarının yerel envanteridir; "
            "uzak cihazların adaptör listesini göstermez."
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
        explicit_role = str(row.get("device_role", "")).strip()
        if explicit_role in {
            "Router / Gateway", "Access Point", "Switch",
            "Repeater", "Mesh Node", "Firewall", "Controller",
        }:
            return explicit_role
        if explicit_role == "Network equipment candidate":
            return "Ağ ekipmanı adayı"

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
            return "Ağ ekipmanı adayı"

        vendor = str(row.get(vendor_col, "")).lower()
        if vendor and any(x in vendor for x in [
            "ruijie", "tp-link", "ubiquiti", "mikrotik", "cisco", "huawei"
        ]):
            return "Ağ ekipmanı adayı"

        return "Diğer / Belirsiz"

    devices["Altyapi rolu"] = devices.apply(role_for, axis=1)

    def evidence_for(row):
        role = row["Altyapi rolu"]
        category = str(
            row.get(category_col, "") if category_col else ""
        ).lower()
        classification_value = str(row.get(class_col, "")).lower()

        if role == "Diğer / Belirsiz":
            return "Sınıflandırılmamış"
        if role == "Ağ ekipmanı adayı":
            if str(row.get("role_evidence_type", "")).strip() == "vendor_only":
                return "Yalnızca üretici bilgisi; cihaz rolü doğrulanmadı"
            return "Üretici veya tahmini sınıflandırma"
        if str(row.get("role_evidence_type", "")).strip() == "hostname_role_hint":
            return "Hostname ipucuna dayalı tahmin"
        if str(row.get("role_evidence_type", "")).strip() == "hostname_model_family_inference":
            return "Model ailesi ipucuna dayalı tahmin"
        if "manufacturer-based inference" in category or "inferred" in classification_value:
            return "Tahmini sınıflandırma"
        return "Kayıtlı sınıflandırma"

    devices["KanIt durumu"] = devices.apply(evidence_for, axis=1)

    total = len(devices)
    infrastructure = devices[
        devices["Altyapi rolu"] != "Diğer / Belirsiz"
    ]
    candidates = devices[
        devices["Altyapi rolu"] == "Ağ ekipmanı adayı"
    ]

    a, b, c, d = st.columns(4)
    a.metric("Toplam cihaz", f"{total:,}")
    b.metric("Altyapı kaydı", f"{len(infrastructure):,}")
    c.metric("Ekipman adayı", f"{len(candidates):,}")
    d.metric("Wi-Fi AP kaydı", f"{len(access_points):,}")

    st.divider()

    overview, inventory_tab, wifi_tab, evidence_tab = st.tabs([
        "Genel bakış",
        "Cihaz envanteri",
        "Wi-Fi bağlantısı",
        "Kanıt ve kaynaklar",
    ])

    with overview:
        st.markdown("### Altyapı rol dağılımı")
        counts = (
            devices["Altyapi rolu"]
            .value_counts()
            .rename_axis("Rol")
            .reset_index(name="Cihaz sayısı")
        )
        left, right = st.columns([1.15, 1])
        with left:
            try:
                import plotly.graph_objects as go

                figure = go.Figure(go.Bar(
                    x=counts["Cihaz sayısı"].astype(int),
                    y=counts["Rol"].astype(str),
                    orientation="h",
                    marker_color="#087F78",
                    text=counts["Cihaz sayısı"].astype(int),
                    textposition="outside",
                    cliponaxis=False,
                    hovertemplate="%{y}: %{x} cihaz<extra></extra>",
                ))
                figure.update_layout(
                    height=max(250, 42 * len(counts) + 70),
                    margin={"l": 8, "r": 32, "t": 8, "b": 35},
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    showlegend=False,
                    font={"family": "Segoe UI, sans-serif", "color": "#182B2A", "size": 12},
                    xaxis={"title": "Cihaz sayısı", "rangemode": "tozero",
                           "showgrid": True, "gridcolor": "#E7EEEA"},
                    yaxis={"title": "", "automargin": True},
                )
                st.plotly_chart(
                    figure, width="stretch", config={"displayModeBar": False}
                )
            except ImportError:
                st.dataframe(counts, width="stretch", hide_index=True)
        with right:
            st.markdown("### Kanıt dağılımı")
            evidence_counts = (
                devices["KanIt durumu"]
                .value_counts()
                .rename_axis("Kanıt seviyesi")
                .reset_index(name="Kayıt")
            )
            st.dataframe(
                evidence_counts,
                width="stretch",
                hide_index=True,
                height=min(360, 58 + 38 * len(evidence_counts)),
            )

        st.info(
            "Aynı ağda görünmek fiziksel bağlantı kanıtı değildir. AP-istemci ilişkisi "
            "yalnızca doğrudan ve doğrulanmış kaynaklardan geldiğinde doğrulanmış sayılır."
        )

    with inventory_tab:
        st.subheader("Ağ ekipmanı envanteri")

        filters = st.columns([2, 1, 1])
        with filters[0]:
            search = st.text_input(
                "Envanterde ara",
                placeholder="IP, MAC, marka, model veya cihaz adı",
                key="infrastructure_inventory_search",
            )
        role_options = ["Tüm roller"] + sorted(
            devices["Altyapi rolu"].dropna().unique().tolist()
        )
        with filters[1]:
            selected_role = st.selectbox(
                "Altyapı rolü", role_options, key="infrastructure_role_filter"
            )
        evidence_options = ["Tüm kanıtlar"] + sorted(
            devices["KanIt durumu"].dropna().unique().tolist()
        )
        with filters[2]:
            selected_evidence = st.selectbox(
                "Kanıt durumu", evidence_options,
                key="infrastructure_evidence_filter",
            )

        filtered = devices.copy()
        if search.strip():
            mask = filtered.astype(str).apply(
                lambda col: col.str.contains(
                    search.strip(), case=False, na=False, regex=False
                )
            ).any(axis=1)
            filtered = filtered[mask]
        if selected_role != "Tüm roller":
            filtered = filtered[filtered["Altyapi rolu"] == selected_role]
        if selected_evidence != "Tüm kanıtlar":
            filtered = filtered[filtered["KanIt durumu"] == selected_evidence]

        st.caption(f"{len(filtered):,} kayit listeleniyor.")

        preferred = [
            name_col, ip_col, mac_col, vendor_col,
            "model", "firmware_version", "model_status", "firmware_status", "Altyapi rolu",
            status_col, "KanIt durumu"
        ]
        columns = []
        for col in preferred:
            if col in filtered.columns and col not in columns:
                columns.append(col)

        if columns:
            display_names = {
                name_col: "Cihaz",
                ip_col: "IP adresi",
                mac_col: "MAC adresi",
                vendor_col: "Üretici",
                "model": "Model",
                "firmware_version": "Firmware",
                "model_status": "Model kanıtı",
                "firmware_status": "Firmware kanıtı",
                "Altyapi rolu": "Altyapı rolü",
                status_col: "Durum",
                "KanIt durumu": "Kanıt durumu",
            }
            display = filtered[columns].rename(columns={
                column: display_names.get(
                    column, str(column).replace("_", " ").title()
                )
                for column in columns
            })
            st.dataframe(
                display.head(200),
                width="stretch",
                hide_index=True,
                height=min(520, 58 + 35 * min(len(display), 12)),
            )
            if len(display) > 200:
                st.caption(
                    "İlk 200 kayıt gösteriliyor. Arama ve rol filtresiyle daraltabilirsiniz."
                )

        if not filtered.empty:
            @st.dialog("Altyapı cihazı", width="large")
            def show_infrastructure_device(selected):
                left, right = st.columns(2)
                for column, fields in [
                    (left, [(name_col, "Cihaz adı"), (ip_col, "IP adresi"), (mac_col, "MAC adresi"), (vendor_col, "Üretici")]),
                    (right, [("model", "Model"), ("model_status", "Model kanıt durumu"), ("model_source", "Model kaynağı"), ("firmware_version", "Firmware"), ("firmware_status", "Firmware kanıt durumu"), ("firmware_source", "Firmware kaynağı"), ("ssid", "SSID"), ("channel", "Kanal"), ("frequency", "Frekans"), ("band", "Bant")]),
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
        st.subheader("Mevcut Wi-Fi bağlantısı")
        if wifi.empty:
            st.info("Wi-Fi baglanti verisi bulunamadi.")
        else:
            st.dataframe(wifi, width="stretch", hide_index=True)

        st.subheader("Keşfedilen erişim noktaları")
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


        st.divider()
        st.subheader("Doğrulanmış AP–istemci ilişkileri")
        st.caption(
            "Yalnızca Windows WLAN arayüzünden doğrudan alınan istemci MAC → AP BSSID "
            "eşleşmeleri doğrulanmış kabul edilir. Ortak SSID veya aynı ağda bulunma "
            "tek başına AP bağlantısı kanıtı değildir."
        )
        associations = split_ap_client_records(ap_client_history)
        verified_associations = associations["verified"]
        unverified_associations = associations["unverified"]
        assoc_left, assoc_right = st.columns(2)
        assoc_left.metric("Doğrulanmış gözlem", f"{len(verified_associations):,}")
        assoc_right.metric("Doğrulanmamış kayıt", f"{len(unverified_associations):,}")
        association_columns = [
            "observed_at", "client_hostname", "client_mac", "client_ip",
            "ap_bssid", "ssid", "source", "evidence_type",
            "confidence", "verification_status",
        ]
        if not verified_associations.empty:
            st.markdown("**Doğrudan doğrulanmış ilişkiler**")
            available = [column for column in association_columns if column in verified_associations.columns]
            st.dataframe(
                verified_associations[available].rename(columns={
                    "observed_at": "Gözlem zamanı",
                    "client_hostname": "İstemci",
                    "client_mac": "İstemci MAC",
                    "client_ip": "İstemci IP",
                    "ap_bssid": "AP BSSID",
                    "ssid": "SSID",
                    "source": "Kaynak",
                    "evidence_type": "Kanıt türü",
                    "confidence": "Güven",
                    "verification_status": "Doğrulama",
                }),
                width="stretch",
                hide_index=True,
                height=min(420, 58 + 35 * min(len(verified_associations), 10)),
            )
        else:
            st.info("Henüz doğrudan doğrulanmış AP–istemci gözlemi yok.")
        if not unverified_associations.empty:
            with st.expander("Doğrulanmamış AP–istemci kayıtları"):
                st.caption("Bu kayıtlar doğrulanmış ilişki olarak sunulmaz.")
                st.dataframe(unverified_associations, width="stretch", hide_index=True)

    with evidence_tab:
        st.subheader("Kanıt ve veri kaynakları")
        st.markdown(
            "- **Kayitli siniflandirma:** Kaynak dosyada cihaz turu veya siniflandirma var.\n"
            "- **Uretici bilgisine dayali aday:** Uretici ag ekipmani markasi olarak taniniyor; rol kesin degil.\n"
            "- **Tahmini siniflandirma:** Siniflandirma kaynagi tahmine dayaniyor.\n"
            "- **Siniflandirilmamis:** Cihaz turu icin yeterli veri yok.\n"
            "- **Model/Firmware verified:** Yönetim API’si veya manuel doğrulama kaynağı.\n"
            "- **Model/Firmware observed_unverified:** SNMP/LLDP açıklaması; cihaz kimliği ayrıca doğrulanmalı.\n"
            "- **Model/Firmware unknown:** Kaynak veri yok; tahminle doldurulmaz."
        )

        st.markdown("**Kullanilan yerel veri dosyalari**")
        for filename in [
            "device_inventory.csv",
            "topology_nodes.csv",
            "device_classification.csv",
            "wifi_connection.csv",
            "wifi_access_points.csv",
            "network_context.csv"
        ]:
            path = DATA / filename
            st.write(
                f"{filename} ? "
                f"{'Mevcut' if path.exists() else 'Bulunamadi'}"
            )



def split_ap_client_records(frame):
    """Separate direct, explicitly verified AP associations from all other records."""
    if frame is None or frame.empty:
        empty = pd.DataFrame() if frame is None else frame.iloc[0:0].copy()
        return {"verified": empty.copy(), "unverified": empty.copy()}

    required = {"verification_status", "confidence", "evidence_type"}
    if not required.issubset(frame.columns):
        return {"verified": frame.iloc[0:0].copy(), "unverified": frame.copy()}

    verified_mask = (
        frame["verification_status"].fillna("").astype(str).str.strip().str.casefold().eq("verified")
        & frame["confidence"].fillna("").astype(str).str.strip().str.casefold().eq("verified")
        & frame["evidence_type"].fillna("").astype(str).str.strip().str.casefold().eq("direct_association")
    )
    return {
        "verified": frame[verified_mask].copy(),
        "unverified": frame[~verified_mask].copy(),
    }
