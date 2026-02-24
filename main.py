from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///./database.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True)
    password = Column(String)
    role = Column(String)


class Coefficient(Base):
    __tablename__ = "coefficients"

    id = Column(Integer, primary_key=True, index=True)
    card_name = Column(String)
    installments = Column(Integer)
    value = Column(Float)
Base.metadata.create_all(bind=engine)    
from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import json
import os
from decimal import Decimal, ROUND_HALF_UP

app = FastAPI()

# Crear carpetas si no existen
os.makedirs("static/images", exist_ok=True)
os.makedirs("templates", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

DATA_FILE = "data.json"

def load_data():
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def round2(value):
    return float(Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

@app.get("/", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    data = load_data()
    user = data["usuarios"].get(username)

    if user and user["password"] == password:
        response = RedirectResponse(url="/dashboard", status_code=302)
        response.set_cookie(key="user", value=username)
        return response

    return templates.TemplateResponse("login.html", {"request": request, "error": "Credenciales incorrectas"})

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    username = request.cookies.get("user")
    if not username:
        return RedirectResponse("/", status_code=302)

    data = load_data()
    rol = data["usuarios"][username]["rol"]

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "tarjetas": data["tarjetas"],
        "rol": rol,
        "username": username
    })

@app.post("/calcular", response_class=HTMLResponse)
def calcular(request: Request,
             tarjeta: str = Form(...),
             precio: float = Form(...),
             cuotas: str = Form(None)):

    data = load_data()
    tarjetas = data["tarjetas"]

    if tarjeta == "plan_z":
        coef = tarjetas["plan_z"]["coeficiente"]
        monto_pos = round2(precio * coef)
        codigo = tarjetas["plan_z"]["codigo_pos"]
        monto_cuota = None
    else:
        coef = tarjetas[tarjeta]["cuotas"][cuotas]
        monto_pos = round2(precio * coef)
        monto_cuota = round2(monto_pos / int(cuotas))
        codigo = cuotas

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "tarjetas": tarjetas,
        "resultado": {
            "monto_pos": monto_pos,
            "monto_cuota": monto_cuota,
            "codigo": codigo
        },
        "rol": "vendedor"
    })

@app.get("/logout")
def logout():
    response = RedirectResponse("/", status_code=302)
    response.delete_cookie("user")
    return response
