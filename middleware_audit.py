from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from typing import Callable

from repository.audit_repository import write_audit_log
from auth import get_current_user


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Собираем базовые данные запроса
        method = request.method
        path = request.url.path
        user_id = None
        email = None

        # Пытаемся извлечь пользователя из cookie JWT (без падения при 401)
        try:
            user = get_current_user(request)
            if user:
                # user может быть dict из user_repository
                user_id = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
                email = user.get("email") if isinstance(user, dict) else getattr(user, "email", None)
        except Exception:
            pass

        ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

        response = await call_next(request)

        write_audit_log(
            method=method,
            path=path,
            user_id=user_id,
            email=email,
            status_code=response.status_code,
            ip=ip,
            user_agent=user_agent,
        )

        return response


