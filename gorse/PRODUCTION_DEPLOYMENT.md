# 🚀 Gorse Production Deployment Guide

## **Overview**
This guide covers deploying Gorse recommendation services in production for BetterBundle.

## **Architecture**
- **Gorse Master**: Manages training and coordinates services (Port 8088)
- **Gorse Server**: Serves recommendations (Port 8087)  
- **Gorse Worker**: Processes training jobs (Port 8089)

## **Deployment Options**

### **Option 1: Docker on Same Infrastructure (Recommended)**
Deploy Gorse containers on the same infrastructure as your main app.

**Pros:**
- ✅ Same network, no DNS issues
- ✅ Easy to manage
- ✅ Consistent with existing infrastructure

**Steps:**
1. Deploy to Render, Railway, or similar platform
2. Use same PostgreSQL and Redis instances
3. Configure internal networking

### **Option 2: Docker with External Services (Current Setup)**
Deploy locally with external PostgreSQL/Redis.

**Pros:**
- ✅ Local development and testing
- ✅ Can use production databases

**Cons:**
- ❌ DNS resolution issues
- ❌ Network connectivity problems
- ❌ Not suitable for production

**Current Issue:**
```
dial tcp: lookup dpg-d2qpjbemcj7s73cegbv0-a on 127.0.0.11:53: no such host
```

### **Option 3: Python-Based ML Training (Alternative)**
Use Python libraries instead of Gorse.

**Pros:**
- ✅ No external services needed
- ✅ Full control over training
- ✅ Easier deployment

**Cons:**
- ❌ Less mature than Gorse
- ❌ Need to implement recommendation serving

## **Production Deployment Steps**

### **Step 1: Choose Deployment Option**
Based on your infrastructure:
- **Same Platform**: Use Option 1
- **Different Platforms**: Use Option 3 (Python-based)

### **Step 2: Configure Environment**
```bash
# Production environment variables
GORSE_CACHE_STORE=redis://your-redis-url
GORSE_DATA_STORE=postgres://your-postgres-url
GORSE_LOG_LEVEL=info
```

### **Step 3: Deploy Services**
```bash
# For Docker deployment
docker-compose -f docker-compose.production.yml up -d

# For platform deployment
# Use platform-specific deployment commands
```

### **Step 4: Verify Deployment**
```bash
# Check service health
curl http://localhost:8088/api/status
curl http://localhost:8087/api/health

# Check logs
docker logs gorse-gorse-master-1
```

## **Current Status & Next Steps**

### **✅ What's Working:**
- Feature transformation pipeline
- Computed features (358 products, 397 customers, 397 interactions)
- Smart incremental logic
- Gorse service integration code

### **🔧 What Needs Fixing:**
- DNS resolution for external services
- Docker networking configuration
- Production deployment strategy

### **🚀 Recommended Next Steps:**

1. **Immediate**: Test Python-based ML training as alternative
2. **Short-term**: Deploy Gorse to same platform as main app
3. **Long-term**: Evaluate Gorse vs. custom ML solution

## **Testing the Integration**

Once Gorse is deployed, test with:

```bash
# Export features
curl -X POST http://localhost:8001/api/v1/gorse/export-features/cmf2cmny90000v3brxaluj8j0

# Trigger training
curl -X POST http://localhost:8001/api/v1/gorse/train/cmf2cmny90000v3brxaluj8j0

# Get recommendations
curl http://localhost:8001/api/v1/gorse/recommendations/cmf2cmny90000v3brxaluj8j0/user123
```

## **Production Considerations**

### **Security:**
- Use environment variables for secrets
- Enable HTTPS in production
- Implement authentication if needed

### **Monitoring:**
- Health checks for all services
- Log aggregation
- Performance metrics

### **Scaling:**
- Multiple worker instances
- Load balancing for server
- Database connection pooling

### **Backup & Recovery:**
- Regular model backups
- Training data versioning
- Rollback procedures

## **Troubleshooting**

### **Common Issues:**

1. **DNS Resolution:**
   ```bash
   # Check if hostname resolves
   nslookup your-hostname
   
   # Use IP address if needed
   GORSE_DATA_STORE=postgres://user:pass@IP:5432/db
   ```

2. **Network Connectivity:**
   ```bash
   # Test from container
   docker exec gorse-gorse-master-1 ping your-hostname
   
   # Check firewall rules
   ```

3. **Database Connection:**
   ```bash
   # Test connection string
   # Verify credentials and permissions
   ```

## **Support & Resources**

- **Gorse Documentation**: https://gorse.io/docs/
- **Docker Networking**: https://docs.docker.com/network/
- **Production Best Practices**: Platform-specific guides
