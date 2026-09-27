let ALL_ITEMS = [];
let CART = {}; // id -> {id, name, price, unit, qty}

async function loadItems() {
  const q = document.getElementById('searchBox').value.trim();
  const res = await fetch(`/api/items?q=${encodeURIComponent(q)}`);
  ALL_ITEMS = await res.json();
  renderItemGrid();
}

function renderItemGrid() {
  const grid = document.getElementById('itemGrid');
  const noItems = document.getElementById('noItems');
  grid.innerHTML = '';
  if (ALL_ITEMS.length === 0) {
    noItems.classList.remove('hidden');
    return;
  }
  noItems.classList.add('hidden');

  ALL_ITEMS.forEach(item => {
    const card = document.createElement('button');
    card.className = "text-left bg-orange-50/60 hover:bg-orange-100 border border-orange-100 rounded-xl p-3 " +
                      "transition-all active:scale-95 hover:shadow-md group";
    card.onclick = () => addToCart(item);
    card.innerHTML = `
      <div class="flex items-start justify-between">
        <p class="font-semibold text-slate-700 text-sm leading-snug pr-2">${escapeHtml(item.name)}</p>
        <i data-lucide="plus-circle" class="w-5 h-5 text-brand-500 shrink-0 group-hover:animate-wiggle"></i>
      </div>
      <p class="text-xs text-slate-400 mt-1">${escapeHtml(item.category || 'General')}</p>
      <p class="text-brand-700 font-bold mt-1">₹${item.price.toFixed(2)} <span class="text-xs font-normal text-slate-400">/ ${item.unit}</span></p>
    `;
    grid.appendChild(card);
  });
  lucide.createIcons();
}

function addToCart(item) {
  if (CART[item.id]) {
    CART[item.id].qty += 1;
  } else {
    CART[item.id] = { id: item.id, name: item.name, price: item.price, unit: item.unit, qty: 1 };
  }
  renderCart();
  showToast(`${item.name} added`);
}

function updateQty(id, qty) {
  qty = parseFloat(qty);
  if (isNaN(qty) || qty <= 0) {
    delete CART[id];
  } else {
    CART[id].qty = qty;
  }
  renderCart();
}

function removeFromCart(id) {
  delete CART[id];
  renderCart();
}

function clearCart() {
  CART = {};
  renderCart();
}

function renderCart() {
  const list = document.getElementById('cartList');
  const emptyMsg = document.getElementById('emptyCartMsg');
  const items = Object.values(CART);

  list.innerHTML = '';
  if (items.length === 0) {
    list.appendChild(emptyMsg);
    emptyMsg.classList.remove('hidden');
  } else {
    items.forEach(line => {
      const row = document.createElement('div');
      row.className = "flex items-center gap-2 py-2 animate-pop";
      row.innerHTML = `
        <div class="flex-1 min-w-0">
          <p class="text-sm font-semibold text-slate-700 truncate">${escapeHtml(line.name)}</p>
          <p class="text-xs text-slate-400">₹${line.price.toFixed(2)} / ${line.unit}</p>
        </div>
        <input type="number" min="0" step="0.01" value="${line.qty}"
               onchange="updateQty(${line.id}, this.value)"
               class="w-16 text-center px-1 py-1.5 rounded-lg border border-slate-200 text-sm outline-none focus:border-brand-500">
        <p class="w-16 text-right text-sm font-bold text-slate-700">₹${(line.price * line.qty).toFixed(2)}</p>
        <button onclick="removeFromCart(${line.id})" class="text-slate-300 hover:text-red-500 transition">
          <i data-lucide="x-circle" class="w-4 h-4"></i>
        </button>
      `;
      list.appendChild(row);
    });
  }
  lucide.createIcons();
  updateTotals();
}

function updateTotals() {
  const items = Object.values(CART);
  const subtotal = items.reduce((s, l) => s + l.price * l.qty, 0);
  const discount = Math.min(parseFloat(document.getElementById('discountInput').value || 0), subtotal);
  const total = subtotal - discount;
  document.getElementById('subtotalVal').textContent = `₹${subtotal.toFixed(2)}`;
  document.getElementById('totalVal').textContent = `₹${total.toFixed(2)}`;
}

document.addEventListener('input', (e) => {
  if (e.target && e.target.id === 'discountInput') updateTotals();
});

function showToast(msg) {
  const toast = document.getElementById('toast');
  document.getElementById('toastMsg').textContent = msg;
  toast.classList.remove('hidden');
  clearTimeout(window._toastTimer);
  window._toastTimer = setTimeout(() => toast.classList.add('hidden'), 1800);
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

async function generateBill() {
  const items = Object.values(CART);
  if (items.length === 0) {
    showToast('Add at least one item first');
    return;
  }
  const btn = document.getElementById('generateBtn');
  btn.disabled = true;
  btn.innerHTML = `<i data-lucide="loader-2" class="w-5 h-5 animate-spin"></i> Generating...`;
  lucide.createIcons();

  const payload = {
    customer_name: document.getElementById('customerName').value.trim(),
    discount: parseFloat(document.getElementById('discountInput').value || 0),
    payment_mode: document.getElementById('paymentMode').value,
    cart: items.map(i => ({ id: i.id, qty: i.qty }))
  };

  try {
    const res = await fetch('/api/billing/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok) {
      showToast(data.error || 'Could not generate bill');
      return;
    }
    renderReceipt(data);
    window.print();

    // reset after printing
    clearCart();
    document.getElementById('customerName').value = '';
    document.getElementById('discountInput').value = 0;
    updateTotals();
    showToast(`Bill ${data.invoice_no} generated`);
  } catch (err) {
    console.error(err);
    showToast('Network error, please try again');
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<i data-lucide="printer" class="w-5 h-5"></i> Generate &amp; Print Bill`;
    lucide.createIcons();
  }
}

function renderReceipt(bill) {
  const el = document.getElementById('receiptContent');
  const itemRows = bill.items.map(li => `
    <div class="r-row">
      <div class="r-name">${escapeHtml(li.item_name)}</div>
    </div>
    <div class="r-row">
      <span>${li.qty} ${li.unit || ''} x ₹${li.price.toFixed(2)}</span>
      <span>₹${li.line_total.toFixed(2)}</span>
    </div>
  `).join('');

  el.innerHTML = `
    <div class="r-center r-bold r-big">POOJA STORE</div>
    <div class="r-center">Thank you for shopping with us!</div>
    <div class="r-line"></div>
    <div class="r-row"><span>Bill No:</span><span>${bill.invoice_no}</span></div>
    <div class="r-row"><span>Date:</span><span>${bill.created_at}</span></div>
    ${bill.customer_name ? `<div class="r-row"><span>Customer:</span><span>${escapeHtml(bill.customer_name)}</span></div>` : ''}
    <div class="r-row"><span>Payment:</span><span>${bill.payment_mode}</span></div>
    <div class="r-line"></div>
    ${itemRows}
    <div class="r-line"></div>
    <div class="r-row"><span>Subtotal</span><span>₹${bill.subtotal.toFixed(2)}</span></div>
    <div class="r-row"><span>Discount</span><span>₹${bill.discount.toFixed(2)}</span></div>
    <div class="r-row r-bold r-big"><span>TOTAL</span><span>₹${bill.total.toFixed(2)}</span></div>
    <div class="r-line"></div>
    <div class="r-center">*** Thank You, Visit Again! ***</div>
  `;
}

// init
document.addEventListener('DOMContentLoaded', () => {
  loadItems();
  document.getElementById('searchBox').addEventListener('input', loadItems);
});
