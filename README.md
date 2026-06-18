# Celine Esthetique AI Backend Chatbot and RAG Pipeline

### Project Tracking Metadata
* Developer Name: Ameema Rashid (AI Lead)
* Current Date: June 17, 2026
* Phase Snapshot: Phase 1 Completion (Local RAG Workflow and API Gateway Setup)
* Submission Host: TechNexus Portal

---

## 1. Phase 1 Milestone Verification
1. Directory Structure and Venv: Created clean, modular Python app backend structure and active isolated virtual environment (venv) using PowerShell.
2. FastAPI Configuration: Formulated core routing entrypoints (app/main.py) and validated the interactive swagger documentation service line.
3. Knowledge Ingestion: Populated initial salon knowledge database (data/salon_knowledge.json) with initial service/FAQ chunks spanning treatment rules, hours, and cancellation protocols.
4. Local Embedding Workflow: Constructed an offline mathematical vector mapping pipeline utilizing HuggingFace's all-MiniLM-L6-v2.
5. FAISS Indexing and Tests: Deposited data vectors directly into a localized FAISS indexing cache and successfully passed live integration test queries (tests/test_rag.py) returning 200 OK responses.

---

## 2. All-In-One Setup, Installation, and Execution Commands

Copy and run this entire script block in your Windows PowerShell terminal to configure, install, and execute the complete pipeline automatically:

```powershell
# Step 1: Set script execution policy bypass for the current session
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned

# Step 2: Initialize and activate the virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Step 3: Upgrade pip and install all project dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt

# Step 4: Run the integration verification test script
python tests/test_rag.py

# Step 5: Launch the live Uvicorn API server loop
uvicorn app.main:app --reload
