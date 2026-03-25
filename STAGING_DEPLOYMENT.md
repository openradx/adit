# Staging Deployment - Dev Mode on Docker Swarm

## What is Staging?

Staging is **literally your dev environment running on Docker Swarm**. It's useful for:

- ✅ Testing worker scaling (multiple mass_transfer_worker replicas)
- ✅ Testing Swarm deployment before production
- ✅ Testing auto-restart and self-healing features
- ✅ **Same as dev in every other way**: localhost, DEBUG=True, debug toolbar, plain HTTP

## Key Differences from Dev

| Feature | Dev (`compose up`) | Staging (Swarm) |
|---------|-------------------|-----------------|
| **Django settings** | development | development ✓ |
| **Access URL** | http://localhost:8000 | http://localhost:8001 |
| **DICOM receiver** | Port 11122 | Port 11123 |
| **PostgreSQL** | Port 5432 | Port 5433 |
| **Debug toolbar** | ✓ Yes | ✓ Yes |
| **SSL/HTTPS** | ✗ Plain HTTP | ✗ Plain HTTP ✓ |
| **Email** | Console logs | Console logs ✓ |
| **Worker scaling** | `--scale` flag | `deploy.replicas` |
| **Auto-restart** | Manual | Automatic |
| **Database password** | postgres | postgres ✓ |

**Summary**: Staging = Dev + Swarm orchestration + Different ports

## Quick Start

### 1. Use Your Existing .env

```bash
# Just use your existing .env - it already has staging ports defined!
# No changes needed!

# Staging uses these ports from example.env:
# WEB_STAGING_PORT=8001
# POSTGRES_STAGING_PORT=5433
# RECEIVER_STAGING_PORT=11123
# etc.
```

### 2. Deploy to Swarm

```bash
# Initialize swarm (one-time setup)
docker swarm init

# Deploy staging stack (uses .env automatically)
docker stack deploy \
  -c docker-compose.base.yml \
  -c docker-compose.staging.yml \
  adit-staging
```

### 3. Access Staging

```bash
# Different port from dev!
http://localhost:8001
```

## Scaling Workers

This is the **main reason** to use staging instead of regular dev.

### Default Replicas

Staging starts with these replicas (defined in `docker-compose.staging.yml`):
- Web: 1
- Default worker: 1
- DICOM worker: 1
- **Mass transfer worker: 3** (to test scaling)

### Check Current Replicas

```bash
docker service ls

# NAME                               REPLICAS
# adit-staging_mass_transfer_worker  3/3
# adit-staging_dicom_worker          1/1
# adit-staging_web                   1/1
```

### Scale Workers Dynamically

```bash
# Scale mass_transfer workers to 5
docker service scale adit-staging_mass_transfer_worker=5

# Scale down to 1
docker service scale adit-staging_mass_transfer_worker=1

# Verify
docker service ps adit-staging_mass_transfer_worker
```

### Change Default Replicas

Edit `docker-compose.staging.yml` to change defaults:

```yaml
mass_transfer_worker:
  deploy:
    replicas: 10  # Start with 10 workers
```

Then redeploy:
```bash
docker stack deploy -c docker-compose.base.yml -c docker-compose.staging.yml adit-staging
```

## Monitoring

### View Logs

```bash
# Web server logs
docker service logs -f adit-staging_web

# Mass transfer worker logs (all 5 replicas)
docker service logs -f adit-staging_mass_transfer_worker

# Single worker logs
docker logs <container-id>
```

### Check Service Status

```bash
# List all services
docker service ls

# Detailed info on a service
docker service ps adit-staging_mass_transfer_worker

# See which containers are running
docker ps | grep adit-staging
```

### Shell Access

```bash
# Get shell in web container
docker exec -it $(docker ps -q -f name=adit-staging_web) bash

# Run Django commands
docker exec $(docker ps -q -f name=adit-staging_web) \
  python manage.py shell
```

## Testing Worker Scaling

### Create Test Jobs

```bash
# Access Django shell
docker exec -it $(docker ps -q -f name=adit-staging_web) bash
./manage.py shell
```

```python
# Create a bunch of mass transfer tasks
from adit.batch_transfer.models import BatchTransferJob

# Create test job
job = BatchTransferJob.objects.create(...)

# Now scale workers and watch them process tasks
```

### Watch Workers Process Tasks

```bash
# Scale to 5 workers
docker service scale adit-staging_mass_transfer_worker=5

# Watch logs from all 5 workers
docker service logs -f adit-staging_mass_transfer_worker

# You'll see all 5 workers processing tasks concurrently!
```

## Running All Three Environments Simultaneously

✅ **All three can run at the same time!** They use different ports:

### Port Allocation

| Service | Dev | Staging | Production |
|---------|-----|---------|------------|
| **Web UI** | 8000 | 8001 | 80, 443 |
| **PostgreSQL** | 5432 | 5433 | (internal) |
| **DICOM Receiver** | 11122 | 11123 | 11112 |
| **Orthanc1** | 7501 | 7503 | (internal) |
| **Orthanc2** | 7502 | 7504 | (internal) |

### Run All Three Together

```bash
# 1. Start dev (docker compose)
uv run cli compose-up

# 2. Start production (docker swarm)
docker swarm init  # if not already in swarm mode
export $(cat .env | grep -v '^#' | xargs)
docker stack deploy -c docker-compose.base.yml -c docker-compose.prod.yml adit-prod

# 3. Start staging (docker swarm - uses same .env)
docker stack deploy -c docker-compose.base.yml -c docker-compose.staging.yml adit-staging

# Now all three are running!
```

### Access Each Environment

```bash
# Development
http://localhost:8000       # Web UI
# PostgreSQL: localhost:5432
# DICOM: localhost:11122

# Staging
http://localhost:8001       # Web UI
# PostgreSQL: localhost:5433
# DICOM: localhost:11123

# Production
http://localhost:80         # or your domain
https://localhost:443       # with SSL
# DICOM: localhost:11112
```

### Why Run All Three?

- **Dev**: Active development with hot reload
- **Staging**: Test worker scaling before pushing to production
- **Production**: Serve real users

Each has its own database, so changes in dev/staging don't affect production.

## Cleanup

### Remove Staging Stack

```bash
# Remove all services
docker stack rm adit-staging

# Wait 30 seconds for graceful shutdown
sleep 30

# Check they're gone
docker service ls
```

### Remove Volumes (WARNING: deletes data!)

```bash
# List volumes
docker volume ls | grep adit-staging

# Remove (careful!)
docker volume prune
```

### Leave Swarm Mode

```bash
# If you want to go back to regular docker compose
docker swarm leave --force
```

## Troubleshooting

### Port Already in Use

```bash
# Dev is probably still running
uv run cli compose-down

# Or use different ports in .env.staging
```

### Workers Not Scaling

```bash
# Check service status
docker service ps adit-staging_mass_transfer_worker

# Common issue: not enough resources
# Swarm won't schedule if host is resource-constrained
```

### Can't Access localhost:8000

```bash
# Check if web service is running
docker service ps adit-staging_web

# Check logs
docker service logs adit-staging_web

# Verify port mapping
docker service inspect adit-staging_web --pretty
```

### Database Connection Issues

```bash
# Each service needs time to start
# Check postgres is ready:
docker service ps adit-staging_postgres

# Check logs for "database system is ready"
docker service logs adit-staging_postgres
```

## Comparison: Dev vs Staging vs Production

```
┌──────────────────────────────────────────────────────────────┐
│ Development (docker compose up)                              │
├──────────────────────────────────────────────────────────────┤
│ Command:   uv run cli compose-up -- --scale worker=3        │
│ URL:       http://localhost:8000                            │
│ Ports:     8000, 5432, 11122, 7501, 7502                    │
│ Settings:  DEBUG=True, debug toolbar, console email         │
│ Workers:   Manual scaling with --scale flag                 │
│ Restart:   Manual (container stops if it crashes)           │
│ Use for:   Local development                                │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ Staging (docker swarm - dev settings)                        │
├──────────────────────────────────────────────────────────────┤
│ Command:   docker stack deploy ... adit-staging             │
│ URL:       http://localhost:8001                            │
│ Ports:     8001, 5433, 11123, 7503, 7504                    │
│ Settings:  DEBUG=True, debug toolbar, console email         │
│ Workers:   Swarm replicas, auto-scale, auto-restart         │
│ Restart:   Automatic (Swarm reschedules failed containers)  │
│ Use for:   Testing worker scaling, Swarm deployment         │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ Production (docker swarm - production settings)              │
├──────────────────────────────────────────────────────────────┤
│ Command:   docker stack deploy ... adit-prod                │
│ URL:       https://adit.example.com                         │
│ Ports:     80, 443, 11112                                   │
│ Settings:  DEBUG=False, real SSL, SMTP email                │
│ Workers:   Swarm replicas, multi-node, auto-restart         │
│ Restart:   Automatic across multiple servers                │
│ Use for:   Real clinical use                                │
└──────────────────────────────────────────────────────────────┘
```

## Summary

**Staging is dev mode on Swarm with different ports** - that's it!

```bash
# Just use your existing .env (ports already defined in example.env)
# No .env.staging needed!

# Deploy to Swarm
docker swarm init
docker stack deploy -c docker-compose.base.yml -c docker-compose.staging.yml adit-staging

# Starts with 3 mass_transfer_workers by default
# Scale if needed:
docker service scale adit-staging_mass_transfer_worker=5

# Access on different port from dev
http://localhost:8001

# Cleanup
docker stack rm adit-staging
```

**Port allocation** (all three can run simultaneously):
- Dev: 8000, 5432, 11122, 7501, 7502
- Staging: 8001, 5433, 11123, 7503, 7504
- Production: 80, 443, 11112

**No .env.staging, no SSL, no special config** - just use your .env and deploy!
