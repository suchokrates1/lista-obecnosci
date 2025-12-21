# Instrukcja konfiguracji faktur KSeF

## Wprowadzenie

Aplikacja została rozszerzona o automatyczne wystawianie faktur przy wysyłaniu zestawień miesięcznych. Faktury generowane są w formacie FA(2) zgodnym z wymaganiami Krajowego Systemu e-Faktur (KSeF).

## Jak to działa?

Gdy wysyłasz zestawienie miesięczne (raport) e-mailem do koordynatora:
1. System automatycznie oblicza sumę godzin w danym miesiącu
2. Generuje fakturę w formacie XML FA(2) (dla KSeF)
3. Generuje fakturę w formacie PDF (dla koordynatora)
4. Jeśli KSeF jest włączony - wysyła fakturę XML do systemu KSeF
5. Jeśli KSeF jest wyłączony - zapisuje fakturę lokalnie w katalogu `invoices/`
6. **Dołącza PDF faktury do emaila z raportem** - koordynator dostaje i raport i fakturę
7. Zwiększa licznik faktur o 1

**Email do koordynatora zawiera:**
- Raport miesięczny (DOCX)
- Faktura (PDF)

## Konfiguracja

### 1. Migracja bazy danych

Przed pierwszym użyciem uruchom migrację bazy:

```bash
flask db upgrade
```

To doda wszystkie wymagane pola konfiguracyjne do tabeli ustawień.

### 2. Dostęp do panelu ustawień

Zaloguj się jako administrator i przejdź do **Ustawienia** → zakładka **Faktury KSeF**.

### 3. Konfiguracja KSeF

**Włącz automatyczne wystawianie faktur w KSeF** - zaznacz, aby włączyć integrację

**Środowisko KSeF:**
- `test` - środowisko testowe (zalecane na początku)
- `demo` - środowisko przedprodukcyjne
- `production` - środowisko produkcyjne (tylko po testach!)

**NIP do KSeF** - Twój numer NIP zarejestrowany w systemie KSeF

**Token autoryzacyjny KSeF** - Token z systemu KSeF do autoryzacji API

### 4. Dane wystawiającego (Twoje dane)

Uzupełnij dane swojej firmy:
- Nazwa firmy
- NIP
- Adres (ulica i numer)
- Kod pocztowy
- Miasto
- Kod kraju (PL)
- Email kontaktowy
- Telefon

### 5. Dane kontrahenta (nabywcy usługi)

Uzupełnij dane firmy, dla której świadczysz usługi:
- Nazwa firmy kontrahenta
- NIP kontrahenta
- Adres
- Kod pocztowy
- Miasto
- Kod kraju

### 6. Konfiguracja usługi i płatności

**Nazwa usługi** - podstawowa nazwa bez miesiąca i roku, np.:
```
Prowadzenie zajęć z tworzenia podcastów w ramach projektu ShareOko III
```
System automatycznie doda do tego miesiąc i rok, np.:
```
Prowadzenie zajęć z tworzenia podcastów w ramach projektu ShareOko III - grudzień 2025
```

**Stawka za godzinę (PLN)** - ile zarabiasz za jedną godzinę zajęć

**Waluta** - domyślnie PLN

**Stawka VAT (%)** - domyślnie 23%

**Termin płatności (dni)** - ile dni ma kontrahent na zapłatę (np. 14)

**Sposób płatności:**
- Przelew (1) - zalecane
- Gotówka (2)
- Karta płatnicza (6)

### 7. Numeracja faktur

**Prefiks numeru faktury** - np. `FV` lub `F`

**Aktualny licznik** - numer kolejnej faktury (np. 1 dla pierwszej faktury)

Format numeru faktury: `FV/001/12/2025`
- FV - prefiks
- 001 - numer z licznika (z zerami wiodącymi)
- 12 - miesiąc
- 2025 - rok

## Testowanie

### Krok 1: Konfiguracja testowa

1. Ustaw `KSEF_ENABLED` na `0` (wyłączone)
2. Wypełnij wszystkie wymagane dane
3. Zapisz ustawienia

### Krok 2: Wygeneruj raport testowy

1. Przejdź do panelu prowadzącego
2. Wygeneruj raport miesięczny
3. Kliknij **Wyślij e-mailem**
4. Sprawdź komunikaty - powinno być:
   - "Raport został wysłany e-mailem"
   - "Faktura wygenerowana: invoices/2025/12/faktura_FV_001_12_2025.xml"
   - "Faktura PDF została dołączona do emaila"
5. Sprawdź email - powinien zawierać:
   - Raport miesięczny (plik DOCX)
   - Faktura (plik PDF)

### Krok 3: Sprawdź wygenerowaną fakturę

Otwórz katalog `invoices/` i zweryfikuj:
- Plik XML faktury (do KSeF)
- Plik PDF faktury (dla koordynatora)
- Czy dane są poprawne
- Czy liczba godzin się zgadza
- Czy kwoty są właściwe

### Krok 4: Włącz KSeF (opcjonalnie)

Jeśli wszystko działa poprawnie:
1. Zarejestruj się w środowisku testowym KSeF: https://ksef-test.mf.gov.pl
2. Uzyskaj token autoryzacyjny
3. Ustaw `KSEF_ENABLED` na `1`
4. Ustaw `KSEF_ENVIRONMENT` na `test`
5. Wpisz swój NIP i token
6. Wygeneruj testowy raport
7. Sprawdź w systemie KSeF czy faktura została przyjęta

## Często zadawane pytania

**Q: Co się stanie jeśli nie skonfiguruję KSeF?**
A: Faktury będą generowane i zapisywane lokalnie w formacie XML, ale nie będą wysyłane do systemu.

**Q: Czy mogę ręcznie edytować licznik faktur?**
A: Tak, w panelu ustawień możesz zmienić wartość licznika.

**Q: Czy faktury są generowane automatycznie dla każdego raportu?**
A: Tak, przy każdym wysłaniu raportu miesięcznego e-mailem generowana jest faktura (XML + PDF) i PDF jest dołączany do emaila.

**Q: Co jeśli w danym miesiącu nie było żadnych zajęć?**
A: Faktura nie zostanie wygenerowana (0 godzin = brak faktury).

**Q: Czy mogę zmienić format numeru faktury?**
A: Format jest stały: PREFIX/NNN/MM/YYYY. Możesz zmienić tylko PREFIX.

**Q: Jak sprawdzić status faktury w KSeF?**
A: Po wysłaniu faktury otrzymasz numer referencyjny, który możesz sprawdzić w systemie KSeF.

**Q: Co zrobić w przypadku błędu wysyłania do KSeF?**
A: System zapisze fakturę lokalnie i wyświetli komunikat błędu. Możesz ręcznie wysłać fakturę przez panel KSeF.

## Środowiska KSeF

- **Test**: https://ksef-test.mf.gov.pl - do testów przed wdrożeniem
- **Demo**: https://ksef-demo.mf.gov.pl - środowisko demonstracyjne
- **Produkcja**: https://ksef.mf.gov.pl - rzeczywiste faktury

## Wsparcie

W razie problemów sprawdź:
1. Logi aplikacji - zawierają szczegółowe informacje o błędach
2. Plik XML faktury - czy jest poprawnie wygenerowany
3. Konfigurację w panelu ustawień - czy wszystkie pola są wypełnione

Więcej informacji o KSeF: https://www.gov.pl/web/kas/krajowy-system-e-faktur
