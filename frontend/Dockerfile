FROM node:25-alpine3.22 AS base

WORKDIR /app

RUN npm install -g corepack --force \
    && corepack enable \
    && corepack prepare pnpm@10.33.0 --activate

EXPOSE 3000

# ---- Development stage (bind-mounted source) ----
FROM base AS dev

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

# ---- Production build stage ----
FROM base AS build

COPY pnpm-lock.yaml pnpm-workspace.yaml package.json ./
RUN pnpm install --frozen-lockfile

COPY . .
RUN pnpm build

# ---- Production runtime stage ----
FROM base AS prod

COPY --from=build /app/.output /app/.output

ENV NODE_ENV=production

CMD ["node", ".output/server/index.mjs"]
