# Use Python 3.11 slim image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV HOST=0.0.0.0
ENV ENVIRONMENT=production

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-client \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . /app/

# Create static files directory
RUN mkdir -p /app/staticfiles

# NOTE: Do not collect static at build time; run at container start after envs are present

# Ensure log directory exists for production logging
RUN mkdir -p /var/log/betterbundle-admin

# Create entrypoint script
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# Wait for database\n\
echo "Waiting for database..."\n\
DB_HOST_ENV="${DB_HOST:-postgres}"\n\
DB_PORT_ENV="${DB_PORT:-5432}"\n\
DB_USER_FLAG=""\n\
if [ -n "${DB_USER}" ]; then\n\
  DB_USER_FLAG="-U ${DB_USER}"\n\
fi\n\
while ! pg_isready -h "${DB_HOST_ENV}" -p "${DB_PORT_ENV}" ${DB_USER_FLAG}; do\n\
  sleep 1\n\
done\n\
echo "Database is ready!"\n\
\n\
# Run migrations\n\
python manage.py migrate\n\
\n\
# Collect static files now that env vars are available\n\
python manage.py collectstatic --noinput\n\
\n\
# Create admin user if it doesn\'t exist\n\
python manage.py create_admin_user --username admin --email admin@betterbundle.com --password admin123\n\
\
# Start server with environment-based configuration\n\
python manage.py runserver $HOST:$PORT' > /app/entrypoint.sh

RUN chmod +x /app/entrypoint.sh

# Expose port (will be overridden by docker-compose)
EXPOSE $PORT

# Set entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]

# Default command (will use environment variables)
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]