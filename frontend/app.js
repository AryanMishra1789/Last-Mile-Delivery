let orders = JSON.parse(localStorage.getItem('last_mile_demo_orders') || '[]');
let loggedIn = localStorage.getItem('delivery_demo_user') === 'customer';

function login() {
  loggedIn = true;
  localStorage.setItem('delivery_demo_user', 'customer');
  document.querySelector('#session').innerHTML = '<span>Demo Customer</span>';
  loadOrders();
}

function showForm() { document.querySelector('#form').classList.toggle('hidden'); }

function createOrder() {
  const [length, breadth, height] = document.querySelector('#dims').value.split('x').map(Number);
  const actualWeight = Number(document.querySelector('#weight').value);
  const orderType = document.querySelector('#kind').value;
  const paymentType = document.querySelector('#payment').value;
  const volumetricWeight = length * breadth * height / 5000;
  const billableWeight = Math.max(actualWeight, volumetricWeight);
  const intraZone = document.querySelector('#pp').value.slice(0, 3) === document.querySelector('#dp').value.slice(0, 3);
  const baseRate = intraZone ? (orderType === 'B2C' ? 50 : 70) : (orderType === 'B2C' ? 120 : 150);
  const perKg = intraZone ? (orderType === 'B2C' ? 18 : 14) : (orderType === 'B2C' ? 28 : 24);
  const cod = paymentType === 'COD' ? (orderType === 'B2C' ? 35 : 55) : 0;
  const charge = Math.round((baseRate + billableWeight * perKg + cod) * 100) / 100;
  document.querySelector('#quote').textContent = `${intraZone ? 'Intra-zone' : 'Inter-zone'} | ${billableWeight.toFixed(3)}kg billable | Charge: Rs ${charge}`;
  if (!confirm(`Place this delivery for Rs ${charge}?`)) return;
  orders.unshift({ id: Date.now(), pickup: document.querySelector('#pickup').value || 'North Hub', drop: document.querySelector('#drop').value || 'South Hub', orderType, paymentType, charge, status: 'Pending' });
  localStorage.setItem('last_mile_demo_orders', JSON.stringify(orders));
  loadOrders();
}

function loadOrders() {
  if (!loggedIn) return;
  document.querySelector('#active').textContent = orders.filter(order => !['Delivered', 'Failed'].includes(order.status)).length;
  document.querySelector('#attention').textContent = orders.filter(order => ['Pending', 'Failed'].includes(order.status)).length;
  document.querySelector('#orders').innerHTML = orders.length ? orders.map(order => `<article class="order"><div class="order-id">#${String(order.id).slice(-4)}</div><div class="route">${order.pickup} -> ${order.drop}<small>${order.orderType} / ${order.paymentType}</small></div><div class="agent">Demo assignment</div><div class="status">${order.status}</div><div class="price">Rs ${order.charge}</div></article>`).join('') : '<p>No deliveries yet. Create your first demo order above.</p>';
}

if (loggedIn) { document.querySelector('#session').innerHTML = '<span>Demo Customer</span>'; loadOrders(); }
