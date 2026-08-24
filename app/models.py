from datetime import datetime
from enum import Enum
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base


class Role(str, Enum):
    customer = "customer"
    agent = "agent"
    admin = "admin"


class OrderStatus(str, Enum):
    pending = "Pending"
    assigned = "Assigned"
    picked_up = "Picked Up"
    in_transit = "In Transit"
    out_for_delivery = "Out for Delivery"
    delivered = "Delivered"
    failed = "Failed"
    rescheduled = "Rescheduled"


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30), default=Role.customer.value)
    phone: Mapped[str] = mapped_column(String(40), default="")
    available: Mapped[bool] = mapped_column(Boolean, default=True)
    latitude: Mapped[float] = mapped_column(Float, default=28.6139)
    longitude: Mapped[float] = mapped_column(Float, default=77.2090)


class Zone(Base):
    __tablename__ = "zones"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    pincodes: Mapped[str] = mapped_column(Text, default="")
    latitude: Mapped[float] = mapped_column(Float, default=0)
    longitude: Mapped[float] = mapped_column(Float, default=0)


class RateCard(Base):
    __tablename__ = "rate_cards"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_type: Mapped[str] = mapped_column(String(10))
    from_zone_id: Mapped[int] = mapped_column(ForeignKey("zones.id"))
    to_zone_id: Mapped[int] = mapped_column(ForeignKey("zones.id"))
    base_rate: Mapped[float] = mapped_column(Float)
    per_kg_rate: Mapped[float] = mapped_column(Float)
    cod_surcharge: Mapped[float] = mapped_column(Float, default=0)


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    agent_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    pickup_address: Mapped[str] = mapped_column(Text)
    drop_address: Mapped[str] = mapped_column(Text)
    pickup_pincode: Mapped[str] = mapped_column(String(12))
    drop_pincode: Mapped[str] = mapped_column(String(12))
    length: Mapped[float] = mapped_column(Float)
    breadth: Mapped[float] = mapped_column(Float)
    height: Mapped[float] = mapped_column(Float)
    actual_weight: Mapped[float] = mapped_column(Float)
    volumetric_weight: Mapped[float] = mapped_column(Float)
    billable_weight: Mapped[float] = mapped_column(Float)
    order_type: Mapped[str] = mapped_column(String(10))
    payment_type: Mapped[str] = mapped_column(String(10))
    charge: Mapped[float] = mapped_column(Float)
    pickup_zone_id: Mapped[int] = mapped_column(ForeignKey("zones.id"))
    drop_zone_id: Mapped[int] = mapped_column(ForeignKey("zones.id"))
    status: Mapped[str] = mapped_column(String(30), default=OrderStatus.pending.value)
    delivery_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TrackingEvent(Base):
    __tablename__ = "tracking_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    status: Mapped[str] = mapped_column(String(30))
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
