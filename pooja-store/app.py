import os
import sqlite3
from datetime import datetime
from flask import Flask, g, render_template, request, jsonify

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "store.db")

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            category TEXT DEFAULT '',
            stock REAL DEFAULT 0,
            unit TEXT DEFAULT 'pc',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_no TEXT NOT NULL UNIQUE,
            customer_name TEXT DEFAULT '',
            subtotal REAL NOT NULL,
            discount REAL DEFAULT 0,
            total REAL NOT NULL,
            payment_mode TEXT DEFAULT 'Cash',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS invoice_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL,
            item_name TEXT NOT NULL,
            price REAL NOT NULL,
            qty REAL NOT NULL,
            line_total REAL NOT NULL,
            FOREIGN KEY (invoice_id) REFERENCES invoices (id)
        );
        """
    )
    # seed a few demo items only if table is empty
    cur = db.execute("SELECT COUNT(*) FROM items")
    if cur.fetchone()[0] == 0:
        demo_items = [
            ("Rice (1kg)", 60, "Grocery", 50, "kg"),
            ("Wheat Flour (1kg)", 45, "Grocery", 50, "kg"),
            ("Sugar (1kg)", 42, "Grocery", 40, "kg"),
            ("Tea Powder (250g)", 90, "Grocery", 30, "pkt"),
            ("Cooking Oil (1L)", 150, "Grocery", 20, "ltr"),
            ("Soap", 35, "Personal Care", 100, "pc"),
            ("Shampoo Sachet", 5, "Personal Care", 200, "pc"),
            ("Biscuit Packet", 20, "Snacks", 80, "pkt"),
            ("Milk (500ml)", 28, "Dairy", 60, "pkt"),
            ("Notebook", 40, "Stationery", 50, "pc"),
        ]
        db.executemany(
            "INSERT INTO items (name, price, category, stock, unit) VALUES (?,?,?,?,?)",
            demo_items,
        )
    db.commit()
    db.close()


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
@app.route("/")
def billing_page():
    return render_template("billing.html")


@app.route("/items")
def items_page():
    return render_template("items.html")


# ---------------------------------------------------------------------------
# Items CRUD API
# ---------------------------------------------------------------------------
@app.route("/api/items", methods=["GET"])
def api_items_list():
    db = get_db()
    q = request.args.get("q", "").strip()
    if q:
        rows = db.execute(
            "SELECT * FROM items WHERE name LIKE ? OR category LIKE ? ORDER BY name",
            (f"%{q}%", f"%{q}%"),
        ).fetchall()
    else:
        rows = db.execute("SELECT * FROM items ORDER BY name").fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/items", methods=["POST"])
def api_items_create():
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    price = data.get("price")
    category = (data.get("category") or "").strip()
    stock = data.get("stock", 0)
    unit = (data.get("unit") or "pc").strip()

    if not name or price is None:
        return jsonify({"error": "Name and price are required"}), 400
    try:
        price = float(price)
        stock = float(stock) if stock not in (None, "") else 0
    except ValueError:
        return jsonify({"error": "Price and stock must be numbers"}), 400

    db = get_db()
    cur = db.execute(
        "INSERT INTO items (name, price, category, stock, unit) VALUES (?,?,?,?,?)",
        (name, price, category, stock, unit),
    )
    db.commit()
    new_item = db.execute("SELECT * FROM items WHERE id=?", (cur.lastrowid,)).fetchone()
    return jsonify(dict(new_item)), 201


@app.route("/api/items/<int:item_id>", methods=["PUT"])
def api_items_update(item_id):
    data = request.get_json(force=True)
    db = get_db()
    existing = db.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
    if not existing:
        return jsonify({"error": "Item not found"}), 404

    name = (data.get("name") or existing["name"]).strip()
    category = data.get("category", existing["category"])
    unit = data.get("unit", existing["unit"])
    try:
        price = float(data.get("price", existing["price"]))
        stock = float(data.get("stock", existing["stock"]))
    except ValueError:
        return jsonify({"error": "Price and stock must be numbers"}), 400

    db.execute(
        "UPDATE items SET name=?, price=?, category=?, stock=?, unit=? WHERE id=?",
        (name, price, category, stock, unit, item_id),
    )
    db.commit()
    updated = db.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
    return jsonify(dict(updated))


@app.route("/api/items/<int:item_id>", methods=["DELETE"])
def api_items_delete(item_id):
    db = get_db()
    existing = db.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
    if not existing:
        return jsonify({"error": "Item not found"}), 404
    db.execute("DELETE FROM items WHERE id=?", (item_id,))
    db.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Billing API
# ---------------------------------------------------------------------------
def generate_invoice_no(db):
    today = datetime.now().strftime("%Y%m%d")
    row = db.execute(
        "SELECT COUNT(*) as c FROM invoices WHERE invoice_no LIKE ?", (f"PS-{today}-%",)
    ).fetchone()
    seq = row["c"] + 1
    return f"PS-{today}-{seq:03d}"


@app.route("/api/billing/generate", methods=["POST"])
def api_billing_generate():
    data = request.get_json(force=True)
    cart = data.get("cart", [])
    customer_name = (data.get("customer_name") or "").strip()
    discount = float(data.get("discount") or 0)
    payment_mode = data.get("payment_mode") or "Cash"

    if not cart:
        return jsonify({"error": "Cart is empty"}), 400

    db = get_db()
    subtotal = 0.0
    line_items = []
    for line in cart:
        try:
            item_id = int(line.get("id"))
            qty = float(line.get("qty"))
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid cart line"}), 400
        item = db.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
        if not item:
            continue
        if qty <= 0:
            continue
        line_total = round(item["price"] * qty, 2)
        subtotal += line_total
        line_items.append(
            {
                "item_name": item["name"],
                "price": item["price"],
                "qty": qty,
                "unit": item["unit"],
                "line_total": line_total,
            }
        )

    if not line_items:
        return jsonify({"error": "No valid items in cart"}), 400

    subtotal = round(subtotal, 2)
    discount = max(0.0, min(discount, subtotal))
    total = round(subtotal - discount, 2)

    invoice_no = generate_invoice_no(db)
    cur = db.execute(
        "INSERT INTO invoices (invoice_no, customer_name, subtotal, discount, total, payment_mode) VALUES (?,?,?,?,?,?)",
        (invoice_no, customer_name, subtotal, discount, total, payment_mode),
    )
    invoice_id = cur.lastrowid
    for li in line_items:
        db.execute(
            "INSERT INTO invoice_items (invoice_id, item_name, price, qty, line_total) VALUES (?,?,?,?,?)",
            (invoice_id, li["item_name"], li["price"], li["qty"], li["line_total"]),
        )
    db.commit()

    return jsonify(
        {
            "invoice_no": invoice_no,
            "customer_name": customer_name,
            "created_at": datetime.now().strftime("%d-%m-%Y %I:%M %p"),
            "items": line_items,
            "subtotal": subtotal,
            "discount": discount,
            "total": total,
            "payment_mode": payment_mode,
            "store_name": "POOJA STORE",
        }
    )


# ---------------------------------------------------------------------------
init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
