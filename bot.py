import requests
import os
import json
import re
from datetime import datetime, timezone

# === CONFIGURATION ===
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
COLLECTION = "0xf0ad42e8d11dd0a3f06f76ddb39279c797568cb0"
BID_THRESHOLD = 100      # Bid ≥ 100 AVAX
SALE_THRESHOLD = 150     # Buy/Sell ≥ 150 AVAX
STATE_FILE = "last_state.json"

def send_discord(title, description, color=0x57F287):
    if not DISCORD_WEBHOOK:
        print("Pas de webhook Discord configuré")
        return
    payload = {
        "embeds": [{
            "title": title,
            "description": description,
            "color": color,
            "url": f"https://salvor.io/collections/{COLLECTION}/activity",
            "footer": {"text": "Ferdy Fish • Salvor"},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }]
    }
    try:
        requests.post(DISCORD_WEBHOOK, json=payload, timeout=10)
        print("Notification Discord envoyée")
    except Exception as e:
        print("Erreur Discord:", e)

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"last_bids": [], "last_sales": []}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def check_activity():
    state = load_state()
    new_bids = []
    new_sales = []

    # --- 1. Vérification du Top Bid ---
    try:
        r = requests.get(
            f"https://salvor.io/collections/{COLLECTION}",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            timeout=15
        )
        text = r.text.lower()
        matches = re.findall(r'top bid[^0-9]*([\d.]+)', text)
        if matches:
            top_bid = float(matches[0])
            print(f"Top bid actuel : {top_bid} AVAX")
            if top_bid >= BID_THRESHOLD:
                key = f"bid_{top_bid}"
                if key not in state["last_bids"]:
                    new_bids.append(top_bid)
                    state["last_bids"].append(key)
                    state["last_bids"] = state["last_bids"][-20:]
    except Exception as e:
        print("Erreur top bid:", e)

    # --- 2. Vérification des Sales / Buys (via Snowtrace) ---
    try:
        url = (
            f"https://api.snowtrace.io/api"
            f"?module=account&action=tokennfttx"
            f"&contractaddress={COLLECTION}"
            f"&page=1&offset=20&sort=desc"
        )
        r = requests.get(url, timeout=15)
        data = r.json()

        if data.get("status") == "1":
            for tx in data["result"]:
                ts = int(tx["timeStamp"])
                age_minutes = (datetime.now(timezone.utc).timestamp() - ts) / 60
                if age_minutes > 180:  # on regarde les 3 dernières heures
                    continue

                value_avax = int(tx.get("value", 0)) / 1e18
                if value_avax >= SALE_THRESHOLD:
                    key = tx["hash"]
                    if key not in state["last_sales"]:
                        new_sales.append({
                            "hash": key,
                            "value": value_avax,
                            "token_id": tx.get("tokenID", "?"),
                            "from": tx["from"][:8] + "...",
                            "to": tx["to"][:8] + "..."
                        })
                        state["last_sales"].append(key)
                        state["last_sales"] = state["last_sales"][-30:]
    except Exception as e:
        print("Erreur sales:", e)

    # --- Envoi des notifications ---
    for bid in new_bids:
        title = "🐟 Nouveau Bid élevé sur Ferdy Fish"
        desc = f"**{bid} AVAX**\n\n[Voir l’activité sur Salvor](https://salvor.io/collections/{COLLECTION}/activity)"
        send_discord(title, desc, color=0x5865F2)  # bleu

    for sale in new_sales:
        title = "🐟 Sale / Buy ≥ 150 AVAX"
        desc = (
            f"**{sale['value']:.2f} AVAX**\n"
            f"Token **#{sale['token_id']}**\n"
            f"`{sale['from']}` → `{sale['to']}`\n\n"
            f"[Voir la transaction](https://snowtrace.io/tx/{sale['hash']})\n"
            f"[Activité Salvor](https://salvor.io/collections/{COLLECTION}/activity)"
        )
        send_discord(title, desc, color=0x57F287)  # vert

    save_state(state)
    print(f"Check terminé — Nouveaux bids: {len(new_bids)} | Nouvelles sales: {len(new_sales)}")

if __name__ == "__main__":
    check_activity()
