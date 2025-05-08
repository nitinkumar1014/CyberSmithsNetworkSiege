FROM python:3.8-slim

WORKDIR /app

COPY src/client.py .

CMD ["python", "client.py"]