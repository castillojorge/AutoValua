"""
Capa de persistencia — Memoria semántica, episódica, procedimental y de notificaciones.
"""
import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "autovalua.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    # --- Memoria semántica: tablas de valuación ingeridas ---
    cur.execute("""
    CREATE TABLE IF NOT EXISTS vehiculos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vigencia TEXT NOT NULL,
        codigo TEXT NOT NULL,
        tipo TEXT NOT NULL,
        marca TEXT NOT NULL,
        modelo TEXT NOT NULL,
        carroceria TEXT,
        precios_json TEXT NOT NULL,
        UNIQUE(vigencia, codigo)
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS vigencias_ingeridas (
        vigencia TEXT PRIMARY KEY,
        fuente TEXT,
        fecha_ingesta TEXT DEFAULT CURRENT_TIMESTAMP,
        cantidad_vehiculos INTEGER
    )""")

    # --- Memoria procedimental: alias aprendidos por resolución humana ---
    cur.execute("""
    CREATE TABLE IF NOT EXISTS alias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        alias_texto TEXT NOT NULL,
        codigo_resuelto TEXT NOT NULL,
        aprendido_de_caso_id INTEGER,
        fecha TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(alias_texto)
    )""")

    # --- Memoria episódica: historial de consultas por usuario ---
    cur.execute("""
    CREATE TABLE IF NOT EXISTS consultas_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT DEFAULT CURRENT_TIMESTAMP,
        usuario TEXT,
        canal TEXT,
        consulta_texto TEXT,
        marca_detectada TEXT,
        modelo_detectado TEXT,
        anio_detectado TEXT,
        estrategia TEXT,
        codigo_match TEXT,
        confianza REAL,
        resultado TEXT
    )""")

    # --- Casos escalados a humano (Validador + Consulta) ---
    cur.execute("""
    CREATE TABLE IF NOT EXISTS casos_escalados (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT DEFAULT CURRENT_TIMESTAMP,
        tipo TEXT NOT NULL,               -- 'ambiguedad_consulta' | 'anomalia_validacion'
        origen_agente TEXT NOT NULL,      -- 'Consulta/Matching' | 'Validador'
        detalle_json TEXT NOT NULL,
        prioridad TEXT DEFAULT 'media',
        estado TEXT DEFAULT 'pendiente',  -- 'pendiente' | 'resuelto' | 'descartado'
        resolucion TEXT
    )""")

    # --- Memoria de notificaciones ---
    cur.execute("""
    CREATE TABLE IF NOT EXISTS notificaciones_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT NOT NULL,
        codigo_vehiculo TEXT NOT NULL,
        condicion TEXT DEFAULT 'cualquier_cambio',
        canal TEXT DEFAULT 'chat'
    )""")

    conn.commit()
    conn.close()


def reset_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_db()
