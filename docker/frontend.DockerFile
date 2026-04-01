# ── Frontend Dockerfile ───────────────────────────────────────────────────────
# Multi-stage: build React app, serve with nginx

# Stage 1: build
FROM node:20-alpine3.21 AS builder

WORKDIR /app
RUN apk upgrade --no-cache

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --silent

COPY frontend/ .

# Inject API base URL at build time
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN npm run build


# Stage 2: serve with nginx
FROM nginx:1.27-alpine AS runtime

RUN apk upgrade --no-cache

# Copy built assets
COPY --from=builder /app/dist /usr/share/nginx/html

# Write nginx config inside the image (build context is ./frontend)
RUN { \
    echo 'server {'; \
    echo '    listen 3000;'; \
    echo '    server_name localhost;'; \
    echo ''; \
    echo '    root /usr/share/nginx/html;'; \
    echo '    index index.html;'; \
    echo ''; \
    echo '    location / {'; \
    echo '        try_files $uri $uri/ /index.html;'; \
    echo '    }'; \
    echo ''; \
    echo '    location /api/ {'; \
    echo '        proxy_pass         http://backend:8000/api/;'; \
    echo '        proxy_http_version 1.1;'; \
    echo '        proxy_set_header   Host              $host;'; \
    echo '        proxy_set_header   X-Real-IP         $remote_addr;'; \
    echo '        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;'; \
    echo '        proxy_set_header   X-Forwarded-Proto $scheme;'; \
    echo '        proxy_connect_timeout  10s;'; \
    echo '        proxy_send_timeout     30s;'; \
    echo '        proxy_read_timeout     30s;'; \
    echo '    }'; \
    echo ''; \
    echo '    location ~ ^/(health|ready|docs|redoc|openapi.json)$ {'; \
    echo '        proxy_pass http://backend:8000/$1;'; \
    echo '    }'; \
    echo ''; \
    echo '    location ~* \.(js|css|png|jpg|svg|ico|woff2?)$ {'; \
    echo '        expires 1y;'; \
    echo '        add_header Cache-Control "public, immutable";'; \
    echo '    }'; \
    echo ''; \
    echo '    gzip on;'; \
    echo '    gzip_types text/plain text/css application/json application/javascript;'; \
    echo '    gzip_min_length 1000;'; \
    echo '}'; \
} > /etc/nginx/conf.d/default.conf

RUN chown -R nginx:nginx /usr/share/nginx/html /var/cache/nginx /var/run /etc/nginx/conf.d
USER nginx

EXPOSE 3000

HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost:3000 || exit 1

CMD ["nginx", "-g", "daemon off;"]
