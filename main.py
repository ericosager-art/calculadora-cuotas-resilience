import os
import json
from decimal import Decimal, ROUND_HALF_UP

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import sessionmaker, declarative_base

# ==============================
# DATABASE
# ==============================

DATABASE_URL = "sqlite:///./database2.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)
    role = Column(String)


class Coefficient(Base):
    __tablename__ = "coefficients"

    id = Column(Integer, primary_key=True, index=True)
    card_name = Column(String, index=True)
    installments = Column(Integer)
    value = Column(Float)


# ==============================
# APP INIT
# ==============================

app = FastAPI()
Base.metadata.create_all(bind=engine)

# Mapping oficial entre frontend y DB
CARD_NAME_MAP = {
    "tuya": "tarjeta_tuya",
    "bancarias": "tarjetas_bancarias",
    "naranja": "naranja_visa_master",
    "plan_z": "plan_z",
}

# ==============================
# STARTUP
# ==============================

@app.on_event("startup")
def startup_event():
    db = SessionLocal()

    # Crear admin si no existe
    if not db.query(User).filter(User.username == "admin").first():
        db.add(User(username="admin", password="admin123", role="admin"))

    # Crear vendedor si no existe
    if not db.query(User).filter(User.username == "vendedor").first():
        db.add(User(username="vendedor", password="1234", role="vendedor"))

    # Insertar coeficientes SOLO si tabla está vacía
    if db.query(Coefficient).count() == 0:

        tuya = {
            1: 1.06, 2: 1.24, 3: 1.25, 4: 1.47,
            5: 1.51, 6: 1.58, 7: 1.62, 8: 1.64,
            9: 1.69, 10: 1.75, 11: 1.81, 12: 1.94
        }

        for cuota, coef in tuya.items():
            db.add(Coefficient(
                card_name=CARD_NAME_MAP["tuya"],
                installments=cuota,
                value=coef
            ))

        bancarias = {3: 1.20, 6: 1.37, 12: 1.70}
        for cuota, coef in bancarias.items():
            db.add(Coefficient(
                card_name=CARD_NAME_MAP["bancarias"],
                installments=cuota,
                value=coef
            ))

        db.add(Coefficient(
            card_name=CARD_NAME_MAP["naranja"],
            installments=3,
            value=1.39
        ))

        db.add(Coefficient(
            card_name=CARD_NAME_MAP["plan_z"],
            installments=11,
            value=1.30
        ))

    db.commit()
    db.close()

# ==============================
# STATIC & TEMPLATES
# ==============================

os.makedirs("static/images", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

DATA_FILE = "data.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"tarjetas": []}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def round2(value):
    return float(
        Decimal(value).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )
    )

# ==============================
# LOGIN
# ==============================

@app.get("/", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
def login(username: str = Form(...), password: str = Form(...)):
    db = SessionLocal()
    user = db.query(User).filter(
        User.username == username,
        User.password == password
    ).first()
    db.close()

    if not user:
        return RedirectResponse("/", status_code=302)

    response = RedirectResponse("/dashboard", status_code=302)
    response.set_cookie("user", user.username)
    return response

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

    if not user:
        return RedirectResponse("/", status_code=302)

    data = load_data()

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "tarjetas": data.get("tarjetas", []),
        "rol": user.role,
        "username": username
    })

# ==============================
# CALCULAR (VERSIÓN DEFINITIVA)
# ==============================

@app.post("/calcular", response_class=HTMLResponse)
def calcular(
    request: Request,
    tarjeta: str = Form(...),
    precio: float = Form(...),
    cuotas: int = Form(...)
):
    username = request.cookies.get("user")
    if not username:
        return RedirectResponse("/", status_code=302)

    db = SessionLocal()
    user = db.query(User).filter(User.username == username).first()

    if not user:
        db.close()
        return RedirectResponse("/", status_code=302)

    data = load_data()

    # Traducción segura frontend → DB
    tarjeta_db = CARD_NAME_MAP.get(tarjeta, tarjeta)

    coef_record = db.query(Coefficient).filter(
        Coefficient.card_name == tarjeta_db,
        Coefficient.installments == cuotas
    ).first()

    if not coef_record:
        db.close()
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "tarjetas": data.get("tarjetas", []),
            "error": "No existe coeficiente para esa combinación.",
            "rol": user.role,
            "username": username
        })

    coef = coef_record.value
    total = round2(precio * coef)
    cuota_valor = round2(total / cuotas)

    resultado = {
        "coeficiente": coef,
        "total": total,
        "cuota": cuota_valor
    }

    db.close()

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "tarjetas": data.get("tarjetas", []),
        "resultado": resultado,
        "rol": user.role,
        "username": username
    })
