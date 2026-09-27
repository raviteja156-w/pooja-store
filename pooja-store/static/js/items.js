let EDIT_ID = null;

async function loadItems() {
  const q = document.getElementById('searchBox').value.trim();
  const res = await fetch(`/api/items?q=${encodeURIComponent(q)}`);
  const items = await res.json();
  renderTable(items);
}

function renderTable(items) {
  const body = document.getElementById('itemsTableBody');
  const noRow = document.getElementById('noItemsRow');
  body.innerHTML = '';

  if (items.length === 0) {
    noRow.classList.remove('hidden');
    return;
  }
  noRow.classList.add('hidden');

  items.forEach(item => {
    const tr = document.createElement('tr');
    tr.className = "hover:bg-orange-50/60 transition-colors";
    tr.innerHTML = `
      <td class="px-4 py-3 font-semibold text-slate-700">${escapeHtml(item.name)}</td>
      <td class="px-4 py-3 text-slate-500">${escapeHtml(item.category || '-')}</td>
      <td class="px-4 py-3 text-right font-bold text-brand-700">₹${item.price.toFixed(2)}</td>
      <td class="px-4 py-3 text-right text-slate-500">${item.stock}</td>
      <td class="px-4 py-3 text-slate-500">${escapeHtml(item.unit)}</td>
      <td class="px-4 py-3">
        <div class="flex items-center justify-center gap-2">
          <button onclick='editItem(${JSON.stringify(item)})' class="p-1.5 rounded-lg bg-blue-50 text-blue-600 hover:bg-blue-100 transition">
            <i data-lucide="pencil" class="w-4 h-4"></i>
          </button>
          <button onclick="deleteItem(${item.id}, '${escapeJs(item.name)}')" class="p-1.5 rounded-lg bg-red-50 text-red-600 hover:bg-red-100 transition">
            <i data-lucide="trash-2" class="w-4 h-4"></i>
          </button>
        </div>
      </td>
    `;
    body.appendChild(tr);
  });
  lucide.createIcons();
}

function openModal() {
  EDIT_ID = null;
  document.getElementById('modalTitle').innerHTML = `<i data-lucide="package-plus" class="w-5 h-5 text-brand-600"></i> Add Item`;
  document.getElementById('itemId').value = '';
  document.getElementById('itemName').value = '';
  document.getElementById('itemPrice').value = '';
  document.getElementById('itemStock').value = 0;
  document.getElementById('itemCategory').value = '';
  document.getElementById('itemUnit').value = 'pc';
  document.getElementById('itemModal').classList.remove('hidden');
  document.getElementById('itemModal').classList.add('flex');
  lucide.createIcons();
}

function editItem(item) {
  EDIT_ID = item.id;
  document.getElementById('modalTitle').innerHTML = `<i data-lucide="pencil" class="w-5 h-5 text-brand-600"></i> Edit Item`;
  document.getElementById('itemId').value = item.id;
  document.getElementById('itemName').value = item.name;
  document.getElementById('itemPrice').value = item.price;
  document.getElementById('itemStock').value = item.stock;
  document.getElementById('itemCategory').value = item.category;
  document.getElementById('itemUnit').value = item.unit;
  document.getElementById('itemModal').classList.remove('hidden');
  document.getElementById('itemModal').classList.add('flex');
  lucide.createIcons();
}

function closeModal() {
  document.getElementById('itemModal').classList.add('hidden');
  document.getElementById('itemModal').classList.remove('flex');
}

async function saveItem() {
  const name = document.getElementById('itemName').value.trim();
  const price = document.getElementById('itemPrice').value;
  const stock = document.getElementById('itemStock').value;
  const category = document.getElementById('itemCategory').value.trim();
  const unit = document.getElementById('itemUnit').value;

  if (!name || price === '') {
    showToast('Name and price are required');
    return;
  }

  const payload = { name, price, stock, category, unit };
  const url = EDIT_ID ? `/api/items/${EDIT_ID}` : '/api/items';
  const method = EDIT_ID ? 'PUT' : 'POST';

  const res = await fetch(url, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  const data = await res.json();
  if (!res.ok) {
    showToast(data.error || 'Something went wrong');
    return;
  }
  closeModal();
  loadItems();
  showToast(EDIT_ID ? 'Item updated' : 'Item added');
}

async function deleteItem(id, name) {
  if (!confirm(`Delete "${name}"? This cannot be undone.`)) return;
  const res = await fetch(`/api/items/${id}`, { method: 'DELETE' });
  const data = await res.json();
  if (!res.ok) {
    showToast(data.error || 'Could not delete item');
    return;
  }
  loadItems();
  showToast('Item deleted');
}

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
function escapeJs(str) {
  return String(str).replace(/'/g, "\\'");
}

document.addEventListener('DOMContentLoaded', loadItems);
