# Usamos Miniconda como base para instalar librerías geoespaciales fácilmente
FROM continuumio/miniconda3:latest

# Evitar que Python genere archivos .pyc y forzar logs sin búfer
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copiamos el archivo de dependencias primero para aprovechar la caché de Docker
COPY environment.yml .

# Creamos el entorno e instalamos las dependencias
RUN conda env create -f environment.yml

# Configuramos el shell para usar el entorno creado por defecto
SHELL ["conda", "run", "-n", "mapa_env", "/bin/bash", "-c"]

# Copiamos el código fuente y los recursos (header.png, footer.png)
COPY . /app

# Exponemos el puerto para Google Cloud Run
EXPOSE 8080

# Comando de inicio
CMD ["conda", "run", "--no-capture-output", "-n", "mapa_env", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]