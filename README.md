# Paw of Help Backend

Бэкенд-сервис на FastAPI для платформы помощи животным.

## Установка и запуск (PowerShell)

```powershell
cd paw_of_help
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Установка и запуск (bash / Git Bash)

```bash
cd paw_of_help
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Проверка после запуска

- Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
