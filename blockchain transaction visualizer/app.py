import os
import time
import pandas as pd
import streamlit as st

from api.etherscan_api import fetch_transactions_from_etherscan
from graph.graph_builder import build_graph_from_txlist
from graph.graph_visualizer import pyvis_from_networkx
from utils.helpers import wei_to_eth

st.set_page_config(page_title="Blockchain Transaction Visualizer", layout="wide")
st.title("🔗 Blockchain Transaction Visualizer (Ethereum)")


# ----------------------------------
# Sidebar Input
# ----------------------------------
st.sidebar.header("Data Source")
mode = st.sidebar.radio("Choose input:", ["Etherscan API", "Upload CSV", "Sample Data"])

if mode == "Etherscan API":
    address = st.sidebar.text_input("Ethereum address")
    api_key = st.sidebar.text_input("Etherscan API Key", value=os.getenv("ETHERSCAN_API_KEY", ""))
    fetch_btn = st.sidebar.button("Fetch")

elif mode == "Upload CSV":
    uploaded = st.sidebar.file_uploader("Upload CSV", type=["csv"])

else:
    sample_btn = st.sidebar.button("Load Sample Data")


# Visualization settings
st.sidebar.header("Filters")
min_value = st.sidebar.number_input("Min Value (ETH)", min_value=0.0, value=0.0)
focus_addr = st.sidebar.text_input("Highlight address")
max_nodes = st.sidebar.slider("Max nodes", 50, 1000, 300, step=50)
physics = st.sidebar.checkbox("Enable physics", value=True)


# ----------------------------------
# Load Data
# ----------------------------------
txlist = None

if mode == "Etherscan API" and 'fetch_btn' in locals() and fetch_btn:
    with st.spinner("Fetching transactions..."):
        try:
            txlist = fetch_transactions_from_etherscan(address, api_key)
            st.session_state["txs"] = txlist
        except Exception as e:
            st.error(f"Fetch failed: {e}")

elif mode == "Upload CSV" and uploaded:
    df = pd.read_csv(uploaded)
    txlist = df.to_dict(orient="records")
    st.session_state["txs"] = txlist

elif mode == "Sample Data" and 'sample_btn' in locals() and sample_btn:
    sample = [
        {"hash": "0x1", "from": "0xAAA", "to": "0xBBB", "value": str(int(0.5 * 1e18)), "timeStamp": str(int(time.time()))},
        {"hash": "0x2", "from": "0xBBB", "to": "0xCCC", "value": str(int(0.3 * 1e18)), "timeStamp": str(int(time.time()))},
    ]
    txlist = sample
    st.session_state["txs"] = sample


# ----------------------------------
# Display / Process
# ----------------------------------
st.subheader("Transactions")

if "txs" in st.session_state:
    txlist = st.session_state["txs"]

if txlist:
    df = pd.DataFrame(txlist)
    df["value_eth"] = df["value"].apply(lambda v: wei_to_eth(str(v)))
    df = df[df["value_eth"] >= min_value]

    st.dataframe(df.head(200))

    # Build graph
    G = build_graph_from_txlist(df.to_dict(orient="records"), focus_addr, max_nodes)

    # Stats
    st.write(f"Graph Nodes: {G.number_of_nodes()}, Edges: {G.number_of_edges()}")

    total_value = sum([d.get("total_value", 0) for _, _, d in G.edges(data=True)])
    st.metric("Total ETH Moved", f"{total_value:.5f} ETH")

    # Visualize graph
    st.subheader("Network Graph")
    net = pyvis_from_networkx(G, focus_node=focus_addr, physics=physics)
    net.save_graph("network.html")

    with open("network.html", "r", encoding="utf-8") as f:
        st.components.v1.html(f.read(), height=750)

else:
    st.info("Load data from the left panel.")
