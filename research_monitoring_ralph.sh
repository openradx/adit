#!/bin/bash

# ============================================================================
# Ralph Wiggum Monitoring Research Loop
# "I'm learnding!" - Ralph Wiggum
# ============================================================================

# Colors for pretty output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Ralph Wiggum quotes
RALPH_QUOTES=(
    "Me fail monitoring? That's unpossible!"
    "I'm learnding about Prometheus!"
    "My cat's breath smells like metrics."
    "When I grow up, I want to be a principal or a caterpillar or a monitoring service."
    "The doctor said I wouldn't have so many alerts if I kept my fingers out of it."
    "Hi Super Nintendo Chalmers! Look at my dashboards!"
    "I bent my CPU."
    "That's where I saw the Grafana! He told me to burn things."
    "My logs taste like burning."
    "I found a container! And I'm gonna name it Kubernetes!"
    "I'm a monitoring unity."
    "Even my uvula is collecting metrics!"
    "Go banana metrics!"
    "Mrs. Krabappel and Principal Skinner were in the closet making babies and I saw one of the babies and the baby looked at me and said 'enable health checks'."
    "I heard your server cry itself to sleep."
)

# Output file for research results
OUTPUT_FILE="monitoring_research_results.md"

# Function to get a random Ralph quote
ralph_says() {
    echo -e "${YELLOW}Ralph: ${RALPH_QUOTES[$RANDOM % ${#RALPH_QUOTES[@]}]}${NC}"
    echo ""
}

# Function to print a section header
print_header() {
    echo -e "${CYAN}============================================================================${NC}"
    echo -e "${GREEN}$1${NC}"
    echo -e "${CYAN}============================================================================${NC}"
    ralph_says
}

# Function to add to research file
add_to_research() {
    echo "$1" >> "$OUTPUT_FILE"
}

# Clear the output file
echo "# Lightweight Monitoring Services Research for ADIT" > "$OUTPUT_FILE"
echo "Generated on: $(date)" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"
echo "---" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

echo -e "${PURPLE}"
echo "    ╔═══════════════════════════════════════════════════════════════════╗"
echo "    ║     RALPH WIGGUM'S MONITORING RESEARCH LOOP                       ║"
echo "    ║     'I choo-choo-choose you, Prometheus!'                         ║"
echo "    ╚═══════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
ralph_says

# ============================================================================
# RESEARCH LOOP - Monitoring Services
# ============================================================================

declare -A MONITORING_SERVICES

# Define lightweight monitoring services to research
MONITORING_SERVICES=(
    ["prometheus"]="Prometheus - Pull-based time-series monitoring with powerful query language"
    ["grafana"]="Grafana - Beautiful dashboards and visualization platform"
    ["cadvisor"]="cAdvisor - Container resource usage and performance metrics"
    ["node_exporter"]="Node Exporter - Hardware and OS metrics for Prometheus"
    ["loki"]="Loki - Log aggregation system by Grafana Labs"
    ["uptime_kuma"]="Uptime Kuma - Self-hosted monitoring tool (like Uptime Robot)"
    ["netdata"]="Netdata - Real-time performance monitoring"
    ["healthchecks"]="Healthchecks.io - Cron job and scheduled task monitoring"
)

echo -e "${BLUE}Starting research loop... (Press Ctrl+C to stop)${NC}"
echo ""
sleep 1

LOOP_COUNT=0

for service in "${!MONITORING_SERVICES[@]}"; do
    ((LOOP_COUNT++))

    print_header "Researching: ${MONITORING_SERVICES[$service]}"

    add_to_research "## $LOOP_COUNT. ${service^^}"
    add_to_research ""
    add_to_research "**Description:** ${MONITORING_SERVICES[$service]}"
    add_to_research ""

    case $service in
        "prometheus")
            add_to_research "### Overview"
            add_to_research "- Pull-based monitoring system with a built-in time-series database"
            add_to_research "- Excellent for monitoring Docker containers and Kubernetes"
            add_to_research "- Native support for Django via django-prometheus"
            add_to_research ""
            add_to_research "### Integration with ADIT (Django)"
            add_to_research "\`\`\`python"
            add_to_research "# In settings.py"
            add_to_research "INSTALLED_APPS = ["
            add_to_research "    # ..."
            add_to_research "    'django_prometheus',"
            add_to_research "]"
            add_to_research ""
            add_to_research "MIDDLEWARE = ["
            add_to_research "    'django_prometheus.middleware.PrometheusBeforeMiddleware',"
            add_to_research "    # ... other middleware"
            add_to_research "    'django_prometheus.middleware.PrometheusAfterMiddleware',"
            add_to_research "]"
            add_to_research "\`\`\`"
            add_to_research ""
            add_to_research "### Docker Compose Addition"
            add_to_research "\`\`\`yaml"
            add_to_research "prometheus:"
            add_to_research "  image: prom/prometheus:latest"
            add_to_research "  volumes:"
            add_to_research "    - ./prometheus.yml:/etc/prometheus/prometheus.yml"
            add_to_research "    - prometheus_data:/prometheus"
            add_to_research "  ports:"
            add_to_research "    - '9090:9090'"
            add_to_research "  restart: unless-stopped"
            add_to_research "\`\`\`"
            add_to_research ""
            add_to_research "### Resource Usage"
            add_to_research "- Memory: ~200-500MB depending on metrics volume"
            add_to_research "- CPU: Low to moderate"
            add_to_research "- Storage: Depends on retention period"
            add_to_research ""
            echo -e "${GREEN}[+] Prometheus research complete!${NC}"
            ;;

        "grafana")
            add_to_research "### Overview"
            add_to_research "- Industry standard for metrics visualization"
            add_to_research "- Supports multiple data sources (Prometheus, Loki, PostgreSQL)"
            add_to_research "- Rich alerting capabilities"
            add_to_research ""
            add_to_research "### Docker Compose Addition"
            add_to_research "\`\`\`yaml"
            add_to_research "grafana:"
            add_to_research "  image: grafana/grafana:latest"
            add_to_research "  volumes:"
            add_to_research "    - grafana_data:/var/lib/grafana"
            add_to_research "  environment:"
            add_to_research "    - GF_SECURITY_ADMIN_PASSWORD=admin"
            add_to_research "    - GF_USERS_ALLOW_SIGN_UP=false"
            add_to_research "  ports:"
            add_to_research "    - '3000:3000'"
            add_to_research "  restart: unless-stopped"
            add_to_research "\`\`\`"
            add_to_research ""
            add_to_research "### Useful Dashboards for ADIT"
            add_to_research "- Django Prometheus Dashboard (ID: 17658)"
            add_to_research "- Docker Container Metrics (ID: 893)"
            add_to_research "- PostgreSQL Database (ID: 9628)"
            add_to_research "- Node Exporter Full (ID: 1860)"
            add_to_research ""
            add_to_research "### Resource Usage"
            add_to_research "- Memory: ~100-200MB"
            add_to_research "- CPU: Very low"
            add_to_research ""
            echo -e "${GREEN}[+] Grafana research complete!${NC}"
            ;;

        "cadvisor")
            add_to_research "### Overview"
            add_to_research "- Analyzes resource usage of running containers"
            add_to_research "- Built by Google, lightweight and efficient"
            add_to_research "- Native Prometheus metrics endpoint"
            add_to_research ""
            add_to_research "### Docker Compose Addition"
            add_to_research "\`\`\`yaml"
            add_to_research "cadvisor:"
            add_to_research "  image: gcr.io/cadvisor/cadvisor:latest"
            add_to_research "  volumes:"
            add_to_research "    - /:/rootfs:ro"
            add_to_research "    - /var/run:/var/run:ro"
            add_to_research "    - /sys:/sys:ro"
            add_to_research "    - /var/lib/docker/:/var/lib/docker:ro"
            add_to_research "  ports:"
            add_to_research "    - '8080:8080'"
            add_to_research "  restart: unless-stopped"
            add_to_research "\`\`\`"
            add_to_research ""
            add_to_research "### ADIT-Specific Metrics"
            add_to_research "- Worker container CPU/Memory usage"
            add_to_research "- Receiver container network I/O"
            add_to_research "- PostgreSQL container disk I/O"
            add_to_research ""
            add_to_research "### Resource Usage"
            add_to_research "- Memory: ~50-100MB"
            add_to_research "- CPU: Very low"
            add_to_research ""
            echo -e "${GREEN}[+] cAdvisor research complete!${NC}"
            ;;

        "node_exporter")
            add_to_research "### Overview"
            add_to_research "- Exposes hardware and OS metrics"
            add_to_research "- Essential for monitoring the Docker host"
            add_to_research "- Works with Prometheus"
            add_to_research ""
            add_to_research "### Docker Compose Addition"
            add_to_research "\`\`\`yaml"
            add_to_research "node-exporter:"
            add_to_research "  image: prom/node-exporter:latest"
            add_to_research "  volumes:"
            add_to_research "    - /proc:/host/proc:ro"
            add_to_research "    - /sys:/host/sys:ro"
            add_to_research "    - /:/rootfs:ro"
            add_to_research "  command:"
            add_to_research "    - '--path.procfs=/host/proc'"
            add_to_research "    - '--path.sysfs=/host/sys'"
            add_to_research "    - '--collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)'"
            add_to_research "  ports:"
            add_to_research "    - '9100:9100'"
            add_to_research "  restart: unless-stopped"
            add_to_research "\`\`\`"
            add_to_research ""
            add_to_research "### Resource Usage"
            add_to_research "- Memory: ~20-50MB"
            add_to_research "- CPU: Minimal"
            add_to_research ""
            echo -e "${GREEN}[+] Node Exporter research complete!${NC}"
            ;;

        "loki")
            add_to_research "### Overview"
            add_to_research "- Log aggregation system inspired by Prometheus"
            add_to_research "- Cost-effective: indexes labels, not log content"
            add_to_research "- Integrates seamlessly with Grafana"
            add_to_research ""
            add_to_research "### Docker Compose Addition"
            add_to_research "\`\`\`yaml"
            add_to_research "loki:"
            add_to_research "  image: grafana/loki:latest"
            add_to_research "  volumes:"
            add_to_research "    - loki_data:/loki"
            add_to_research "  ports:"
            add_to_research "    - '3100:3100'"
            add_to_research "  restart: unless-stopped"
            add_to_research ""
            add_to_research "promtail:"
            add_to_research "  image: grafana/promtail:latest"
            add_to_research "  volumes:"
            add_to_research "    - /var/log:/var/log:ro"
            add_to_research "    - /var/lib/docker/containers:/var/lib/docker/containers:ro"
            add_to_research "    - ./promtail-config.yml:/etc/promtail/config.yml"
            add_to_research "  restart: unless-stopped"
            add_to_research "\`\`\`"
            add_to_research ""
            add_to_research "### ADIT Log Sources"
            add_to_research "- Django application logs"
            add_to_research "- DICOM transfer worker logs"
            add_to_research "- Receiver container logs"
            add_to_research "- Celery task logs"
            add_to_research ""
            add_to_research "### Resource Usage"
            add_to_research "- Memory: ~100-300MB"
            add_to_research "- CPU: Low"
            add_to_research ""
            echo -e "${GREEN}[+] Loki research complete!${NC}"
            ;;

        "uptime_kuma")
            add_to_research "### Overview"
            add_to_research "- Self-hosted uptime monitoring tool"
            add_to_research "- Beautiful UI, easy to set up"
            add_to_research "- Multiple notification channels"
            add_to_research ""
            add_to_research "### Docker Compose Addition"
            add_to_research "\`\`\`yaml"
            add_to_research "uptime-kuma:"
            add_to_research "  image: louislam/uptime-kuma:latest"
            add_to_research "  volumes:"
            add_to_research "    - uptime_kuma_data:/app/data"
            add_to_research "  ports:"
            add_to_research "    - '3001:3001'"
            add_to_research "  restart: unless-stopped"
            add_to_research "\`\`\`"
            add_to_research ""
            add_to_research "### ADIT Health Checks"
            add_to_research "- HTTP endpoint monitoring for Django app"
            add_to_research "- DICOM ping for connected PACS servers"
            add_to_research "- PostgreSQL connection check"
            add_to_research "- Worker heartbeat monitoring"
            add_to_research ""
            add_to_research "### Resource Usage"
            add_to_research "- Memory: ~100-150MB"
            add_to_research "- CPU: Very low"
            add_to_research ""
            echo -e "${GREEN}[+] Uptime Kuma research complete!${NC}"
            ;;

        "netdata")
            add_to_research "### Overview"
            add_to_research "- Real-time performance monitoring"
            add_to_research "- Zero configuration for most use cases"
            add_to_research "- Beautiful built-in dashboards"
            add_to_research ""
            add_to_research "### Docker Compose Addition"
            add_to_research "\`\`\`yaml"
            add_to_research "netdata:"
            add_to_research "  image: netdata/netdata:latest"
            add_to_research "  cap_add:"
            add_to_research "    - SYS_PTRACE"
            add_to_research "  security_opt:"
            add_to_research "    - apparmor:unconfined"
            add_to_research "  volumes:"
            add_to_research "    - netdataconfig:/etc/netdata"
            add_to_research "    - netdatalib:/var/lib/netdata"
            add_to_research "    - netdatacache:/var/cache/netdata"
            add_to_research "    - /etc/passwd:/host/etc/passwd:ro"
            add_to_research "    - /etc/group:/host/etc/group:ro"
            add_to_research "    - /proc:/host/proc:ro"
            add_to_research "    - /sys:/host/sys:ro"
            add_to_research "    - /var/run/docker.sock:/var/run/docker.sock:ro"
            add_to_research "  ports:"
            add_to_research "    - '19999:19999'"
            add_to_research "  restart: unless-stopped"
            add_to_research "\`\`\`"
            add_to_research ""
            add_to_research "### Resource Usage"
            add_to_research "- Memory: ~100-200MB"
            add_to_research "- CPU: Low (1-3%)"
            add_to_research ""
            echo -e "${GREEN}[+] Netdata research complete!${NC}"
            ;;

        "healthchecks")
            add_to_research "### Overview"
            add_to_research "- Cron job and scheduled task monitoring"
            add_to_research "- Perfect for monitoring ADIT's background workers"
            add_to_research "- Alerts on missed check-ins"
            add_to_research ""
            add_to_research "### Docker Compose Addition"
            add_to_research "\`\`\`yaml"
            add_to_research "healthchecks:"
            add_to_research "  image: healthchecks/healthchecks:latest"
            add_to_research "  environment:"
            add_to_research "    - DB=sqlite"
            add_to_research "    - SECRET_KEY=your-secret-key-here"
            add_to_research "    - ALLOWED_HOSTS=*"
            add_to_research "  volumes:"
            add_to_research "    - healthchecks_data:/data"
            add_to_research "  ports:"
            add_to_research "    - '8000:8000'"
            add_to_research "  restart: unless-stopped"
            add_to_research "\`\`\`"
            add_to_research ""
            add_to_research "### ADIT Integration"
            add_to_research "\`\`\`python"
            add_to_research "# In worker task completion"
            add_to_research "import requests"
            add_to_research "requests.get('http://healthchecks:8000/ping/<uuid>')"
            add_to_research "\`\`\`"
            add_to_research ""
            add_to_research "### Resource Usage"
            add_to_research "- Memory: ~50-100MB"
            add_to_research "- CPU: Minimal"
            add_to_research ""
            echo -e "${GREEN}[+] Healthchecks research complete!${NC}"
            ;;
    esac

    add_to_research "---"
    add_to_research ""

    ralph_says
    sleep 1
done

# ============================================================================
# RECOMMENDATIONS SECTION
# ============================================================================

print_header "Generating Recommendations for ADIT"

add_to_research "## Recommendations for ADIT"
add_to_research ""
add_to_research "### Minimal Stack (Low Resource Usage)"
add_to_research "For a lightweight monitoring setup:"
add_to_research "1. **Uptime Kuma** - Simple health checks and uptime monitoring"
add_to_research "2. **Healthchecks.io** - Worker/task monitoring"
add_to_research ""
add_to_research "### Standard Stack (Recommended)"
add_to_research "For comprehensive monitoring:"
add_to_research "1. **Prometheus** - Metrics collection"
add_to_research "2. **Grafana** - Visualization and alerting"
add_to_research "3. **cAdvisor** - Container metrics"
add_to_research "4. **django-prometheus** - Django application metrics"
add_to_research ""
add_to_research "### Full Stack (Enterprise)"
add_to_research "For complete observability:"
add_to_research "1. Everything in Standard Stack"
add_to_research "2. **Loki + Promtail** - Log aggregation"
add_to_research "3. **Node Exporter** - Host metrics"
add_to_research "4. **Alertmanager** - Advanced alerting"
add_to_research ""
add_to_research "### ADIT-Specific Metrics to Monitor"
add_to_research "- Transfer job success/failure rates"
add_to_research "- Transfer task queue length"
add_to_research "- Worker processing time"
add_to_research "- DICOM connection health (C-ECHO)"
add_to_research "- Database connection pool"
add_to_research "- Storage space for temporary DICOM files"
add_to_research ""
add_to_research "### Example prometheus.yml for ADIT"
add_to_research "\`\`\`yaml"
add_to_research "global:"
add_to_research "  scrape_interval: 15s"
add_to_research ""
add_to_research "scrape_configs:"
add_to_research "  - job_name: 'adit-django'"
add_to_research "    static_configs:"
add_to_research "      - targets: ['web:8000']"
add_to_research ""
add_to_research "  - job_name: 'cadvisor'"
add_to_research "    static_configs:"
add_to_research "      - targets: ['cadvisor:8080']"
add_to_research ""
add_to_research "  - job_name: 'node-exporter'"
add_to_research "    static_configs:"
add_to_research "      - targets: ['node-exporter:9100']"
add_to_research "\`\`\`"
add_to_research ""

echo -e "${PURPLE}"
echo "    ╔═══════════════════════════════════════════════════════════════════╗"
echo "    ║     RESEARCH COMPLETE!                                            ║"
echo "    ║     Results saved to: $OUTPUT_FILE                                ║"
echo "    ╚═══════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

ralph_says

echo -e "${GREEN}Research Summary:${NC}"
echo -e "  - Researched ${LOOP_COUNT} lightweight monitoring services"
echo -e "  - Generated integration examples for Django/Docker"
echo -e "  - Created ADIT-specific recommendations"
echo ""
echo -e "${YELLOW}Ralph's Final Words: 'I'm a monitoring star!'${NC}"
echo ""
echo -e "${BLUE}To view the full research results:${NC}"
echo -e "  cat $OUTPUT_FILE"
echo ""
