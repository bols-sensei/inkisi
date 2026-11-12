"""Durable Web Push outbox worker. Run with ``python -m app.services.push_worker``."""
import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import joinedload

from app.database import SessionLocal
from app.models import PushOutbox, PushSubscription
from app.services.messaging import get_vapid_public_key

MAX_ATTEMPTS = 8
LOCK_TIMEOUT = timedelta(minutes=5)
RETRY_BASE_SECONDS = 15
RETRY_MAX_SECONDS = 3600
OUTBOX_RETENTION = timedelta(days=30)
logger = logging.getLogger(__name__)


def _now():
    return datetime.now(timezone.utc)


def _claim_one():
    db = SessionLocal()
    now = _now()
    stale_before = now - LOCK_TIMEOUT
    try:
        job_id = db.query(PushOutbox.id).filter(
            PushOutbox.status == 'pending',
            PushOutbox.available_at <= now,
            (PushOutbox.locked_at.is_(None) | (PushOutbox.locked_at <= stale_before)),
        ).order_by(PushOutbox.available_at, PushOutbox.id).limit(1).scalar()
        if job_id is None:
            return None
        claimed = db.query(PushOutbox).filter(
            PushOutbox.id == job_id,
            PushOutbox.status == 'pending',
            PushOutbox.available_at <= now,
            (PushOutbox.locked_at.is_(None) | (PushOutbox.locked_at <= stale_before)),
        ).update({
            PushOutbox.locked_at: now,
            PushOutbox.attempts: PushOutbox.attempts + 1,
        }, synchronize_session=False)
        db.commit()
        if not claimed:
            return None
        return job_id
    finally:
        db.close()


def _finish(job_id: int, *, error_code: str | None = None):
    db = SessionLocal()
    try:
        job = db.query(PushOutbox).filter_by(id=job_id, status='pending').first()
        if not job:
            return
        now = _now()
        job.locked_at = None
        if error_code is None:
            job.status = 'sent'
            job.sent_at = now
            job.last_error = ''
        else:
            job.last_error = error_code[:40]
            if job.attempts >= MAX_ATTEMPTS:
                job.status = 'failed'
            else:
                delay = min(RETRY_BASE_SECONDS * (2 ** max(0, job.attempts - 1)), RETRY_MAX_SECONDS)
                job.available_at = now + timedelta(seconds=delay)
        db.commit()
    finally:
        db.close()


def _discard_expired_subscription(subscription_id: int):
    db = SessionLocal()
    try:
        db.query(PushOutbox).filter_by(subscription_id=subscription_id).delete(synchronize_session=False)
        db.query(PushSubscription).filter_by(id=subscription_id).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def _deliver(job_id: int):
    db = SessionLocal()
    try:
        job = db.query(PushOutbox).options(
            joinedload(PushOutbox.notification), joinedload(PushOutbox.subscription)
        ).filter_by(id=job_id, status='pending').first()
        if not job:
            return
        if not job.subscription or not job.notification:
            db.close()
            _finish(job_id, error_code='delivery_target_missing')
            return
        endpoint = job.subscription.endpoint
        keys = {'p256dh': job.subscription.p256dh, 'auth': job.subscription.auth}
        notification = job.notification
        payload = json.dumps({
            'title': notification.title,
            'body': notification.body,
            'url': f'/event/{notification.event_id}' if notification.event_id else '/',
        }, ensure_ascii=False)
        subscription_id = job.subscription_id
    finally:
        db.close()

    vapid_private = os.getenv('VAPID_PRIVATE_KEY')
    if not vapid_private or not get_vapid_public_key():
        _finish(job_id, error_code='vapid_configuration_unavailable')
        return
    try:
        from pywebpush import webpush
        webpush(
            {'endpoint': endpoint, 'keys': keys}, payload,
            vapid_private_key=vapid_private,
            vapid_claims={'sub': os.getenv('VAPID_SUBJECT', 'mailto:admin@example.invalid')},
            timeout=10,
            ttl=86400,
        )
    except Exception as exc:
        response = getattr(exc, 'response', None)
        status = getattr(response, 'status_code', None)
        if status in (404, 410):
            _discard_expired_subscription(subscription_id)
            return
        if status is not None:
            code = f'provider_http_{status}'
        elif isinstance(exc, ImportError):
            code = 'push_provider_unavailable'
        else:
            code = 'push_delivery_failed'
        _finish(job_id, error_code=code)
        return
    _finish(job_id)


def process_push_outbox_batch(limit: int = 20) -> int:
    """Deliver ready jobs; concurrent workers claim each row atomically."""
    sent = 0
    for _ in range(max(1, min(int(limit), 100))):
        job_id = _claim_one()
        if job_id is None:
            break
        _deliver(job_id)
        sent += 1
    db = SessionLocal()
    try:
        cutoff = _now() - OUTBOX_RETENTION
        db.query(PushOutbox).filter(
            PushOutbox.status.in_(('sent', 'failed')),
            PushOutbox.created_at < cutoff,
        ).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()
    return sent


async def run_worker():
    try:
        interval = max(0.25, min(float(os.getenv('PUSH_OUTBOX_POLL_SECONDS', '2')), 30.0))
    except ValueError:
        interval = 2.0
    while True:
        try:
            await asyncio.to_thread(process_push_outbox_batch)
        except Exception:
            # A transient database error must not permanently stop push delivery.
            logger.warning('Push outbox worker iteration failed; it will retry.')
        await asyncio.sleep(interval)


def main():
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
