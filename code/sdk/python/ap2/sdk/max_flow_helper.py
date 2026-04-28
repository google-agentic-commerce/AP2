"""Helper functions for evaluating line items using max flow algorithms."""

from collections import deque
from typing import Literal

from ap2.sdk.generated.open_checkout_mandate import LineItemRequirements
from ap2.sdk.generated.types.line_item import LineItem


# Used for bipartite matching edges to represent unlimited capacity
INF = int(1e15)


def evaluate_line_items_max_flow(  # noqa: PLR0912, PLR0915  (single-pass graph builder + validator; splitting hurts readability)
    checkout_items: list[LineItem],
    requirements: list[LineItemRequirements],
    mode: Literal['dinic', 'edmonds_karp'] = 'dinic',
) -> list[str]:
    """Evaluate line items using the specified max flow algorithm.

    Args:
        checkout_items: List of line items in the cart
        requirements: Requirements configuration
        mode: The max flow algorithm to use (default: 'dinic')

    Returns:
        A list of violation messages, or an empty list if valid.
    """
    cart_qty: dict[str, int] = {}
    for li in checkout_items:
        sku = li.item.id
        cart_qty[sku] = cart_qty.get(sku, 0) + li.quantity

    sku_list = list(cart_qty.keys())

    req_acceptable: list[set[str]] = [
        {ai.id for ai in req.acceptable_items}
        if req.acceptable_items
        else set()
        for req in requirements
    ]
    req_is_wildcard: list[bool] = [
        not req.acceptable_items for req in requirements
    ]

    violations: list[str] = []

    has_wildcard = any(req_is_wildcard)
    all_acceptable = set()
    if not has_wildcard:
        for acc in req_acceptable:
            all_acceptable.update(acc)

    for sku, qty in cart_qty.items():
        if qty <= 0:
            continue
        if not has_wildcard and sku not in all_acceptable:
            violations.append(
                f"Item {sku} not in any requirement's acceptable items"
            )
    if violations:
        return violations

    # Greedy elimination of degree-1 matching
    req_remaining_capacity = [req.quantity for req in requirements]
    complex_sku_list = []
    unassigned_items = []

    for sku in sku_list:
        qty = cart_qty[sku]
        if qty <= 0:
            continue

        match_idx = -1
        is_complex = False
        for j in range(len(requirements)):
            if req_is_wildcard[j] or sku in req_acceptable[j]:
                if match_idx == -1:
                    match_idx = j
                else:
                    is_complex = True
                    break

        if match_idx != -1 and not is_complex:
            assigned = min(qty, req_remaining_capacity[match_idx])
            req_remaining_capacity[match_idx] -= assigned
            leftover = qty - assigned
            if leftover > 0:
                unassigned_items.append(f'{sku} ({leftover})')
        else:
            complex_sku_list.append(sku)

    if complex_sku_list:
        max_f, residual = _line_items_max_flow(
            complex_sku_list,
            cart_qty,
            requirements,
            req_acceptable,
            req_is_wildcard,
            req_remaining_capacity,
            mode,
        )
        total_complex_cart = sum(cart_qty[sku] for sku in complex_sku_list)

        if max_f < total_complex_cart:
            source = 0
            sku_offset = 1
            for i, sku in enumerate(complex_sku_list):
                sku_node = sku_offset + i
                remaining = residual[source].get(sku_node, 0)
                if remaining > 0:
                    unassigned_items.append(f'{sku} ({remaining})')

    if unassigned_items:
        violations.append(
            'Cannot satisfy line item constraints: '
            + ', '.join(unassigned_items)
            + ' could not be assigned to any requirement slot'
        )

    return violations


def _line_items_max_flow(  # noqa: PLR0913  (pre-computed inputs passed in to keep the caller single-pass)
    sku_list: list[str],
    cart_qty: dict[str, int],
    requirements: list[LineItemRequirements],
    req_acceptable: list[set[str]],
    req_is_wildcard: list[bool],
    req_remaining_capacity: list[int],
    mode: Literal['dinic', 'edmonds_karp'] = 'dinic',
) -> tuple[int, list[dict[int, int]]]:
    """Build a sparse bipartite flow network and compute max flow.

    Args:
      sku_list: Unique SKU identifiers involved in the complex matching.
      cart_qty: A dictionary mapping SKU IDs to their quantities in the cart.
      requirements: A list of LineItemRequirements.
      req_acceptable: A list of sets, where each set contains the acceptable SKU
        IDs for the corresponding requirement.
      req_is_wildcard: A list of booleans indicating if each requirement accepts
        any SKU (wildcard).
      req_remaining_capacity: A list of integers representing the remaining
        capacity for each requirement after greedy assignments.
      mode: The max flow algorithm to use ('dinic' or 'edmonds_karp').

    Returns:
      A tuple containing:
        max_flow_value: The total maximum flow from source to sink.
        residual_graph_dictionaries: The residual graph after computing the max
          flow, represented as a list of dictionaries.
    """
    s_count = len(sku_list)
    r_count = len(requirements)
    n = 1 + s_count + r_count + 1
    source, sink = 0, n - 1

    sku_offset = 1
    req_offset = sku_offset + s_count

    # graph[u][v] = capacity
    # A list of dicts is memory efficient and gives O(1) edge lookups.
    graph: list[dict[int, int]] = [{} for _ in range(n)]

    # 1. Source to SKUs
    for i, sku in enumerate(sku_list):
        u, v = source, sku_offset + i
        graph[u][v] = cart_qty[sku]
        graph[v][u] = 0

    # 2. SKUs to Requirements
    for i, sku in enumerate(sku_list):
        for j in range(len(requirements)):
            if req_is_wildcard[j] or sku in req_acceptable[j]:
                u, v = sku_offset + i, req_offset + j
                graph[u][v] = INF
                graph[v][u] = 0

    # 3. Requirements to Sink
    for j in range(len(requirements)):
        u, v = req_offset + j, sink
        graph[u][v] = req_remaining_capacity[j]
        graph[v][u] = 0

    # 4. Compute Flow
    if mode == 'edmonds_karp':
        flow = _edmonds_karp_sparse(graph, source, sink, n)
    else:
        flow = _dinic_sparse(graph, source, sink, n)

    return flow, graph


def _edmonds_karp_sparse(
    graph: list[dict[int, int]], source: int, sink: int, n: int
) -> int:
    """Edmonds-Karp using sparse adjacency dictionaries."""
    max_flow = 0

    while True:
        parent = [-1] * n
        parent[source] = source

        q: deque[int] = deque([source])
        reached_sink = False

        while q and not reached_sink:
            u = q.popleft()
            # ONLY iterate over active edges, bypassing the O(V) scan penalty
            for v, cap in graph[u].items():
                if parent[v] == -1 and cap > 0:
                    parent[v] = u

                    if v == sink:
                        # Found an augmenting path
                        reached_sink = True
                        break

                    q.append(v)

        if parent[sink] == -1:
            break

        push = INF
        curr = sink
        while curr != source:
            p = parent[curr]
            push = min(push, graph[p][curr])
            curr = p

        max_flow += push

        curr = sink
        while curr != source:
            p = parent[curr]
            graph[p][curr] -= push
            graph[curr][p] += push
            curr = p

    return max_flow


def _dinic_sparse(
    graph: list[dict[int, int]], source: int, sink: int, n: int
) -> int:
    """Dinic's algorithm using sparse adjacency dictionaries."""
    # pre-cache the adjacent nodes as lists.
    adj_nodes = [list(graph[i].keys()) for i in range(n)]

    def bfs_level() -> list[int] | None:
        level = [-1] * n
        level[source] = 0
        q: deque[int] = deque([source])
        while q:
            u = q.popleft()
            # Only check neighbors that actually exist
            for v in adj_nodes[u]:
                if level[v] == -1 and graph[u][v] > 0:
                    level[v] = level[u] + 1
                    q.append(v)
        return level if level[sink] != -1 else None

    def dfs_block(u: int, pushed: int, level: list[int], it: list[int]) -> int:
        if u == sink or pushed == 0:
            return pushed

        total_pushed = 0
        # Iterate using the pointer to avoid re-evaluating dead ends
        while it[u] < len(adj_nodes[u]):
            v = adj_nodes[u][it[u]]
            cap = graph[u][v]

            if level[v] == level[u] + 1 and cap > 0:
                d = dfs_block(v, min(pushed, cap), level, it)
                if d > 0:
                    graph[u][v] -= d
                    graph[v][u] += d
                    total_pushed += d
                    pushed -= d
                    # If incoming flow is exhausted, stop checking neighbors
                    if pushed == 0:
                        break
            it[u] += 1

        return total_pushed

    total = 0
    while True:
        level = bfs_level()
        if level is None:
            break
        it = [0] * n
        while True:
            f = dfs_block(source, INF, level, it)
            if f == 0:
                break
            total += f

    return total
