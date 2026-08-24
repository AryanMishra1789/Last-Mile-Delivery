from pathlib import Path
from fastapi import Depends, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from .auth import current_user, hash_password, require_roles, token_for, verify_password
from .database import Base, SessionLocal, engine, get_db, settings
from .models import Order, OrderStatus, RateCard, Role, TrackingEvent, User, Zone
from .schemas import AgentPresence, Login, OrderCreate, RateCreate, Reschedule, StatusUpdate, UserCreate, ZoneCreate
from .services import add_event, calculate_charge, nearest_agent, notify

app = FastAPI(title="Last-Mile Delivery Tracker", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=[origin.strip() for origin in settings.allowed_origins.split(",") if origin.strip()], allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


def seed():
    Base.metadata.create_all(engine)
    db = SessionLocal()
    if db.query(User).count():
        db.close(); return
    admin = User(name="Operations Admin", email="admin@example.com", password_hash=hash_password("admin123"), role=Role.admin.value)
    customer = User(name="Demo Customer", email="customer@example.com", password_hash=hash_password("customer123"), role=Role.customer.value)
    agent = User(name="Aarav Agent", email="agent@example.com", password_hash=hash_password("agent123"), role=Role.agent.value, latitude=28.62, longitude=77.21)
    db.add_all([admin, customer, agent]); db.flush()
    north = Zone(name="North Hub", pincodes="110001,110002,110003")
    south = Zone(name="South Hub", pincodes="560001,560002,560003")
    db.add_all([north, south]); db.flush()
    for kind in ("B2B", "B2C"):
        db.add_all([RateCard(order_type=kind, from_zone_id=north.id, to_zone_id=north.id, base_rate=50 if kind == "B2C" else 70, per_kg_rate=18 if kind == "B2C" else 14, cod_surcharge=30 if kind == "B2C" else 45), RateCard(order_type=kind, from_zone_id=north.id, to_zone_id=south.id, base_rate=120 if kind == "B2C" else 150, per_kg_rate=28 if kind == "B2C" else 24, cod_surcharge=35 if kind == "B2C" else 55)])
    db.commit(); db.close()


@app.on_event("startup")
def startup():
    seed()


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    db.query(User).count()
    return {"status": "ok", "database": "sqlite"}


@app.post("/api/auth/register")
def register(data: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter_by(email=data.email).first(): raise HTTPException(409, "Email already registered")
    user = User(name=data.name, email=data.email, password_hash=hash_password(data.password), phone=data.phone, role=Role.customer.value)
    db.add(user); db.commit(); db.refresh(user)
    return {"access_token": token_for(user), "user": {"id": user.id, "name": user.name, "role": user.role}}


@app.post("/api/auth/login")
def login(data: Login, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=data.email).first()
    if not user or not verify_password(data.password, user.password_hash): raise HTTPException(401, "Invalid credentials")
    return {"access_token": token_for(user), "user": {"id": user.id, "name": user.name, "role": user.role}}


def order_view(order, db):
    agent = db.get(User, order.agent_id) if order.agent_id else None
    return {"id": order.id, "status": order.status, "charge": order.charge, "order_type": order.order_type, "payment_type": order.payment_type, "pickup_address": order.pickup_address, "drop_address": order.drop_address, "billable_weight": order.billable_weight, "agent": agent.name if agent else None, "created_at": order.created_at, "delivery_date": order.delivery_date, "tracking": [{"status": e.status, "note": e.note, "created_at": e.created_at} for e in db.query(TrackingEvent).filter_by(order_id=order.id).order_by(TrackingEvent.created_at).all()]}


@app.post("/api/orders/preview")
def preview(data: OrderCreate, db: Session = Depends(get_db), _: User = Depends(current_user)):
    try: pickup, drop, volumetric, billable, charge = calculate_charge(db, data)
    except ValueError as error: raise HTTPException(422, str(error))
    return {"pickup_zone": pickup.name, "drop_zone": drop.name, "volumetric_weight": round(volumetric, 3), "billable_weight": round(billable, 3), "charge": charge}


@app.post("/api/orders")
def create_order(data: OrderCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    try: pickup, drop, volumetric, billable, charge = calculate_charge(db, data)
    except ValueError as error: raise HTTPException(422, str(error))
    customer_id = data.customer_id if user.role == Role.admin.value and data.customer_id else user.id
    if not db.get(User, customer_id): raise HTTPException(404, "Customer not found")
    order = Order(customer_id=customer_id, pickup_address=data.pickup_address, drop_address=data.drop_address, pickup_pincode=data.pickup_pincode, drop_pincode=data.drop_pincode, length=data.length, breadth=data.breadth, height=data.height, actual_weight=data.actual_weight, volumetric_weight=volumetric, billable_weight=billable, order_type=data.order_type, payment_type=data.payment_type, charge=charge, pickup_zone_id=pickup.id, drop_zone_id=drop.id)
    db.add(order); db.flush(); add_event(db, order, OrderStatus.pending.value, user.id, "Order created"); db.commit(); db.refresh(order)
    notify(db.get(User, customer_id), order, OrderStatus.pending.value)
    return order_view(order, db)


@app.get("/api/orders")
def list_orders(status: str | None = None, zone_id: int | None = None, agent_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)):
    query = db.query(Order)
    if user.role == Role.customer: query = query.filter_by(customer_id=user.id)
    if user.role == Role.agent: query = query.filter_by(agent_id=user.id)
    if status: query = query.filter_by(status=status)
    if zone_id: query = query.filter((Order.pickup_zone_id == zone_id) | (Order.drop_zone_id == zone_id))
    if agent_id: query = query.filter_by(agent_id=agent_id)
    return [order_view(order, db) for order in query.order_by(Order.created_at.desc()).all()]


@app.get("/api/orders/{order_id}")
def get_order(order_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    order = db.get(Order, order_id)
    if not order: raise HTTPException(404, "Order not found")
    if user.role == Role.customer and order.customer_id != user.id: raise HTTPException(403, "Forbidden")
    return order_view(order, db)


@app.post("/api/orders/{order_id}/auto-assign")
def auto_assign(order_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.admin))):
    order = db.get(Order, order_id); agent = nearest_agent(db, order.pickup_zone_id) if order else None
    if not order: raise HTTPException(404, "Order not found")
    if not agent: raise HTTPException(409, "No available agents")
    order.agent_id = agent.id; agent.available = False; add_event(db, order, OrderStatus.assigned.value, user.id, f"Auto-assigned to {agent.name}"); db.commit()
    return order_view(order, db)


@app.post("/api/orders/{order_id}/assign")
def assign(order_id: int, agent_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.admin))):
    order = db.get(Order, order_id)
    agent = db.get(User, agent_id)
    if not order or not agent or agent.role != Role.agent.value or not agent.available:
        raise HTTPException(422, "Order or available agent not found")
    order.agent_id = agent.id
    agent.available = False
    add_event(db, order, OrderStatus.assigned.value, user.id, f"Manually assigned to {agent.name}")
    db.commit()
    return order_view(order, db)


@app.post("/api/orders/{order_id}/status")
def update_status(order_id: int, data: StatusUpdate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    order = db.get(Order, order_id)
    if not order: raise HTTPException(404, "Order not found")
    allowed = {item.value for item in OrderStatus}
    if data.status not in allowed: raise HTTPException(422, "Invalid status")
    if user.role not in (Role.admin.value, Role.agent.value): raise HTTPException(403, "Only an admin or assigned agent can update status")
    if user.role == Role.agent.value and order.agent_id != user.id: raise HTTPException(403, "Order is assigned to another agent")
    add_event(db, order, data.status, user.id, data.note)
    if data.status in (OrderStatus.delivered.value, OrderStatus.failed.value) and order.agent_id:
        assigned_agent = db.get(User, order.agent_id)
        if assigned_agent: assigned_agent.available = True
    db.commit(); notify(db.get(User, order.customer_id), order, data.status)
    return order_view(order, db)


@app.post("/api/orders/{order_id}/reschedule")
def reschedule(order_id: int, data: Reschedule, db: Session = Depends(get_db), user: User = Depends(current_user)):
    order = db.get(Order, order_id)
    if not order or order.customer_id != user.id or order.status != OrderStatus.failed.value: raise HTTPException(422, "Only your failed orders can be rescheduled")
    order.delivery_date = data.delivery_date
    order.agent_id = None
    add_event(db, order, OrderStatus.rescheduled.value, user.id, "Customer requested a new delivery date")
    agent = nearest_agent(db, order.pickup_zone_id)
    if agent:
        order.agent_id = agent.id
        agent.available = False
        add_event(db, order, OrderStatus.assigned.value, user.id, f"Reassigned to {agent.name} for rescheduled attempt")
    db.commit()
    notify(user, order, OrderStatus.rescheduled.value)
    return order_view(order, db)


@app.post("/api/admin/zones")
def create_zone(data: ZoneCreate, db: Session = Depends(get_db), _: User = Depends(require_roles(Role.admin))):
    zone = Zone(name=data.name, pincodes=data.pincodes); db.add(zone); db.commit(); db.refresh(zone); return zone


@app.get("/api/admin/zones")
def list_zones(db: Session = Depends(get_db), _: User = Depends(require_roles(Role.admin))): return db.query(Zone).all()


@app.post("/api/admin/rates")
def create_rate(data: RateCreate, db: Session = Depends(get_db), _: User = Depends(require_roles(Role.admin))):
    rate = RateCard(**data.model_dump()); db.add(rate); db.commit(); db.refresh(rate); return rate


@app.get("/api/admin/agents")
def list_agents(db: Session = Depends(get_db), _: User = Depends(require_roles(Role.admin))): return db.query(User).filter_by(role=Role.agent.value).all()


@app.patch("/api/agents/me/presence")
def update_presence(data: AgentPresence, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.agent))):
    user.available = data.available
    user.latitude = data.latitude
    user.longitude = data.longitude
    db.commit()
    return {"available": user.available, "latitude": user.latitude, "longitude": user.longitude}


@app.get("/api/admin/rates")
def list_rates(db: Session = Depends(get_db), _: User = Depends(require_roles(Role.admin))):
    return db.query(RateCard).all()


@app.get("/")
def frontend(): return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/admin")
def admin_frontend(): return FileResponse(Path(__file__).parent / "static" / "admin.html")
