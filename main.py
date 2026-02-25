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


app = FastAPI()

Base.metadata.create_all(bind=engine)

# ==============================
# STARTUP EVENT (PROFESIONAL)
# ==============================

@app.on_event("startup")
def startup_event():
    db = SessionLocal()

    # Crear o actualizar admin
    admin = db.query(User).filter(User.username == "admin").first()
    if not admin:
        db.add(User(username="admin", password="admin123", role="admin"))
    else:
        admin.password = "admin123"
        admin.role = "admin"

    # Crear o actualizar vendedor
    vendedor = db.query(User).filter(User.username == "vendedor").first()
    if not vendedor:
        db.add(User(username="vendedor", password="1234", role="vendedor"))
    else:
        vendedor.password = "1234"
        vendedor.role = "vendedor"

    # Crear coeficientes si no existen
    if not db.query(Coefficient).first():
        tuya = {
            1: 1.06, 2: 1.24, 3: 1.25, 4: 1.47,
            5: 1.51, 6: 1.58, 7: 1.62, 8: 1.64,
            9: 1.69, 10: 1.75, 11: 1.81, 12: 1.94
        }

        for cuota, coef in tuya.items():
            db.add(Coefficient(card_name="tarjeta_tuya", installments=cuota, value=coef))

        bancarias = {3: 1.20, 6: 1.37, 12: 1.70}
        for cuota, coef in bancarias.items():
            db.add(Coefficient(card_name="tarjetas_bancarias", installments=cuota, value=coef))

        db.add(Coefficient(card_name="naranja_visa_master", installments=3, value=1.39))
        db.add(Coefficient(card_name="plan_z", installments=11, value=1.30))

    db.commit()
    db.close()

# ==============================
# ARCHIVOS Y TEMPLATES
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
    return float(Decimal(value).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    ))

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
        response = RedirectResponse("/dashboard", status_code=302)
        response.set_cookie("user", username)
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
# CALCULAR
# ==============================

@app.post("/calcular", response_class=HTMLResponse)
def calcular(request: Request,
             tarjeta: str = Form(...),
             precio: float = Form(...),
             cuotas: int = Form(...)):

    username = request.cookies.get("user")
    if not username:
        return RedirectResponse("/", status_code=302)

    db = SessionLocal()
    user = db.query(User).filter(User.username == username).first()

    if not user:
        db.close()
        return RedirectResponse("/", status_code=302)

    data = load_data()

    coef_record = db.query(Coefficient).filter(
        Coefficient.card_name == tarjeta,
        Coefficient.installments == cuotas
    ).first()

    if not coef_record:
        db.close()
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "tarjetas": data.get("tarjetas", []),
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
        "tarjetas": data.get("tarjetas", []),
        "resultado": {
            "monto_pos": monto_pos,
            "monto_cuota": monto_cuota,
            "codigo": codigo,
            "tarjeta": tarjeta
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
