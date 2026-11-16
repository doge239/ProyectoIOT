FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend /app/backend
ENV HOST=0.0.0.0 ENVIRONMENT=production
CMD ["sh", "-c", "uvicorn backend.main:create_app --factory --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers"]
