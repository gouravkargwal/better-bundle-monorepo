docker build -t yourdockerhubusername/gorse:latest .
docker push yourdockerhubusername/gorse:latest
fly launch --name your-gorse-app-name --region syd --image yourdockerhubusername/gorse:latest
fly secrets set DATABASE_DSN="postgres://user:password@neon-host:5432/dbname?sslmode=require"
fly secrets set REDIS_ENDPOINT="upstash-redis-url"
fly secrets set REDIS_PASSWORD="upstash-redis-password"
fly deploy
fly logs
fly scale count 1
