from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import declarative_base, sessionmaker
from decimal import Decimal, ROUND_HALF_UP
import json
import os

# ==============================
# CONFIGURACIÓN BASE DE DATOS
# ==============================

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


def init_users():
    db = SessionLocal()
    ...
    db.close()


def init_coefficients():
    db = SessionLocal()

    if db.query(Coefficient).first():
        db.close()
        return

    # Tarjeta Tuya
    tuya = {
        1: 1.06, 2: 1.24, 3: 1.25, 4: 1.47,
        5: 1.51, 6: 1.58, 7: 1.62, 8: 1.64,
        9: 1.69, 10: 1.75, 11: 1.81, 12: 1.94
    }

    for cuota, coef in tuya.items():
        db.add(Coefficient(card_name="tarjeta_tuya", installments=cuota, value=coef))

    bancarias = {
        3: 1.20,
        6: 1.37,
        12: 1.70
    }

    for cuota, coef in bancarias.items():
        db.add(Coefficient(card_name="tarjetas_bancarias", installments=cuota, value=coef))

    db.add(Coefficient(card_name="naranja_visa_master", installments=3, value=1.39))
    db.add(Coefficient(card_name="plan_z", installments=11, value=1.30))

    db.commit()
    db.close()


init_users()
init_coefficients()

# ==============================
# CONFIGURACIÓN FASTAPI
# ==============================

app = FastAPI()

os.makedirs("static/images", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

DATA_FILE = "data.json"


def load_data():
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def round2(value):
    return float(Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


# ==============================
# LOGIN
# ==============================

@app.get("/", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    db = SessionLocal()
    user = db.query(User).filter(User.username == username).first()
    db.close()

    if user and user.password == password:
        response = RedirectResponse(url="/dashboard", status_code=302)
        response.set_cookie(key="user", value=username)
        return response

    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": "Credenciales incorrectas"
    })


# ==============================
# DASHBOARD
# ==============================

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    username = request.cookies.get("user")
    if not username:
        return RedirectResponse("/", status_code=302)

    db = SessionLocal()
    user = db.query(User).filter(User.username == username).first()
    db.close()

    data = load_data()

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "tarjetas": data["tarjetas"],
        "rol": user.role,
        "username": username
    })


# ==============================
# CALCULAR
# ==============================

@app.post("/calcular", response_class=HTMLResponse)
def calcular(request: Request,
             tarjeta: str = Form(...),
             precio: float = Form(...),
             cuotas: int = Form(None)):

    username = request.cookies.get("user")
    if not username:
        return RedirectResponse("/", status_code=302)

    db = SessionLocal()
    user = db.query(User).filter(User.username == username).first()

    # Buscar coeficiente en base de datos
    coef_record = db.query(Coefficient).filter(
        Coefficient.card_name == tarjeta,
        Coefficient.installments == cuotas
    ).first()

    if not coef_record:
        db.close()
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "error": "No se encontró coeficiente",
            "rol": user.role,
            "username": username
        })

    coef = coef_record.value
    monto_pos = round2(precio * coef)
    monto_cuota = round2(monto_pos / cuotas)

    codigo = cuotas
    if tarjeta == "plan_z":
        codigo = 11
        monto_cuota = None

    db.close()

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "resultado": {
            "monto_pos": monto_pos,
            "monto_cuota": monto_cuota,
            "codigo": codigo
        },
        "rol": user.role,
        "username": username
    })


# ==============================
# LOGOUT
# ==============================

@app.get("/logout")
def logout():
    response = RedirectResponse("/", status_code=302)
    response.delete_cookie("user")
    return response
