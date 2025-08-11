from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from auth import get_current_user, create_access_token
from repository.user_repository import (
    update_user_profile,
    update_user_password,
)

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/profile")
async def profile_page(request: Request, user=Depends(get_current_user)):
    return templates.TemplateResponse(
        "pages/index_profile.html",
        {
            "request": request,
            "user": user,
            "error": None,
            "success": None,
        },
    )


@router.post("/profile/update")
async def profile_update(
    request: Request,
    email: str = Form(None),
    username: str = Form(None),
    user=Depends(get_current_user),
):
    result = update_user_profile(user["id"], email=email, username=username)
    if isinstance(result, dict) and result.get("error") == "EMAIL_TAKEN":
        return templates.TemplateResponse(
            "pages/index_profile.html",
            {
                "request": request,
                "user": user,
                "error": "Почта уже занята",
                "success": None,
            },
        )
    if result is None:
        return templates.TemplateResponse(
            "pages/index_profile.html",
            {
                "request": request,
                "user": user,
                "error": "Пользователь не найден",
                "success": None,
            },
        )
    # Если почта изменилась — перевыдаём токен
    if email and email != user["email"]:
        access_token = create_access_token(data={"sub": result["email"]})
        response = RedirectResponse(url="/profile", status_code=302)
        response.set_cookie("access_token", f"Bearer {access_token}", httponly=True)
        return response
    return RedirectResponse(url="/profile", status_code=302)


@router.post("/profile/password")
async def profile_change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    new_password2: str = Form(...),
    user=Depends(get_current_user),
):
    if new_password != new_password2:
        return templates.TemplateResponse(
            "pages/index_profile.html",
            {
                "request": request,
                "user": user,
                "error": "Пароли не совпадают",
                "success": None,
            },
        )
    result = update_user_password(user["id"], current_password, new_password)
    if isinstance(result, dict) and result.get("error") == "INVALID_PASSWORD":
        return templates.TemplateResponse(
            "pages/index_profile.html",
            {
                "request": request,
                "user": user,
                "error": "Текущий пароль неверен",
                "success": None,
            },
        )
    return RedirectResponse(url="/profile", status_code=302)


