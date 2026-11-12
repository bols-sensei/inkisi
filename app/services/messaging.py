import os
import base64
from datetime import datetime, timezone
from app.database import SessionLocal
from app.models import Notification, PushSubscription, PushOutbox


def get_vapid_public_key() -> str | None:
    """Return the canonical uncompressed P-256 public key for PushManager."""
    public_value = (os.getenv('VAPID_PUBLIC_KEY') or '').strip()
    private_value = (os.getenv('VAPID_PRIVATE_KEY') or '').strip()
    if not public_value or not private_value:
        return None
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from py_vapid import Vapid

        if public_value.startswith('-----BEGIN'):
            public_key = serialization.load_pem_public_key(public_value.encode())
        else:
            encoded = public_value.encode()
            decoded = base64.b64decode(encoded + b'=' * ((4 - len(encoded) % 4) % 4), altchars=b'-_', validate=True)
            if len(decoded) == 65 and decoded[0] == 4:
                public_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), decoded)
            else:
                public_key = serialization.load_der_public_key(decoded)
        if not isinstance(public_key, ec.EllipticCurvePublicKey) or public_key.curve.name != 'secp256r1':
            return None
        point = public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        derived = Vapid.from_string(private_value).public_key.public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        if point != derived:
            return None
        return base64.urlsafe_b64encode(point).decode('ascii').rstrip('=')
    except Exception:
        return None


def notify_user(user_id: int, organization_id: int, title: str, body: str, event_id: int | None = None, category: str = 'general'):
    db = SessionLocal()
    try:
        notification = Notification(user_id=user_id, organization_id=organization_id, event_id=event_id,
                                    title=title, body=body, category=category)
        db.add(notification)
        db.flush()
        for subscription in db.query(PushSubscription).filter_by(user_id=user_id).all():
            db.add(PushOutbox(notification_id=notification.id, subscription_id=subscription.id))
        db.commit()
    finally: db.close()
