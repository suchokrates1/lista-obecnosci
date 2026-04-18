FROM python:3.11-slim

# Ustaw zmienną środowiskową żeby nie buforować pyc
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apt-get update \
	&& apt-get install -y --no-install-recommends fonts-dejavu-core \
	&& rm -rf /var/lib/apt/lists/*

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
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", "app:create_app()"]
