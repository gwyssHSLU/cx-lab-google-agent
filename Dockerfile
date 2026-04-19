# 1. Wir nutzen ein leichtgewichtiges Python-Image
FROM python:3.12-slim

# 2. Arbeitsverzeichnis im Container festlegen
WORKDIR /app

# 3. requirements kopieren und installieren
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Den restlichen Code und den Key kopieren
COPY . .

# 5. Port für Code Engine freigeben (Standard ist oft 8080)
EXPOSE 8081

# 6. Startbefehl (ähnlich wie dein lokaler Befehl)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8081"]