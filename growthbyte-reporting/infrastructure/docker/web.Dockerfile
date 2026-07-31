FROM node:22-bookworm-slim AS dependencies

ENV PNPM_HOME=/pnpm
ENV PATH=$PNPM_HOME:$PATH

RUN corepack enable
WORKDIR /workspace

COPY . .
RUN pnpm install --frozen-lockfile

FROM dependencies AS development

EXPOSE 3000
CMD ["pnpm", "--filter", "@growthbyte/web", "dev"]

FROM dependencies AS build

RUN pnpm --filter @growthbyte/web... build

FROM build AS production

ENV NODE_ENV=production
EXPOSE 3000
CMD ["pnpm", "--filter", "@growthbyte/web", "start"]
