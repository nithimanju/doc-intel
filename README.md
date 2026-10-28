# doc-intel
**Running Instructions:**
docker compose --env-file .env -f docker/dev/docker-compose.yml -f docker/dev/docker-compose-db.yml up -d
docker exec -it doc-intel-dev bash
**Alembic Commands:**
alembic revision -m "message"