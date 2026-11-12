"""Capacity policy: only accepted registrations reserve seats."""
import base64
import io
import PIL.Image
from PIL import ImageOps


def process_photo(photo_data: str | None) -> str | None:
    """Valide, recadre au carré et optimise la photo du participant en JPEG."""
    if not photo_data or not isinstance(photo_data, str):
        return None
    b64_str = photo_data
    if ',' in b64_str:
        b64_str = b64_str.split(',', 1)[1]
    try:
        raw = base64.b64decode(b64_str)
        if len(raw) > 10 * 1024 * 1024:  # Max 10 Mo
            return None
        img = PIL.Image.open(io.BytesIO(raw))
        try:
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass
        if img.mode not in ('RGB', 'L'):
            img = img.convert('RGB')
        w, h = img.size
        min_dim = min(w, h)
        left = (w - min_dim) // 2
        top = (h - min_dim) // 2
        img = img.crop((left, top, left + min_dim, top + min_dim))
        if min_dim > 400:
            img = img.resize((400, 400), PIL.Image.Resampling.LANCZOS)
        out = io.BytesIO()
        img.save(out, format='JPEG', quality=85, optimize=True)
        return 'data:image/jpeg;base64,' + base64.b64encode(out.getvalue()).decode('ascii')
    except Exception:
        return None


def decide_registration_status(requested: str, capacity: int | None,
                               accepted_count: int, already_accepted: bool = False) -> str:
    if requested == 'accepted' and capacity is not None and not already_accepted and accepted_count >= capacity:
        return 'waitlist'
    return requested
