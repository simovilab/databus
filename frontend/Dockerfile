FROM node:25-alpine3.22

WORKDIR /app

RUN npm install -g corepack --force \
    && corepack enable \
    && corepack prepare pnpm@10.33.0 --activate

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 3000

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
