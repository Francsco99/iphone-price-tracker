import os, re, json, time, argparse, requests
from pathlib import Path
from bs4 import BeautifulSoup

URL = "https://www.liveyourphone.it/iphone-apple-iphone-16-128gb-bianco.1.1.8.gp.318.uw"
STATE_FILE = Path("price_state.json")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

PRICE_RE = re.compile(r"€\s*\d{1,3}(?:\.\d{3})*,\d{2}")

def fetch_price():
    hdrs = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/128.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.google.com/"
    }
    r = requests.get(URL, headers=hdrs, timeout=20)
    r.raise_for_status()
    html = r.text

    # DEBUG: salva i primi 5000 caratteri per capire cosa arriva
    Path("last_response.html").write_text(html[:5000])

    s = BeautifulSoup(html, "html.parser")

    # cerca direttamente elementi col prezzo
    price_tag = s.select_one(".price, .product-price, span.price")
    if price_tag:
        raw = price_tag.get_text(strip=True)
    else:
        # fallback regex
        txt = s.get_text(" ", strip=True)
        candidates = PRICE_RE.findall(txt)
        if not candidates:
            raise RuntimeError("Prezzo non trovato nella pagina")
        raw = candidates[0]

    n = raw.replace("€", "").replace(".", "").replace(" ", "").replace("\xa0", "").replace(",", ".")
    return float(n)

def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}

def save_state(state):
    STATE_FILE.write_text(json.dumps(state))

def send_telegram(msg):
    if not BOT_TOKEN or not CHAT_ID:
        raise RuntimeError("BOT_TOKEN o CHAT_ID mancanti")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": msg, "disable_web_page_preview": True}
    r = requests.post(url, data=data, timeout=20)
    r.raise_for_status()

def main(always=False):
    now = time.strftime("%Y-%m-%d %H:%M")
    price = fetch_price()
    st = load_state()
    prev = st.get("price")
    if prev is None:
        st["price"] = price
        save_state(st)
        send_telegram(f"🔎 Prezzo iniziale iPhone 16 128GB Bianco: €{price:,.2f} (al {now})".replace(",", "X").replace(".", ",").replace("X","."))
        return
    changed = (abs(price - prev) > 1e-6)
    if changed or always:
        prefix = "🟢 CAMBIATO" if changed else "ℹ️ Report giornaliero"
        delta = f" (prima €{prev:,.2f})" if changed else ""
        msg = f"{prefix}: ora €{price:,.2f}{delta}\nPagina: {URL}\n{now}"
        msg = msg.replace(",", "X").replace(".", ",").replace("X",".")
        send_telegram(msg)
    if changed:
        st["price"] = price
        save_state(st)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--always", action="store_true", help="Invia comunque un report anche senza variazioni")
    args = ap.parse_args()
    main(always=args.always)
