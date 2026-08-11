# Docker Deployment

`compose.yml` defines web, worker, and PostgreSQL. The same `weekend-report:local` image is used by web and worker. PostgreSQL is only attached to the backend network and is not exposed publicly.

The checked-in `env.example` contains placeholders only. Replace values through an approved secret mechanism before production use.

```powershell
docker compose -f deploy/docker/compose.yml config
docker build -t weekend-report:local .
docker compose -f deploy/docker/compose.yml up
```
