#!/bin/bash
set -e

# On first run (empty volume), seed cloudcli from the image's pre-installed copy
if [ ! -f "$NPM_CONFIG_PREFIX/bin/cloudcli" ]; then
    echo "First run: seeding cloudcli to persistent volume..."
    cp -r /opt/cloudcli-seed/. "$NPM_CONFIG_PREFIX/"
fi

# Generate a stable JWT secret once, store it in the persisted .cloudcli dir
JWT_SECRET_FILE="$HOME/.cloudcli/.jwt_secret"
CLOUDCLI_ENV="$NPM_CONFIG_PREFIX/lib/node_modules/@cloudcli-ai/cloudcli/.env"

mkdir -p "$HOME/.cloudcli"

if [ ! -f "$JWT_SECRET_FILE" ]; then
    node -e "console.log(require('crypto').randomBytes(32).toString('hex'))" > "$JWT_SECRET_FILE"
    echo "Generated new JWT secret"
fi

# Write .env for cloudcli using the persisted secret
JWT_SECRET=$(cat "$JWT_SECRET_FILE")
echo "JWT_SECRET=$JWT_SECRET" > "$CLOUDCLI_ENV"

exec cloudcli
