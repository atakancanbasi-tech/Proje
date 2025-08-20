# Proje (Django Web Uygulaması)

Bu depo Django tabanlı bir web uygulamasıdır. Varsayılan veritabanı **SQLite** (db.sqlite3).
Gizli bilgiler repoya girmez; `.env.example` dosyasından kendi `.env` dosyanızı oluşturursunuz.

## Gereksinimler
- Python 3.11+ (önerilir)
- Git

## Kurulum

### 1) Sanal ortam ve bağımlılıklar
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

pip install -r requirements.txt
```

requirements.txt yoksa bildiriniz; oluşturacağız.

### 2) Ortam değişkenleri
```bash
# Windows (PowerShell): copy .env.example .env
# macOS/Linux: cp .env.example .env
```

.env içindeki değerleri ihtiyaca göre düzenleyin (repoya koymayın).

### 3) Veritabanı ve geliştirme sunucusu
```bash
python manage.py migrate
python manage.py runserver
```

Tarayıcı: http://127.0.0.1:8000/

## Notlar

- Veritabanı: SQLite (db.sqlite3). İleride Postgres/MySQL'e geçilebilir.
- .env repoda yoktur; .env.example şablon amaçlıdır.
- Git akışı: main ana dal; özellikler için ayrı dallar önerilir.

## Güvenlik

- Gerçek API anahtarları ve parolalar repoya asla eklenmez.
- Dağıtımda gizli anahtarlar CI/CD veya host ortam değişkenlerinde yönetilir.