from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=6)
    phone: str = ""
    role: str = "customer"


class Login(BaseModel):
    email: EmailStr
    password: str


class OrderCreate(BaseModel):
    pickup_address: str
    drop_address: str
    pickup_pincode: str
    drop_pincode: str
    length: float = Field(gt=0)
    breadth: float = Field(gt=0)
    height: float = Field(gt=0)
    actual_weight: float = Field(gt=0)
    order_type: str = "B2C"
    payment_type: str = "Prepaid"
    customer_id: int | None = None


class StatusUpdate(BaseModel):
    status: str
    note: str = ""


class Reschedule(BaseModel):
    delivery_date: datetime


class AgentPresence(BaseModel):
    available: bool
    latitude: float
    longitude: float


class ZoneCreate(BaseModel):
    name: str
    pincodes: str


class RateCreate(BaseModel):
    order_type: str
    from_zone_id: int
    to_zone_id: int
    base_rate: float
    per_kg_rate: float
    cod_surcharge: float = 0


class ReadModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
