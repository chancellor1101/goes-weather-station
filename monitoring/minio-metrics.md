# MinIO -> Prometheus

Enable public scrape on the MinIO server (LXC 203), then restart:

    echo 'MINIO_PROMETHEUS_AUTH_TYPE=public' >> /etc/default/minio
    systemctl restart minio

Metrics: `http://10.10.0.10:80/minio/v2/metrics/cluster`
Grafana dashboard: grafana.com id **13502** (imported as uid `TgmJnqnnk`).
GOES receiver dashboard: `grafana/goes-receiver-dashboard.json` (uid `goes-ns-receiver`).
