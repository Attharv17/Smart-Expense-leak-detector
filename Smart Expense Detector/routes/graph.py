"""
routes/graph.py
---------------
REST endpoints for expense graph analysis:

  GET /graph/build  — Build and return the full adjacency-list graph
  GET /graph/bfs    — BFS traversal from a start node (default: ROOT)
  GET /graph/dfs    — DFS traversal from a start node (default: ROOT)

All endpoints are read-only: they fetch expenses from the DB, build
an in-memory graph, and return structured JSON results.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from database import get_db
from models import Expense
from services.graph_utils import build_graph, bfs_traversal, dfs_traversal, ROOT_NODE

router = APIRouter(prefix="/graph", tags=["Expense Graph"])


def _load_graph(db: Session) -> dict:
    """
    Shared helper: fetch all expenses from SQLite and build the graph.
    Called internally by all three graph endpoints so each always reflects
    the current state of the database.
    """
    expenses = db.query(Expense).order_by(Expense.date.asc()).all()
    return build_graph(expenses), len(expenses)


# ---------------------------------------------------------------------------
# GET /graph/build — Return the raw adjacency-list graph
# ---------------------------------------------------------------------------

@router.get(
    "/build",
    summary="Build the expense graph",
    description=(
        "Loads all expenses from the database and constructs an adjacency-list "
        "graph where ROOT → Category nodes → Vendor (leaf) nodes. "
        "Each edge carries the transaction metadata. "
        "Returns the full graph as a JSON object, along with node/edge statistics."
    ),
)
def build_expense_graph(db: Session = Depends(get_db)):
    """
    Constructs and returns the full expense graph.

    Response shape:
    ```json
    {
      "meta": {
        "total_expenses": 33,
        "total_nodes":    46,
        "total_edges":    79,
        "node_types":     {"ROOT": 1, "Category": 13, "Vendor": 32}
      },
      "graph": {
        "ROOT":              [{"to": "Category:SaaS", "total_amount": 1291.00, ...}],
        "Category:SaaS":     [{"to": "Vendor:Slack", "amount": 299.00, ...}],
        "Vendor:Slack":      []
      }
    }
    ```
    """
    graph, expense_count = _load_graph(db)

    # ── Compute graph statistics ─────────────────────────────────────────────
    total_nodes = len(graph)
    total_edges = sum(len(neighbours) for neighbours in graph.values())

    # Count node types by their prefix
    node_types: dict[str, int] = {"ROOT": 0, "Category": 0, "Vendor": 0, "Other": 0}
    for node in graph:
        if node == ROOT_NODE:
            node_types["ROOT"] += 1
        elif node.startswith("Category:"):
            node_types["Category"] += 1
        elif node.startswith("Vendor:"):
            node_types["Vendor"] += 1
        else:
            node_types["Other"] += 1

    return {
        "meta": {
            "total_expenses": expense_count,
            "total_nodes":    total_nodes,
            "total_edges":    total_edges,
            "node_types":     node_types,
        },
        "graph": graph,
    }


# ---------------------------------------------------------------------------
# GET /graph/bfs — BFS traversal
# ---------------------------------------------------------------------------

@router.get(
    "/bfs",
    summary="BFS traversal of expense graph",
    description=(
        "Performs Breadth-First Search starting from `start` (default: ROOT). "
        "Level 0 = ROOT, Level 1 = Category nodes, Level 2 = Vendor nodes. "
        "**Use-case:** detect the most frequent / highest-spend categories before "
        "drilling into individual vendors."
    ),
)
def bfs_expense_graph(
    start: Optional[str] = Query(
        default=None,
        description=(
            "Starting node for BFS. Use 'ROOT' for the full graph. "
            "Or specify a category node like 'Category:Food' to explore just that subtree. "
            "Leave blank to default to ROOT."
        ),
    ),
    db: Session = Depends(get_db),
):
    """
    Runs BFS on the expense graph and returns:
    - `order`   — nodes visited in BFS order
    - `levels`  — nodes grouped by their distance from the start node
    - `insights`— top categories by frequency and by total spend
    """
    graph, expense_count = _load_graph(db)

    # Default start node
    bfs_start = start.strip() if start else ROOT_NODE

    result = bfs_traversal(graph, start=bfs_start)
    result["meta"] = {
        "total_expenses":      expense_count,
        "graph_node_count":    len(graph),
        "traversal_algorithm": "BFS",
        "start_node":          bfs_start,
    }
    return result


# ---------------------------------------------------------------------------
# GET /graph/dfs — DFS traversal
# ---------------------------------------------------------------------------

@router.get(
    "/dfs",
    summary="DFS traversal of expense graph",
    description=(
        "Performs Depth-First Search starting from `start` (default: ROOT). "
        "Traces complete root-to-leaf paths (spending chains) and returns "
        "rich insights: deepest chain, highest-spend chain, and all transactions "
        "along each path. "
        "**Use-case:** uncover hidden spending chains where a single category "
        "funnels large amounts to one specific vendor."
    ),
)
def dfs_expense_graph(
    start: Optional[str] = Query(
        default=None,
        description=(
            "Starting node for DFS. Use 'ROOT' for the full graph. "
            "Or specify a category like 'Category:Consulting' to deep-dive one branch. "
            "Leave blank to default to ROOT."
        ),
    ),
    db: Session = Depends(get_db),
):
    """
    Runs DFS on the expense graph and returns:
    - `order`           — nodes visited in DFS order
    - `spending_chains` — every root-to-leaf path with transactions + totals
    - `insights`        — deepest chain and highest-spend chain
    """
    graph, expense_count = _load_graph(db)

    dfs_start = start.strip() if start else ROOT_NODE

    result = dfs_traversal(graph, start=dfs_start)
    result["meta"] = {
        "total_expenses":      expense_count,
        "graph_node_count":    len(graph),
        "traversal_algorithm": "DFS",
        "start_node":          dfs_start,
    }
    return result
