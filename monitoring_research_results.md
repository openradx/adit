# Lightweight Monitoring Services Research for ADIT
Generated on: Tue Jan 20 10:03:13 AM UTC 2026

---

## 1. PROMETHEUS

**Description:** Prometheus - Pull-based time-series monitoring with powerful query language

### Overview
- Pull-based monitoring system with a built-in time-series database
- Excellent for monitoring Docker containers and Kubernetes
- Native support for Django via django-prometheus

### Integration with ADIT (Django)
```python
# In settings.py
INSTALLED_APPS = [
    # ...
    'django_prometheus',
]

MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',
    # ... other middleware
    'django_prometheus.middleware.PrometheusAfterMiddleware',
]
```

### Docker Compose Addition
```yaml
prometheus:
  image: prom/prometheus:latest
  volumes:
    - ./prometheus.yml:/etc/prometheus/prometheus.yml
    - prometheus_data:/prometheus
  ports:
    - '9090:9090'
  restart: unless-stopped
```

### Resource Usage
- Memory: ~200-500MB depending on metrics volume
- CPU: Low to moderate
- Storage: Depends on retention period

---

## 2. GRAFANA

**Description:** Grafana - Beautiful dashboards and visualization platform

### Overview
- Industry standard for metrics visualization
- Supports multiple data sources (Prometheus, Loki, PostgreSQL)
- Rich alerting capabilities

### Docker Compose Addition
```yaml
grafana:
  image: grafana/grafana:latest
  volumes:
    - grafana_data:/var/lib/grafana
  environment:
    - GF_SECURITY_ADMIN_PASSWORD=admin
    - GF_USERS_ALLOW_SIGN_UP=false
  ports:
    - '3000:3000'
  restart: unless-stopped
```

### Useful Dashboards for ADIT
- Django Prometheus Dashboard (ID: 17658)
- Docker Container Metrics (ID: 893)
- PostgreSQL Database (ID: 9628)
- Node Exporter Full (ID: 1860)

### Resource Usage
- Memory: ~100-200MB
- CPU: Very low

---

## 3. CADVISOR

**Description:** cAdvisor - Container resource usage and performance metrics

### Overview
- Analyzes resource usage of running containers
- Built by Google, lightweight and efficient
- Native Prometheus metrics endpoint

### Docker Compose Addition
```yaml
cadvisor:
  image: gcr.io/cadvisor/cadvisor:latest
  volumes:
    - /:/rootfs:ro
    - /var/run:/var/run:ro
    - /sys:/sys:ro
    - /var/lib/docker/:/var/lib/docker:ro
  ports:
    - '8080:8080'
  restart: unless-stopped
```

### ADIT-Specific Metrics
- Worker container CPU/Memory usage
- Receiver container network I/O
- PostgreSQL container disk I/O

### Resource Usage
- Memory: ~50-100MB
- CPU: Very low

---

## 4. NETDATA

**Description:** Netdata - Real-time performance monitoring

### Overview
- Real-time performance monitoring
- Zero configuration for most use cases
- Beautiful built-in dashboards

### Docker Compose Addition
```yaml
netdata:
  image: netdata/netdata:latest
  cap_add:
    - SYS_PTRACE
  security_opt:
    - apparmor:unconfined
  volumes:
    - netdataconfig:/etc/netdata
    - netdatalib:/var/lib/netdata
    - netdatacache:/var/cache/netdata
    - /etc/passwd:/host/etc/passwd:ro
    - /etc/group:/host/etc/group:ro
    - /proc:/host/proc:ro
    - /sys:/host/sys:ro
    - /var/run/docker.sock:/var/run/docker.sock:ro
  ports:
    - '19999:19999'
  restart: unless-stopped
```

### Resource Usage
- Memory: ~100-200MB
- CPU: Low (1-3%)

---

## 5. UPTIME_KUMA

**Description:** Uptime Kuma - Self-hosted monitoring tool (like Uptime Robot)

### Overview
- Self-hosted uptime monitoring tool
- Beautiful UI, easy to set up
- Multiple notification channels

### Docker Compose Addition
```yaml
uptime-kuma:
  image: louislam/uptime-kuma:latest
  volumes:
    - uptime_kuma_data:/app/data
  ports:
    - '3001:3001'
  restart: unless-stopped
```

### ADIT Health Checks
- HTTP endpoint monitoring for Django app
- DICOM ping for connected PACS servers
- PostgreSQL connection check
- Worker heartbeat monitoring

### Resource Usage
- Memory: ~100-150MB
- CPU: Very low

---

## 6. HEALTHCHECKS

**Description:** Healthchecks.io - Cron job and scheduled task monitoring

### Overview
- Cron job and scheduled task monitoring
- Perfect for monitoring ADIT's background workers
- Alerts on missed check-ins

### Docker Compose Addition
```yaml
healthchecks:
  image: healthchecks/healthchecks:latest
  environment:
    - DB=sqlite
    - SECRET_KEY=your-secret-key-here
    - ALLOWED_HOSTS=*
  volumes:
    - healthchecks_data:/data
  ports:
    - '8000:8000'
  restart: unless-stopped
```

### ADIT Integration
```python
# In worker task completion
import requests
requests.get('http://healthchecks:8000/ping/<uuid>')
```

### Resource Usage
- Memory: ~50-100MB
- CPU: Minimal

---

## 7. NODE_EXPORTER

**Description:** Node Exporter - Hardware and OS metrics for Prometheus

### Overview
- Exposes hardware and OS metrics
- Essential for monitoring the Docker host
- Works with Prometheus

### Docker Compose Addition
```yaml
node-exporter:
  image: prom/node-exporter:latest
  volumes:
    - /proc:/host/proc:ro
    - /sys:/host/sys:ro
    - /:/rootfs:ro
  command:
    - '--path.procfs=/host/proc'
    - '--path.sysfs=/host/sys'
    - '--collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)(25389|/)'
  ports:
    - '9100:9100'
  restart: unless-stopped
```

### Resource Usage
- Memory: ~20-50MB
- CPU: Minimal

---

## 8. LOKI

**Description:** Loki - Log aggregation system by Grafana Labs

### Overview
- Log aggregation system inspired by Prometheus
- Cost-effective: indexes labels, not log content
- Integrates seamlessly with Grafana

### Docker Compose Addition
```yaml
loki:
  image: grafana/loki:latest
  volumes:
    - loki_data:/loki
  ports:
    - '3100:3100'
  restart: unless-stopped

promtail:
  image: grafana/promtail:latest
  volumes:
    - /var/log:/var/log:ro
    - /var/lib/docker/containers:/var/lib/docker/containers:ro
    - ./promtail-config.yml:/etc/promtail/config.yml
  restart: unless-stopped
```

### ADIT Log Sources
- Django application logs
- DICOM transfer worker logs
- Receiver container logs
- Celery task logs

### Resource Usage
- Memory: ~100-300MB
- CPU: Low

---

## Recommendations for ADIT

### Minimal Stack (Low Resource Usage)
For a lightweight monitoring setup:
1. **Uptime Kuma** - Simple health checks and uptime monitoring
2. **Healthchecks.io** - Worker/task monitoring

### Standard Stack (Recommended)
For comprehensive monitoring:
1. **Prometheus** - Metrics collection
2. **Grafana** - Visualization and alerting
3. **cAdvisor** - Container metrics
4. **django-prometheus** - Django application metrics

### Full Stack (Enterprise)
For complete observability:
1. Everything in Standard Stack
2. **Loki + Promtail** - Log aggregation
3. **Node Exporter** - Host metrics
4. **Alertmanager** - Advanced alerting

### ADIT-Specific Metrics to Monitor
- Transfer job success/failure rates
- Transfer task queue length
- Worker processing time
- DICOM connection health (C-ECHO)
- Database connection pool
- Storage space for temporary DICOM files

### Example prometheus.yml for ADIT
```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'adit-django'
    static_configs:
      - targets: ['web:8000']

  - job_name: 'cadvisor'
    static_configs:
      - targets: ['cadvisor:8080']

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']
```

