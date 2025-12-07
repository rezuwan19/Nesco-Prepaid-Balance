# ------------------ nesco_monitor.py ------------------
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
import json
import os

import config
import notifier

PANEL_URL = "https://customer.nesco.gov.bd/pre/panel"
STATE_FILE = "last_data.json"


def fetch_nesco_data(session, cust_no: str) -> dict:
    """
    Fetch balance + latest recharge from the recharge table.
    Includes full recharge details from HTML table.
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    r1 = session.get(PANEL_URL, headers=headers, timeout=20)
    r1.raise_for_status()

    soup_page = BeautifulSoup(r1.text, "html.parser")

    token_tag = soup_page.find("input", {"name": "_token"})
    if not token_tag:
        raise RuntimeError("Cannot find CSRF token.")
    csrf_token = token_tag["value"]

    data = {
        "_token": csrf_token,
        "cust_no": cust_no.strip(),
        "submit": "রিচার্জ হিস্ট্রি"
    }

    r2 = session.post(PANEL_URL, headers=headers, data=data, timeout=30)
    r2.raise_for_status()
    soup = BeautifulSoup(r2.text, "html.parser")

    # ----- BALANCE -----
    balance_anchor_tag = soup.find(string=re.compile("অবশিষ্ট ব্যালেন্স"))
    if not balance_anchor_tag:
        with open("error_page.html", "w", encoding="utf-8") as f:
            f.write(r2.text)
        raise RuntimeError("Cannot find balance field.")

    label = balance_anchor_tag.find_parent("label")
    balance_input = label.find_next_sibling("div").find("input")
    balance_value = float(balance_input["value"])

    date_span = label.find("span")
    balance_date = datetime.strptime(date_span.text.strip(), "%d %B %Y %I:%M:%S %p")

    # ----- RECHARGE TABLE EXTRACTION -----
    table = soup.find("table")
    if not table:
        raise RuntimeError("Recharge table not found.")

    rows = table.find_all("tr")[1:]  # skip header row
    if not rows:
        raise RuntimeError("No recharge rows found.")

    # Extract FIRST (latest) row:
    cols = [c.text.strip() for c in rows[0].find_all("td")]

    latest_recharge = {
        "seq_no": cols[1],
        "token_no": cols[2],
        "meter_rent": float(cols[3]),
        "demand_charge": float(cols[4]),
        "pfc_charge": float(cols[5]),
        "vat": float(cols[6]),
        "due_penalty": float(cols[7]),
        "discount": float(cols[8]),
        "energy_charge": float(cols[9]),
        "recharge_amount": float(cols[10]),
        "kwh": cols[11],
        "method": cols[12],
        "recharge_date_raw": cols[13],
        "remote_status": cols[14],
    }

    recharge_date = datetime.strptime(latest_recharge["recharge_date_raw"], "%d-%b-%Y %I:%M %p")

    return {
        "balance": balance_value,
        "balance_date": balance_date,
        "recharge_info": latest_recharge,
        "recharge_date": recharge_date,
        "token_no": latest_recharge["token_no"]
    }


def load_last_data() -> dict:
    if not os.path.exists(STATE_FILE):
        return {}
    with open(STATE_FILE, "r") as f:
        return json.load(f)


def save_last_data(data: dict):
    storable = {
        "balance_date": data["balance_date"].isoformat(),
        "balance": data["balance"],
        "token_no": data["token_no"],
        "recharge_date": data["recharge_date"].isoformat(),
        "recharge_info": data["recharge_info"],
    }
    with open(STATE_FILE, "w") as f:
        json.dump(storable, f, indent=4)
    print("✅ State updated.")


def main():
    print(f"🔍 Running NESCO monitor for {config.NESCO_CUSTOMER_NO}")

    last_data = load_last_data()

    try:
        with requests.Session() as session:
            current = fetch_nesco_data(session, config.NESCO_CUSTOMER_NO)
    except Exception as e:
        print("❌ Error:", e)
        return

    updated = False

    # --- BALANCE CHANGE ---
    if last_data.get("balance_date") != current["balance_date"].isoformat():
        updated = True
        msg = (
            f"💰 NESCO Balance Update\n\n"
            f"👤 Consumer Name: {config.NESCO_Consumer_Name}\n"
            f"💳 Consumer No: {config.NESCO_CUSTOMER_NO}\n"
            f"💵 Balance: {current['balance']:.2f} BDT\n"
            f"📅 Time: {current['balance_date'].strftime('%d %b %Y, %I:%M %p')}"
        )
        notifier.send_notification(msg)
    else:
        print("✔️ Balance unchanged.")

    # --- RECHARGE CHANGE (using TOKEN NO) ---
    if last_data.get("token_no") != current["token_no"]:
        updated = True
        r = current["recharge_info"]

        msg = (
            f"⚡ NESCO Recharge Alert\n\n"
            f"👤 Consumer Name: {config.NESCO_Consumer_Name}\n"
            f"💳 Consumer No: {config.NESCO_CUSTOMER_NO}\n\n"
            f"⚡ Recharge Details\n"
            f"🔢 Token Number: {r['token_no']}\n"
            f"💰 Recharge Amount: {r['recharge_amount']} BDT\n"
            f"📅 Date: {current['recharge_date'].strftime('%d %b %Y, %I:%M %p')}\n\n"
            f"💡 Breakdown:\n"
            f"📜 Meter Rent: {r['meter_rent']} BDT\n"
            f"📜 Demand Charge: {r['demand_charge']} BDT\n"
            f"🧾 VAT: {r['vat']} BDT\n"
            f"🎁 Rebate (Tk.): {r['discount']} BDT\n"
            f"⚡ Energy Amount (Tk.): {r['energy_charge']} BDT\n"
            f"⚡ Estimated Unit (KWH): {r['kwh']} kWh\n"
            f"🏛️ Recharge Media: {r['method']}\n"
            f"✅ Remote Recharge Status: {r['remote_status']}\n"
        )

        notifier.send_notification(msg)
    else:
        print("✔️ Recharge unchanged.")

    # --- SAVE NEW DATA ---
    if updated:
        save_last_data(current)
    else:
        print("✨ No new updates.")


if __name__ == "__main__":
    main()
