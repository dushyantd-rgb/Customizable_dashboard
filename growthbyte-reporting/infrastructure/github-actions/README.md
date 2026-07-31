# GitHub Actions

The active workflow is `.github/workflows/ci.yml`. It validates Node installation, frozen pnpm dependencies, Prettier, frontend lint/test/typecheck/build, Python 3.11 and Poetry dependency installation, Ruff, Pytest, and Docker Compose syntax.

Phase 1 intentionally includes no deployment, AWS, ECR, EKS, Helm release, scheduled job, secret, or external-service job.
