# Celine Esthetique AI Backend Chatbot and RAG Pipeline

### Project Tracking Metadata
* Developer Name: Ameema Rashid (AI Lead)
* Current Date: June 18, 2026
* Phase Snapshot: Phase 2 Completion (Cloud LLM Integration)
* Submission Host: TechNexus Portal

---

## 1. Phase 1 & 2 Completed Milestones
1. Directory Structure and Venv: Created modular Python app backend architecture and active isolated virtual environment using PowerShell.
2. FastAPI Configuration: Formulated core routing entrypoints and built interactive swagger UI testing structures.
3. Knowledge Ingestion: Populated mock salon knowledge databases with initial service/FAQ chunks.
4. Local Embedding Workflow: Constructed offline vector mapping pipeline utilizing HuggingFace's all-MiniLM-L6-v2.
5. FAISS Indexing: Deposited data vectors directly into a localized FAISS indexing cache.
6. Groq Cloud Integration: Swapped placeholder code with a live cloud LLM client routing queries to llama3-70b-8192.
7. Luxury Prompt Engineering: Structured system persona profiles mapping out the elegant Celine AI concierge tone.

---

## 2. All-In-One Setup, Installation, and Execution Commands

Copy and run this entire script block in your Windows PowerShell terminal to configure, install, and execute the complete pipeline automatically:

```powershell
# Step 1: Set script execution policy bypass for the current session
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned

# Step 2: Initialize and activate the virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Step 3: Install all project dependencies
pip install -r requirements.txt

# Step 4: Launch the live Uvicorn API server loop
uvicorn app.main:app --reload