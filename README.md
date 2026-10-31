# doc-intel
**Running Instructions:**
docker compose --env-file .env -f docker/dev/docker-compose.yml -f docker/dev/docker-compose-db.yml up -d
docker exec -it doc-intel-dev bash
**Alembic Commands:**
python -m alembic revision -m "message"
python -m alembic upgrade head
**Embedding Server:**
docker compose -f docker/dev/docker-compose.yml -f docker/dev/docker-compose-db.yml -f docker/dev/docker-compose-embed.yml --env-file .env up -d embed
docker logs -f doc-intel-embed