FROM python:3.11-slim

# Ustaw zmienną środowiskową żeby nie buforować pyc
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Ustaw katalog roboczy
WORKDIR /app

# Kopiuj pliki zależności i zainstaluj
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopiuj resztę aplikacji
COPY . .

# Otwórz port
EXPOSE 5000

# Domyślne polecenie uruchamiające aplikację
CMD ["python", "app.py"]
