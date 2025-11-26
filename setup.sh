#!/bin/bash

# Telegram E-commerce Bot Setup Script

set -e

echo "========================================"
echo "  Telegram E-commerce Bot Setup"
echo "========================================"
echo ""

# Determine mode: development or production
MODE="${1:-dev}"

if [[ "$MODE" == "production" ]] || [[ "$MODE" == "prod" ]]; then
    echo "Running in PRODUCTION mode..."
    PRODUCTION=true
else
    echo "Running in DEVELOPMENT mode..."
    echo "(Use: ./setup.sh production for production setup)"
    PRODUCTION=false
fi

# Create required directories
echo ""
echo "Creating directories..."
mkdir -p data logs monero-wallet
chmod 700 monero-wallet
echo "Done."

# Check if .env exists
if [ ! -f .env ]; then
    echo ""
    echo "Creating .env file from template..."
    cp .env.template .env

    # Generate encryption key
    echo "Generating encryption key..."
    if command -v python3 &> /dev/null; then
        KEY=$(python3 -c "import base64, os; print(base64.b64encode(os.urandom(32)).decode())")
    else
        KEY=$(openssl rand -base64 32)
    fi

    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s/^ENCRYPTION_KEY=$/ENCRYPTION_KEY=$KEY/" .env
    else
        sed -i "s/^ENCRYPTION_KEY=$/ENCRYPTION_KEY=$KEY/" .env
    fi
    echo "Done."

    # Generate Monero RPC credentials
    echo "Generating Monero wallet credentials..."
    WALLET_PASS=$(openssl rand -base64 24 | tr -d '/+=' | head -c 32)
    RPC_PASS=$(openssl rand -base64 24 | tr -d '/+=' | head -c 32)

    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s/^MONERO_WALLET_PASSWORD=$/MONERO_WALLET_PASSWORD=$WALLET_PASS/" .env
        sed -i '' "s/^MONERO_RPC_PASSWORD=$/MONERO_RPC_PASSWORD=$RPC_PASS/" .env
    else
        sed -i "s/^MONERO_WALLET_PASSWORD=$/MONERO_WALLET_PASSWORD=$WALLET_PASS/" .env
        sed -i "s/^MONERO_RPC_PASSWORD=$/MONERO_RPC_PASSWORD=$RPC_PASS/" .env
    fi
    echo "Done."

    echo ""
    echo "IMPORTANT: Please edit .env and set:"
    echo "  - TELEGRAM_TOKEN (from @BotFather)"
    echo "  - ADMIN_IDS (your Telegram user ID)"
    echo "  - SUPER_ADMIN_IDS (super admin user IDs)"
else
    echo ".env file already exists"
fi

if [ "$PRODUCTION" = true ]; then
    # Production mode: Docker deployment
    echo ""
    echo "Checking Docker..."
    if ! command -v docker &> /dev/null; then
        echo "ERROR: Docker is not installed!"
        exit 1
    fi
    echo "Docker is installed."

    echo ""
    echo "========================================"
    echo "  Production Setup Complete!"
    echo "========================================"
    echo ""
    echo "To deploy:"
    echo "  1. Edit .env with your configuration"
    echo "  2. Run: docker-compose up -d"
    echo "  3. Check: curl http://localhost:8080/status"
    echo ""
    echo "The Monero wallet will be created automatically."
    echo "Wallet files: ./monero-wallet/"
else
    # Development mode: Local Python setup
    echo ""
    echo "Checking Python..."
    if command -v python3.12 &> /dev/null; then
        echo "Python 3.12 found"
    elif command -v python3 &> /dev/null; then
        echo "Python 3 found"
    else
        echo "ERROR: Python 3 not found!"
        exit 1
    fi

    if [ -f "Makefile" ]; then
        echo ""
        echo "Installing dependencies..."
        make setup 2>/dev/null || {
            python3 -m pip install poetry
            poetry install
        }
    fi

    echo ""
    echo "========================================"
    echo "  Development Setup Complete!"
    echo "========================================"
    echo ""
    echo "To run locally:"
    echo "  1. Edit .env with your configuration"
    echo "  2. Run: make run (or poetry run python -m bot.main)"
    echo ""
    echo "To run tests:"
    echo "  make test"
fi