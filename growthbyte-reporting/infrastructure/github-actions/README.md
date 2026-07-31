# GitHub Actions

The active workflow is at repository-root `.github/workflows/ci.yml`, one directory above the `growthbyte-reporting` project. It validates Node installation, frozen pnpm dependencies, Prettier, frontend lint/test/typecheck/build, Python 3.11 and Poetry dependency installation, Ruff, Pytest, and Docker Compose syntax. All commands and cache paths explicitly target the project subdirectory.

Phase 1 intentionally includes no deployment, AWS, ECR, EKS, Helm release, scheduled job, secret, or external-service job.
