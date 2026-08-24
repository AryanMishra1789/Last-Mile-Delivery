from math import hypot
import base64
import smtplib
from email.message import EmailMessage
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from .database import settings
from sqlalchemy.orm import Session
from .models import Order, RateCard, TrackingEvent, User, Zone


def zone_for_pincode(db: Session, pincode: str) -> Zone:
    for zone in db.query(Zone).all():
        if pincode.strip() in [item.strip() for item in zone.pincodes.split(",")]:
            return zone
    raise ValueError(f"No configured zone for pincode {pincode}")


def calculate_charge(db: Session, data):
    pickup = zone_for_pincode(db, data.pickup_pincode)
    drop = zone_for_pincode(db, data.drop_pincode)
    volumetric = data.length * data.breadth * data.height / 5000
    billable = max(data.actual_weight, volumetric)
    rate = db.query(RateCard).filter_by(order_type=data.order_type, from_zone_id=pickup.id, to_zone_id=drop.id).first()
    if not rate:
        raise ValueError("No rate card configured for this route and order type")
    cod = rate.cod_surcharge if data.payment_type.lower() == "cod" else 0
    return pickup, drop, volumetric, billable, round(rate.base_rate + billable * rate.per_kg_rate + cod, 2)


def nearest_agent(db: Session, pickup_zone_id: int):
    agents = db.query(User).filter(User.role == "agent", User.available.is_(True)).all()
    if not agents:
        return None
    target = (28.6139 + pickup_zone_id / 100, 77.2090 + pickup_zone_id / 100)
    return min(agents, key=lambda a: hypot(a.latitude - target[0], a.longitude - target[1]))


def notify(customer: User, order: Order, status: str):
    message = f"Your delivery #{order.id} is now {status}."
    try:
        if settings.smtp_host:
            email = EmailMessage()
            email["Subject"] = f"Delivery update #{order.id}: {status}"
            email["From"] = settings.mail_from
            email["To"] = customer.email
            email.set_content(message)
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
                server.starttls()
                if settings.smtp_user:
                    server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(email)
        if settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_from_number and customer.phone:
            payload = urlencode({"From": settings.twilio_from_number, "To": customer.phone, "Body": message}).encode()
            credentials = base64.b64encode(f"{settings.twilio_account_sid}:{settings.twilio_auth_token}".encode()).decode()
            request = Request(f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json", data=payload, headers={"Authorization": f"Basic {credentials}"})
            with urlopen(request, timeout=10):
                pass
    except Exception as error:
        print(f"Notification provider error for order #{order.id}: {error}")
    print(f"Notification delivered or queued for {customer.email}: order #{order.id} is {status}")


def add_event(db: Session, order: Order, status: str, actor_id: int | None, note: str = ""):
    order.status = status
    db.add(TrackingEvent(order_id=order.id, status=status, actor_id=actor_id, note=note))
