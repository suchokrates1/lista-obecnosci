import io
from werkzeug.datastructures import FileStorage

import utils
from utils import is_valid_email


def test_is_valid_email():
    assert is_valid_email('user@example.com')
    assert not is_valid_email('invalid')
    assert not is_valid_email('a@')


def test_validate_signature_ok(monkeypatch):
    monkeypatch.setattr(utils, 'SIGNATURE_MAX_SIZE', 10)
    fs = FileStorage(io.BytesIO(b'x'), filename='sig.png', content_type='image/png')
    name, error = utils.validate_signature(fs)
    assert name == 'sig.png'
    assert error is None


def test_validate_signature_bad_extension(monkeypatch):
    monkeypatch.setattr(utils, 'SIGNATURE_MAX_SIZE', 10)
    fs = FileStorage(io.BytesIO(b'x'), filename='sig.txt', content_type='text/plain')
    name, error = utils.validate_signature(fs)
    assert name is None
    assert error


def test_validate_signature_too_big(monkeypatch):
    monkeypatch.setattr(utils, 'SIGNATURE_MAX_SIZE', 1)
    fs = FileStorage(io.BytesIO(b'ab'), filename='sig.png', content_type='image/png')
    name, error = utils.validate_signature(fs)
    assert name is None
    assert error
