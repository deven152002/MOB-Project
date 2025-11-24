# Backend Setup Guide

## Step 2: Dependency Installation

### Quick Start

1. **Install dependencies using the script:**
   ```bash
   ./install.sh
   ```

2. **Or install manually:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Verify installation:**
   ```bash
   python verify_dependencies.py
   ```

### Required Dependencies

All dependencies are listed in `requirements.txt`:

- **fastapi** - Web framework for building APIs
- **uvicorn[standard]** - ASGI server with standard extras
- **sqlalchemy** - Database ORM
- **pydantic** - Data validation
- **python-dotenv** - Environment variable management
- **python-jose[cryptography]** - JWT token handling
- **python-multipart** - File upload support
- **passlib[bcrypt]** - Password hashing
- **httpx** - HTTP client (optional but recommended)

### Environment Variables

Create a `.env` file in the backend directory with:

```env
# Database Configuration
DATABASE_URL=sqlite:///./image_processing.db

# JWT Secret Key (change this in production!)
SECRET_KEY=your-secret-key-here-change-in-production

# API Configuration
API_HOST=0.0.0.0
API_PORT=8001

# CORS Origins (comma-separated, use * for development only)
CORS_ORIGINS=*
```

### Testing the Installation

1. **Check dependencies:**
   ```bash
   python verify_dependencies.py
   ```

2. **Start the server:**
   ```bash
   uvicorn app:app --reload --host 0.0.0.0 --port 8001
   ```

3. **Test the health endpoint:**
   ```bash
   curl http://localhost:8001/health
   ```

   Expected response:
   ```json
   {"status": "healthy", "service": "Image Processing API"}
   ```

### Troubleshooting

#### Issue: "Module not found"
- Make sure virtual environment is activated
- Run: `pip install -r requirements.txt`

#### Issue: "Port already in use"
- Backend uses port 8001 (to avoid conflict with main API)
- Change port: `uvicorn app:app --port 8002`

#### Issue: "Permission denied" on install.sh
- Run: `chmod +x install.sh`

#### Issue: Database errors
- Make sure SQLite is available (usually built-in with Python)
- Check DATABASE_URL in .env file

### Next Steps

After dependencies are installed:
1. ✅ Step 1: CORS and Database - **COMPLETE**
2. ✅ Step 2: Dependencies - **COMPLETE**
3. ⏭️ Step 3: Complete API Integration
4. ⏭️ Step 4: Add Security and Error Handling
5. ⏭️ Step 5: Add Docker/CI/CD

