from app.db import db_add_attendee, db_get_attendee, db_mark_ticket_used
from app.security import create_signed_ticket_token, verify_signed_ticket_token


def test_signed_ticket_round_trip_and_one_time_use():
    attendee = db_add_attendee('signed-ticket-user@example.com', 'Signed Ticket User', 1, 'Male Stag')
    token = create_signed_ticket_token(attendee['ticket_id'])
    payload = verify_signed_ticket_token(token)

    assert payload['ticket_id'] == attendee['ticket_id']
    assert payload['ticket_id'].split('/', 1)[0].isdigit()

    assert db_get_attendee(ticket_id=attendee['ticket_id'])['used_at'] is None
    db_mark_ticket_used(attendee['ticket_id'])
    assert db_get_attendee(ticket_id=attendee['ticket_id'])['used_at'] is not None
