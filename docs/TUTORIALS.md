# Tutorials

**Step-by-step learning guides for Local Mind**

These tutorials teach you how to use Local Mind effectively through hands-on examples.

---

## Tutorial Index

1. [Building Your First Research Project](#tutorial-1-building-your-first-research-project)
2. [Advanced Search Techniques](#tutorial-2-advanced-search-techniques)
3. [Organizing Knowledge with Projects](#tutorial-3-organizing-knowledge-with-projects)
4. [Integrating Local Mind into Your Workflow](#tutorial-4-integrating-local-mind-into-your-workflow)

---

## Tutorial 1: Building Your First Research Project

**Learning Objectives:**
- Create a project for research papers
- Upload and organize multiple documents
- Use AI to explore and synthesize information
- Save important insights to notes

**Prerequisites:**
- Local Mind installed and running
- 3-5 PDF research papers or articles

**Time**: 15 minutes

### Step 1: Create a Research Project

1. Click the **Project Selector** dropdown in the header
2. Click **"+ New Project"**
3. Name it: `🔬 Research`
4. Click **Create**

**Why**: Projects keep your research separate from other documents.

### Step 2: Upload Your Papers

1. Click **"+ Add"** in the Sources sidebar
2. Select 3-5 research papers (PDF format)
3. Wait for uploads to complete (progress bars)

**Expected**: Each paper appears with a timestamp suffix (e.g., `paper_1734720000.pdf`)

### Step 3: Review AI Summaries

1. Click on the first paper title
2. Read the **Summary** and **Key Topics**
3. Note the **Suggested Questions**

**Pro Tip**: Summaries help you decide which papers to read in detail.

### Step 4: Ask Comparative Questions

1. Select **2-3 papers** (check boxes)
2. Open chat
3. Ask: *"What do these papers agree on regarding [your topic]?"*

**Example Response**:
```
Based on the selected papers, there is consensus on:

1. [Point of agreement 1]
2. [Point of agreement 2]
3. [Point of agreement 3]

However, they differ on [specific aspect]...
```

### Step 5: Save Important Insights

1. When you get a valuable response, click **📌 Pin**
2. Open the **Notes Panel** (notes icon in header)
3. View your pinned messages

**What You Learned:**
- ✅ How to create and organize projects
- ✅ How to use AI summaries for quick review
- ✅ How to ask comparative questions
- ✅ How to save insights for later

**Next Steps**: Try Tutorial 2 to learn advanced search techniques.

---

## Tutorial 2: Advanced Search Techniques

**Learning Objectives:**
- Master source-filtered search
- Use Quick Actions effectively
- Ask follow-up questions
- Understand search relevance scores

**Prerequisites:**
- Completed Tutorial 1
- At least 5 documents uploaded

**Time**: 10 minutes

### Step 1: Focused Search

**Scenario**: You want to find information only in recent papers.

1. Select **only the 2 most recent papers**
2. Ask: *"What are the latest findings on [topic]?"*

**Why**: Source filtering ensures you get current information only.

### Step 2: Use Quick Actions

1. Select a single document
2. Click **📝 Summarize**
3. Review the summary
4. Click **🔍 Deep Dive**
5. Compare the depth of information

**Observation**: Quick Actions provide different levels of detail.

### Step 3: Ask Follow-Up Questions

After getting a response:

1. **First question**: *"What is the main argument?"*
2. **Follow-up**: *"What evidence supports this argument?"*
3. **Deep dive**: *"Are there any counterarguments mentioned?"*

**Pattern**: Start broad, then narrow down.

### Step 4: Understand Relevance Scores

Look at the sources cited in responses:

```
Sources:
• Chunk ID: abc123 (Score: 0.92) ← Highly relevant
• Chunk ID: def456 (Score: 0.78) ← Relevant
• Chunk ID: ghi789 (Score: 0.65) ← Marginally relevant
```

**Interpretation**:
- **0.9-1.0**: Direct answer to your question
- **0.7-0.9**: Related information
- **<0.7**: Tangentially related

**What You Learned:**
- ✅ How to use source filtering strategically
- ✅ When to use different Quick Actions
- ✅ How to ask effective follow-up questions
- ✅ How to interpret relevance scores

**Next Steps**: Tutorial 3 teaches project organization strategies.

---

## Tutorial 3: Organizing Knowledge with Projects

**Learning Objectives:**
- Design an effective project structure
- Move between projects efficiently
- Understand project isolation
- Archive old projects

**Prerequisites:**
- At least 10 documents uploaded
- Mix of work and personal documents

**Time**: 15 minutes

### Step 1: Plan Your Project Structure

**Recommended Structure**:
```
🏢 Work
   - Company policies
   - Meeting notes
   - Internal docs

🔬 Research
   - Academic papers
   - Literature reviews

📚 Learning
   - Tutorials
   - Course materials

💡 Personal
   - Book highlights
   - Articles
```

### Step 2: Create Multiple Projects

1. Create **Work** project
2. Create **Research** project
3. Create **Learning** project

### Step 3: Organize Existing Documents

**Current limitation**: Can't move documents between projects.

**Workaround**:
1. Note which documents belong where
2. Delete from current project
3. Switch to target project
4. Re-upload

**Future feature**: Drag-and-drop between projects.

### Step 4: Test Project Isolation

1. Upload a document to **Work** project
2. Switch to **Research** project
3. Try to search for the Work document

**Expected**: Document is NOT found. Projects are isolated.

### Step 5: Efficient Project Switching

**Best Practice**:
- Use keyboard shortcut (future feature)
- Keep 3-5 active projects max
- Name projects clearly

**What You Learned:**
- ✅ How to design a project structure
- ✅ How project isolation works
- ✅ Best practices for organization

**Next Steps**: Tutorial 4 shows workflow integration.

---

## Tutorial 4: Integrating Local Mind into Your Workflow

**Learning Objectives:**
- Build a daily research routine
- Use Local Mind for literature reviews
- Integrate with note-taking apps
- Automate document uploads

**Prerequisites:**
- Comfortable with all features
- Regular research workflow

**Time**: 20 minutes

### Step 1: Daily Research Routine

**Morning Routine** (10 minutes):
1. Upload new papers from overnight downloads
2. Review AI summaries
3. Pin interesting findings
4. Add quick notes for follow-up

### Step 2: Literature Review Workflow

**For a new research topic**:

1. **Collect** (Day 1):
   - Upload 10-15 papers on the topic
   - Create a new project: `📖 [Topic] Review`

2. **Survey** (Day 2-3):
   - Read AI summaries of all papers
   - Identify key themes
   - Group papers by approach

3. **Deep Dive** (Day 4-5):
   - Select papers by theme
   - Ask comparative questions
   - Pin important findings

4. **Synthesize** (Day 6-7):
   - Review all pinned messages
   - Export notes to writing tool
   - Draft literature review

### Step 3: Integration with Note-Taking Apps

**Export to Obsidian/Notion**:

1. Open Notes Panel
2. Copy pinned messages
3. Paste into your note-taking app
4. Add your own commentary

**Future feature**: Direct export to Markdown.

### Step 4: Automate Document Uploads

**Using the API**:

```python
import requests
import os

def auto_upload_pdfs(directory, project_id):
    for file in os.listdir(directory):
        if file.endswith('.pdf'):
            with open(os.path.join(directory, file), 'rb') as f:
                requests.post(
                    'http://localhost:8000/api/v1/sources/upload',
                    files={'file': f},
                    params={'project_id': project_id}
                )
```

**Use case**: Automatically upload papers from Downloads folder.

### Step 5: Weekly Review

**Every Friday** (15 minutes):
1. Review all pinned messages
2. Export important notes
3. Delete outdated documents
4. Plan next week's reading

**What You Learned:**
- ✅ How to build a research routine
- ✅ Literature review workflow
- ✅ Integration with other tools
- ✅ API automation basics

---

## Next Steps

**Continue Learning:**
- Read the [User Guide](../USER_GUIDE.md) for complete feature reference
- Explore the [Architecture Guide](ARCHITECTURE.md) to understand how it works
- Check the [API Reference](API_REFERENCE.md) for programmatic access

**Get Help:**
- [Troubleshooting Guide](TROUBLESHOOTING.md) for common issues
- [GitHub Discussions](https://github.com/your-org/local-mind/discussions) for questions

---

**Completed all tutorials?** You're now a Local Mind power user! 🎉
