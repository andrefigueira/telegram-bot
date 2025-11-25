#!/bin/bash

# Telegram E-commerce Bot Setup Script

set -e

echo "🚀 Telegram E-commerce Bot Setup"
echo "================================"

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo "⚠️  This script should not be run as root!"
   exit 1
fi

# Create required directories
echo "📁 Creating directories..."
mkdir -p data logs monero-wallet

# Check if .env exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.template .env
    echo "⚠️  Please edit .env file with your configuration!"
else
    echo "✅ .env file already exists"
fi

# Generate encryption key if not set
if grep -q "^ENCRYPTION_KEY=$" .env; then
    echo "🔐 Generating encryption key..."
    KEY=$(python3 -c "import base64, os; print(base64.b64encode(os.urandom(32)).decode())")
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s/^ENCRYPTION_KEY=$/ENCRYPTION_KEY=$KEY/" .env
    else
        # Linux
        sed -i "s/^ENCRYPTION_KEY=$/ENCRYPTION_KEY=$KEY/" .env
    fi
    echo "✅ Encryption key generated"
fi

# Check Python version
echo "🐍 Checking Python version..."
if command -v python3.12 &> /dev/null; then
    echo "✅ Python 3.12 found"
else
    echo "⚠️  Python 3.12 not found. Please install it first."
    echo "   On macOS: brew install python@3.12"
    echo "   On Ubuntu: sudo apt install python3.12"
    exit 1
fi

# Install dependencies
if [ -f "Makefile" ]; then
    echo "📦 Installing dependencies..."
    make setup
else
    echo "⚠️  Makefile not found. Installing manually..."
    python3.12 -m pip install poetry
    poetry install
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your configuration:"
echo "   - Set TELEGRAM_TOKEN from @BotFather"
echo "   - Set your ADMIN_IDS and SUPER_ADMIN_IDS"
echo "   - Configure Monero RPC if available"
echo ""
echo "2. Run the bot:"
echo "   make run              # Local development"
echo "   docker-compose up -d  # Production deployment"
echo ""
echo "3. Test the bot:"
echo "   make test            # Run tests"
echo "   make lint            # Check code quality"
echo ""
echo "📚 See README.md for detailed instructions"