import os
import pytest

from doc_generator import generuj_liste_obecnosci, generuj_raport_miesieczny

class Dummy:
    pass


def test_missing_liste_template():
    if os.path.exists('szablon.docx'):
        os.remove('szablon.docx')
    with pytest.raises(RuntimeError) as exc:
        generuj_liste_obecnosci('2024-01-01', '1', [], 'T', None)
    assert 'szablon.docx' in str(exc.value)


def test_missing_report_template(tmp_path):
    path = tmp_path / 'missing.docx'
    dummy = Dummy()
    dummy.imie = 'A'
    dummy.nazwisko = 'B'
    dummy.numer_umowy = '1'
    dummy.podpis_filename = 'sig.png'
    with pytest.raises(RuntimeError) as exc:
        generuj_raport_miesieczny(dummy, [], str(path), 'static', 1, 2024)
    assert str(path) in str(exc.value)
