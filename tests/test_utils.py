import io
from werkzeug.datastructures import FileStorage
from PIL import Image

import utils
import pytest
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


def test_process_signature(monkeypatch, tmp_path):
    monkeypatch.setattr(utils, 'REMOVE_SIGNATURE_BG', False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'static').mkdir()
    img = Image.new('RGB', (1, 1), (255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    filename = utils.process_signature(buf)
    saved = tmp_path / 'static' / filename
    assert saved.exists()
    out = Image.open(saved)
    assert out.format == 'PNG'

def test_validate_signature_none():
    name, error = utils.validate_signature(None)
    assert name is None
    assert error is None


class FailingStream(io.BytesIO):
    def seek(self, *a, **k):
        raise IOError('fail')


def test_validate_signature_exception():
    fs = FileStorage(FailingStream(b'x'), filename='sig.png', content_type='image/png')
    with pytest.raises(utils.SignatureValidationError):
        utils.validate_signature(fs)
