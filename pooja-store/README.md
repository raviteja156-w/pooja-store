# 🛍️ Pooja Store — Billing System

A simple, fast, single-purpose billing app for a shop:

- **Page 1 — Billing (`/`)**: Tap items to add to the cart, type quantities, see the total live, then hit **Generate & Print Bill**. It creates the invoice and opens the print dialog formatted for an 80mm thermal receipt.
- **Page 2 — Items (`/items`)**: Full CRUD — add, edit, delete items and manage their prices, stock and units. These are the predefined prices used on the billing page.

Built with **Flask + SQLite** (backend), **Tailwind CSS + Lucide animated icons** (frontend), vanilla JS (no build step).

---

## 1. Run locally

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open **http://localhost:5000**. A `store.db` SQLite file is created automatically on first run, pre-seeded with a few demo grocery items — edit/delete them from the Items page.

---

## 2. Deploy to Render (free tier ready)

1. Push this folder to a GitHub repo.
2. On [render.com](https://render.com) → **New → Web Service** → connect the repo.
3. Render auto-detects `render.yaml`. Otherwise set manually:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
4. Deploy. Done — you'll get a public URL like `https://pooja-store.onrender.com`.

⚠️ **Note on the free tier:** Render's free web services use an **ephemeral filesystem** — the SQLite file (`store.db`) resets on redeploys/restarts. For a shop you actually run day-to-day, either:
- upgrade to a paid instance with a persistent disk (add a Render "Disk" mounted at `/opt/render/project/src`), or
- swap SQLite for Render's free PostgreSQL and change the few `sqlite3` calls in `app.py` (this keeps the app structure identical).

---

## 3. Connecting a thermal printer — how it actually works

Cloud-hosted web apps (Render, or any server) **cannot directly talk to a USB/Bluetooth thermal printer plugged into your shop counter** — the printer is physically attached to *your* computer/phone, not to Render's servers. The reliable, industry-standard way browsers print to thermal printers is exactly what this app does:

1. **Generate & Print Bill** builds a perfectly-sized 80mm receipt (`static/css/style.css` → `@media print` + `#printArea`) and calls `window.print()`.
2. Your browser's print dialog opens — pick your thermal printer there, same as printing any web page.

### To make this work with your printer:

| Printer type | Setup |
|---|---|
| **USB thermal printer (Windows/Mac/Linux)** | Install the manufacturer's driver so it shows up as a normal system printer (e.g. "POS-80", "EPSON TM-T20"). Select it in the print dialog. Set paper size to **80mm / Receipt** in printer preferences so it doesn't print on A4. |
| **Bluetooth/USB thermal printer on Android** | Install a print-bridge app like **RawBT** or **Print Master POS**, set it as your default/virtual printer. Chrome's print dialog will list it; it converts the HTML receipt to ESC/POS commands automatically. |
| **Network/LAN thermal printer** | Install its driver on the till PC (most POS thermal printers support IP driver installs), then it appears in the OS print list like a USB one. |

This means: **no extra native code, no serial/ESC-POS libraries, and no OS-specific installs needed in this codebase** — the browser + your printer driver do the ESC/POS translation. This is also why the app works identically whether it's running on `localhost` or deployed on Render.

### If you specifically want raw ESC/POS control (advanced, optional)
If later you want the *server* to push raw ESC/POS bytes directly to a LAN thermal printer (skipping the browser print dialog entirely — useful for unattended kiosks), you'd add a small local print-agent using a library like `python-escpos`, running **on the shop's own PC/Raspberry Pi** (not on Render, since Render has no access to your LAN or USB ports), and have the Flask app POST the receipt JSON to that local agent's `/print` endpoint. Ask if you'd like this extended version — it needs to run alongside the till computer, not on Render.

---

## 4. Project structure

```
pooja-store/
├── app.py                  # Flask app: routes + REST API + SQLite
├── requirements.txt
├── Procfile                 # gunicorn start command (Render/Heroku)
├── render.yaml               # Render blueprint (auto-config)
├── templates/
│   ├── base.html            # shared layout, nav, Tailwind/Lucide setup
│   ├── billing.html          # Page 1: billing
│   └── items.html            # Page 2: items CRUD
└── static/
    ├── css/style.css         # UI polish + 80mm receipt print styles
    └── js/
        ├── billing.js         # cart logic, bill generation, printing
        └── items.js           # items CRUD logic
```

## 5. API endpoints (for reference / future integrations)

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/items?q=` | list/search items |
| POST | `/api/items` | create item `{name, price, category, stock, unit}` |
| PUT | `/api/items/<id>` | update item |
| DELETE | `/api/items/<id>` | delete item |
| POST | `/api/billing/generate` | `{customer_name, discount, payment_mode, cart:[{id,qty}]}` → saves invoice, returns receipt JSON |

Enjoy running Pooja Store! 🧾
