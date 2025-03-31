import json
import requests
from datetime import datetime, timedelta

# === CONFIG ===
ODOO_URL = "https://daisymv.odoo.com/jsonrpc"
DB = "daisymv"
USERNAME = "daisyshapewear@protonmail.com"
API_KEY = "278605e84ae8e29930f60ebbbd47473e7acad6f9"
VIBER_BOT_TOKEN = "4fff43514827e06e-765ce1f4c7ef1643-47cb4636c5f758da"
API_URL = "https://rccmaldives.com/api/customers.php"  # TODO: Replace with your actual API URL

# === PRODUCT PRICE MAP ===
PRODUCT_PRICES = {
    "DHFG-0003": {"Male": 0,     "Female": 90},  # Womens Shirt Top
    "DHFG-0031": {"Male": 0,     "Female": 95},  # Women Pants
    "DHFG-0032": {"Male": 90,    "Female": 90},  # Shorts
    "DHFG-0002": {"Male": 115,   "Female": 0},   # Men Shirt
    "DHFG-0007": {"Male": 120,   "Female": 0},   # Men Pants
    "FG/86045":  {"Male": 10,    "Female": 10},  # School Badge
    "DHFG-0009": {"Male": 0,     "Female": 110}, # Ladies Skirt
    "DHFG-TIE":  {"Male": 15,    "Female": 15},  # Tie
    "DHFG-0033": {"Male": 0,     "Female": 125}, # Burka
}

# === Odoo Authentication ===
def odoo_auth():
    payload = {
        "jsonrpc": "2.0", "method": "call",
        "params": {
            "service": "common", "method": "authenticate",
            "args": [DB, USERNAME, API_KEY, {}]
        }, "id": 1
    }
    res = requests.post(ODOO_URL, json=payload).json()
    return res.get("result")

# === JSON-RPC Call Helper ===
def odoo_call(model, method, args, kwargs=None):
    payload = {
        "jsonrpc": "2.0", "method": "call",
        "params": {
            "service": "object", "method": "execute_kw",
            "args": [DB, uid, API_KEY, model, method, args, kwargs or {}]
        }, "id": 2
    }
    return requests.post(ODOO_URL, json=payload).json()["result"]

# === Ensure Customer ===
def create_partner(name, phone):
    partner_id = odoo_call("res.partner", "create", [{
        "name": name,
        "phone": phone
    }])
    return partner_id

# === Ensure Product ===
def get_or_create_product(code, price):
    ids = odoo_call("product.product", "search", [[["default_code", "=", code]]])
    if ids: return ids[0]
    return odoo_call("product.product", "create", [{
        "name": code,
        "default_code": code,
        "list_price": price
    }])

# === Create Quotation ===
def create_quotation(partner_id, order_lines):
    order_id = odoo_call("sale.order", "create", [{
        "partner_id": partner_id,
        "validity_date": (datetime.today() + timedelta(days=15)).strftime("%Y-%m-%d"),
        "note": "Please send the transfer slips to 9227799 on Viber."
    }])
    for product_id, qty, price in order_lines:
        odoo_call("sale.order.line", "create", [{
            "order_id": order_id,
            "product_id": product_id,
            "product_uom_qty": qty,
            "price_unit": price
        }])
    odoo_call("sale.order", "write", [[order_id], {"state": "sent"}])
    order = odoo_call("sale.order", "read", [[order_id], ["access_token", "name"]])[0]
    return order_id, order["access_token"], order["name"]

# === Send Viber File ===
def send_viber(phone, pdf_url, file_name):
    payload = {
        "receiver": phone,
        "type": "file",
        "media": pdf_url,
        "file_name": file_name
    }
    headers = {
        "X-Viber-Auth-Token": VIBER_BOT_TOKEN
    }
    res = requests.post("https://chatapi.viber.com/pa/send_message", json=payload, headers=headers)
    return res.status_code == 200

# === Main Execution ===
uid = odoo_auth()
if not uid:
    print("❌ Authentication failed.")
    exit()

response = requests.get(API_URL)
customers = response.json()

for customer in customers:
    name = customer["name"]
    phone = customer["phone"]
    gender = customer["gender"]
    with_fabric = customer.get("with_fabric", True)

    partner_id = create_partner(name, phone)
    order_lines = []

    for item in customer["items"]:
        code = item["code"]
        qty = item["qty"]
        base_price = PRODUCT_PRICES.get(code, {}).get(gender, 0)
        price = base_price if with_fabric else 0
        product_id = get_or_create_product(code, price)
        order_lines.append((product_id, qty, price))

    if not order_lines: continue

    order_id, token, order_name = create_quotation(partner_id, order_lines)
    pdf_url = f"https://daisymv.odoo.com/my/orders/{order_id}?access_token={token}&report_type=pdf"
    success = send_viber(phone, pdf_url, f"{order_name}.pdf")
    print(f"{'✅' if success else '❌'} Sent {order_name} to {phone}")
