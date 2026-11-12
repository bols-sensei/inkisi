import base64
import io
from PIL import Image

from app.models import ConferenceRegistration, MemberBadge


def _photo():
    image = Image.new('RGB', (32, 32), (35, 80, 70))
    out = io.BytesIO(); image.save(out, format='JPEG')
    return 'data:image/jpeg;base64,' + base64.b64encode(out.getvalue()).decode()


def test_member_badge_link_stays_out_of_participant_registrations(make_org, db):
    admin, _ = make_org()
    event = admin.post('/admin/api/events', json={'name': 'Forum membres'}).json()['id']
    settings = admin.put(f'/admin/api/events/{event}/member-badges', json={
        'palette': 'malachite', 'categories': ['Presse', 'Protocole'], 'enabled': True,
    })
    assert settings.status_code == 200
    token = settings.json()['token']

    page = admin.get(f'/member-badge/{token}')
    assert page.status_code == 200
    assert 'Presse' in page.text and 'Protocole' in page.text
    response = admin.post(f'/member-badge/{token}', data={
        'full_name': 'Awa Diallo', 'email': 'awa@example.com',
        'organization_name': 'Presse locale', 'category': 'Presse',
        'photo_data': _photo(),
    })
    assert response.status_code == 200
    badge = db.query(MemberBadge).filter_by(event_id=event, email='awa@example.com').one()
    assert badge.category == 'Presse'
    assert badge.photo_data.startswith('data:image/jpeg;base64,')
    assert db.query(ConferenceRegistration).filter_by(event_id=event).count() == 0
    png = admin.get(f'/api/public/member-badge/{badge.public_token}.png')
    assert png.status_code == 200
    assert png.headers['content-type'] == 'image/png'
    assert len(png.content) > 1000


def test_support_ticket_thread_isolated_between_organizations(make_org, db):
    admin, _ = make_org()
    other, _ = make_org()
    platform = __import__('tests.conftest', fromlist=['login']).login('root', 'RootPassword-123')
    opened = admin.post('/support/api/tickets', json={'subject': 'Aide badge', 'body': 'Question de configuration'})
    assert opened.status_code == 201, opened.text
    ticket_id = opened.json()['id']
    assert other.get(f'/support/api/tickets/{ticket_id}').status_code == 404
    assert platform.get(f'/support/api/tickets/{ticket_id}').json()['messages'][0]['body'] == 'Question de configuration'
    replied = platform.post(f'/support/api/tickets/{ticket_id}/messages', json={'body': 'Nous vous accompagnons.'})
    assert replied.status_code == 201, replied.text
    thread = admin.get(f'/support/api/tickets/{ticket_id}').json()
    assert [m['body'] for m in thread['messages']] == ['Question de configuration', 'Nous vous accompagnons.']


def test_member_badge_rejects_missing_or_invalid_photo(make_org):
    admin, _ = make_org()
    event = admin.post('/admin/api/events', json={'name': 'Badges photo requise'}).json()['id']
    settings = admin.put(f'/admin/api/events/{event}/member-badges', json={
        'palette': 'royal', 'categories': ['Protocole'], 'enabled': True,
    }).json()
    payload = {'full_name': 'Awa Diallo', 'email': 'photo@example.com', 'category': 'Protocole'}
    assert admin.post(f"/member-badge/{settings['token']}", data=payload).status_code == 422
    payload['photo_data'] = 'data:image/jpeg;base64,bad'
    assert admin.post(f"/member-badge/{settings['token']}", data=payload).status_code == 422
