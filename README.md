# Как подгрузить переменные окружения из файла .env

Для загрузки переменных окружения из файла `.env` в Python-проекте рекомендуется использовать пакет [python-dotenv](https://pypi.org/project/python-dotenv/).

## Шаги:

1. **Установите пакет python-dotenv:**

   ```
   pip install python-dotenv
   ```

2. **Создайте файл `.env` в корне вашего проекта:**

   ```
   S3_BUCKET=your-bucket-name
   S3_REGION=us-east-1
   S3_ACCESS_KEY_ID=your-access-key
   S3_SECRET_ACCESS_KEY=your-secret-key
   S3_ENDPOINT_URL=https://your-s3-endpoint
   ```

3. **Добавьте загрузку переменных в ваш код (например, в `main.py` или перед использованием переменных окружения):**

   ```python
   from dotenv import load_dotenv
   load_dotenv()  # автоматически загрузит переменные из .env в os.environ
   import os

   # Теперь переменные доступны через os.environ или os.getenv
   bucket = os.getenv("S3_BUCKET")
   ```

4. **Проверьте, что файл `.env` добавлен в `.gitignore`, чтобы не публиковать секретные данные:**

   ```
   .env
   ```

## Примечания

- Если вы используете uvicorn/gunicorn, убедитесь, что переменные окружения загружаются до старта приложения.
- Для локальной разработки можно использовать [direnv](https://direnv.net/) или аналогичные инструменты для автоматической подгрузки переменных окружения.

---
