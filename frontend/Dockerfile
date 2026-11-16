FROM node:24-alpine AS build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM node:24-alpine
WORKDIR /app
COPY --from=build /app/frontend/dist ./dist
COPY frontend/server.mjs ./server.mjs
ENV NODE_ENV=production
CMD ["node", "server.mjs"]
