from pyvis.network import Network
import math


def pyvis_from_networkx(G, focus_node=None, physics=True):
    net = Network(height="750px", width="100%", directed=True)
    net.force_atlas_2based()

    # Nodes
    max_volume = max(
        [(d.get("total_in", 0) + d.get("total_out", 0)) for n, d in G.nodes(data=True)], 
        default=1
    )

    for n, d in G.nodes(data=True):
        vol = d.get("total_in", 0) + d.get("total_out", 0)
        size = 10 + (50 * (vol / max_volume))

        color = "#ffcc00" if focus_node and n.lower() == focus_node.lower() else None

        net.add_node(
            n,
            label=n[:10] + "..." if len(n) > 14 else n,
            title=f"In: {d.get('total_in',0):.6f} | Out: {d.get('total_out',0):.6f}",
            size=size,
            color=color
        )

    # Edges
    for u, v, d in G.edges(data=True):
        val = d.get("total_value", 0)
        width = 1 + math.log1p(val + 1) * 2

        net.add_edge(
            u, v, width=width, title=f"{val:.4f} ETH", arrows="to"
        )

    net.toggle_physics(physics)
    return net
