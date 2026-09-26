from app import state
from app.qr import is_token_valid, rotate_token


def test_multiple_qr_tokens_remain_valid():
    state.current_base_url = 'http://localhost:8000'
    state.active_tokens = {}
    state.current_token = None

    first = rotate_token('http://localhost:8000')
    second = rotate_token('http://localhost:8000')

    assert first['token'] != second['token']
    assert is_token_valid(first['token'])
    assert is_token_valid(second['token'])
    assert state.current_token == second['token']
