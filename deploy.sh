#!/bin/bash

# 🚀 AI Email Assistant - Quick Deployment Script
# Supports: Railway.app, DigitalOcean, Local Docker

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}"
echo "🤖 AI Email Assistant - Deployment Script"
echo "========================================="
echo -e "${NC}"

# Check if running on Railway
if [ ! -z "$RAILWAY_ENVIRONMENT" ]; then
    echo -e "${GREEN}✓ Detected Railway environment${NC}"
    echo "  Environment: $RAILWAY_ENVIRONMENT"
    
    # Railway automatically installs dependencies
    echo -e "${YELLOW}Installing dependencies...${NC}"
    pip install --no-cache-dir -r requirements_deploy.txt
    
    echo -e "${GREEN}✓ Deployment ready!${NC}"
    exit 0
fi

# Check if Docker is available
if command -v docker &> /dev/null; then
    echo -e "${GREEN}✓ Docker detected${NC}"
    
    read -p "Do you want to use Docker for deployment? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Building Docker image...${NC}"
        docker build -t email-assistant .
        
        echo -e "${YELLOW}Starting containers with docker-compose...${NC}"
        docker-compose up -d
        
        echo -e "${GREEN}✓ Services started!${NC}"
        echo "  Bot: Running in background"
        echo "  Dashboard: http://localhost:8503"
        echo "  Ollama: http://localhost:11434"
        
        exit 0
    fi
fi

# Manual Python installation
echo -e "${YELLOW}Installing Python dependencies...${NC}"

# Check Python version
python_version=$(python3 --version | grep -oP '\d+\.\d+')
required_version="3.10"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo -e "${RED}✗ Python $required_version or higher required, found $python_version${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Python $python_version detected${NC}"

# Install dependencies
pip install --no-cache-dir -r requirements_deploy.txt

# Check if .env exists
if [ ! -f "config/.env" ]; then
    echo -e "${YELLOW}⚠ config/.env not found!${NC}"
    echo "Please copy config/.env.example to config/.env and fill in your credentials:"
    echo "  cp config/.env.example config/.env"
    echo "  nano config/.env  # Edit with your credentials"
    exit 1
fi

echo -e "${GREEN}✓ Dependencies installed!${NC}"
echo -e "${YELLOW}To start the application:${NC}"
echo "  ./start_bot.sh       # Start Telegram bot"
echo "  ./start_dashboard.sh # Start Streamlit dashboard"
