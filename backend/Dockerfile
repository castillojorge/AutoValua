# AutoValúa AI — backend
# Imagen simple de una sola etapa: FastAPI + SQLite no necesitan build steps
# pesados, y rapidfuzz/pdfplumber traen wheels precompilados para linux/amd64
# y linux/arm64, así que no hace falta gcc ni build-essential.
FROM python:3.12-slim

WORKDIR /app

# Instalar dependencias primero (capa cacheable: no se reinstala si solo
# cambia el código de la app)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código de la aplicación
COPY . .

# La base SQLite y los archivos de vigencia viven acá — se monta como
# volumen desde docker-compose.yml para que los datos sobrevivan a un
# `docker compose down` / rebuild de la imagen.
RUN mkdir -p /app/data

EXPOSE 8000

# Sin --reload: esto es para correr, no para desarrollar. Para desarrollo
# con recarga automática, ver la sección "Desarrollo" del README.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
