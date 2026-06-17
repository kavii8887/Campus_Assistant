# Project Report: eduQ / Campus Assistance Chatbot

## 1. Project Overview
**eduQ (Campus Assistance)** is an AI-powered Student Chatbot application built for institutional environments (like Dharmahack 2026). The project serves as a highly capable academic assistant that helps students query syllabus details, track their attendance, and extract/calculate grades from marksheets using OCR. It features role-based access, offering distinct interfaces for Students (to query data) and Admins (to ingest and manage data).

## 2. Technology Stack & Architecture
The application is built on a modern full-stack architecture with a heavy emphasis on local, privacy-preserving AI.

### Frontend
- **Framework**: React 19 with Vite.
- **Styling**: Tailwind CSS for a modern, responsive UI.
- **Authentication**: Supabase Auth (via `@supabase/supabase-js`) handles secure login, signup, and user profiles (Student vs. Admin roles).
- **Key Components**: 
  - `ChatInterface.jsx`: The primary conversational UI for students.
  - `AdminChatInterface.jsx`: A dashboard for administrators to upload new attendance sheets and manage data.
  - `ProfileSetupModal.jsx`: Ensures users provide necessary academic details (Department, Year, Semester) upon first login.
  - `NewsFeed.jsx`: A component to display campus updates.

### Backend
- **Framework**: FastAPI (`api_server.py`), providing a high-performance REST API.
- **AI Integration**: Relies on a local **Ollama** instance.
  - **Language Model**: `mistral:7b-instruct` is used as the conversational brain to synthesize answers.
  - **Embedding Model**: `nomic-embed-text` is used to convert academic text into mathematical vectors for search.
- **Data Stores**:
  - **Structured Data**: A local SQLite database (`structured_store/academic.db`) stores hard facts like Course Objectives, Outcomes, and Textbooks.
  - **Vector DB**: A local semantic vector store (`vector_db/`) segmented by department (e.g., CSE, ECE) to store chunked text from syllabi and attendance records.
- **OCR Services**: Integrates OCR capabilities (via AWS Textract / custom parsers) to extract tables from images, parse grades, and calculate CGPA (`textract_service.py`, `cgpa_calculator.py`).

## 3. Core Subsystems & Workflows

### 3.1. Retrieval-Augmented Generation (RAG) Pipeline
The core of the chatbot is a sophisticated RAG engine that prevents AI hallucinations by grounding responses in real institutional data.
- **Syllabus Ingestion (`ingest_syllabus.py`)**: Admins provide raw Markdown files of the syllabus. The script cleans the markdown, parses it by course code and unit, generates acronyms (e.g., OOP, OOP LAB), and splits the text into semantic chunks. These chunks are embedded and stored.
- **Attendance Ingestion (`ingest_attendance.py`)**: Admins upload Excel (`.xlsx`) files. The pipeline saves a raw copy for deterministic calculations, parses the rows into text strings, chunks them, and generates embeddings.
- **Runtime Engine (`runtime_engine.py`)**: When a student asks a question (e.g., "What is the syllabus for unit 2 of OOP?"), the backend extracts the user's department and session state, converts the question to an embedding, retrieves the most relevant chunks from the Vector DB, and prompts Mistral to formulate a conversational answer.

### 3.2. OCR & Grade Calculation
- **Endpoint**: `/api/analyze-result`
- **Workflow**: Students can upload an image of their gradesheet. The backend uses `textract_service.py` to identify tables, `grade_parser.py` to extract subjects and letter grades, and `cgpa_calculator.py` to return the final calculated GPA and percentage.

### 3.3. Session Management
- The backend utilizes a `SessionManager` (`session_manager.py`) to track active chat sessions. It associates the current chat with the student's Registration Number, Year, Semester, and Department to ensure queries are automatically scoped to the correct context.

## 4. Directory Structure Analysis

- `backend/`
  - `api_server.py`: The main FastAPI entry point.
  - `cli_interface.py`: A terminal-based version of the chatbot for testing without the frontend.
  - `ingest/`: Contains scripts for converting raw data (Attendance, Syllabus, Regulations) into vector embeddings.
  - `structured_store/`: Contains the SQLite database and schemas for tabular academic data.
  - `vector_db/`: The physical location where the generated semantic vectors and raw Excel files are stored.
  - `services/`: Contains auxiliary services like OCR, CGPA calculation, and image processing.
  
- `frontend/`
  - `src/components/`: Contains all React UI components.
  - `src/services/`: Contains `apiService.js` (for calling the FastAPI backend) and `supabaseClient.js`.
  - `.env`: Holds the Vite environment variables, specifically the Supabase URL/Anon Key and the backend API URL.

## 5. Current State & Known Issues
- The application is actively functional. The backend FastAPI server runs on port `8000`, and the Vite frontend runs on port `5173`.
- **Supabase Dependency**: The frontend requires an active Supabase project for user authentication. If the configured Supabase URL is paused or deleted, the frontend will throw `ERR_NAME_NOT_RESOLVED` errors during login.
- **Ollama Dependency**: The backend will throw a `ConnectionRefused` or `404` error if the local Ollama application is not running or if the specific models (`mistral:7b-instruct` and `nomic-embed-text`) are not pulled.
