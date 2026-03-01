# CycleMaster - Render Deployment Guide

## Overview

This guide covers deploying the CycleMaster FastAPI backend to [Render](https://render.com).

## Prerequisites

1. **Render Account**: Create a free account at https://render.com
2. **GitHub Repository**: Push your code to a GitHub repository (public or link your account)
3. **Git**: For version control

## Deployment Steps

### 1. Connect Render to GitHub

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click **New +** → **Web Service**
3. Select **Build and deploy from a Git repository**
4. Connect your GitHub account and select the repository
5. Select the branch (typically `main` or `develop`)

### 2. Configure Web Service

Set the following configuration in Render:

**Basic Settings:**
- **Name**: `cyclemaster-api` (or your desired name)
- **Runtime**: `Python`
- **Python Version**: `3.12`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

**Environment Variables:**
Add the following in the **Environment** section:

```
DB_PATH=/data/cyclemaster.db
LOG_LEVEL=INFO
PORT=8000
```

Add additional configuration variables from `.env.production` if needed.

### 3. Configure Persistent Storage (Important!)

**SQLite Database Directory:**
1. In Render dashboard, go to **Disks**
2. Click **Add Disk**
3. Set:
   - **Name**: `data`
   - **Mount Path**: `/data`
   - **Size**: `1 GB` (adjust based on needs)

This ensures your SQLite database persists across deployments.

### 4. Health Check

Render will automatically use the configured health check endpoint:
- **Path**: `/`
- **Response**: Returns `{"status": "healthy", "service": "CycleMaster"}`

### 5. Deploy

1. Click **Create Web Service**
2. Render will automatically build and deploy
3. Monitor the deployment in the **Logs** tab

### 6. View Your API

Once deployed, your API will be available at:
```
https://cyclemaster-api.onrender.com
```

Access the interactive API documentation:
```
https://cyclemaster-api.onrender.com/docs
```

## Project Structure

```
CycleMaster/
├── app/
│   ├── main.py                 # FastAPI application entry point
│   ├── api/
│   │   └── routes.py           # API endpoints
│   ├── models/
│   │   ├── db.py               # Database configuration
│   │   └── models.py           # SQLAlchemy models
│   ├── services/               # Business logic services
│   ├── utils/
│   │   ├── config.py           # Environment configuration
│   │   └── logging.py          # Logging setup
│   └── scheduler/              # Background job scheduler
├── requirements.txt            # Python dependencies
├── start.sh                    # Render start script
├── Procfile                    # Alternative start configuration
├── render.yaml                 # Render configuration (optional)
├── .env.production             # Production environment template
└── .gitignore
```

## Key Features for Render

### 1. **Health Check Endpoint**
- **Endpoint**: `GET /`
- **Response**: Confirms service is running
- Used by Render for automatic service monitoring

### 2. **Environment-Based Configuration**

Database path is configurable via `DB_PATH` environment variable:
```python
# Default: /data/cyclemaster.db
# Set DB_PATH=/custom/path/db.sqlite in environment
```

### 3. **SQLite Database**

Database is stored in persistent disk at `/data/cyclemaster.db`:
- Survives application restarts
- Survives deployment updates
- Can be backed up from Render dashboard

### 4. **Automatic Port Binding**

The application respects the `PORT` environment variable set by Render:
```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### 5. **CORS Configuration**

CORS middleware allows requests from all origins (production-ready):
```python
CORSMiddleware(
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*']
)
```

## Configuration Files Explained

### `requirements.txt`
- Pinned dependency versions for reproducible builds
- Includes gunicorn and uvicorn with all extras
- Production-ready with all needed packages

### `start.sh`
Creates `/data` directory and starts the application:
```bash
#!/bin/bash
set -e
mkdir -p /data
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

### `Procfile`
Simple process configuration file for deployment:
```
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### `render.yaml`
Complete Render service configuration (optional):
```yaml
services:
  - type: web
    name: cyclemaster-api
    runtime: python
    startCommand: bash start.sh
    disk:
      - name: data
        mountPath: /data
        sizeGB: 1
```

### `.env.production`
Template for production environment variables - **Never commit actual secrets**

## Monitoring & Logs

### View Logs in Render
1. Go to your service in Render dashboard
2. Click **Logs**
3. View real-time application logs

### Key Log Messages
- `Database initialized successfully` - DB startup complete
- `Scheduler started successfully` - Background jobs running
- `health_check` - Health check requests

## Troubleshooting

### Issue: Database file not found

**Solution**: Ensure `/data` disk is mounted in Render dashboard

### Issue: ModuleNotFoundError

**Solution**: Verify all dependencies in `requirements.txt` and rebuild

### Issue: Port already in use

**Solution**: Always use `$PORT` environment variable (Render handles this automatically)

### Issue: Scheduler not starting

**Solution**: Check logs for scheduler errors - not critical for API function

## Important Notes

1. **Business Logic Untouched**: This refactoring only affects deployment configuration, not business logic
2. **No Breaking Changes**: Existing API endpoints and functionality remain unchanged
3. **Production Ready**: All configurations follow FastAPI/Render best practices
4. **CORS Open**: For production, consider restricting `allow_origins` to specific domains
5. **Database**: SQLite on persistent disk is suitable for moderate traffic

## Next Steps After Deployment

1. Test health endpoint: `https://your-service.onrender.com/`
2. Access Swagger docs: `https://your-service.onrender.com/docs`
3. Configure custom domain (optional)
4. Set up monitoring alerts (optional)
5. Configure auto-deploy from GitHub (automatic by default)

## Support

For Render-specific issues, check:
- [Render Documentation](https://render.com/docs)
- [Render Support](https://support.render.com)

For FastAPI issues:
- [FastAPI Documentation](https://fastapi.tiangolo.com)
