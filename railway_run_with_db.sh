#!/bin/bash
# Helper script to run Railway commands with DATABASE_PUBLIC_URL explicitly set
# Usage: ./railway_run_with_db.sh python manage.py list_users

# Get DATABASE_PUBLIC_URL from Railway
DATABASE_PUBLIC_URL=$(railway variables --json | grep -o '"DATABASE_PUBLIC_URL": "[^"]*"' | cut -d'"' -f4)

if [ -z "$DATABASE_PUBLIC_URL" ]; then
    echo "Error: Could not get DATABASE_PUBLIC_URL from Railway"
    exit 1
fi

# Export it and run the command
export DATABASE_PUBLIC_URL
railway run "$@"

