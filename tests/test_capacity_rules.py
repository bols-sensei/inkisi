import pytest
from app.services.conference import decide_registration_status
from app.models import ConferenceRegistration, EventProgramItem, TeamTask, EntryRecord


def test_pending_does_not_reserve_capacity():
    assert decide_registration_status('pending', True, 10, 10) == 'pending'


def test_acceptance_reserves_place_when_available():
    assert decide_registration_status('accepted', True, 10, 9) == 'accepted'


def test_full_capacity_sends_acceptance_to_waitlist():
    assert decide_registration_status('accepted', True, 10, 10) == 'waitlist'


def test_unlimited_capacity_accepts_verified_registration():
    assert decide_registration_status('accepted', True, None, 1000) == 'accepted'


def test_unverified_registration_cannot_be_accepted_or_waitlisted():
    with pytest.raises(ValueError): decide_registration_status('accepted', False, 10, 0)
    with pytest.raises(ValueError): decide_registration_status('waitlist', False, 10, 10)


def test_existing_acceptance_does_not_consume_a_second_place_on_update():
    assert decide_registration_status('accepted', True, 10, 10, already_accepted=True) == 'accepted'


def test_conference_registration_has_individual_secure_token_fields():
    columns = ConferenceRegistration.__table__.columns
    assert {'public_token', 'verification_token_hash', 'email_verified'} <= set(columns.keys())


def test_program_and_task_models_are_event_scoped():
    assert EventProgramItem.__table__.c.event_id.foreign_keys
    assert TeamTask.__table__.c.event_id.foreign_keys


def test_offline_idempotency_key_is_unique():
    constraints = EntryRecord.__table__.constraints
    assert any(getattr(c, 'name', None) == 'uq_entry_idempotency_key' for c in constraints)
