from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.v1.auth import router as auth_router
from app.api.v1.listings import router as listings_router
from app.api.v1.users import router as users_router

app = FastAPI(title="Boomgardi Platform")

app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")

app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(users_router, prefix="/api/v1/users", tags=["users"])
app.include_router(listings_router, prefix="/api/v1/listings", tags=["listings"])


@app.get("/health")
async def health_check():
    return JSONResponse(content={"status": "healthy"})


@app.get("/", include_in_schema=False)
async def index():
    return RedirectResponse(url="/login")


@app.get("/login", include_in_schema=False)
async def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")


@app.get("/admin", include_in_schema=False)
async def admin_page(request: Request):
    return templates.TemplateResponse(request=request, name="admin.html")


@app.get("/profile", include_in_schema=False)
async def profile_page(request: Request):
    return templates.TemplateResponse(request=request, name="profile.html")


@app.get("/host", include_in_schema=False)
async def host_page(request: Request):
    return templates.TemplateResponse(request=request, name="host_dashboard.html")
