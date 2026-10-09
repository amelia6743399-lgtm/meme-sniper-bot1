import json, os, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

DATA = Path("data")
STATE = DATA / "state.json"
LOG = DATA / "decisions.jsonl"
CHAIN_ID = os.getenv("CHAIN_ID", "base")
START_BALANCE = float(os.getenv("PAPER_START_BALANCE", "1000"))
TRADE_SIZE = float(os.getenv("PAPER_TRADE_SIZE", "25"))
MIN_LIQUIDITY = float(os.getenv("MIN_LIQUIDITY_USD", "20000"))
MIN_CONFIDENCE = float(os.getenv("MIN_CONFIDENCE", "0.70"))
MAX_RISK = int(os.getenv("MAX_RISK_SCORE", "4"))
MAX_CANDIDATES = int(os.getenv("MAX_CANDIDATES", "25"))

def now():
    return datetime.now(timezone.utc).isoformat()

def get_json(url):
    req = Request(url, headers={"User-Agent":"MemePaperTrader/1.0", "Accept":"application/json"})
    with urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))

def load_state():
    DATA.mkdir(exist_ok=True)
    if STATE.exists():
        try:
            d = json.loads(STATE.read_text(encoding="utf-8"))
            d.setdefault("paper_balance_usd", START_BALANCE)
            d.setdefault("open_positions", [])
            d.setdefault("recent_decisions", [])
            d.setdefault("total_decisions", 0)
            return d
        except Exception:
            pass
    return {"paper_balance_usd": START_BALANCE, "open_positions": [], "recent_decisions": [], "total_decisions": 0}

def save_jsonl(item):
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")

def main():
    state = load_state()
    state["chain_id"] = CHAIN_ID
    state["updated_at"] = now()
    state["error"] = ""
    decisions = []
    seen = set()
    try:
        profiles = get_json("https://api.dexscreener.com/token-profiles/latest/v1")
        # Only scan EVM token addresses on the configured chain.
        candidates = [p for p in profiles if p.get("chainId") == CHAIN_ID and p.get("tokenAddress")]
        candidates = candidates[:MAX_CANDIDATES]
        state["candidates_seen"] = len(candidates)
        for p in candidates:
            addr = p["tokenAddress"]
            if addr.lower() in seen:
                continue
            seen.add(addr.lower())
            try:
                pairs = get_json(f"https://api.dexscreener.com/token-pairs/v1/{CHAIN_ID}/{addr}")
                pair = max(pairs, key=lambda x: (x.get("liquidity") or {}).get("usd") or 0) if pairs else {}
                liq = float((pair.get("liquidity") or {}).get("usd") or 0)
                base_token = pair.get("baseToken") or {}
                token = base_token if str(base_token.get("address","")).lower() == addr.lower() else (pair.get("quoteToken") or base_token)
                symbol = token.get("symbol") or "Unknown"
                name = token.get("name") or "Unknown"
                # Conservative heuristic score; this is NOT an AI model or a security audit.
                age_h = None
                created = pair.get("pairCreatedAt")
                if created:
                    age_h = max(0, (time.time() * 1000 - float(created)) / 3600000)
                txns = pair.get("txns") or {}
                h1 = txns.get("h1") or {}
                buys = int(h1.get("buys") or 0); sells = int(h1.get("sells") or 0)
                volume = float((pair.get("volume") or {}).get("h24") or 0)
                risk = 5
                reasons = []
                if liq >= MIN_LIQUIDITY:
                    risk -= 1
                else:
                    reasons.append("liquidity бага")
                if buys + sells >= 10:
                    risk -= 1
                else:
                    reasons.append("гүйлгээний өгөгдөл бага")
                if volume >= liq * 0.1 and liq > 0:
                    risk -= 1
                else:
                    reasons.append("volume/liquidity хангалтгүй")
                risk = max(0, min(10, risk))
                confidence = min(0.95, 0.45 + (0.15 if liq >= MIN_LIQUIDITY else 0) + (0.1 if buys+sells >= 10 else 0) + (0.1 if volume >= liq*0.1 and liq>0 else 0))
                # Public pair data does not prove owner renounced or contract code status.
                owner_renounced = None
                contract_has_code = None
                gates = {
                    "liquidity_ok": liq >= MIN_LIQUIDITY,
                    "confidence_ok": confidence >= MIN_CONFIDENCE,
                    "risk_ok": risk <= MAX_RISK,
                    "owner_renounced": owner_renounced is True,
                    "contract_has_code": contract_has_code is True,
                }
                eligible = all(gates.values())
                decision = {
                    "timestamp": now(), "chain_id": CHAIN_ID, "address": addr, "symbol": symbol, "name": name,
                    "pair_url": pair.get("url") or p.get("url"), "liquidity_usd": round(liq, 2),
                    "volume_24h_usd": round(volume, 2), "buys_1h": buys, "sells_1h": sells,
                    "risk_score": risk, "confidence": round(confidence, 2),
                    "owner_renounced": owner_renounced, "contract_has_code": contract_has_code,
                    "gates": gates, "decision": "BUY" if eligible else "SKIP",
                    "reason": "Бүх hard gate давсан" if eligible else ("; ".join(reasons) if reasons else "owner-renounced болон contract-code баталгаажаагүй"),
                    "paper_trade": False
                }
                # Safety: current version always fails closed when ownership/code checks are unknown.
                if decision["decision"] == "BUY":
                    if state["paper_balance_usd"] >= TRADE_SIZE:
                        state["paper_balance_usd"] -= TRADE_SIZE
                        state["open_positions"].append({"address": addr, "symbol": symbol, "entry_price_usd": pair.get("priceUsd"), "size_usd": TRADE_SIZE, "opened_at": now(), "paper_only": True})
                        decision["paper_trade"] = True
                    else:
                        decision["decision"] = "SKIP"
                        decision["reason"] = "paper balance хүрэлцэхгүй"
                save_jsonl(decision)
                decisions.append(decision)
                time.sleep(0.15)
            except Exception as e:
                err = {"timestamp": now(), "chain_id": CHAIN_ID, "address": addr, "decision":"ERROR", "reason":str(e)[:250]}
                save_jsonl(err)
                decisions.append(err)
        state["error"] = ""
    except (HTTPError, URLError, TimeoutError, ValueError) as e:
        state["error"] = f"API error: {str(e)[:250]}"
        state["candidates_seen"] = 0
    # Newest first; retain 100 on dashboard, JSONL is the audit trail.
    state["recent_decisions"] = (decisions + state.get("recent_decisions", []))[:100]
    state["total_decisions"] = int(state.get("total_decisions", 0)) + len(decisions)
    state["updated_at"] = now()
    state["paper_balance_usd"] = round(float(state.get("paper_balance_usd", START_BALANCE)), 2)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Paper scan complete: {len(decisions)} decisions; chain={CHAIN_ID}; balance=${state['paper_balance_usd']:.2f}")

if __name__ == "__main__":
    main()
