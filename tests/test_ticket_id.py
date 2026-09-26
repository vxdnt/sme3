from app.db import db_add_attendee, db_get_attendee, generate_ticket_id


def test_generate_ticket_id_returns_unique_secure_value():
    seen = set()
    for _ in range(20):
        ticket_id = generate_ticket_id()
        assert '/' in ticket_id
        prefix = int(ticket_id.split('/', 1)[0])
        assert 1110 <= prefix <= 9990
        assert ticket_id not in seen
        seen.add(ticket_id)


def test_db_add_attendee_assigns_ticket_id():
    email = 'ticket-id-test-user@example.com'
    attendee = db_add_attendee(email, 'Ticket ID User', 1, 'Male Stag')
    assert attendee.get('ticket_id')
    lookup = db_get_attendee(email)
    assert lookup and lookup['ticket_id'] == attendee['ticket_id']
