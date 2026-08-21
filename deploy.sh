#!/bin/bash
# ============================================================
# EC2 Deployment Script — Domain Intelligence API
# Run this on your EC2 Ubuntu instance after uploading files
# ============================================================

set -e  # Exit on any error

echo "=== Step 1: Update system ==="
sudo apt update && sudo apt upgrade -y

echo "=== Step 2: Install dependencies ==="
sudo apt install -y python3-pip python3-venv nginx git unzip

echo "=== Step 3: Install dnspython system dependency ==="
sudo apt install -y python3-dns

echo "=== Step 4: Create virtual environment ==="
cd /home/ubuntu/domain_collector
python3 -m venv venv
source venv/bin/activate

echo "=== Step 5: Install Python packages ==="
pip install --upgrade pip
pip install -r requirements.txt

echo "=== Step 6: Create .env file ==="
if [ ! -f .env ]; then
cat > .env << 'EOF'
APP_NAME=Domain Intelligence API
APP_VERSION=1.0.0
DEBUG=False
DATABASE_URL=sqlite:///./domain_intelligence.db
LOG_LEVEL=INFO
REQUEST_TIMEOUT=15.0
USER_AGENT=DomainIntelligenceBot/1.0 (+business-research)
MAX_PAGE_SIZE=2000000
MAX_RESPONSE_SIZE=2000000
MAX_PAGES_PER_SCAN=3
REQUEST_DELAY=0.5
EOF
echo ".env created"
fi

echo "=== Step 7: Set up systemd service ==="
sudo cp domain-intelligence.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable domain-intelligence
sudo systemctl start domain-intelligence

echo "=== Step 8: Set up Nginx ==="
sudo cp nginx.conf /etc/nginx/sites-available/domain-intelligence
sudo ln -sf /etc/nginx/sites-available/domain-intelligence /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx

echo ""
echo "=========================================="
echo " DEPLOYMENT COMPLETE!"
echo " API is running at: http://$(curl -s ifconfig.me)"
echo " Swagger UI:        http://$(curl -s ifconfig.me)/docs"
echo "=========================================="
