"""
Blockchain Transaction Visualizer - Desktop UI (Tkinter)

Save this file as `desktop_app.py` and run:
    python desktop_app.py

Features:
- Enter Ethereum address + Etherscan API key (or load CSV)
- Fetch transactions via Etherscan or load CSV file
- Build directed graph with NetworkX
- Visualize graph inside the Tkinter window using Matplotlib
- Preview transactions in a table and export nodes/edges CSV

Dependencies:
- requests
- pandas
- networkx
- matplotlib

Install: pip install requests pandas networkx matplotlib

"""

import os
import io
import math
import time
import csv
import requests
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import networkx as nx
import matplotlib
matplotlib.use('Agg')  # use non-interactive backend for drawing then display as image
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

ETHERSCAN_URL = "https://api.etherscan.io/api"

# -------------------- Helpers --------------------

def wei_to_eth(value):
    try:
        return int(value) / 1e18
    except Exception:
        try:
            return float(value) / 1e18
        except Exception:
            return 0.0


def fetch_transactions_from_etherscan(address, apikey, startblock=0, endblock=99999999, sort='asc'):
    params = {
        'module': 'account',
        'action': 'txlist',
        'address': address,
        'startblock': startblock,
        'endblock': endblock,
        'sort': sort,
        'apikey': apikey,
    }
    resp = requests.get(ETHERSCAN_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get('status') == '0' and data.get('message') == 'No transactions found':
        return []
    if data.get('message') == 'OK':
        return data.get('result', [])
    raise Exception(f"Etherscan error: {data}")


# build graph
def build_graph_from_txlist(txlist, min_value_eth=0.0):
    G = nx.DiGraph()
    for tx in txlist:
        frm = tx.get('from')
        to = tx.get('to')
        value = wei_to_eth(tx.get('value', 0))
        if not frm or not to:
            continue
        if value < min_value_eth:
            continue
        if not G.has_node(frm):
            G.add_node(frm, total_in=0.0, total_out=0.0, tx_in=0, tx_out=0)
        if not G.has_node(to):
            G.add_node(to, total_in=0.0, total_out=0.0, tx_in=0, tx_out=0)
        G.nodes[frm]['total_out'] += value
        G.nodes[frm]['tx_out'] += 1
        G.nodes[to]['total_in'] += value
        G.nodes[to]['tx_in'] += 1
        if G.has_edge(frm, to):
            G[frm][to]['total_value'] += value
            G[frm][to]['tx_count'] += 1
        else:
            G.add_edge(frm, to, total_value=value, tx_count=1)
    return G


# -------------------- UI App --------------------
class App:
    def __init__(self, root):
        self.root = root
        self.root.title('Blockchain Transaction Visualizer - Desktop')
        self.root.geometry('1100x700')
        self.tx_df = None
        self.graph = None

        # Top frame for inputs
        top = ttk.Frame(root)
        top.pack(side=tk.TOP, fill=tk.X, padx=8, pady=6)

        ttk.Label(top, text='Ethereum address:').pack(side=tk.LEFT)
        self.address_entry = ttk.Entry(top, width=44)
        self.address_entry.pack(side=tk.LEFT, padx=6)

        ttk.Label(top, text='Etherscan API Key:').pack(side=tk.LEFT, padx=(10,0))
        self.api_entry = ttk.Entry(top, width=30)
        self.api_entry.pack(side=tk.LEFT, padx=6)

        self.fetch_btn = ttk.Button(top, text='Fetch (Etherscan)', command=self.on_fetch)
        self.fetch_btn.pack(side=tk.LEFT, padx=6)

        self.load_btn = ttk.Button(top, text='Load CSV', command=self.on_load_csv)
        self.load_btn.pack(side=tk.LEFT, padx=6)

        # Controls frame
        ctrl = ttk.Frame(root)
        ctrl.pack(side=tk.TOP, fill=tk.X, padx=8, pady=6)

        ttk.Label(ctrl, text='Min value (ETH):').pack(side=tk.LEFT)
        self.min_value_var = tk.DoubleVar(value=0.0)
        self.min_value_spin = ttk.Spinbox(ctrl, from_=0.0, to=1e9, increment=0.0001, textvariable=self.min_value_var, width=10)
        self.min_value_spin.pack(side=tk.LEFT, padx=6)

        ttk.Label(ctrl, text='Highlight address:').pack(side=tk.LEFT, padx=(10,0))
        self.highlight_entry = ttk.Entry(ctrl, width=44)
        self.highlight_entry.pack(side=tk.LEFT, padx=6)

        self.draw_btn = ttk.Button(ctrl, text='Build & Draw Graph', command=self.on_draw)
        self.draw_btn.pack(side=tk.LEFT, padx=6)

        self.export_btn = ttk.Button(ctrl, text='Export Nodes/Edges', command=self.on_export)
        self.export_btn.pack(side=tk.LEFT, padx=6)

        # Main paned window
        paned = ttk.Panedwindow(root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)

        # Left: Matplotlib canvas for graph
        left_frame = ttk.Frame(paned, width=700, height=600)
        paned.add(left_frame, weight=3)
        self.fig = Figure(figsize=(7,6))
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=left_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Right: Transactions table and stats
        right_frame = ttk.Frame(paned, width=380)
        paned.add(right_frame, weight=1)

        stats_frame = ttk.Frame(right_frame)
        stats_frame.pack(fill=tk.X, pady=(0,6))
        self.stat_label = ttk.Label(stats_frame, text='Transactions: 0 | Nodes: 0 | Edges: 0')
        self.stat_label.pack(side=tk.LEFT, padx=6)

        # Treeview for transactions
        cols = ('hash', 'from', 'to', 'value_eth', 'timeStamp')
        self.tree = ttk.Treeview(right_frame, columns=cols, show='headings', height=25)
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=90 if c!='hash' else 140, anchor=tk.W)
        self.tree.pack(fill=tk.BOTH, expand=True)

        # allow double click to copy address
        self.tree.bind('<Double-1>', self.on_tree_double)

    def on_fetch(self):
        address = self.address_entry.get().strip()
        api = self.api_entry.get().strip() or os.getenv('ETHERSCAN_API_KEY', '')
        if not address:
            messagebox.showwarning('Input', 'Enter an Ethereum address first')
            return
        if not api:
            if not messagebox.askyesno('No API key', 'No Etherscan API key provided. Continue and hope rate limit allows?'):
                return
        try:
            self.root.config(cursor='wait')
            self.root.update()
            txs = fetch_transactions_from_etherscan(address, api)
            # normalize into DataFrame
            df = pd.DataFrame(txs)
            if df.empty:
                messagebox.showinfo('No tx', 'No transactions found for this address')
                self.tx_df = None
                return
            df['value_eth'] = df['value'].apply(lambda v: wei_to_eth(str(v)))
            self.tx_df = df
            self.populate_table()
            messagebox.showinfo('Done', f'Fetched {len(df)} transactions')
        except Exception as e:
            messagebox.showerror('Error', str(e))
        finally:
            self.root.config(cursor='')

    def on_load_csv(self):
        path = filedialog.askopenfilename(filetypes=[('CSV files','*.csv'),('All files','*.*')])
        if not path:
            return
        try:
            df = pd.read_csv(path)
            # ensure value column exists
            if 'value' not in df.columns and 'Value' in df.columns:
                df = df.rename(columns={'Value':'value'})
            if 'value' not in df.columns:
                messagebox.showerror('CSV error', 'CSV must contain a "value" column (in Wei)')
                return
            df['value_eth'] = df['value'].apply(lambda v: wei_to_eth(str(v)))
            self.tx_df = df
            self.populate_table()
            messagebox.showinfo('Loaded', f'Loaded CSV with {len(df)} rows')
        except Exception as e:
            messagebox.showerror('Error', str(e))

    def populate_table(self):
        for r in self.tree.get_children():
            self.tree.delete(r)
        if self.tx_df is None:
            self.stat_label.config(text='Transactions: 0 | Nodes: 0 | Edges: 0')
            return
        for _, row in self.tx_df.iterrows():
            h = row.get('hash', '')
            frm = row.get('from', '')
            to = row.get('to', '')
            v = row.get('value_eth', 0.0)
            ts = row.get('timeStamp', '')
            self.tree.insert('', tk.END, values=(h, frm, to, f"{v:.6f}", ts))
        self.stat_label.config(text=f'Transactions: {len(self.tx_df)} | Nodes: 0 | Edges: 0')

    def on_draw(self):
        if self.tx_df is None:
            messagebox.showwarning('No data', 'No transactions loaded. Use Fetch or Load CSV.')
            return
        min_v = float(self.min_value_var.get() or 0.0)
        df = self.tx_df.copy()
        df = df[df['value_eth'] >= min_v]
        txlist = df.to_dict(orient='records')
        G = build_graph_from_txlist(txlist, min_value_eth=min_v)
        self.graph = G
        # update stats
        self.stat_label.config(text=f'Transactions: {len(df)} | Nodes: {G.number_of_nodes()} | Edges: {G.number_of_edges()}')
        # draw graph with matplotlib
        self.draw_network(G)

    def draw_network(self, G):
        self.ax.clear()
        if G.number_of_nodes() == 0:
            self.ax.text(0.5,0.5,'No nodes to display', ha='center')
            self.canvas.draw()
            return
        # compute positions
        try:
            pos = nx.spring_layout(G, k=0.5, iterations=50)
        except Exception:
            pos = nx.spring_layout(G)
        # compute node sizes by total volume
        vols = []
        for n,d in G.nodes(data=True):
            vol = d.get('total_in',0) + d.get('total_out',0)
            vols.append(vol)
        maxv = max(vols) if vols else 1.0
        sizes = [50 + (400 * (v / maxv)) for v in vols]
        labels = {n: (n[:8] + '...') for n in G.nodes()}
        # draw nodes
        nx.draw_networkx_nodes(G, pos, node_size=sizes, ax=self.ax)
        nx.draw_networkx_labels(G, pos, labels=labels, font_size=8, ax=self.ax)
        # draw edges with width scaled
        edge_widths = []
        for u,v,d in G.edges(data=True):
            val = d.get('total_value',0)
            edge_widths.append(1 + math.log1p(val+1)*2)
        nx.draw_networkx_edges(G, pos, width=edge_widths, arrows=True, ax=self.ax, arrowstyle='->', arrowsize=10)
        # highlight node if requested
        highlight = self.highlight_entry.get().strip()
        if highlight:
            if G.has_node(highlight):
                nx.draw_networkx_nodes(G, pos, nodelist=[highlight], node_color='gold', node_size=600, ax=self.ax)
        self.ax.set_axis_off()
        self.fig.tight_layout()
        # render to canvas
        # To show in Tkinter we need to use FigureCanvasTkAgg with interactive backend: switch temporarily
        try:
            # Use AGG to draw then show via FigureCanvasTkAgg
            self.canvas.figure = self.fig
            self.canvas.draw()
        except Exception as e:
            messagebox.showerror('Draw error', str(e))

    def on_export(self):
        if self.graph is None:
            messagebox.showwarning('No graph', 'Build the graph first')
            return
        path = filedialog.askdirectory()
        if not path:
            return
        nodes_out = []
        for n,d in self.graph.nodes(data=True):
            nodes_out.append({'address': n, 'total_in': d.get('total_in',0), 'total_out': d.get('total_out',0), 'tx_in': d.get('tx_in',0), 'tx_out': d.get('tx_out',0)})
        edges_out = []
        for u,v,d in self.graph.edges(data=True):
            edges_out.append({'from': u, 'to': v, 'total_value': d.get('total_value',0), 'tx_count': d.get('tx_count',0)})
        nodes_csv = os.path.join(path, 'nodes.csv')
        edges_csv = os.path.join(path, 'edges.csv')
        pd.DataFrame(nodes_out).to_csv(nodes_csv, index=False)
        pd.DataFrame(edges_out).to_csv(edges_csv, index=False)
        messagebox.showinfo('Exported', f'Exported nodes.csv and edges.csv to {path}')

    def on_tree_double(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            return
        vals = self.tree.item(item, 'values')
        # copy address to address entry when double clicked
        # prefer copying 'from' address
        from_addr = vals[1]
        self.address_entry.delete(0, tk.END)
        self.address_entry.insert(0, from_addr)
        self.root.clipboard_clear()
        self.root.clipboard_append(from_addr)
        messagebox.showinfo('Copied', f'Address {from_addr} copied to clipboard')


if __name__ == '__main__':
    root = tk.Tk()
    app = App(root)
    root.mainloop()
