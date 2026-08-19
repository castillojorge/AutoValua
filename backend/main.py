"""
Orquestador central — AutoValúa AI
-------------------------------------
Expone dos canales tal como define el diseño original:
  1) Chatbot (uso público, sin API key) -> POST /chat/consulta
  2) API REST autenticada para integraciones de terceros -> POST /api/v1/consulta
     (requiere header X-API-Key)

Además expone el panel administrativo (casos escalados) que usa el equipo
humano, y los endpoints que disparan Scraper/Ingestor/Validador para simular
el ciclo mensual (acá, bajo demanda, dado que no hay scraping real a la
DNRPA en este prototipo académico).
"""
import os
import json
import glob
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import db
from agente_ingestor import ingerir_vigencia, LayoutError
from agente_validador import validar_vigencia
from agente_matching import consultar
from agente_historico import serie_historica

app = FastAPI(title="AutoValúa AI", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
API_KEYS_VALIDAS = {"demo-key-autovalua-2024": "Integración de demostración"}


@app.on_event("startup")
def startup():
    db.init_db()


# ---------- Modelos de request ----------
class ConsultaChat(BaseModel):
    texto: str
    usuario: str = "usuario_web"
    vigencia: str | None = None


class ConsultaAPI(BaseModel):
    marca: str | None = None
    modelo: str | None = None
    anio: str | None = None
    texto: str | None = None
    vigencia: str | None = None


class ResolucionCaso(BaseModel):
    accion: str  # "asignar_alias" | "descartar" | "confirmar_anomalia"
    codigo_resuelto: str | None = None
    alias_texto: str | None = None
    comentario: str | None = None


class NotificacionConfig(BaseModel):
    usuario: str
    codigo_vehiculo: str
    condicion: str = "cualquier_cambio"
    canal: str = "chat"


def verificar_api_key(x_api_key: str = Header(default=None)):
    if x_api_key not in API_KEYS_VALIDAS:
        raise HTTPException(status_code=401, detail="API key inválida o ausente (header X-API-Key requerido).")
    return API_KEYS_VALIDAS[x_api_key]


# ---------- Canal 1: Chatbot público ----------
@app.post("/chat/consulta")
def chat_consulta(payload: ConsultaChat):
    return consultar(payload.texto, usuario=payload.usuario, canal="chatbot", vigencia=payload.vigencia)


# ---------- Canal 2: API REST autenticada ----------
@app.post("/api/v1/consulta")
def api_consulta(payload: ConsultaAPI, integracion: str = Depends(verificar_api_key)):
    if payload.texto:
        texto = payload.texto
    else:
        partes = [p for p in [payload.marca, payload.modelo, payload.anio] if p]
        texto = " ".join(partes)
        if not texto:
            raise HTTPException(status_code=400, detail="Se requiere 'texto' o 'marca'/'modelo'/'anio'.")
    resultado = consultar(texto, usuario=f"api:{integracion}", canal="api", vigencia=payload.vigencia)
    return resultado


@app.get("/api/v1/historico/{codigo}")
def api_historico(codigo: str, integracion: str = Depends(verificar_api_key)):
    return serie_historica(codigo)


# ---------- Histórico (también accesible desde el chat) ----------
@app.get("/chat/historico/{codigo}")
def chat_historico(codigo: str):
    return serie_historica(codigo)


# ---------- Ciclo de ingesta (Scraper simulado + Ingestor + Validador) ----------
@app.get("/admin/vigencias_disponibles")
def vigencias_disponibles():
    """Simula lo que el Agente Scraper detectaría en el portal de la DNRPA:
    lista los archivos de vigencia presentes y cuáles ya fueron ingeridos."""
    conn = db.get_conn()
    ingeridas = {r["vigencia"] for r in conn.execute("SELECT vigencia FROM vigencias_ingeridas").fetchall()}
    conn.close()
    archivos = sorted(glob.glob(os.path.join(DATA_DIR, "vigencia_*.json")))
    out = []
    for a in archivos:
        with open(a, encoding="utf-8") as f:
            v = json.load(f).get("vigencia")
        out.append({"archivo": os.path.basename(a), "vigencia": v, "ingerida": v in ingeridas})
    return out


@app.post("/admin/ingestar/{nombre_archivo}")
def admin_ingestar(nombre_archivo: str):
    path = os.path.join(DATA_DIR, nombre_archivo)
    if not os.path.exists(path):
        raise HTTPException(404, "Archivo no encontrado")
    try:
        resultado_ingesta = ingerir_vigencia(path)
    except LayoutError as e:
        raise HTTPException(422, f"Error de layout detectado por el Ingestor: {e}")
    reporte_validacion = validar_vigencia(resultado_ingesta["vigencia"])
    return {"ingesta": resultado_ingesta, "validacion": reporte_validacion}


# ---------- Panel administrativo: casos escalados ----------
@app.get("/admin/casos")
def listar_casos(estado: str = "pendiente"):
    conn = db.get_conn()
    filtro = "" if estado == "todos" else "WHERE estado = ?"
    params = () if estado == "todos" else (estado,)
    filas = conn.execute(f"SELECT * FROM casos_escalados {filtro} ORDER BY fecha DESC", params).fetchall()
    conn.close()
    return [dict(f) | {"detalle": json.loads(f["detalle_json"])} for f in filas]


@app.post("/admin/casos/{caso_id}/resolver")
def resolver_caso(caso_id: int, payload: ResolucionCaso):
    conn = db.get_conn()
    cur = conn.cursor()
    caso = cur.execute("SELECT * FROM casos_escalados WHERE id = ?", (caso_id,)).fetchone()
    if not caso:
        conn.close()
        raise HTTPException(404, "Caso no encontrado")

    if payload.accion == "asignar_alias":
        if caso["tipo"] != "ambiguedad_consulta":
            conn.close()
            raise HTTPException(400, "'asignar_alias' solo aplica a casos de tipo ambiguedad_consulta")
        if not (payload.codigo_resuelto and payload.alias_texto):
            conn.close()
            raise HTTPException(400, "Se requiere codigo_resuelto y alias_texto")
        # --- Aprendizaje procedimental: la corrección humana pasa a memoria ---
        cur.execute("""
            INSERT INTO alias (alias_texto, codigo_resuelto, aprendido_de_caso_id)
            VALUES (?, ?, ?)
            ON CONFLICT(alias_texto) DO UPDATE SET codigo_resuelto=excluded.codigo_resuelto
        """, (payload.alias_texto.strip().upper(), payload.codigo_resuelto, caso_id))
        estado_final = "resuelto"
    elif payload.accion in ("descartar", "confirmar_anomalia"):
        estado_final = "resuelto" if payload.accion == "confirmar_anomalia" else "descartado"
    else:
        conn.close()
        raise HTTPException(400, "Acción inválida")

    cur.execute("UPDATE casos_escalados SET estado = ?, resolucion = ? WHERE id = ?",
                (estado_final, payload.comentario or payload.accion, caso_id))
    conn.commit()
    conn.close()
    return {"caso_id": caso_id, "estado": estado_final}


@app.get("/admin/alias")
def listar_alias():
    conn = db.get_conn()
    filas = conn.execute("SELECT * FROM alias ORDER BY fecha DESC").fetchall()
    conn.close()
    return [dict(f) for f in filas]


@app.get("/admin/stats")
def stats():
    conn = db.get_conn()
    c = conn.cursor()
    out = {
        "vehiculos_en_catalogo": c.execute("SELECT COUNT(DISTINCT codigo) n FROM vehiculos").fetchone()["n"],
        "vigencias_ingeridas": c.execute("SELECT COUNT(*) n FROM vigencias_ingeridas").fetchone()["n"],
        "consultas_totales": c.execute("SELECT COUNT(*) n FROM consultas_log").fetchone()["n"],
        "consultas_resueltas_automaticamente": c.execute(
            "SELECT COUNT(*) n FROM consultas_log WHERE resultado='match'").fetchone()["n"],
        "consultas_escaladas": c.execute(
            "SELECT COUNT(*) n FROM consultas_log WHERE resultado='escalado'").fetchone()["n"],
        "consultas_no_encontradas": c.execute(
            "SELECT COUNT(*) n FROM consultas_log WHERE resultado='no_encontrado'").fetchone()["n"],
        "casos_pendientes": c.execute(
            "SELECT COUNT(*) n FROM casos_escalados WHERE estado='pendiente'").fetchone()["n"],
        "alias_aprendidos": c.execute("SELECT COUNT(*) n FROM alias").fetchone()["n"],
    }
    conn.close()
    return out


# ---------- Notificaciones ----------
@app.post("/chat/notificaciones")
def crear_notificacion(payload: NotificacionConfig):
    conn = db.get_conn()
    conn.execute("""
        INSERT INTO notificaciones_config (usuario, codigo_vehiculo, condicion, canal)
        VALUES (?, ?, ?, ?)
    """, (payload.usuario, payload.codigo_vehiculo, payload.condicion, payload.canal))
    conn.commit()
    conn.close()
    return {"estado": "configurada"}


# ---------- Frontend estático ----------
app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static"), html=True), name="static")
