import networkx as nx
from utils.helpers import wei_to_eth


def build_graph_from_txlist(txlist, focus_addr=None, max_nodes=300):
    G = nx.DiGraph()

    for tx in txlist:
        frm = tx.get("from")
        to = tx.get("to")
        amt = wei_to_eth(tx.get("value", "0"))

        if not frm or not to:
            continue

        # ensure nodes
        if not G.has_node(frm):
            G.add_node(frm, total_in=0, total_out=0)
        if not G.has_node(to):
            G.add_node(to, total_in=0, total_out=0)

        # update values
        G.nodes[frm]["total_out"] += amt
        G.nodes[to]["total_in"] += amt

        # edges
        if G.has_edge(frm, to):
            G[frm][to]["total_value"] += amt
        else:
            G.add_edge(frm, to, total_value=amt)

    # trim nodes if too large
    if G.number_of_nodes() > max_nodes and focus_addr:
        focus = focus_addr.lower()
        if G.has_node(focus):
            neighbors = list(G.predecessors(focus)) + list(G.successors(focus))
            neighbors = neighbors[: max_nodes - 1]
            keep = {focus} | set(neighbors)
            return G.subgraph(keep).copy()

    return G
