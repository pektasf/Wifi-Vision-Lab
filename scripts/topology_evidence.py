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
