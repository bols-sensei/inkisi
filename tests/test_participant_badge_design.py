from io import BytesIO
from types import SimpleNamespace

from PIL import Image

from app.services.badge import generate_participant_badge_png


def test_participant_badge_png_is_high_resolution():
    registration = SimpleNamespace(
        category='participant', photo_data=None, full_name='Awa Diallo', first_name='Awa', last_name='Diallo',
        profession='Journaliste', organization_name='Presse locale', badge_reference='f5fc98bf-21a1-400b-8a88-09f8c5c3f082',
    )
    event = SimpleNamespace(id=7, name='Forum de Kinshasa', event_date='12 décembre 2026', start_date='', venue='Gombe')

    png = generate_participant_badge_png(registration, event)
    image = Image.open(BytesIO(png))

    assert image.size == (1280, 2000)
    assert image.format == 'PNG'
