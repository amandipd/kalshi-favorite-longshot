import requests, time

BASE = "https://api.elections.kalshi.com/trade-api/v2"
candidates = [
    "KXBTC15M","KXETH15M","KXSOL15M","KXBNB15M","KXXRP15M","KXHYPE15M",
    "KXBCH15M","KXADA15M","KXNEAR15M","KXDOGE15M","KXTON15M","KXZEC15M",
    "KXGOLD15M","KXSILVER15M","KXPLATINUM15M","KXCOPPER15M","KXPALLADIUM15M",
    "KXOIL15M","KXNATGAS15M","KXSPX15M","KXNASDAQ15M","KXWTI15M",
]

ok = []
for t in candidates:
    r = requests.get(f"{BASE}/markets", params={"series_ticker": t, "status": "settled", "limit": 1})
    if r.status_code == 200:
        d = r.json()
        n = len(d.get("markets", []))
        if n > 0:
            ok.append(t)
            print(t, "EXISTS, sample:", d["markets"][0]["ticker"], d["markets"][0]["result"])
        else:
            print(t, "no settled markets found (status 200, empty)")
    else:
        print(t, "HTTP", r.status_code)
    time.sleep(0.15)

print("\nConfirmed with settled data:", ok)
