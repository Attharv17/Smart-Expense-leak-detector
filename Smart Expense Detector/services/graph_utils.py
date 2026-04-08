"""
services/graph_utils.py
-----------------------
Builds and traverses an expense graph where:
  - Nodes  = Category nodes  (e.g.  "Category:Food")
             + Vendor  nodes  (e.g.  "Vendor:Swiggy")
             + a synthetic ROOT node that anchors the whole graph
  - Edges  = expense transactions flowing  ROOT → Category → Vendor

Graph topology:
    ROOT
     ├── Category:Food
     │    ├── Vendor:Swiggy  (edge carries amount, expense_id, date)
     │    └── Vendor:Zomato
     ├── Category:SaaS
     │    └── Vendor:Slack
     └── ...

This adjacency-list representation lets us run:
  - BFS → level-wise exploration  (ROOT → all categories → all vendors)
           useful for ranking the most frequent/expensive categories first
  - DFS → deep path tracing       (ROOT → one category → all its vendors recursively)
           useful for uncovering hidden spending chains within a category
"""

from collections import defaultdict, deque
from typing import Any

# ── Sentinel node that serves as the single entry-point for traversals ──────
ROOT_NODE = "ROOT"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_graph(expenses: list) -> dict[str, list[dict]]:
    """
    Build an adjacency-list graph from a list of Expense ORM objects.

    Adjacency list format:
        {
            "ROOT": [
                {"to": "Category:Food",  "weight": 197.75, "edge_count": 5},
                ...
            ],
            "Category:Food": [
                {
                    "to":        "Vendor:Swiggy",
                    "amount":    42.50,
                    "expense_id": 1,
                    "date":      "2024-01-05",
                    "description": "Team lunch order"
                },
                ...
            ],
            "Vendor:Swiggy": []   # leaf nodes have empty lists
        }

    The ROOT → Category edges summarise the total spend and tx count for
    each category so BFS callers can sort by weight immediately.
    """
    graph: dict[str, list[dict]] = defaultdict(list)

    # Accumulate category-level totals for the ROOT edges
    category_totals: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"total_amount": 0.0, "edge_count": 0}
    )

    for exp in expenses:
        cat_node    = f"Category:{exp.category}"
        vendor_node = f"Vendor:{exp.vendor}"

        # ROOT → Category  (aggregated; de-duplicated later)
        category_totals[cat_node]["total_amount"] += exp.amount
        category_totals[cat_node]["edge_count"]   += 1

        # Category → Vendor  (one edge per transaction)
        graph[cat_node].append({
            "to":          vendor_node,
            "amount":      exp.amount,
            "expense_id":  exp.id,
            "date":        exp.date,
            "description": exp.description or "",
        })

        # Ensure vendor leaf node exists (so all nodes are in the graph)
        if vendor_node not in graph:
            graph[vendor_node] = []

    # Materialise ROOT → Category edges (sorted by total spend descending)
    graph[ROOT_NODE] = [
        {
            "to":           cat_node,
            "total_amount": round(totals["total_amount"], 2),
            "edge_count":   totals["edge_count"],
        }
        for cat_node, totals in sorted(
            category_totals.items(),
            key=lambda kv: kv[1]["total_amount"],
            reverse=True,
        )
    ]

    return dict(graph)


# ---------------------------------------------------------------------------
# BFS traversal
# ---------------------------------------------------------------------------

def bfs_traversal(graph: dict[str, list[dict]], start: str = ROOT_NODE) -> dict:
    """
    Breadth-First Search from `start` through the expense graph.

    Returns a level-by-level breakdown:
        {
            "start":    "ROOT",
            "order":    ["ROOT", "Category:Food", "Category:SaaS", "Vendor:Swiggy", ...],
            "levels":   {
                0: ["ROOT"],
                1: ["Category:Food", "Category:SaaS", ...],   # all categories
                2: ["Vendor:Swiggy", "Vendor:Slack", ...],    # all vendors
            },
            "insights": {
                "frequent_categories":  [...],   # level-1 nodes sorted by edge_count
                "top_spend_categories": [...],   # level-1 nodes sorted by total_amount
                "total_nodes_visited":  N,
            }
        }

    Use-case: quickly surface which spending categories dominate (level 1)
    and which vendors they route to (level 2) without traversing the whole tree.
    """
    if start not in graph:
        return {"error": f"Node '{start}' not found in graph.", "available_nodes": list(graph.keys())}

    visited: set[str]          = set()
    queue:   deque[tuple]      = deque()
    order:   list[str]         = []
    levels:  dict[int, list]   = defaultdict(list)

    queue.append((start, 0))
    visited.add(start)

    while queue:
        node, depth = queue.popleft()
        order.append(node)
        levels[depth].append(node)

        for edge in graph.get(node, []):
            neighbour = edge["to"]
            if neighbour not in visited:
                visited.add(neighbour)
                queue.append((neighbour, depth + 1))

    # ── Insights ────────────────────────────────────────────────────────────
    # Category nodes live at level 1 (children of ROOT)
    category_edges = graph.get(ROOT_NODE, [])

    frequent_categories = sorted(
        category_edges,
        key=lambda e: e.get("edge_count", 0),
        reverse=True,
    )[:5]

    top_spend_categories = sorted(
        category_edges,
        key=lambda e: e.get("total_amount", 0),
        reverse=True,
    )[:5]

    return {
        "start":  start,
        "order":  order,
        "levels": {str(k): v for k, v in sorted(levels.items())},
        "insights": {
            "frequent_categories":  frequent_categories,
            "top_spend_categories": top_spend_categories,
            "total_nodes_visited":  len(order),
        },
    }


# ---------------------------------------------------------------------------
# DFS traversal
# ---------------------------------------------------------------------------

def dfs_traversal(graph: dict[str, list[dict]], start: str = ROOT_NODE) -> dict:
    """
    Depth-First Search from `start`, recording the full traversal path and
    all root-to-leaf chains (spending chains).

    Returns:
        {
            "start":          "ROOT",
            "order":          ["ROOT", "Category:Food", "Vendor:Swiggy", ...],
            "spending_chains": [
                {
                    "path":         ["ROOT", "Category:SaaS", "Vendor:Slack"],
                    "total_amount": 897.00,
                    "tx_count":     3,
                    "transactions": [...]
                },
                ...
            ],
            "insights": {
                "deepest_chain":          [...],
                "highest_spend_chain":    [...],
                "total_nodes_visited":    N,
            }
        }

    Use-case: trace hidden multi-hop spending chains — e.g. if a category
    funnels an unusually large total to a single vendor deep in the graph.
    """
    if start not in graph:
        return {"error": f"Node '{start}' not found in graph.", "available_nodes": list(graph.keys())}

    visited_order: list[str]       = []
    spending_chains: list[dict]    = []

    def _dfs(node: str, path: list[str], visited: set[str], running_amount: float, txns: list):
        """Recursive DFS helper; collects leaf paths as spending chains."""
        visited_order.append(node)

        neighbours = graph.get(node, [])
        is_leaf    = len(neighbours) == 0

        if is_leaf:
            # Reached a vendor node — record the complete chain
            spending_chains.append({
                "path":          list(path),
                "total_amount":  round(running_amount, 2),
                "tx_count":      len(txns),
                "transactions":  list(txns),
            })
            return

        seen = set(visited)  # local copy to allow sibling revisits
        for edge in neighbours:
            neighbour = edge["to"]
            if neighbour not in seen:
                seen.add(neighbour)
                # Carry the edge's amount down into the chain
                edge_amount = edge.get("amount", 0.0)
                _dfs(
                    neighbour,
                    path     + [neighbour],
                    seen,
                    running_amount + edge_amount,
                    txns + ([{
                        "expense_id":  edge.get("expense_id"),
                        "amount":      edge.get("amount"),
                        "date":        edge.get("date"),
                        "description": edge.get("description"),
                    }] if "expense_id" in edge else []),
                )

    _dfs(start, [start], {start}, 0.0, [])

    # ── Insights ─────────────────────────────────────────────────────────────
    deepest_chain       = max(spending_chains, key=lambda c: len(c["path"]),         default=None)
    highest_spend_chain = max(spending_chains, key=lambda c: c["total_amount"],      default=None)

    return {
        "start":           start,
        "order":           visited_order,
        "spending_chains": spending_chains,
        "insights": {
            "deepest_chain":        deepest_chain,
            "highest_spend_chain":  highest_spend_chain,
            "total_chains_found":   len(spending_chains),
            "total_nodes_visited":  len(visited_order),
        },
    }
