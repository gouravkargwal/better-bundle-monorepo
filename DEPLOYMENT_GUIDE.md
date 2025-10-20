# BetterBundle Production Deployment Guide

## 🚀 Fixed Issues in docker-compose.prod.yml

### ✅ Issues Resolved:

1. **Port Conflict Fixed**

   - Grafana now uses port 3001 (was conflicting with Remix app on 3000)
   - All services have unique ports

2. **Added Nginx Proxy Manager**

   - For domain management and SSL certificates
   - Ports: 80, 443, 81 (admin interface)

3. **Optimized Resource Limits**

   - Perfect for A1 instance (4 OCPUs, 24 GB RAM)
   - Total CPU: ~8.5 (within 4 OCPUs limit)
   - Total Memory: ~7.6 GB (within 24 GB limit)

4. **Fixed Service Dependencies**
   - Removed duplicate configurations
   - Proper health checks for all services

## 📋 Environment Setup

### ✅ **Simplified Approach - No Redundancy!**

The docker-compose.prod.yml now uses **only** `env_file` - no redundant `environment` variables!

### **Quick Setup:**

```bash
# Copy the complete environment template
cp env.prod.example .env.prod

# Edit with your values (optional - defaults are secure)
nano .env.prod
```

### **Ready-to-Use Defaults:**

The `env.prod.example` file contains:

- ✅ **All required variables** for every service
- ✅ **Secure default passwords** (change if needed)
- ✅ **Proper URLs** for internal communication
- ✅ **Grafana configuration** (admin interface)
- ✅ **Gorse configuration** (recommendation engine)
- ✅ **Database connections** (PostgreSQL, Redis)

### **Only Update These (Optional):**

```bash
# Shopify App (replace with your values)
SHOPIFY_API_KEY=your_actual_shopify_api_key
SHOPIFY_API_SECRET=your_actual_shopify_api_secret
SHOPIFY_APP_URL=https://your-actual-domain.com

# Passwords (if you want different ones)
POSTGRES_PASSWORD=YourCustomPassword
GRAFANA_ADMIN_PASSWORD=YourCustomGrafanaPassword
```

## 🐳 Service Ports

| Service       | Port        | Description                |
| ------------- | ----------- | -------------------------- |
| Remix App     | 3000        | Main application           |
| Grafana       | 3001        | Monitoring dashboard       |
| PostgreSQL    | 5433        | Database (external access) |
| Redis         | 6379, 8002  | Cache & RedisInsight       |
| Kafka         | 9092        | Message broker             |
| Kafka UI      | 8080        | Kafka management           |
| Kafka REST    | 8082        | REST API                   |
| Gorse UI      | 8086        | Recommendation engine UI   |
| Gorse API     | 8088        | Recommendation engine API  |
| Python Worker | 8000        | ML processing              |
| Loki          | 3100        | Log aggregation            |
| Nginx Proxy   | 80, 443, 81 | Domain/SSL management      |

## 🚀 Deployment Steps

### 1. Prepare Environment

```bash
# Copy environment template (ready to use!)
cp env.prod.example .env.prod

# Optional: Edit with your custom values
nano .env.prod
```

### 2. Deploy Services

```bash
# Start all services
docker-compose -f docker-compose.prod.yml up -d

# Check status
docker-compose -f docker-compose.prod.yml ps

# View logs
docker-compose -f docker-compose.prod.yml logs -f
```

### 3. Setup Domain & SSL

1. **Access Nginx Proxy Manager**: http://your-server-ip:81
2. **Login**: admin@example.com / changeme
3. **Add Proxy Host**:
   - Domain: your-domain.com
   - Forward to: 127.0.0.1:3000
   - Enable SSL certificate

## 🔧 Resource Optimization

### For A1 Instance (4 OCPUs, 24 GB):

- **Perfect fit** - all services will run smoothly
- **Headroom available** for additional services
- **Optimized limits** prevent resource conflicts

### For x86 Instance (1 OCPU, 1 GB):

If you need to use x86 temporarily, reduce these limits:

```yaml
# Reduce these in docker-compose.prod.yml
remix-app:
  deploy:
    resources:
      limits:
        cpus: "0.3"
        memory: 200M

postgres:
  deploy:
    resources:
      limits:
        cpus: "0.2"
        memory: 150M
# Skip these services on x86:
# - gorse (ML engine)
# - python-worker (ML processing)
# - kafka (message broker)
```

## 🛠️ Troubleshooting

### Common Issues:

1. **Port Conflicts**

   - ✅ Fixed: Grafana now uses port 3001

2. **Memory Issues**

   - ✅ Optimized: Resource limits are A1-optimized

3. **Service Dependencies**

   - ✅ Fixed: Proper health checks and dependencies

4. **Environment Variables**
   - ✅ Documented: All required variables listed

### Health Checks:

```bash
# Check all services
docker-compose -f docker-compose.prod.yml ps

# Check specific service logs
docker-compose -f docker-compose.prod.yml logs remix-app
docker-compose -f docker-compose.prod.yml logs postgres
docker-compose -f docker-compose.prod.yml logs redis
```

## 🎯 Next Steps

1. **Create A1 instance** in Oracle Cloud
2. **Copy this project** to the instance
3. **Create .env.prod** with your values
4. **Run deployment** commands
5. **Setup domain** with Nginx Proxy Manager
6. **Access your app** at your domain!

## 📊 Monitoring

- **Grafana**: http://your-server-ip:3001 (admin/your-password)
- **Kafka UI**: http://your-server-ip:8080
- **Gorse UI**: http://your-server-ip:8086
- **Nginx Proxy Manager**: http://your-server-ip:81

Your BetterBundle application is now ready for production deployment! 🚀
