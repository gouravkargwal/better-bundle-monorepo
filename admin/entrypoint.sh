#!/bin/bash
set -e

# Wait for database
echo "Waiting for database..."
DB_HOST_ENV="${DB_HOST:-postgres}"
DB_PORT_ENV="${DB_PORT:-5432}"
DB_USER_FLAG=""
if [ -n "${DB_USER}" ]; then
  DB_USER_FLAG="-U ${DB_USER}"
fi
while ! pg_isready -h "${DB_HOST_ENV}" -p "${DB_PORT_ENV}" ${DB_USER_FLAG}; do
  sleep 1
done
echo "Database is ready!"

# Run migrations
python manage.py migrate

# Collect static files now that env vars are available
python manage.py collectstatic --noinput

# Create admin user if it doesn't exist
python manage.py create_admin_user --username admin --email admin@betterbundle.com --password admin123

# Start server with environment-based configuration
exec python manage.py runserver $HOST:$PORT
