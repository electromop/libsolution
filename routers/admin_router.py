from fastapi import APIRouter, Request, Depends, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse

from auth import get_current_user
from repository.audit_repository import list_audit_logs
from repository.user_repository import list_users, create_user

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def ensure_admin(user):
    if not user or not user.get("admin", False):
        return False
    return True


@router.get("/admin/logs")
async def admin_logs(
    request: Request,
    user=Depends(get_current_user),
    q: str | None = Query(None),
    method: str | None = Query(None),
    email: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    if not ensure_admin(user):
        return RedirectResponse(url="/login", status_code=302)
    total, items = list_audit_logs(
        limit=page_size,
        offset=(page - 1) * page_size,
        user_email=email,
        method=method,
        path_query=q,
        only_with_action=True,
    )
    return templates.TemplateResponse(
        "pages/index_admin_logs.html",
        {
            "request": request,
            "user": user,
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "q": q or "",
            "method": method or "",
            "email": email or "",
        },
    )


@router.get("/admin/users")
async def admin_users(request: Request, user=Depends(get_current_user), page: int = 1, page_size: int = 50):
    if not ensure_admin(user):
        return RedirectResponse(url="/login", status_code=302)
    total, items = list_users(limit=page_size, offset=(page - 1) * page_size)
    return templates.TemplateResponse(
        "pages/index_admin_users.html",
        {
            "request": request,
            "user": user,
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "error": None,
            "success": None,
        },
    )


@router.post("/admin/users")
async def admin_create_user(request: Request, user=Depends(get_current_user)):
    if not ensure_admin(user):
        return RedirectResponse(url="/login", status_code=302)
    form = await request.form()
    email = (form.get("email") or "").strip()
    password = (form.get("password") or "").strip()
    if not email or not password:
        total, items = list_users(limit=50, offset=0)
        return templates.TemplateResponse(
            "pages/index_admin_users.html",
            {"request": request, "user": user, "items": items, "total": total, "page": 1, "page_size": 50, "error": "Заполните почту и пароль", "success": None},
        )
    created = create_user(email, password)
    if not created:
        total, items = list_users(limit=50, offset=0)
        return templates.TemplateResponse(
            "pages/index_admin_users.html",
            {"request": request, "user": user, "items": items, "total": total, "page": 1, "page_size": 50, "error": "Пользователь с такой почтой уже существует", "success": None},
        )
    return RedirectResponse(url="/admin/users", status_code=302)


