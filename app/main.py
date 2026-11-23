from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

app = FastAPI()

templates = Jinja2Templates(directory="app/templates")

@app.get("/health")
async def health_check():
    return JSONResponse(content={"status": "healthy"})

@app.get("/login")
async def login(request: Request):
   return templates.TemplateResponse(request=request, name="login.html")
@app.get("/profile")
async def profile(request: Request):
    return templates.TemplateResponse(request=request, name="profile.html")