from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse

# Импорт роутеров
from routers.types_router import router as types_router
from routers.items_router import router as items_router
from routers.search_router import router as search_router
from routers.auth_router import router as auth_router
from routers.comment_router import router as comment_router
from routers.dashboard_router import router as dashboard_router
from routers.journal_router import router as journal_router
from routers.quantity_router import router as quantity_router
from routers.tag_router import router as tag_router
from routers.task_router import router as task_router
from dotenv import load_dotenv

load_dotenv()  # автоматически загрузит переменные из .env в os.environ

app = FastAPI()

# CORS (если UI на другом порту)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.staticfiles import StaticFiles

app.mount("/static", StaticFiles(directory="static"), name="static")


# Подключаем все роутеры
app.include_router(auth_router)
app.include_router(comment_router)
app.include_router(dashboard_router)
app.include_router(items_router)
app.include_router(journal_router)
app.include_router(quantity_router)
app.include_router(search_router)
app.include_router(tag_router)
app.include_router(task_router)
app.include_router(types_router)

# Кастомный обработчик HTTPException для journal_router
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401:
        return RedirectResponse(url="/login")
    # Для остальных статусов вернём JSON, чтобы корректно завершить ответ
    return JSONResponse({"detail": exc.detail or "Server error"}, status_code=exc.status_code)

# Для инициализации приложения также стоит добавить:
# - Подключение к базе данных (если требуется инициализация)
# - Настройку статических файлов (если используются)
# - Настройку шаблонов Jinja2 (если используются)
# - Логирование (по необходимости)