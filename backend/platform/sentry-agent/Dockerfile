# Pinned via versions.env PYTHON_IMAGE=python:3.12.7-slim
ARG PYTHON_IMAGE=python:3.12.7-slim
FROM ${PYTHON_IMAGE}

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "bot.py"]
