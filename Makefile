PYTHON=python3.12
VENV=.venv
SERVER_IP=$(shell cd terraform && terraform output -raw droplet_ip 2>/dev/null)

.PHONY: help setup run lint test build deploy logs ssh health status infra-init infra-plan infra-apply destroy

help:
	@echo "Development:"
	@echo "  make setup      - Install dependencies"
	@echo "  make run        - Run bot locally"
	@echo "  make lint       - Run linter"
	@echo "  make test       - Run tests"
	@echo "  make build      - Build Docker image"
	@echo ""
	@echo "Production:"
	@echo "  make deploy     - Full deploy (build + push + restart)"
	@echo "  make status     - Show all service statuses"
	@echo "  make health     - Check health endpoint"
	@echo "  make logs       - View bot logs"
	@echo "  make logs-mono  - View Monero wallet logs"
	@echo "  make ssh        - SSH into server"
	@echo "  make restart    - Restart bot service"
	@echo ""
	@echo "Infrastructure:"
	@echo "  make infra-init   - Initialize Terraform"
	@echo "  make infra-plan   - Plan infrastructure changes"
	@echo "  make infra-apply  - Apply infrastructure"
	@echo "  make destroy      - Destroy infrastructure"

# Development
setup:
	pyenv install -s 3.12.10
	pyenv virtualenv -f 3.12.10 $(VENV)
	$(VENV)/bin/pip install poetry
	$(VENV)/bin/poetry install

run:
	$(VENV)/bin/poetry run python -m bot.main

lint:
	$(VENV)/bin/poetry run ruff bot tests
	$(VENV)/bin/poetry run mypy bot

test:
	$(VENV)/bin/poetry run pytest --cov=bot --cov-branch --cov-fail-under=100

build:
	docker build -t telegram-bot .

# Production - Full Deploy
deploy:
	@echo "=== Deploying to production ==="
	@git commit --allow-empty -m "Deploy: $$(date +%Y-%m-%d_%H:%M:%S)" && git push origin main
	@echo ""
	@echo "Build started. Monitor: https://github.com/andrefigueira/telegram-bot/actions"
	@echo ""
	@echo "Once complete, run 'make status' to verify."

# Production - Status & Monitoring
status:
	@echo "=== Server: $(SERVER_IP) ==="
	@echo ""
	@echo "--- Health Check ---"
	@curl -sf http://$(SERVER_IP):8080/health 2>/dev/null && echo " [OK]" || echo "[FAIL]"
	@echo ""
	@echo "--- Bot Service ---"
	@ssh root@$(SERVER_IP) "systemctl status telegram-bot --no-pager -l" 2>/dev/null || echo "Cannot connect"
	@echo ""
	@echo "--- Monero Wallet RPC ---"
	@ssh root@$(SERVER_IP) "systemctl status monero-wallet-rpc --no-pager -l" 2>/dev/null || echo "Cannot connect"
	@echo ""
	@echo "--- Docker Containers ---"
	@ssh root@$(SERVER_IP) "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'" 2>/dev/null || echo "Cannot connect"
	@echo ""
	@echo "--- Database ---"
	@ssh root@$(SERVER_IP) "ls -lh /opt/telegram-bot/data/*.sqlite3 2>/dev/null || echo 'No database file'" 2>/dev/null || echo "Cannot connect"
	@echo ""
	@echo "--- Disk Usage ---"
	@ssh root@$(SERVER_IP) "df -h / | tail -1" 2>/dev/null || echo "Cannot connect"
	@echo ""
	@echo "--- Memory ---"
	@ssh root@$(SERVER_IP) "free -h | head -2" 2>/dev/null || echo "Cannot connect"

health:
	@curl -sf http://$(SERVER_IP):8080/health | python3 -m json.tool || echo "Server not healthy"

ready:
	@curl -sf http://$(SERVER_IP):8080/ready | python3 -m json.tool || echo "Server not ready"

logs:
	@ssh root@$(SERVER_IP) "docker-compose -f /opt/telegram-bot/docker-compose.yml logs -f --tail=100"

logs-monero:
	@ssh root@$(SERVER_IP) "journalctl -u monero-wallet-rpc -f --no-pager -n 50"

logs-all:
	@ssh root@$(SERVER_IP) "journalctl -u telegram-bot -u monero-wallet-rpc -f --no-pager -n 100"

ssh:
	@ssh root@$(SERVER_IP)

restart:
	@echo "Restarting bot..."
	@ssh root@$(SERVER_IP) "cd /opt/telegram-bot && docker-compose restart"
	@sleep 3
	@make health

restart-monero:
	@echo "Restarting Monero wallet RPC..."
	@ssh root@$(SERVER_IP) "systemctl restart monero-wallet-rpc"

restart-all:
	@echo "Restarting all services..."
	@ssh root@$(SERVER_IP) "systemctl restart monero-wallet-rpc && cd /opt/telegram-bot && docker-compose restart"
	@sleep 5
	@make status

# Database
db-backup:
	@echo "Backing up database..."
	@ssh root@$(SERVER_IP) "cp /opt/telegram-bot/data/db.sqlite3 /opt/telegram-bot/data/db.sqlite3.backup-$$(date +%Y%m%d_%H%M%S)"
	@echo "Backup complete"

db-download:
	@echo "Downloading database..."
	@scp root@$(SERVER_IP):/opt/telegram-bot/data/db.sqlite3 ./db-backup-$$(date +%Y%m%d).sqlite3
	@echo "Downloaded to ./db-backup-$$(date +%Y%m%d).sqlite3"

# Monero
monero-status:
	@echo "=== Monero Wallet RPC Status ==="
	@ssh root@$(SERVER_IP) "curl -s http://localhost:18082/json_rpc -d '{\"jsonrpc\":\"2.0\",\"id\":\"0\",\"method\":\"get_version\"}' -H 'Content-Type: application/json'" | python3 -m json.tool 2>/dev/null || echo "Monero RPC not responding"

monero-balance:
	@ssh root@$(SERVER_IP) "curl -s http://localhost:18082/json_rpc -d '{\"jsonrpc\":\"2.0\",\"id\":\"0\",\"method\":\"get_balance\"}' -H 'Content-Type: application/json'" | python3 -m json.tool 2>/dev/null || echo "Monero RPC not responding"

# Security
firewall-status:
	@ssh root@$(SERVER_IP) "ufw status verbose"

fail2ban-status:
	@ssh root@$(SERVER_IP) "fail2ban-client status sshd"

# Infrastructure
infra-init:
	cd terraform && terraform init

infra-plan:
	cd terraform && terraform plan

infra-apply:
	cd terraform && terraform apply

infra-output:
	@cd terraform && terraform output

destroy:
	@echo "WARNING: This will destroy all infrastructure!"
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	cd terraform && terraform destroy
