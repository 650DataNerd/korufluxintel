#!/bin/bash
# ============================================================
# KoruFlux Intelligence System — VPS Setup Script
# ============================================================
# Run this on a fresh Ubuntu 22.04 VPS (DigitalOcean / Hetzner)
# as root:  bash setup_server.sh
#
# What it does:
#   1. Updates system + installs Python, Nginx, Git
#   2. Creates a koruflux system user
#   3. Clones/copies the project
#   4. Creates Python venv + installs deps
#   5. Creates systemd service (auto-restart on crash)
#   6. Sets up Nginx reverse proxy
#   7. Configures daily cron for data refresh
# ============================================================

set -e  # Exit on any error

PROJECT_DIR="/opt/koruflux"
SERVICE_USER="koruflux"
DOMAIN="${DOMAIN:-localhost}"   # Set: DOMAIN=intelligence.koruflux.com bash setup_server.sh
PORT=5000

echo "=================================================="
echo "  KoruFlux Intelligence System — Server Setup"
echo "  Domain: $DOMAIN"
echo "=================================================="

# ── 1. System update + dependencies ──────────────────────────
echo "[1/7] Updating system..."
apt-get update -qq
apt-get install -y -qq \
    python3 python3-pip python3-venv \
    nginx git curl unzip \
    poppler-utils \
    build-essential libssl-dev

# ── 2. Create system user ─────────────────────────────────────
echo "[2/7] Creating service user..."
id -u $SERVICE_USER &>/dev/null || useradd -r -m -d $PROJECT_DIR -s /bin/bash $SERVICE_USER

# ── 3. Copy project ───────────────────────────────────────────
echo "[3/7] Setting up project directory..."
mkdir -p $PROJECT_DIR
cp -r . $PROJECT_DIR/app
chown -R $SERVICE_USER:$SERVICE_USER $PROJECT_DIR

# ── 4. Python environment ─────────────────────────────────────
echo "[4/7] Installing Python dependencies..."
sudo -u $SERVICE_USER python3 -m venv $PROJECT_DIR/venv
sudo -u $SERVICE_USER $PROJECT_DIR/venv/bin/pip install --quiet \
    pyyaml requests beautifulsoup4 lxml \
    matplotlib openpyxl flask \
    pypdf numpy

# ── 5. Systemd service ────────────────────────────────────────
echo "[5/7] Creating systemd service..."
cat > /etc/systemd/system/koruflux.service << EOF
[Unit]
Description=KoruFlux Intelligence System
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$PROJECT_DIR/app
Environment="PATH=$PROJECT_DIR/venv/bin"
Environment="PYTHONPATH=$PROJECT_DIR/app"
ExecStart=$PROJECT_DIR/venv/bin/python webui/app.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=koruflux

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable koruflux
systemctl start koruflux
echo "  Service started: $(systemctl is-active koruflux)"

# ── 6. Nginx reverse proxy ────────────────────────────────────
echo "[6/7] Configuring Nginx..."
cat > /etc/nginx/sites-available/koruflux << EOF
server {
    listen 80;
    server_name $DOMAIN;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN";
    add_header X-Content-Type-Options "nosniff";
    add_header X-XSS-Protection "1; mode=block";

    # Proxy to Flask
    location / {
        proxy_pass http://127.0.0.1:$PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
        proxy_buffering off;
    }

    # SSE (live log streaming) — disable buffering
    location /stream-logs {
        proxy_pass http://127.0.0.1:$PORT;
        proxy_set_header Connection '';
        proxy_http_version 1.1;
        chunked_transfer_encoding on;
        proxy_buffering off;
        proxy_cache off;
    }

    # Static dashboard files served directly (faster)
    location /data/dashboards/ {
        alias $PROJECT_DIR/app/data/dashboards/;
        expires 1h;
        add_header Cache-Control "public";
    }
}
EOF

ln -sf /etc/nginx/sites-available/koruflux /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx
echo "  Nginx configured"

# ── 7. Daily cron ─────────────────────────────────────────────
echo "[7/7] Setting up daily data refresh..."
cat > /etc/cron.d/koruflux << EOF
# KoruFlux Intelligence — daily pipeline at 07:00 EAT (04:00 UTC)
0 4 * * * $SERVICE_USER cd $PROJECT_DIR/app && $PROJECT_DIR/venv/bin/python main.py >> $PROJECT_DIR/cron.log 2>&1
EOF
chmod 644 /etc/cron.d/koruflux

echo ""
echo "=================================================="
echo "  SETUP COMPLETE"
echo "=================================================="
echo "  Service: systemctl status koruflux"
echo "  Logs:    journalctl -u koruflux -f"
echo "  Cron:    tail -f $PROJECT_DIR/cron.log"
echo ""
echo "  Access:  http://$DOMAIN"
echo ""
echo "  Next: Run SSL certificate (if domain set):"
echo "    apt install certbot python3-certbot-nginx"
echo "    certbot --nginx -d $DOMAIN"
echo "=================================================="
