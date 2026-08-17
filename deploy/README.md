# KoruFlux Intelligence System — Deployment Guide

## Option A: Quick Local Access (5 minutes)
Share the HTML files directly — no server needed.

```bash
# Open the hub in your browser
xdg-open data/dashboards/index.html

# Or start the web UI locally
python webui/app.py
# Open: http://localhost:5000
```

---

## Option B: VPS Hosting (30 minutes)

### 1. Get a VPS
Recommended: Hetzner CX22 (~€4/month) or DigitalOcean Droplet ($6/month)
- OS: Ubuntu 22.04
- RAM: 2GB minimum
- Location: Frankfurt (EU) or Nairobi/Johannesburg (Africa)

### 2. Upload the project
```bash
# From your local machine
scp -r koruflux_intel_v6/ root@YOUR_SERVER_IP:/tmp/koruflux_setup
```

### 3. Run setup
```bash
ssh root@YOUR_SERVER_IP
cd /tmp/koruflux_setup
DOMAIN=intelligence.koruflux.com bash deploy/setup_server.sh
```

### 4. Add SSL certificate
```bash
apt install certbot python3-certbot-nginx
certbot --nginx -d intelligence.koruflux.com
```

### 5. Set your API keys (optional but recommended)
```bash
# Edit the service file to add environment variables
nano /etc/systemd/system/koruflux.service

# Add under [Service]:
Environment="ANTHROPIC_API_KEY=sk-ant-YOUR_KEY"
Environment="TWITTER_BEARER_TOKEN=YOUR_TOKEN"

systemctl daemon-reload && systemctl restart koruflux
```

---

## Option C: Add Basic Auth (password protect the UI)

```bash
apt install apache2-utils
htpasswd -c /etc/nginx/.htpasswd koruflux
# Enter password when prompted

# Add to nginx location / block:
#   auth_basic "KoruFlux Intelligence";
#   auth_basic_user_file /etc/nginx/.htpasswd;

systemctl restart nginx
```

---

## Useful Commands

```bash
# Check service status
systemctl status koruflux

# Watch live logs
journalctl -u koruflux -f

# Manually trigger pipeline
sudo -u koruflux bash -c "cd /opt/koruflux/app && /opt/koruflux/venv/bin/python main.py"

# Check cron log
tail -f /opt/koruflux/cron.log

# Update the project
scp -r koruflux_intel_v6/ root@YOUR_SERVER_IP:/tmp/new_version
ssh root@YOUR_SERVER_IP "cp -r /tmp/new_version/* /opt/koruflux/app/ && systemctl restart koruflux"
```

---

## Recommended VPS Providers

| Provider | Plan | Price | Location |
|---|---|---|---|
| Hetzner | CX22 | €3.79/mo | Frankfurt / Helsinki |
| DigitalOcean | Basic Droplet | $6/mo | London / Frankfurt |
| Vultr | Cloud Compute | $6/mo | London / Amsterdam |
| Linode | Nanode | $5/mo | Frankfurt |

All support Ubuntu 22.04 and one-click SSH setup.

---

## Domain Setup (intelligence.koruflux.com)

1. Log into your domain registrar (where koruflux.com is managed)
2. Add an A record: `intelligence` → `YOUR_SERVER_IP`
3. Wait 5-10 minutes for DNS propagation
4. Run certbot for SSL (step 4 above)
