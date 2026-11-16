FROM node:24-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY --from=frontend /app/frontend/dist frontend/dist
ENV ENVIRONMENT=production HOST=0.0.0.0
CMD ["sh", "-c", "uvicorn backend.main:create_app --factory --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers"]
