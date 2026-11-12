"""Contenu commun des QR de badge : BADGE:<UUID v4>. Les anciens formats IA1 et CONF restent acceptés en lecture."""
import re
import uuid

PREFIX = "BADGE"
_RE = re.compile(r"^IA1\.(\d{1,9})\.([A-Za-z0-9_-]{16,128})$")
_BADGE_RE = re.compile(r"^BADGE:([0-9a-fA-F-]{36})$", re.IGNORECASE)
_UUID_SHAPE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def build_payload(event_id: int, badge_reference: str) -> str:
    """Encode only the UUID; event_id is retained for call-site compatibility."""
    if not is_uuid4(badge_reference):
        raise ValueError("Un QR de badge doit contenir une référence UUID v4.")
    return f"{PREFIX}:{badge_reference}"


def new_badge_reference() -> str:
    return str(uuid.uuid4())


def is_uuid4(value: str) -> bool:
    try:
        parsed = uuid.UUID(value)
        return parsed.version == 4 and str(parsed) == value.lower()
    except (ValueError, AttributeError, TypeError):
        return False


def looks_like_uuid(value: str) -> bool:
    return bool(_UUID_SHAPE.fullmatch(value or ""))


def parse_payload(value: str) -> tuple[int | None, str]:
    """Retourne (id_evenement ou None, jeton)."""
    v = (value or "").strip()
    badge = _BADGE_RE.fullmatch(v)
    if badge and is_uuid4(badge.group(1)):
        return None, badge.group(1).lower()
    m = _RE.match(v)
    return (int(m.group(1)), m.group(2)) if m else (None, v)


def qr_filename(event_id: int, reference: str) -> str:
    """Nom de fichier unique par événement : deux dossiers designer ne peuvent plus se mélanger."""
    return f"QR_CODES/E{int(event_id):03d}_{reference}.png"
