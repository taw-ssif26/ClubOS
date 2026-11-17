FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG API_URL=http://api:8000
ARG NEXT_PUBLIC_SITE_URL=http://localhost:3000
ENV API_URL=$API_URL NEXT_PUBLIC_SITE_URL=$NEXT_PUBLIC_SITE_URL
RUN npm run build

FROM node:22-alpine
WORKDIR /app
ENV NODE_ENV=production PORT=3000 HOSTNAME=0.0.0.0
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
RUN adduser -D app && chown -R app /app
USER app
EXPOSE 3000
CMD ["node", "server.js"]
