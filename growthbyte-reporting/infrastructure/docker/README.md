# Docker development

The root `docker-compose.yml` builds one image per service. Compose injects only non-secret operational settings with local defaults. If a root `.env` exists, Compose uses its matching values for interpolation; secrets are neither copied into the Compose file nor required by Phase 1 services.

Run `docker compose up --build`, then check ports 3000, 8000, and 8001. Stop with `docker compose down`.
