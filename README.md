# doc-intel
**Running Instructions:**
docker compose --env-file .env -f docker/dev/docker-compose.yml -f docker/dev/docker-compose-db.yml up -d
docker exec -it doc-intel-dev bash
**Alembic Commands:**
python -m alembic revision -m "message"
python -m alembic upgrade head