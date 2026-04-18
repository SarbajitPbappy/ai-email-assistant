#!/bin/bash

# Activate conda environment
source /opt/anaconda3/etc/profile.d/conda.sh
conda activate email-assistant

# Go to project directory
cd /Volumes/Sarbajit/Personal/ai-email-assistant

# Start Ollama only if not already running
if ! pgrep -x "ollama" > /dev/null; then
    echo "Starting Ollama..."
    ollama serve &
    sleep 5
else
    echo "Ollama already running ✅"
fi

# Start the unified bot
echo "Starting unified bot..."
python unified_bot.py

