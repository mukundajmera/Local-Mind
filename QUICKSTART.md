# Quick Start Guide

## Unified Environment Setup

The Local-Mind project now uses a **single unified virtual environment** at the project root for easier management.

### First Time Setup

1. **Run the environment setup script:**
   ```bash
   ./setup_env.sh
   ```
   
   This will:
   - Create a virtual environment at `./venv`
   - Install all backend dependencies
   - Install optional device manager and test dependencies

2. **Start the application:**
   ```bash
   ./start.sh
   ```
   
   Or start services individually:
   ```bash
   ./start.sh backend   # Backend only
   ./start.sh frontend  # Frontend only
   ./start.sh all       # Both (default)
   ```

### Manual Activation

If you need to run commands manually:

```bash
# Activate the environment
source venv/bin/activate

# Run backend
cd apps/backend
uvicorn main:app --reload

# Run tests
pytest tests/
```

### Environment Management

- **Recreate environment:** Run `./setup_env.sh` again and choose 'y' when prompted
- **Update dependencies:** 
  ```bash
  source venv/bin/activate
  pip install -r apps/backend/requirements.txt
  ```

### Troubleshooting

**Issue: "venv not found"**
- Solution: Run `./setup_env.sh` first

**Issue: Port already in use**
- Solution: `./start.sh stop` then `./start.sh all`

**Issue: Import errors**
- Solution: Recreate the environment with `./setup_env.sh`

### Old Environments

The old separate environments can be safely removed:
```bash
rm -rf .venv                    # Old root venv
rm -rf apps/backend/venv        # Old backend venv
```

The new unified `./venv` replaces both.
