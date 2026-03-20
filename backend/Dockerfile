FROM python:3.9-slim-buster

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY data_engineering/ data_engineering/

CMD ["python", "app.py"]
