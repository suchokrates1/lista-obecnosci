from utils import is_valid_email


def test_is_valid_email():
    assert is_valid_email('user@example.com')
    assert not is_valid_email('invalid')
    assert not is_valid_email('a@')
