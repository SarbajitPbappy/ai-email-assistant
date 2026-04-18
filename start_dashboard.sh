#!/bin/bash
source /opt/anaconda3/etc/profile.d/conda.sh
conda activate email-assistant
cd /Volumes/Sarbajit/Personal/ai-email-assistant
streamlit run src/dashboard/app.py --server.port 8503 >> logs/dashboard.log 2>&1
