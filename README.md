# KIANOSINT

Telegram OSINT-платформа. Работает только с публично доступными данными.
Совместимо с Python 3.10+.

## Установка

    git clone <repo> && cd kianosint
    python -m venv .venv
    # Linux: source .venv/bin/activate
    # Windows: .venv\\Scripts\\activate
    pip install -r requirements.txt
    cp .env.example .env
    python -m bot

## Docker

    docker build -t kianosint .
    docker run --env-file .env kianosint

## Render

См. render.yaml. Создать worker + Postgres, прописать секреты.

## Добавление нового источника

1. Создать sources/mysite.py
2. Унаследоваться от BaseSource
3. Реализовать async def search_username
4. Добавить имя модуля в MODULES в sources/registry.py

## Философия

FACT / SIGNAL / POSSIBLE / UNKNOWN. Мы никогда не пишем "мы нашли человека".