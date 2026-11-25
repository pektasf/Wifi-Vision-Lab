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

    st.title("Ag Topolojisi")
    st.caption("Yerel ag cihazlari, gozlemlenen iliskiler ve altyapi gorunumu")

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
    confidence_col = first_column(edges, ["confidence", "evidence", "status"])

    valid_edges = pd.DataFrame()
    context_edges = pd.DataFrame()

    if edge_from and edge_to and not edges.empty:
        valid_mask = (
            (edges[edge_from].astype(str).str.strip() != "") &
            (edges[edge_to].astype(str).str.strip() != "")
        )
        all_edges = edges[valid_mask].copy()

        context_mask = pd.Series(False, index=all_edges.index)
        if relation_col:
            context_mask |= all_edges[relation_col].astype(str).str.lower().isin(
                ["same_network", "same network", "context_only"]
            )
        if confidence_col:
            context_mask |= all_edges[confidence_col].astype(str).str.lower().isin(
                ["context_only", "inferred", "low"]
            )

        context_edges = all_edges[context_mask].copy()
        valid_edges = all_edges[~context_mask].copy()

    e_count = len(valid_edges)
    context_count = len(context_edges)

    a, b, c, d = st.columns(4)
    a.metric("Toplam cihaz", f"{total:,}")
    b.metric("Cevap veren", f"{online:,}")
    c.metric("Gateway / router", f"{gateway_count:,}")
    d.metric("Dogrulanmis baglanti", f"{e_count:,}")

    st.divider()

    st.subheader("Ag haritasi")
    st.caption(
        "Yalnizca dogrudan dogrulanmis iliskiler baglanti olarak cizilir. "
        "Ayni tarama kapsaminda gorunmek fiziksel baglanti kaniti degildir."
    )

    if e_count and edge_from and edge_to:
        try:
            import plotly.graph_objects as go
            import math

            ids_col = first_column(nodes, ["id", "ip", "mac"])
            if ids_col is None:
                ids_col = "_label"

            node_ids = nodes[ids_col].astype(str).tolist()
            positions = {}
            count = max(len(node_ids), 1)

            for i, node_id in enumerate(node_ids):
                angle = 2 * math.pi * i / count
                positions[node_id] = (math.cos(angle), math.sin(angle))

            edge_x, edge_y = [], []
            for _, edge in valid_edges.iterrows():
                s, t = str(edge[edge_from]), str(edge[edge_to])
                if s in positions and t in positions:
                    edge_x.extend([positions[s][0], positions[t][0], None])
                    edge_y.extend([positions[s][1], positions[t][1], None])

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=edge_x, y=edge_y,
                mode="lines",
                line=dict(width=1.5, color="#94A3B8"),
                hoverinfo="skip",
                name="Kayitli iliskiler"
            ))

            node_x, node_y, hover, labels = [], [], [], []
            for _, row in nodes.iterrows():
                node_id = str(row[ids_col])
                if node_id not in positions:
                    continue
                x, y = positions[node_id]
                node_x.append(x)
                node_y.append(y)
                labels.append(str(row["_label"])[:24])
                hover.append(
                    f"Cihaz: {row['_label']}<br>"
                    f"IP: {row['_ip']}<br>"
                    f"Tur: {row['_type']}<br>"
                    f"Durum: {row['_status']}"
                )

            fig.add_trace(go.Scatter(
                x=node_x, y=node_y,
                mode="markers+text",
                text=labels,
                textposition="bottom center",
                hovertext=hover,
                hoverinfo="text",
                marker=dict(size=19, color="#2563EB",
                            line=dict(width=2, color="#FFFFFF")),
                name="Ag cihazlari"
            ))

            fig.update_layout(
                height=540,
                margin=dict(l=20, r=20, t=20, b=45),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                showlegend=True,
                xaxis=dict(visible=False),
                yaxis=dict(visible=False),
                dragmode="pan"
            )
            st.plotly_chart(fig, width="stretch")
        except ImportError:
            st.info("Grafik kutuphanesi bulunamadi. Baglanti kayitlari tablo olarak gosteriliyor.")
            st.dataframe(edges, width="stretch", hide_index=True)
        except Exception as exc:
            st.warning(f"Ag haritasi olusturulamadi: {exc}")
            st.dataframe(edges, width="stretch", hide_index=True)
    else:
        st.info(
            "Henuz cizilebilir baglanti kaydi yok. Cihazlar kesfedilmis olabilir; "
            "ancak fiziksel veya AP-istemci baglantilari icin dogrulanmis kaynak gerekir."
        )

    if context_count:
        st.subheader("Ayni agda gozlemlenen cihazlar")
        st.caption(
            f"{context_count} iliski ayni ag baglamini gosteriyor. "
            "Bunlar fiziksel kablo veya AP-istemci baglantisi kaniti degildir."
        )
        context_cols = [
            col for col in [
                edge_from, edge_to, relation_col, confidence_col,
                "evidence_type", "evidence_source", "observed_at", "details"
            ] if col and col in context_edges.columns
        ]
        if context_cols:
            st.dataframe(
                context_edges[context_cols],
                width="stretch",
                hide_index=True,
                height=260
            )

    st.divider()
    st.subheader("Cihazlar")
    st.caption("Önemli bilgiler kartlarda; teknik ayrıntılar cihaz penceresinde.")
    search = st.text_input("Cihaz ara", placeholder="IP, MAC, marka veya cihaz adı", key="topology_device_search")
    type_options = ["Tüm cihazlar"] + sorted(
        [x for x in nodes["_type"].dropna().unique().tolist() if x]
    )
    selected_type = st.selectbox("Cihaz türü", type_options, key="topology_device_type")

    filtered = device_nodes.copy()
    if search.strip():
        mask = filtered.astype(str).apply(
            lambda col: col.str.contains(search.strip(), case=False, na=False, regex=False)
        ).any(axis=1)
        filtered = filtered[mask]
    if selected_type != "Tüm cihazlar":
        filtered = filtered[filtered["_type"] == selected_type]

    st.caption(f"{len(filtered):,} cihaz")
    records = list(filtered.iterrows())
    for offset in range(0, len(records), 3):
        columns = st.columns(3)
        for column, (idx, row) in zip(columns, records[offset:offset + 3]):
            with column:
                with st.container(border=True):
                    st.markdown(f"**{str(row['_label']) or 'İsimsiz cihaz'}**")
                    st.caption(str(row["_ip"]) or "IP bilinmiyor")
                    st.write(str(row["_type"]) or "Tür bilinmiyor")
                    st.caption(str(row["_status"]) or "Durum bilinmiyor")
                    if st.button("Detayları aç", key=f"topology_detail_{idx}", width="stretch"):
                        show_topology_device(row)

    st.divider()
    st.subheader("Mevcut Wi-Fi baglantisi")
    if not wifi.empty:
        st.dataframe(wifi, width="stretch", hide_index=True)
    else:
        st.caption("Wi-Fi baglanti kaydi bulunamadi.")

    st.caption(
        "Kanita dayali topoloji: dogrulanmis, gozlemlenmis ve tahmini iliskiler "
        "birbirinden ayri tutulmalidir. Bu ekran tek basina fiziksel kablo veya "
        "AP-istemci iliskisini dogrulamaz."
    )
