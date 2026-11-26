from pathlib import Path
import pandas as pd
import streamlit as st

from scripts.topology_evidence import (
    extract_selected_node_id,
    prepare_association_history,
    prepare_relationship_history,
    prepare_verified_edge_options,
    split_topology_edges,
)


DATA = Path(__file__).resolve().parent.parent / "data" / "processed"


def read_data(filename):
    path = DATA / filename
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return pd.DataFrame()


def first_column(df, names):
    for name in names:
        if name in df.columns:
            return name
    return None



@st.dialog("Cihaz bilgileri", width="large")
def show_topology_device(row):
    left, right = st.columns(2)
    fields = [
        ("Cihaz", "_label"), ("IP adresi", "_ip"),
        ("Tür", "_type"), ("Durum", "_status"),
        ("Üretici", "vendor"), ("MAC adresi", "mac"),
    ]
    for index, (label, key) in enumerate(fields):
        with (left if index % 2 == 0 else right):
            st.markdown(f"**{label}**")
            st.write(str(row.get(key, "") or "Bilinmiyor"))
    with st.expander("Kaynak kaydın tüm alanları"):
        for key, value in row.items():
            if str(value).strip():
                st.markdown(f"**{key}**")
                st.write(str(value))


def render():
    nodes = read_data("topology_nodes.csv")
    edges = read_data("topology_edges.csv")
    inventory = read_data("device_inventory.csv")
    wifi = read_data("wifi_connection.csv")

    st.markdown(
        '<div class="wv-page-header"><h1>Ağ topolojisi</h1>'
        '<p>Gözlemlenen cihazları ve yalnızca doğrulanmış bağlantıları kanıt düzeyiyle incele.</p></div>',
        unsafe_allow_html=True,
    )

    if nodes.empty and inventory.empty:
        st.warning("Topoloji verisi bulunamadi. Once cihaz kesfi yapilmalidir.")
        return

    if nodes.empty:
        nodes = inventory.copy()
        nodes["id"] = nodes.get("ip", pd.Series(dtype=str))
        nodes["label"] = nodes.get("hostname", nodes.get("ip", "Bilinmeyen"))
        nodes["node_type"] = "unknown"

    ip_col = first_column(nodes, ["ip", "IP"])
    label_col = first_column(nodes, ["label", "hostname", "device_name", "ip"])
    type_col = first_column(nodes, ["node_type", "device_type", "type"])
    status_col = first_column(nodes, ["status", "state"])
    vendor_col = first_column(nodes, ["vendor", "manufacturer"])
    mac_col = first_column(nodes, ["mac", "mac_address"])

    if label_col is None:
        nodes["label"] = "Bilinmeyen cihaz"
        label_col = "label"

    nodes = nodes.copy()
    nodes["_label"] = nodes[label_col].astype(str)
    nodes["_ip"] = nodes[ip_col].astype(str) if ip_col else ""
    nodes["_type"] = nodes[type_col].astype(str) if type_col else "unknown"
    nodes["_status"] = nodes[status_col].astype(str) if status_col else "unknown"

    # Scope nodes provide context, not device inventory entries.
    device_nodes = nodes[nodes["_type"].str.lower() != "network_scope"].copy()
    total = len(device_nodes)
    online = device_nodes["_status"].str.lower().isin(
        ["online", "up", "active", "responding", "reachable"]
    ).sum()

    gateway_count = device_nodes["_type"].str.contains(
        "gateway|router", case=False, na=False
    ).sum()

    edge_from = first_column(edges, ["source", "from", "source_id", "src", "from_id"])
    edge_to = first_column(edges, ["target", "to", "target_id", "dst", "to_id"])

    relation_col = first_column(edges, ["relation", "type", "relationship"])
    confidence_col = first_column(edges, ["confidence"])

    edge_groups = split_topology_edges(edges, edge_from, edge_to)
    verified_edges = edge_groups["verified"]
    inferred_edges = edge_groups["inferred"]
    context_edges = edge_groups["context"]
    unverified_edges = edge_groups["unverified"]

    e_count = len(verified_edges)
    inferred_count = len(inferred_edges)
    context_count = len(context_edges)
    unverified_count = len(unverified_edges)

    a, b, c, d = st.columns(4)
    a.metric("Gözlemlenen cihaz", f"{total:,}")
    b.metric("Yanıt veren", f"{online:,}")
    c.metric("Doğrulanmış bağlantı", f"{e_count:,}")
    d.metric("Tahmini ilişki", f"{inferred_count:,}")
    st.caption(
        f"Ağ bağlamı: {context_count:,} · Kanıtı yetersiz: {unverified_count:,} · "
        f"Gateway/router adayı: {gateway_count:,}"
    )

    st.markdown("### İlişki haritası")
    st.caption(
        "Düğümler cihaz rolüne göre gruplanır. Çizgiler yalnızca doğrudan doğrulanmış "
        "ilişkileri gösterir; aynı tarama kapsamı fiziksel bağlantı anlamına gelmez."
    )

    if total:
        try:
            import html
            import plotly.graph_objects as go

            ids_col = first_column(device_nodes, ["id", "ip", "mac"])
            if ids_col is None:
                ids_col = "_label"

            lane_config = {
                "gateway_address": ("Gateway adresi", 3, "diamond", "#8A5A12"),
                "access_point_radio": ("AP radyosu", 2, "hexagon", "#087F78"),
                "network_device_candidate": ("Ağ ekipmanı adayı", 1, "square", "#426C8C"),
                "endpoint": ("Uç cihaz", 0, "circle", "#73827F"),
                "wifi_client": ("Wi-Fi istemcisi", 0, "circle", "#73827F"),
            }
            positions = {}
            grouped_nodes = {}
            for _, row in device_nodes.iterrows():
                node_id = str(row.get(ids_col, "")).strip()
                if not node_id:
                    continue
                node_type = str(row.get("_type", "unknown")).strip().lower()
                config = lane_config.get(
                    node_type, ("Diğer / sınıflandırılmamış", -1, "circle", "#73827F")
                )
                grouped_nodes.setdefault(config[0], []).append((node_id, row, config))

            lane_order = [
                "Gateway adresi", "AP radyosu", "Ağ ekipmanı adayı",
                "Uç cihaz", "Diğer / sınıflandırılmamış",
            ]
            # Wrap large device groups into rows instead of stretching a single
            # horizontal line. This keeps labels and nodes separated on laptops.
            lane_centers = {}
            max_columns = 7
            lane_cursor = 0.0
            total_layout_rows = 0
            for lane in lane_order:
                members = grouped_nodes.get(lane, [])
                if not members:
                    continue
                row_count = (len(members) + max_columns - 1) // max_columns
                total_layout_rows += row_count
                lane_centers[lane] = lane_cursor - (row_count - 1) * 0.75 / 2
                for index, (node_id, row, config) in enumerate(members):
                    row_index, column_index = divmod(index, max_columns)
                    row_size = min(max_columns, len(members) - row_index * max_columns)
                    x = (column_index - (row_size - 1) / 2) * 2.0
                    y = lane_cursor - row_index * 1.5
                    positions[node_id] = (x, y)
                lane_cursor -= row_count * 1.5 + 1.8

            figure = go.Figure()
            edge_x, edge_y = [], []
            if edge_from and edge_to:
                for _, edge in verified_edges.iterrows():
                    source_id = str(edge[edge_from]).strip()
                    target_id = str(edge[edge_to]).strip()
                    if source_id in positions and target_id in positions:
                        edge_x.extend([
                            positions[source_id][0], positions[target_id][0], None
                        ])
                        edge_y.extend([
                            positions[source_id][1], positions[target_id][1], None
                        ])
            if edge_x:
                figure.add_trace(go.Scatter(
                    x=edge_x,
                    y=edge_y,
                    mode="lines",
                    line={"width": 1.7, "color": "#A8B8B2"},
                    hoverinfo="skip",
                    name="Doğrulanmış bağlantı",
                ))

            for lane in lane_order:
                members = grouped_nodes.get(lane, [])
                if not members:
                    continue
                config = members[0][2]
                x_values, y_values, labels, hover = [], [], [], []
                for node_id, row, _ in members:
                    x, y = positions[node_id]
                    x_values.append(x)
                    y_values.append(y)
                    label = str(row.get("_label", node_id)).strip() or node_id
                    labels.append(html.escape(label[:16] + ("…" if len(label) > 16 else "")))
                    hover.append(
                        f"Cihaz: {html.escape(str(row.get('_label', '')))}<br>"
                        f"IP: {html.escape(str(row.get('_ip', '')))}<br>"
                        f"Tür: {html.escape(str(row.get('_type', '')))}<br>"
                        f"Durum: {html.escape(str(row.get('_status', '')))}<br>"
                        f"MAC: {html.escape(str(row.get(mac_col, '')))}"
                    )
                node_ids = [item[0] for item in members]
                figure.add_trace(go.Scatter(
                    x=x_values,
                    y=y_values,
                    customdata=node_ids,
                    mode="markers+text",
                    text=labels,
                    textposition="top center",
                    textfont={"size": 9, "color": "#344744"},
                    hovertext=hover,
                    hoverinfo="text",
                    marker={
                        "size": 19,
                        "symbol": config[2],
                        "color": config[3],
                        "line": {"width": 1.5, "color": "#FFFFFF"},
                    },
                    name=lane,
                ))

            if not edge_x:
                st.info(
                    "Henüz doğrulanmış bağlantı yok. Cihazlar rol gruplarında gösteriliyor; "
                    "bu yerleşim fiziksel bağlantı iddiası değildir."
                )
            figure.update_layout(
                height=min(1600, max(440, 260 + 88 * total_layout_rows)),
                margin={"l": 18, "r": 18, "t": 28, "b": 35},
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="#FFFFFF",
                showlegend=True,
                legend={"orientation": "h", "y": 1.08, "x": 0},
                font={"family": "Segoe UI, sans-serif", "color": "#182B2A", "size": 11},
                xaxis={"visible": False, "showgrid": False, "zeroline": False},
                yaxis={
                    "tickmode": "array",
                    "tickvals": [lane_centers[lane] for lane in lane_order if lane in lane_centers],
                    "ticktext": [lane for lane in lane_order if lane in lane_centers],
                    "range": [
                        min((point[1] for point in positions.values()), default=-1) - 1.0,
                        max((point[1] for point in positions.values()), default=1) + 1.4,
                    ],
                    "showgrid": False,
                    "zeroline": False,
                    "ticks": "",
                    "automargin": True,
                },
                hoverlabel={"bgcolor": "#FFFFFF", "font": {"color": "#182B2A"}},
            )
            chart_selection = st.plotly_chart(
                figure,
                width="stretch",
                config={"displayModeBar": False},
                on_select="rerun",
                selection_mode="points",
                key="topology_relationship_map",
            )
            selected_node_id = extract_selected_node_id(chart_selection)
            if selected_node_id:
                selected_rows = device_nodes[
                    device_nodes[ids_col].astype(str).str.strip() == selected_node_id
                ]
                if not selected_rows.empty:
                    selected_node = selected_rows.iloc[0]
                    st.markdown("#### Haritada seçilen cihaz")
                    detail_left, detail_right = st.columns(2)
                    with detail_left:
                        st.markdown("**Cihaz / IP**")
                        st.write(str(selected_node.get("_label", "Bilinmiyor")))
                        st.write(str(selected_node.get("_ip", "IP yok")))
                        st.markdown("**Rol / durum**")
                        st.write(str(selected_node.get("_type", "Bilinmiyor")))
                        st.write(str(selected_node.get("_status", "Bilinmiyor")))
                    with detail_right:
                        st.markdown("**Üretici / MAC**")
                        st.write(str(selected_node.get(vendor_col, "") or "Bilinmiyor"))
                        st.write(str(selected_node.get(mac_col, "") or "Bilinmiyor"))
                        st.caption("Bu panel, haritada seçilen cihazın mevcut yerel envanter kaydını gösterir.")
        except ImportError:
            st.info("Grafik kütüphanesi bulunamadı. Doğrulanmış bağlantılar tablo olarak gösteriliyor.")
            if not verified_edges.empty:
                st.dataframe(verified_edges, width="stretch", hide_index=True)
        except Exception as exc:
            st.warning(f"Ağ haritası oluşturulamadı: {exc}")
            if not verified_edges.empty:
                st.dataframe(verified_edges, width="stretch", hide_index=True)
    else:
        st.info("Topoloji için henüz cihaz verisi bulunmuyor.")

    display_columns = [
        col for col in [
            edge_from, edge_to, relation_col, confidence_col,
            "evidence_type", "evidence_source", "observed_at", "details"
        ] if col and col in edges.columns
    ]

    for title, frame, explanation in [
        ("Tahmini ilişkiler", inferred_edges,
         "Cihaz adı veya sınıflandırma gibi dolaylı ipuçlarıdır; doğrulanmış fiziksel bağlantı değildir."),
        ("Aynı ağda gözlemlenenler", context_edges,
         "Ortak tarama kapsamı veya ağ yapılandırması bağlamıdır; fiziksel bağlantı kanıtı değildir."),
        ("Kanıtı yetersiz kayıtlar", unverified_edges,
         "Kaynakta açık bir doğrulama seviyesi bulunmuyor; bu kayıtlar haritada bağlantı olarak çizilmez."),
    ]:
        if not frame.empty:
            st.subheader(title)
            st.caption(explanation)
            if display_columns:
                st.dataframe(
                    frame[display_columns],
                    width="stretch",
                    hide_index=True,
                    height=240,
                )

    if not verified_edges.empty:
        st.subheader("Bağlantı seçimi ve kanıt geçmişi")
        edge_options = prepare_verified_edge_options(
            verified_edges, edge_from, edge_to
        )
        selected_index = st.selectbox(
            "İncelenecek doğrulanmış bağlantı",
            options=[option["index"] for option in edge_options],
            format_func=lambda index: edge_options[index]["label"],
            key="topology_verified_edge_detail",
        )
        selected_edge = verified_edges.reset_index(drop=True).iloc[selected_index]
        selected_source = str(selected_edge.get(edge_from, "")).strip()
        selected_target = str(selected_edge.get(edge_to, "")).strip()

        detail_ids_col = first_column(device_nodes, ["id", "ip", "mac"]) or "_label"
        node_labels = {}
        if detail_ids_col in device_nodes.columns:
            node_labels = {
                str(row.get(detail_ids_col, "")).strip(): str(row.get("_label", "")).strip()
                for _, row in device_nodes.iterrows()
                if str(row.get(ids_col, "")).strip()
            }
        source_label = node_labels.get(selected_source, selected_source)
        target_label = node_labels.get(selected_target, selected_target)
        st.markdown(f"**{source_label}** → **{target_label}**")
        st.caption(
            "Seçim, kaynak kayıttaki yönü korur. Aşağıdaki geçmiş aynı iki uç arasındaki "
            "tüm kayıtları gösterir; ters yönlü kayıtlar da ayrıca belirtilir."
        )

        left, right = st.columns(2)
        with left:
            st.markdown("**Kanıt kaynağı**")
            st.write(str(selected_edge.get("evidence_source", "") or "Bilinmiyor"))
            st.markdown("**Kanıt türü**")
            st.write(str(selected_edge.get("evidence_type", "") or "Bilinmiyor"))
        with right:
            st.markdown("**Doğrulama seviyesi**")
            st.write(str(selected_edge.get("confidence", "") or "Bilinmiyor"))
            st.markdown("**Gözlem zamanı**")
            st.write(str(selected_edge.get("observed_at", "") or "Bilinmiyor"))
        if str(selected_edge.get("details", "")).strip():
            st.caption(str(selected_edge.get("details")))

        pair_history = prepare_relationship_history(
            edges, selected_source, selected_target, edge_from, edge_to
        )
        if not pair_history.empty:
            history_columns = [
                column for column in [
                    edge_from, edge_to, relation_col, confidence_col,
                    "evidence_type", "evidence_source", "observed_at", "details",
                ] if column and column in pair_history.columns
            ]
            st.markdown("**Bu iki cihaz arasındaki kayıt geçmişi**")
            st.caption(
                f"{len(pair_history):,} ilişki kaydı · En yeni gözlem üstte · "
                "Yalnızca doğrulanmış kayıtlar haritada çizilir."
            )
            st.dataframe(
                pair_history[history_columns],
                width="stretch",
                hide_index=True,
                height=min(320, 58 + 35 * min(len(pair_history), 7)),
            )
        else:
            st.info("Seçilen iki cihaz için ilişki geçmişi bulunamadı.")

    st.divider()
    st.markdown("### Cihaz envanteri")
    search_col, type_col = st.columns([2, 1])
    with search_col:
        search = st.text_input(
            "Cihaz ara",
            placeholder="IP, MAC, marka veya cihaz adı",
            key="topology_device_search",
        )
    with type_col:
        type_options = ["Tüm cihazlar"] + sorted(
            [value for value in device_nodes["_type"].dropna().unique().tolist() if value]
        )
        selected_type = st.selectbox(
            "Cihaz rolü", type_options, key="topology_device_type"
        )

    filtered = device_nodes.copy()
    if search.strip():
        mask = filtered.astype(str).apply(
            lambda column: column.str.contains(
                search.strip(), case=False, na=False, regex=False
            )
        ).any(axis=1)
        filtered = filtered[mask]
    if selected_type != "Tüm cihazlar":
        filtered = filtered[filtered["_type"] == selected_type]

    st.caption(f"{len(filtered):,} cihaz eşleşti.")
    if filtered.empty:
        st.info("Bu filtrelerle eşleşen cihaz yok.")
    else:
        device_columns = [
            column for column in [
                "_label", "_ip", mac_col, "_type", vendor_col, "_status",
            ] if column and column in filtered.columns
        ]
        display = filtered[device_columns].rename(columns={
            "_label": "Cihaz",
            "_ip": "IP adresi",
            mac_col: "MAC adresi",
            "_type": "Rol / tür",
            vendor_col: "Üretici",
            "_status": "Durum",
        })
        st.dataframe(
            display.head(200),
            width="stretch",
            hide_index=True,
            height=min(480, 58 + 35 * min(len(display), 11)),
        )
        if len(display) > 200:
            st.caption("İlk 200 cihaz gösteriliyor. Arama ve rol filtresiyle daraltabilirsiniz.")
        selected_index = st.selectbox(
            "Detayını incele",
            options=filtered.index.tolist(),
            format_func=lambda index: (
                f"{filtered.loc[index, '_label']} · "
                f"{filtered.loc[index, '_ip'] or 'IP yok'}"
            ),
            key="topology_device_detail_select",
        )
        if st.button("Cihaz kanıtlarını aç", key="topology_device_detail_open"):
            show_topology_device(filtered.loc[selected_index])

    st.divider()
    st.subheader("AP-istemci bağlantı geçmişi")
    association_history = read_data("ap_client_relationships.csv")
    if not association_history.empty:
        association_history = prepare_association_history(association_history)
        h1, h2, h3 = st.columns(3)
        h1.metric("Gozlem kaydi", f"{len(association_history):,}")
        client_count = (
            association_history["client_mac"].nunique()
            if "client_mac" in association_history.columns else 0
        )
        ap_count = (
            association_history["ap_bssid"].nunique()
            if "ap_bssid" in association_history.columns else 0
        )
        h2.metric("Istemci", f"{client_count:,}")
        h3.metric("AP radyosu", f"{ap_count:,}")
        history_search = st.text_input(
            "Gecmiste istemci veya AP ara",
            placeholder="MAC, cihaz adi veya SSID",
            key="topology_association_history_search",
        )
        history_filtered = association_history.copy()
        if history_search.strip():
            history_mask = history_filtered.astype(str).apply(
                lambda column: column.str.contains(
                    history_search.strip(), case=False, na=False, regex=False
                )
            ).any(axis=1)
            history_filtered = history_filtered[history_mask]
        history_columns = [
            column for column in [
                "observed_at", "client_hostname", "client_ip", "client_mac",
                "ssid", "ap_bssid", "source", "confidence", "verification_status",
            ] if column in history_filtered.columns
        ]
        st.caption(f"{len(history_filtered):,} kayit | En yeni gozlem en ustte")
        if history_columns:
            st.dataframe(
                history_filtered[history_columns],
                width="stretch",
                hide_index=True,
                height=300,
            )
    else:
        st.caption("Henuz AP-istemci gozlem gecmisi bulunmuyor.")

    st.divider()
    st.subheader("Mevcut Wi-Fi bağlantısı")
    if not wifi.empty:
        st.dataframe(wifi, width="stretch", hide_index=True)
    else:
        st.caption("Wi-Fi baglanti kaydi bulunamadi.")

    st.caption(
        "Kanita dayali topoloji: dogrulanmis, gozlemlenmis ve tahmini iliskiler "
        "birbirinden ayri tutulmalidir. Bu ekran tek basina fiziksel kablo veya "
        "AP-istemci iliskisini dogrulamaz."
    )
