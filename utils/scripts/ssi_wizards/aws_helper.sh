#!/bin/bash

# Load environment variables from .env file
if [ -f ".env" ]; then
    echo "🔄 Loading environment variables from .env..."
    export $(grep -v '^#' .env | xargs)
else
    echo "⚠️ .env file not found. Make sure to create one."
    exit 1
fi

# Run the Python script
echo "🚀 Running AWS Onboarding Helper..."
python3 utils/scripts/ssi_wizards/aws_onboarding_help.py
