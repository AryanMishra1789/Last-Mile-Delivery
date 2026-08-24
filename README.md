# Last-Mile Delivery Tracker

## Submission status

Hosted application: https://last-mile-delivery-rdesvdypb-aryan-mishras-projects-ea501e54.vercel.app

The Last-Mile Delivery Tracker is a complete delivery operations platform for customer order placement, intelligent pricing, agent dispatch, delivery lifecycle management, and proactive customer communication. The product workspace showcases customer order creation, volumetric and COD pricing, delivery summaries, and operations monitoring. The repository includes the complete FastAPI service, SQLite data layer, role-based security, assignment engine, immutable tracking model, and email/SMS integrations.

The backend is the authoritative implementation of all business rules. The static frontend includes a clearly marked pricing fallback solely so the hosted customer experience remains interactive while the API is deployed independently; backend deployments use admin-managed zones and rate cards rather than frontend values.

The architecture supports a static frontend deployment and an independently hosted Python API. All implementation details, API contracts, setup steps, and system design decisions are documented below for evaluation and production rollout.

## Run locally

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000. API docs are at http://127.0.0.1:8000/docs. First startup creates `delivery.db` and seeds `admin@example.com` / `admin123`, `customer@example.com` / `customer123`, `agent@example.com` / `agent123`, two zones, and B2B/B2C route cards. Change credentials before deployment.

## Frontend deployment

The frontend is in [frontend](frontend) and is deployed to Vercel. The customer workspace is available at the root URL and the operations workspace at `/admin`. It can be redeployed with `vercel --cwd frontend --prod`.

## Rate calculation

Each pincode resolves to an admin-managed zone. Volumetric weight is `L x B x H / 5000`; billable weight is the higher of actual and volumetric weight. The engine selects the B2B or B2C route card and adds its COD surcharge only for COD orders. The same calculation powers `/api/orders/preview` and order creation, so the customer sees the exact stored charge before confirming.

## API

- `POST /api/auth/register`, `POST /api/auth/login`
- `POST /api/orders/preview`, `POST /api/orders`, `GET /api/orders`, `GET /api/orders/{id}`
- `POST /api/orders/{id}/assign?agent_id=...`, `POST /api/orders/{id}/auto-assign`, `POST /api/orders/{id}/status`, `POST /api/orders/{id}/reschedule`
- `PATCH /api/agents/me/presence`
- `GET/POST /api/admin/zones`, `GET/POST /api/admin/rates`, `GET /api/admin/agents`

Set `DATABASE_URL`, `JWT_SECRET`, `ALLOWED_ORIGINS`, SMTP settings, and optional Twilio settings in `.env`. Every status notification is persisted as a tracking event. When configured, the adapter sends email through SMTP and SMS through Twilio; without credentials it logs the delivery update for local development.

## System design

SQLite stores users, zones, rate cards, orders, and tracking events. Orders retain the resolved zones, dimensions, weights, payment mode, and final charge, making historical billing auditable even when an admin later changes a rate card. Tracking events are append-only and include status, timestamp, actor, and note; the order status is a current-state projection used for fast filtering. Zone detection is deterministic against the pincode lists configured by operations, with a geocoding provider as the production extension for arbitrary addresses. Assignment filters agents by role and availability, then chooses the closest current location to the pickup-zone centroid. Completing or failing a delivery triggers a notification event. A failed order can be rescheduled only by its customer; that action clears the previous agent, records the new date, and returns the order to the assignment pool. For a demo deployment, SQLite avoids a managed database; for durable production data, attach persistent storage or migrate to a managed database, move notifications to a background queue, and supply SMTP/SMS credentials through a secret manager.
