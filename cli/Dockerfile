FROM node:20-slim AS builder

WORKDIR /app

COPY package*.json ./

RUN npm install --production=false

COPY . .

RUN npm run build

FROM node:20-slim

WORKDIR /app

COPY package*.json ./

RUN npm install --production && npm cache clean --force

COPY --from=builder /app/dist ./dist

COPY --from=builder /app/skills-recommendations.json ./skills-recommendations.json

ENV GATEWAY_URL=http://api-gateway:3000
ENV AI_CORE_URL=http://ai-core:8000
ENV AI_CORE_PORT=8000
ENV GATEWAY_PORT=3000
ENV ENV_FILE=/app/.env

CMD ["node", "dist/index.js", "interactive"]
