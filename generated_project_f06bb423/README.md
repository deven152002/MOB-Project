# Generated Project

## Structure
- `backend/`: Python backend code
- `frontend/`: React frontend code

## Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

## Setup Instructions

### Backend

#### Option 1: Quick Setup (Recommended)
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Run the installation script:
   ```bash
   ./install.sh
   ```
   This will:
   - Create a virtual environment
   - Install all dependencies
   - Verify the installation

3. Activate the virtual environment (if not already activated):
   ```bash
   source venv/bin/activate
   ```

4. (Optional) Create a `.env` file for environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. Verify dependencies are installed:
   ```bash
   python verify_dependencies.py
   ```

6. Run the backend server:
   ```bash
   uvicorn app:app --reload --host 0.0.0.0 --port 8001
   ```

#### Option 2: Manual Setup
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create a virtual environment (recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Upgrade pip:
   ```bash
   pip install --upgrade pip
   ```

4. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

5. Verify installation:
   ```bash
   python verify_dependencies.py
   ```

6. Run the backend server:
   ```bash
   uvicorn app:app --reload --host 0.0.0.0 --port 8001
   ```

### Frontend
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Start a simple HTTP server to serve the frontend:
   ```bash
   python -m http.server 3000
   ```
   Or use Node.js if you have it installed:
   ```bash
   npm install
   npm start
   ```

## Accessing the Application
- Backend API: http://localhost:8001
- Frontend UI: http://localhost:3000
- API Health Check: http://localhost:8001/health
- API Documentation: http://localhost:8001/docs (Swagger UI)

## Dependencies

### Backend Dependencies
- **fastapi**: Web framework
- **uvicorn**: ASGI server
- **sqlalchemy**: Database ORM
- **pydantic**: Data validation
- **python-jose**: JWT authentication
- **python-multipart**: File uploads
- **passlib**: Password hashing
- **python-dotenv**: Environment variables

### Troubleshooting

#### Dependencies not installing?
- Make sure you're using Python 3.8+
- Try upgrading pip: `pip install --upgrade pip`
- Use virtual environment to avoid conflicts

#### Port already in use?
- Backend uses port 8001 (to avoid conflict with main API on 8000)
- Frontend uses port 3000
- Change ports in the commands if needed

#### Import errors?
- Run `python verify_dependencies.py` to check what's missing
- Make sure virtual environment is activated
- Reinstall: `pip install -r requirements.txt --force-reinstall`
