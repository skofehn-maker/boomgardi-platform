from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.v1.auth import router as auth_router
from app.api.v1.bookings import router as bookings_router
from app.api.v1.listings import router as listings_router
from app.api.v1.users import router as users_router

app = FastAPI(title="Boomgardi Platform")

app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")

app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(users_router, prefix="/api/v1/users", tags=["users"])
app.include_router(listings_router, prefix="/api/v1/listings", tags=["listings"])
app.include_router(bookings_router, prefix="/api/v1/bookings", tags=["bookings"])


@app.get("/health")
async def health_check():
    return JSONResponse(content={"status": "healthy"})


@app.get("/", include_in_schema=False)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/login", include_in_schema=False)
async def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")


@app.get("/register", include_in_schema=False)
async def register_page(request: Request):
    return templates.TemplateResponse(request=request, name="register.html")


@app.get("/admin", include_in_schema=False)
async def admin_page(request: Request):
    return templates.TemplateResponse(request=request, name="admin.html")


@app.get("/profile", include_in_schema=False)
async def profile_page(request: Request):
    return templates.TemplateResponse(request=request, name="profile.html")


@app.get("/host", include_in_schema=False)
async def host_page(request: Request):
    return templates.TemplateResponse(request=request, name="host_dashboard.html")


@app.get("/host/bookings", include_in_schema=False)
async def host_bookings_page(request: Request):
    return templates.TemplateResponse(request=request, name="host_bookings.html")


@app.get("/profile/bookings", include_in_schema=False)
async def profile_bookings_page(request: Request):
    return templates.TemplateResponse(request=request, name="profile_bookings.html")


@app.get("/listings/{listing_id}", include_in_schema=False)
async def listing_detail_page(request: Request, listing_id: str):
    return templates.TemplateResponse(request=request, name="listing_detail.html")
