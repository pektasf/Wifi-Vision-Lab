"""Classify topology edges without overstating their evidence strength."""
import pandas as pd


def split_topology_edges(edges, edge_from, edge_to):
    """Split usable edges into verified, inferred, context-only and unknown sets.

    Only explicitly verified edges are eligible for the topology graph.
    Missing confidence is never silently promoted to verified.
    """
    empty = edges.iloc[0:0].copy()
    if edges.empty or not edge_from or not edge_to:
        return {
            "verified": empty.copy(),
            "inferred": empty.copy(),
            "context": empty.copy(),
            "unverified": empty.copy(),
        }

    valid = (
        edges[edge_from].astype(str).str.strip().ne("")
        & edges[edge_to].astype(str).str.strip().ne("")
    )
    usable = edges[valid].copy()
    relation = (
        usable["relation"].astype(str).str.strip().str.casefold()
        if "relation" in usable.columns
        else pd.Series("", index=usable.index)
    )
    confidence = (
        usable["confidence"].astype(str).str.strip().str.casefold()
        if "confidence" in usable.columns
        else pd.Series("", index=usable.index)
    )

    context_mask = relation.isin(
        {"same_network", "same network", "context_only", "observed_in_scope",
         "configured_default_gateway"}
    ) | confidence.eq("context_only")
    inferred_mask = ~context_mask & confidence.isin({"inferred", "low"})
    verified_mask = ~context_mask & ~inferred_mask & confidence.eq("verified")
    unverified_mask = ~(context_mask | inferred_mask | verified_mask)

    return {
        "verified": usable[verified_mask].copy(),
        "inferred": usable[inferred_mask].copy(),
        "context": usable[context_mask].copy(),
        "unverified": usable[unverified_mask].copy(),
    }



def prepare_association_history(history):
    """Return association observations newest-first, keeping invalid dates last."""
    if history.empty:
        return history.copy()
    result = history.copy()
    if "observed_at" not in result.columns:
        return result.iloc[::-1].reset_index(drop=True)
    result["_observed_at_utc"] = pd.to_datetime(
        result["observed_at"], utc=True, errors="coerce"
    )
    result = result.sort_values(
        "_observed_at_utc", ascending=False, na_position="last", kind="stable"
    )
    return result.drop(columns=["_observed_at_utc"]).reset_index(drop=True)



def prepare_verified_edge_options(edges, edge_from, edge_to):
    """Build unique, stable labels for selecting verified relationship rows."""
    if edges.empty or not edge_from or not edge_to:
        return []
    options = []
    for position, (_, edge) in enumerate(edges.reset_index(drop=True).iterrows(), start=1):
        source = str(edge.get(edge_from, "") or "").strip()
        target = str(edge.get(edge_to, "") or "").strip()
        relation = str(edge.get("relation", "relationship") or "relationship").strip()
        observed_at = str(edge.get("observed_at", "") or "time unknown").strip()
        options.append({
            "index": position - 1,
            "label": f"{position}. {source} → {target} | {relation} | {observed_at}",
        })
    return options



def extract_selected_node_id(selection):
    """Read a selected Plotly node ID without depending on Streamlit internals."""
    def read(value, key, default=None):
        if hasattr(value, "get"):
            return value.get(key, default)
        return getattr(value, key, default)

    selection_data = read(selection, "selection", selection)
    points = read(selection_data, "points", []) or []
    if not points:
        return ""
    customdata = read(points[0], "customdata", "")
    if isinstance(customdata, (list, tuple)):
        customdata = customdata[0] if customdata else ""
    return str(customdata or "").strip()


def prepare_relationship_history(edges, source, target, edge_from, edge_to):
    """Return every recorded relationship for a selected device pair, newest first.

    Direction is preserved in the returned rows. Matching either direction lets
    the UI show the complete pair history without implying the relationship is
    physically symmetric.
    """
    if edges.empty or not edge_from or not edge_to:
        return edges.iloc[0:0].copy()
    source = str(source or "").strip()
    target = str(target or "").strip()
    if not source or not target:
        return edges.iloc[0:0].copy()

    left = edges[edge_from].astype(str).str.strip()
    right = edges[edge_to].astype(str).str.strip()
    result = edges[
        ((left == source) & (right == target))
        | ((left == target) & (right == source))
    ].copy()
    if result.empty:
        return result

    if "observed_at" in result.columns:
        parsed = pd.to_datetime(result["observed_at"], utc=True, errors="coerce")
        result = result.assign(_history_sort_time=parsed)
        result = result.sort_values(
            "_history_sort_time", ascending=False, na_position="last", kind="stable"
        ).drop(columns=["_history_sort_time"])
    else:
        result = result.iloc[::-1]
    return result.reset_index(drop=True)



def topology_render_profile(node_count, edge_count=0):
    """Choose readable, scalable Plotly rendering settings for topology size."""
    node_count = max(0, int(node_count or 0))
    edge_count = max(0, int(edge_count or 0))
    return {
        "use_webgl": node_count >= 300 or edge_count >= 500,
        "show_labels": node_count <= 120,
        "node_count": node_count,
        "edge_count": edge_count,
    }
