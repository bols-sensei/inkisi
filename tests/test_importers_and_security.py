import pytest
from app.services.importer import parse_participant_file, parse_guest_file
from app.security import hash_password, verify_password


def test_participant_csv_parser_requires_name_and_email():
    rows = b"nom_complet;email;telephone;organisation;categorie\nAlice Test;alice@example.com;+243000;Org;vip\n"
    result = parse_participant_file('participants.csv', rows)
    assert result == [{'full_name':'Alice Test','email':'alice@example.com','phone':'+243000','organization_name':'Org','category':'vip'}]


def test_participant_csv_parser_rejects_duplicate_email():
    rows = b"nom_complet,email\nAlice,alice@example.com\nBob,alice@example.com\n"
    with pytest.raises(ValueError, match='dupliqué'):
        parse_participant_file('participants.csv', rows)


def test_wedding_import_preserves_custom_invitation_type():
    rows = b"nom;type;nombre\nEquipe partenaire;partenaire officiel;3\n"
    guests, duplicates = parse_guest_file('invites.csv', rows)
    assert not duplicates
    assert guests[0]['invitation_type'] == 'partenaire officiel'


def test_password_hash_is_not_plain_text_and_verifies():
    hashed = hash_password('UnMotDePasseLong!')
    assert hashed != 'UnMotDePasseLong!'
    assert verify_password('UnMotDePasseLong!', hashed)
    assert not verify_password('incorrect', hashed)
