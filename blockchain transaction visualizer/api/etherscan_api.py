import requests

ETHERSCAN_URL = "https://api.etherscan.io/api"

def fetch_transactions_from_etherscan(address, apikey):
    params = {
        "module": "account",
        "action": "txlist",
        "address": address,
        "startblock": 0,
        "endblock": 99999999,
        "sort": "asc",
        "apikey": apikey
    }

    r = requests.get(ETHERSCAN_URL, params=params, timeout=30)
    data = r.json()

    if data.get("status") == "0" and data.get("message") == "No transactions found":
        return []

    if data.get("message") == "OK":
        return data["result"]

    raise Exception(f"Etherscan Error: {data}")
