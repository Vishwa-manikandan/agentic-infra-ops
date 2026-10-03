FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "main.py"]
version: '3.8'

services:
toy-service:
build: ./toy_app
container_name: toy-service
ports:
  - "8000:8000"
networks:
  - monitoring

prometheus:
image: prom/prometheus:latest
container_name: prometheus
ports:
  - "9090:9090"
volumes:
  - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
networks:
  - monitoring

networks:
monitoring:
driver: bridge