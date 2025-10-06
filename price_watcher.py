import os, json, time, argparse, re
from pathlib import Path
import requests
from playwright.sync_api import sync_playwright

URL = "https://www.liveyourphone.it/iphone-apple-iphone-16-128gb-bianco.1.1.8.gp.318.uw"
STATE_FILE = Path("price_state.json")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

def fetch_price():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL, timeout=60000)
        page.wait_for_selector("span.mainPriceAmount", timeout=30000)

        amount = page.locator("span.mainPriceAmount").inner_text().strip()
        currency = page.locator("span.mainPriceCurrency").inner_text().strip()

        # Normalizza formattazione
        amount = amount.replace(".", "").replace(",", ".")  # gestisce "1.099,00"
        price = float(amount)

        browser.close()
        print(f"Trovato prezzo: {price} {currency}")
        return price

def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}

def save_state(state):
    STATE_FILE.write_text(json.dumps(state))

def send_telegram(msg: str):
    if not BOT_TOKEN or not CHAT_ID:
        raise RuntimeError("BOT_TOKEN o CHAT_ID mancanti")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": msg, "disable_web_page_preview": True}
    r = requests.post(url, data=data, timeout=20)
    r.raise_for_status()

def main(always=False):
    now = time.strftime("%Y-%m-%d %H:%M")
    try:
        price = fetch_price()
    except Exception as e:
        send_telegram(f"❌ Errore durante fetch prezzo: {e}")
        raise

    st = load_state()
    prev = st.get("price")
    if prev is None:
        st["price"] = price
        save_state(st)
        send_telegram(f"🔎 Prezzo iniziale: €{price:,.2f} (al {now})".replace(",", "X").replace(".", ",").replace("X","."))
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
    ap.add_argument("--always", action="store_true", help="Invia sempre report anche senza variazioni")
    args = ap.parse_args()
    main(always=args.always)
