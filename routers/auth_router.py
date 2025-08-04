from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from repository.user_repository import create_user, authenticate_user
from auth import create_access_token

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/register")
async def register_page(request: Request):
    return templates.TemplateResponse("pages/index_register.html", {"request": request, "error": None, "success": None})

@router.post("/register")
async def register(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    password2: str = Form(...)
):
    if password != password2:
        return templates.TemplateResponse("pages/index_register.html", {"request": request, "error": "Пароли не совпадают", "success": None})
    user = create_user(email, password)
    if not user:
        return templates.TemplateResponse("pages/index_register.html", {"request": request, "error": "Пользователь с такой почтой уже существует", "success": None})
    return templates.TemplateResponse("pages/index_register.html", {"request": request, "error": None, "success": "Регистрация успешна! Теперь вы можете войти."})

@router.get("/login")
async def login_page(request: Request):
    print(1)
    return templates.TemplateResponse("pages/index_login.html", {"request": request, "error": None})

@router.post("/login")
async def login(request: Request, email: str = Form(...), password: str = Form(...)):
    user = authenticate_user(email, password)
    if not user:
        return templates.TemplateResponse("pages/index_login.html", {"request": request, "error": "Неверная почта или пароль"})
    access_token = create_access_token(data={"sub": user["email"]})
    response = RedirectResponse(url="/journal/1", status_code=302)
    response.set_cookie("access_token", f"Bearer {access_token}", httponly=True)
    print(f"User {user['email']} logged in, access token set.")
    return response

@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("access_token")
    return response