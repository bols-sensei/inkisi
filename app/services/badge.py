"""Génération de badges participants graphiques haute résolution au format PNG.

Design professionnel, moderne et élégant, respectant la charte visuelle
de l'événement et le design system (palette malachite, contrastes élevés).
Prêt pour affichage écran et impression directe.
"""
import io
import os
import base64
import math
import json
import qrcode
from app.services.qr import build_payload
from PIL import Image, ImageDraw, ImageFont, ImageOps
from app.models import ConferenceRegistration, Event, MemberBadge


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Charge une police TrueType système (Windows/Linux/macOS) avec repli gracieux."""
    windir = os.environ.get('WINDIR', 'C:\\Windows')
    candidates = []
    if bold:
        candidates = [
            os.path.join(windir, 'Fonts', 'segoeuib.ttf'),
            os.path.join(windir, 'Fonts', 'arialbd.ttf'),
            os.path.join(windir, 'Fonts', 'calibrib.ttf'),
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
            '/System/Library/Fonts/Helvetica.ttc',
        ]
    else:
        candidates = [
            os.path.join(windir, 'Fonts', 'segoeui.ttf'),
            os.path.join(windir, 'Fonts', 'arial.ttf'),
            os.path.join(windir, 'Fonts', 'calibri.ttf'),
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/System/Library/Fonts/Helvetica.ttc',
        ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()


def _load_display_font(size: int, bold: bool = False):
    """Serif de remplacement local pour le Cormorant Garamond du fichier de référence."""
    windir = os.environ.get('WINDIR', 'C:\\Windows')
    candidates = ([os.path.join(windir, 'Fonts', 'georgiab.ttf'), '/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf']
                  if bold else [os.path.join(windir, 'Fonts', 'georgia.ttf'), '/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf'])
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return _load_font(size, bold)


def _draw_rounded_rectangle(draw: ImageDraw.ImageDraw, xy, radius: int, fill=None, outline=None, width=1):
    """Trace un rectangle aux coins arrondis."""
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def _draw_centered_text(draw: ImageDraw.ImageDraw, y: float, text: str, font, fill, width: int):
    """Trace un texte parfaitement centré horizontalement."""
    draw.text((width / 2, y), text, font=font, fill=fill, anchor='mm')


def _wrap_text(text: str, font, max_width: int, draw: ImageDraw.ImageDraw) -> list[str]:
    """Découpe un texte pour ne pas dépasser une largeur donnée."""
    words = text.split()
    if not words:
        return []
    lines = []
    current_line = words[0]
    for word in words[1:]:
        trial = f"{current_line} {word}"
        bbox = draw.textbbox((0, 0), trial, font=font)
        if (bbox[2] - bbox[0]) <= max_width:
            current_line = trial
        else:
            lines.append(current_line)
            current_line = word
    lines.append(current_line)
    return lines


def _generate_premium_badge_png(reg, event: Event, qr_payload: str, config: dict | None = None, member: bool = False) -> bytes:
    """Rendu commun inspiré du HTML premium ; le type de QR est fourni par chaque parcours."""
    w, h, scale = 1280, 2000, 2
    if config is None:
        try:
            config = json.loads(getattr(event, 'member_badge_config', '{}') or '{}')
        except (TypeError, ValueError):
            config = {}
    palettes = {
        'royal': '#1f1a4d', 'malachite': '#11463d', 'graphite': '#30343b',
        'burgundy': '#561225', 'midnight': '#0e2f52', 'noir': '#17171b',
    }
    def rgb(hex_color):
        value = hex_color.lstrip('#')
        return tuple(int(value[i:i+2], 16) for i in (0, 2, 4))
    base = rgb(palettes.get(config.get('palette'), palettes['royal']))
    bg_top = base
    bg_bottom = tuple(round(c * .55) for c in base)
    metal_sets = [
        ['#f7e6b8','#cda553','#8b6b2b','#ecd48f'], ['#f7d2ae','#c97f4b','#85451f','#f0b98a'],
        ['#ffffff','#c4c9d1','#767d88','#e8ebf0'], ['#fcefd0','#dbb97c','#96703a','#f4deb0'],
    ]
    metal = [rgb(c) for c in metal_sets[config.get('metal', 0) if config.get('metal', 0) in range(4) else 0]]
    photo_shape = config.get('shape', 'arche')
    show_seal = config.get('seal', True)
    logo_data = config.get('logo_data')
    cream = (246, 240, 226)
    img = Image.new('RGB', (w, h), bg_bottom)
    # Laque dégradée dans une carte à coins arrondis, comme le canvas source.
    gradient = Image.new('RGB', (w, h))
    gd = ImageDraw.Draw(gradient)
    for y in range(h):
        t = y / (h - 1)
        gd.line((0, y, w, y), fill=tuple(round(bg_top[i] * (1-t) + bg_bottom[i] * t) for i in range(3)))
    card_mask = Image.new('L', (w, h), 0)
    ImageDraw.Draw(card_mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=88, fill=255)
    img.paste(gradient, (0, 0), card_mask)
    draw = ImageDraw.Draw(img, 'RGBA')

    # Motif guilloché central et éclat satiné du fichier HTML.
    cx, cy = w // 2, 740
    for i in range(28):
        radius, frequency = 140 + i * 26, 18 + (i % 5) * 2
        points = []
        for angle in range(0, 361, 2):
            theta = math.radians(angle)
            r = radius + 12 * math.sin(frequency * theta + i * .4)
            points.append((cx + r * math.cos(theta), cy + r * math.sin(theta)))
        draw.line(points, fill=(*metal[1], 48), width=2)
    sheen = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sheen)
    for y, alpha in [(0, 0), (580, 20), (900, 0), (1600, 12), (h, 0)]:
        sd.line((0, y, w, y), fill=(255, 255, 255, alpha), width=5)
    img = Image.alpha_composite(img.convert('RGBA'), sheen).convert('RGB')
    draw = ImageDraw.Draw(img, 'RGBA')

    # Double frame with the same four-stop metallic gradient.
    metal_img = Image.new('RGB', (w, h))
    md = ImageDraw.Draw(metal_img)
    for y in range(h):
        t = y / h * 3; idx = min(2, int(t)); frac = t - idx
        color = tuple(round(metal[idx][c] * (1-frac) + metal[idx+1][c] * frac) for c in range(3))
        md.line((0, y, w, y), fill=color)
    frame = Image.new('L', (w, h), 0); fd = ImageDraw.Draw(frame)
    fd.rounded_rectangle((20, 20, w-20, h-20), radius=72, fill=255)
    fd.rounded_rectangle((30, 30, w-30, h-30), radius=62, fill=0)
    img.paste(metal_img, (0, 0), frame)
    draw = ImageDraw.Draw(img, 'RGBA')
    draw.rounded_rectangle((48, 48, w-48, h-48), radius=52, outline=(*metal[1], 110), width=2)

    def fit(text, size, bold, max_width, serif=False):
        loader = _load_display_font if serif else _load_font
        font = loader(size, bold)
        while size > 16 and draw.textbbox((0, 0), text, font=font)[2] > max_width:
            size -= 2; font = loader(size, bold)
        return font

    event_name = (event.name or 'Événement').strip()
    # Tiny repeated security text on the top and bottom edges.
    micro = f"{event_name}  •  BADGE OFFICIEL  •  "
    micro_font = _load_font(12, False)
    micro_text = (micro * 5)[:180]
    draw.text((90, 24), micro_text, font=micro_font, fill=(*metal[1], 150))
    draw.text((90, h-34), micro_text, font=micro_font, fill=(*metal[1], 150))

    # Logo remplace la marque typographique comme dans le modèle fourni.
    logo_loaded = False
    if logo_data:
        try:
            logo = Image.open(io.BytesIO(base64.b64decode(logo_data.split(',', 1)[-1]))).convert('RGBA')
            logo.thumbnail((520, 112), Image.Resampling.LANCZOS)
            img.paste(logo, ((w-logo.width)//2, 152), logo)
            logo_loaded = True
        except Exception:
            pass
    if not logo_loaded:
        event_font = fit(event_name, 62, True, 800, serif=True)
        draw.text((w//2, 218), event_name, font=event_font, fill=metal[0], anchor='mm', stroke_width=1, stroke_fill=metal[2])
    subheading = 'BADGE MEMBRE · IDENTIFICATION PAR CATÉGORIE' if member else 'BADGE OFFICIEL · ACCÈS NOMINATIF'
    draw.text((w//2, 280), subheading, font=_load_font(20, True), fill=(*cream, 220), anchor='mm')

    # The portrait sits in the original arched frame.
    ax, ay, aw, ah = 320, 340, 640, 800
    def photo_mask(x, y, width, height):
        m = Image.new('L', (w, h), 0); d = ImageDraw.Draw(m)
        if photo_shape == 'cercle':
            offset=(height-width)//2
            d.ellipse((x, y+offset, x+width, y+offset+width), fill=255)
        elif photo_shape == 'carre':
            d.rounded_rectangle((x, y+60, x+width, y+height-60), radius=88, fill=255)
        else:
            d.ellipse((x, y, x+width, y+width), fill=255)
            d.rectangle((x, y+width//2, x+width, y+height-56), fill=255)
            d.rounded_rectangle((x, y+height-112, x+width, y+height), radius=56, fill=255)
        return m
    frame_mask = photo_mask(ax-scale*9, ay-scale*9, aw+scale*18, ah+scale*18)
    inner_mask = photo_mask(ax, ay, aw, ah)
    img.paste(metal_img, (0, 0), frame_mask)
    inner_bg = Image.new('RGB', (w, h), bg_bottom)
    img.paste(inner_bg, (0, 0), inner_mask)
    photo_loaded = False
    photo_data = getattr(reg, 'photo_data', None)
    if photo_data and len(photo_data) > 30:
        try:
            raw = photo_data.split(',', 1)[-1]
            photo = ImageOps.exif_transpose(Image.open(io.BytesIO(base64.b64decode(raw)))).convert('RGB')
            photo = ImageOps.fit(photo, (aw, ah), method=Image.Resampling.LANCZOS, centering=(.5, .35))
            img.paste(photo, (ax, ay), inner_mask.crop((ax, ay, ax+aw, ay+ah)))
            photo_loaded = True
        except Exception:
            pass
    if not photo_loaded:
        silhouette = Image.new('RGBA', (w, h), (0, 0, 0, 0)); silhouette_draw = ImageDraw.Draw(silhouette)
        silhouette_draw.ellipse((cx-92, 590, cx+92, 774), fill=(*metal[1], 110))
        silhouette_draw.ellipse((cx-235, 850, cx+235, 1260), fill=(*metal[1], 96))
        composed = Image.alpha_composite(img.convert('RGBA'), silhouette).convert('RGB')
        img = Image.composite(composed, img, inner_mask)
    draw = ImageDraw.Draw(img, 'RGBA')
    draw.arc((ax+26, ay+30, ax+aw-26, ay+aw-20), 180, 360, fill=(*metal[0], 55), width=3)
    if show_seal:
        # Holographic seal from the source design.
        sx, sy, sr = 1030, 410, 76
        holo = Image.new('RGBA', (w, h), (0,0,0,0)); hd = ImageDraw.Draw(holo)
        holo_colors = [(255,122,217), (122,215,255), (166,255,184), (255,243,160), (255,154,208), (154,168,255)]
        for i, col in enumerate(holo_colors):
            hd.pieslice((sx-sr, sy-sr, sx+sr, sy+sr), i*60, (i+1)*60, fill=(*col, 225))
        hd.ellipse((sx-sr, sy-sr, sx+sr, sy+sr), outline=(*metal[1], 255), width=6)
        gloss = Image.new('RGBA', (w,h), (0,0,0,0)); ImageDraw.Draw(gloss).ellipse((sx-sr//2, sy-sr, sx+sr//2, sy+sr), fill=(255,255,255,60))
        holo = Image.alpha_composite(holo, gloss)
        img = Image.alpha_composite(img.convert('RGBA'), holo).convert('RGB')
        draw = ImageDraw.Draw(img, 'RGBA')
        brand_initial = (event_name[:1] or '•').upper()
        draw.text((sx, sy+2), brand_initial, font=_load_display_font(48, True), fill=(*bg_bottom, 235), anchor='mm')

    full_name = (reg.full_name or f"{getattr(reg, 'first_name', '')} {getattr(reg, 'last_name', '')}").strip() or 'Participant'
    name_font = fit(full_name, 66, True, 1040, serif=True)
    draw.text((w//2, 1300), full_name, font=name_font, fill=cream, anchor='mm')
    if getattr(reg, 'profession', ''):
        role = reg.profession.strip()
        draw.text((w//2, 1380), role, font=fit(role, 38, False, 1000), fill=(cream[0], cream[1], cream[2], 225), anchor='mm')
    if reg.organization_name:
        organization = reg.organization_name[:42]
        draw.text((w//2, 1424), organization, font=fit(organization, 26, False, 920), fill=(*cream, 210), anchor='mm')
    category = (reg.category or 'participant').strip().upper()
    cat_font = fit(category, 28, True, 720)
    cat_w = min(760, draw.textbbox((0,0), category, font=cat_font)[2] + 104)
    chip = Image.new('RGBA', (w,h), (0,0,0,0)); cd=ImageDraw.Draw(chip)
    cd.rounded_rectangle((w//2-cat_w//2, 1470, w//2+cat_w//2, 1546), radius=38, fill=(*metal[1], 245))
    img=Image.alpha_composite(img.convert('RGBA'),chip).convert('RGB');draw=ImageDraw.Draw(img)
    draw.text((w//2,1508),category,font=cat_font,fill=bg_bottom,anchor='mm')

    # Diamond divider and event metadata, with a high-contrast secure QR.
    draw=ImageDraw.Draw(img,'RGBA'); dy=1600
    draw.line((120,dy,w//2-28,dy),fill=(*metal[1],180),width=2);draw.line((w//2+28,dy,w-120,dy),fill=(*metal[1],180),width=2)
    draw.polygon([(w//2,dy-16),(w//2+16,dy),(w//2,dy+16),(w//2-16,dy)],fill=metal[1])
    details=[('ÉVÉNEMENT',event.name or ''),('DATE',event.event_date or getattr(event,'start_date','') or ''),('LIEU',event.venue or '')]
    for i,(label,value) in enumerate(details):
        y=1660+i*88
        draw.text((120,y),label,font=_load_font(20,True),fill=(*metal[0],210))
        draw.text((120,y+44),value[:42],font=fit(value[:42],30,False,560),fill=cream)
    qr= qrcode.QRCode(box_size=6,border=2,error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(qr_payload);qr.make(fit=True)
    qr_img=qr.make_image(fill_color=bg_top,back_color='#f8f2e4').convert('RGB')
    target=224;qr_img=qr_img.resize((target,target),Image.Resampling.NEAREST)
    qr_base=Image.new('RGBA',(target+48,target+48),(248,242,228,255))
    img.paste(qr_base,(w-392,1620));img.paste(qr_img,(w-380,1632))
    draw=ImageDraw.Draw(img,'RGBA')
    draw.rounded_rectangle((w-392,1620,w-144,1868),radius=22,outline=(*metal[1],255),width=4)
    draw.text((w-268,1900),reg.badge_reference[:18],font=_load_font(15,True),fill=(*metal[0],225),anchor='mm')
    out=io.BytesIO();img.save(out,format='PNG',optimize=True)
    return out.getvalue()


def generate_participant_badge_png(reg: ConferenceRegistration, event: Event) -> bytes:
    """Badge participant premium avec payload de contrôle sécurisé."""
    return _generate_premium_badge_png(reg, event, build_payload(event.id, reg.badge_reference))


def generate_member_badge_png(badge: MemberBadge, event: Event, config: dict) -> bytes:
    """Même design premium que les participants ; le QR membre reste informatif."""
    from types import SimpleNamespace
    data = SimpleNamespace(full_name=badge.full_name, category=badge.category,
                           organization_name=badge.organization_name, profession='',
                           photo_data=badge.photo_data, badge_reference=badge.badge_reference)
    return _generate_premium_badge_png(data, event, f'MEMBRE:{badge.badge_reference}', config=config, member=True)
