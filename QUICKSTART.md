# Quick Start: Your First 10 Minutes with Local Mind

Welcome! This tutorial will guide you through setting up Local Mind and uploading your first document. By the end, you'll have a working AI research assistant running on your machine.

---

## What You'll Learn

- ✅ How to install and start Local Mind
- ✅ How to verify everything is working
- ✅ How to upload your first document
- ✅ How to chat with your documents using AI
- ✅ How to troubleshoot common issues

**Time Required**: 10 minutes  
**Difficulty**: Beginner

---

## Prerequisites

Before starting, ensure you have:

| Requirement | Check Command | Expected Output |
|------------|---------------|-----------------|
| **Python 3.11+** | `python3 --version` | `Python 3.11.x` or higher |
| **Node.js 20+** | `node --version` | `v20.x.x` or higher |
| **Docker or Nerdctl** | `docker --version` or `nerdctl --version` | Any recent version |
| **8GB+ RAM** | `free -h` (Linux) or Activity Monitor (Mac) | At least 8GB available |

**Don't have these?** See [Installation Prerequisites](docs/TROUBLESHOOTING.md#prerequisites) for installation guides.

---

## Step 1: Clone and Setup (2 minutes)

### 1.1 Clone the Repository

```bash
git clone https://github.com/your-org/local-mind.git
cd local-mind
```

**Expected Output:**
```
Cloning into 'local-mind'...
remote: Enumerating objects: 1234, done.
...
```

### 1.2 Copy Environment Configuration

```bash
cp .env.example .env
```

**What this does**: Creates your local configuration file. The defaults work for local development.

**Optional**: Edit `.env` to customize settings:
```bash
# Optional: Change LLM model (default: llama3.2:3b)
# LLM_MODEL=llama3.2:8b

# Optional: Change upload directory
# UPLOAD_DIR=./data/uploads
```

---

## Step 2: Start Local Mind (3 minutes)

### 2.1 Run the Initialization Script

```bash
sh scripts/init.sh
```

**What happens**:
1. Creates Python virtual environment
2. Installs backend dependencies
3. Starts Milvus (vector database)
4. Starts Redis (cache)
5. Starts backend API
6. Installs frontend dependencies
7. Starts frontend development server

**Expected Output:**
```
🔧 Setting up Python environment...
✅ Virtual environment created

📦 Installing backend dependencies...
✅ Backend dependencies installed

🚀 Starting infrastructure...
✅ Milvus started on port 19530
✅ Redis started on port 6379

🌐 Starting backend API...
✅ Backend running on http://localhost:8000

🎨 Starting frontend...
✅ Frontend running on http://localhost:3000

🎉 Local Mind is ready!
   Open http://localhost:3000 in your browser
```

**⏱️ This takes 2-3 minutes on first run** (downloads Docker images and npm packages).

### 2.2 Verify Services are Running

Open a new terminal and check:

```bash
# Check backend health
curl http://localhost:8000/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "services": {
    "milvus": "healthy",
    "redis": "healthy"
  }
}
```

**❌ Got an error?** See [Troubleshooting: Services Not Starting](#troubleshooting)

---

## Step 3: Open the Interface (1 minute)

Open your browser and navigate to:

```
http://localhost:3000
```

**What you should see:**
- Clean, dark-themed interface
- Left sidebar labeled "Sources" (empty for now)
- Center panel with "Source Guide" or "Chat"
- Header with theme toggle and help button

**✅ Success Check**: Can you see the interface? Great! Move to the next step.

---

## Step 4: Upload Your First Document (2 minutes)

### 4.1 Prepare a Test Document

You can use any of these file types:
- PDF (`.pdf`)
- Markdown (`.md`)
- Text (`.txt`)

**Don't have a document handy?** Create a test file:

```bash
cat > test-document.md << 'EOF'
# My First Document

This is a test document for Local Mind.

## Key Points
- Local Mind uses vector search
- All data stays on your machine
- AI helps you understand your documents

## Conclusion
This is a simple test to verify the system works.
EOF
```

### 4.2 Upload the Document

1. Click the **"+ Add"** button in the Sources sidebar
2. Select your document (or `test-document.md`)
3. Wait for the upload progress bar to complete

**Expected Behavior:**
- Progress bar appears (0% → 100%)
- Document appears in Sources sidebar with a unique name like `test-document_1734720000.md`
- A summary badge appears after a few seconds

**⏱️ Upload time**: 5-10 seconds for small documents

### 4.3 View the Document Summary

Click on the document title in the sidebar.

**What you should see:**
- **Summary**: AI-generated overview of the document
- **Key Topics**: Main themes extracted
- **Suggested Questions**: Starting points for exploration

**✅ Success Check**: Do you see the summary? Perfect! The AI briefing agent is working.

---

## Step 5: Chat with Your Document (2 minutes)

### 5.1 Select the Document for Chat

1. Check the **checkbox** next to your document in the Sources sidebar
2. The document is now "selected" for chat queries

**Why this matters**: Local Mind only searches within selected documents, giving you focused answers.

### 5.2 Ask a Question

1. Click the chat icon or the document title to open the chat panel
2. Type a question in the input box, for example:
   ```
   What are the key points in this document?
   ```
3. Press **Enter** or click the send button

**Expected Response:**
- Loading indicator (three pulsing dots)
- AI response appears within 2-5 seconds
- Response includes information from your document

**Example Response:**
```
Based on the document, the key points are:

1. Local Mind uses vector search for semantic document retrieval
2. All data remains on your local machine for privacy
3. AI assists in understanding and exploring documents

The document emphasizes the local-first, privacy-focused approach.
```

### 5.3 Try the Quick Actions

Click one of the suggestion buttons:
- 📝 **Summarize**
- ❓ **Key Questions**
- 🔍 **Deep Dive**

These auto-fill the chat input with common prompts.

---

## ✅ Verification Checklist

Confirm everything is working:

- [ ] Backend health check returns `"status": "healthy"`
- [ ] Frontend loads at http://localhost:3000
- [ ] Document uploads successfully
- [ ] Document appears in Sources sidebar
- [ ] AI summary is generated
- [ ] Chat responds to questions
- [ ] Chat responses reference your document

**All checked?** Congratulations! 🎉 Local Mind is fully operational.

---

## 🎯 What's Next?

Now that you have Local Mind running, explore these features:

### Immediate Next Steps
1. **Upload more documents** - Try PDFs, research papers, or notes
2. **Create a project** - Organize documents by topic (Work, Research, Personal)
3. **Pin important insights** - Click 📌 on AI responses to save them to Notes
4. **Explore multi-document chat** - Select multiple documents and ask comparative questions

### Learn More
- **[User Guide](USER_GUIDE.md)**: Complete feature walkthrough
- **[Tutorials](docs/TUTORIALS.md)**: Advanced usage patterns
- **[Architecture](docs/ARCHITECTURE.md)**: How Local Mind works under the hood

---

## 🔧 Troubleshooting

### Services Not Starting

**Problem**: `init.sh` fails or services don't start

**Solutions**:

1. **Check if ports are already in use**:
   ```bash
   # Check if ports 3000, 8000, 19530 are free
   lsof -i :3000
   lsof -i :8000
   lsof -i :19530
   ```
   If occupied, stop the conflicting process or change ports in `.env`

2. **Verify Docker/Nerdctl is running**:
   ```bash
   docker ps
   # or
   nerdctl ps
   ```
   If not running, start Docker Desktop or the nerdctl daemon

3. **Check Python version**:
   ```bash
   python3 --version
   ```
   Must be 3.11 or higher. Update if needed.

4. **Manual restart**:
   ```bash
   ./start.sh stop
   ./start.sh all
   ```

### Backend Returns 503 (Service Unavailable)

**Problem**: Health check shows `"status": "degraded"` or `"milvus": "unhealthy"`

**Solutions**:

1. **Check Milvus is running**:
   ```bash
   docker ps | grep milvus
   # or
   nerdctl ps | grep milvus
   ```

2. **Restart Milvus**:
   ```bash
   cd infrastructure/nerdctl
   nerdctl compose restart milvus
   ```

3. **Check logs**:
   ```bash
   docker logs sce-memory-bank --tail 50
   ```

### Upload Fails or Hangs

**Problem**: Upload progress bar stuck or returns error

**Solutions**:

1. **Check file size**: Files over 100MB may take longer. Wait up to 30 seconds.

2. **Check backend logs**:
   ```bash
   tail -f apps/backend/logs/app.log
   ```

3. **Verify file format**: Only PDF, MD, TXT supported. Check file extension.

4. **Check disk space**:
   ```bash
   df -h
   ```
   Ensure at least 1GB free space

### Chat Returns Empty or Error

**Problem**: Chat doesn't respond or returns "Failed to connect"

**Solutions**:

1. **Verify document is selected**: Check the checkbox next to the document

2. **Check LLM service**:
   ```bash
   # If using Ollama
   ollama list
   ollama run llama3.2:3b "test"
   ```

3. **Check backend logs for LLM errors**:
   ```bash
   grep -i "llm" apps/backend/logs/app.log
   ```

4. **Restart backend**:
   ```bash
   ./start.sh stop backend
   ./start.sh backend
   ```

### More Help

- **[Full Troubleshooting Guide](docs/TROUBLESHOOTING.md)**: Comprehensive problem-solving
- **[GitHub Issues](https://github.com/your-org/local-mind/issues)**: Report bugs
- **[Discussions](https://github.com/your-org/local-mind/discussions)**: Ask questions

---

## 🔄 Stopping Local Mind

When you're done:

```bash
./start.sh stop
```

**What this does**:
- Stops frontend development server
- Stops backend API
- Stops Milvus and Redis containers

**Your data is preserved**. Documents and vectors remain in `data/` directory.

---

## 🚀 Advanced Setup (Optional)

### Using a Different LLM Model

Edit `.env` and change:
```bash
LLM_MODEL=llama3.2:8b  # Larger model, better quality
```

Then restart:
```bash
./start.sh stop
./start.sh all
```

### Running Services Separately

```bash
# Backend only
./start.sh backend

# Frontend only (in another terminal)
./start.sh frontend

# Infrastructure only
./start.sh infra
```

### Manual Environment Activation

If you need to run commands manually:

```bash
# Activate virtual environment
source venv/bin/activate

# Run backend
cd apps/backend
uvicorn main:app --reload

# Run tests
pytest tests/
```

---

## 📚 Additional Resources

- **[Developer Guide](DEVELOPER_GUIDE.md)**: Contributing and development workflows
- **[Operations Guide](OPERATIONS.md)**: Production deployment
- **[Security Guide](SECURITY.md)**: Hardening and best practices
- **[API Reference](docs/API_REFERENCE.md)**: Complete API documentation

---

**Questions?** Check the [FAQ](docs/TROUBLESHOOTING.md#faq) or [open an issue](https://github.com/your-org/local-mind/issues).

**Ready to dive deeper?** Continue to the [User Guide](USER_GUIDE.md) to learn all features.
