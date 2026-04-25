# 🚀 DevOps AI Assistant (RAG + FastAPI)

A production-style **Retrieval-Augmented Generation (RAG)** based AI assistant designed for DevOps troubleshooting.

This project demonstrates how to build, expose, and scale an AI-powered backend service using modern LLMOps principles.

---

## 🧠 Key Features

* ✅ Semantic search using embeddings
* ✅ Vector database powered retrieval
* ✅ LLM-based intelligent responses
* ✅ FastAPI-based REST service (`/ask`)
* ✅ Source-aware answers (RAG pipeline)
* ✅ DevOps-focused knowledge base

---

## 🏗️ Architecture

```
Client (Postman / UI)
        ↓
FastAPI (/ask endpoint)
        ↓
RAG Pipeline
   ├── Embedding Model
   ├── Vector DB (Chroma)
   ├── Retriever (Top-K Search)
        ↓
LLM (Response Generation)
        ↓
JSON Response
```

---

## 🧰 Tech Stack

* Python
* LangChain
* Chroma (Vector Database)
* OpenAI (LLM + Embeddings)
* FastAPI
* Uvicorn

---

## 📁 Project Structure

```
app/
 ├── main.py          # FastAPI entry point
 ├── rag_pipeline.py  # RAG logic (retrieval + LLM)

requirements.txt
README.md
.env.example
```

---

## ⚙️ Setup & Run

### 1. Clone repo

```bash
git clone <your-repo-url>
cd <repo-name>
```

---

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

---

### 3. Set environment variable

```bash
export OPENAI_API_KEY=your-api-key
```

---

### 4. Run the API

```bash
uvicorn app.main:app --reload
```

---

### 5. Access API

* Swagger UI:

```
http://127.0.0.1:8000/docs
```

---

## 📡 API Usage

### POST `/ask`

#### Request

```json
{
  "question": "Why is my Kubernetes pod restarting?"
}
```

#### Response

```json
{
  "answer": "Your pod is restarting due to memory limits or failing health checks...",
  "sources": [
    "Pod restart issues are often caused by memory limits...",
    "CrashLoopBackOff occurs when..."
  ]
}
```

---

## 🧠 How It Works

1. User sends query via API
2. Query is converted into embeddings
3. Vector DB retrieves top relevant documents
4. Context + query sent to LLM
5. LLM generates final response

---

## 🔥 Key Concepts Demonstrated

* Retrieval-Augmented Generation (RAG)
* Embeddings & Vector Search
* Prompt-based LLM interaction
* API-driven AI systems
* Modular AI architecture

---

## ⚠️ Current Limitations

* No authentication
* No rate limiting
* No logging/monitoring
* Uses in-memory vector store

---

## 🚀 Future Improvements (LLMOps Roadmap)

* Add logging & observability (Prometheus, tracing)
* Dockerize the service
* Deploy on Kubernetes
* Add caching & cost optimization
* Implement authentication & rate limiting
* Replace in-memory DB with scalable vector DB

---

## 💼 Resume Highlight

> Built a FastAPI-based Retrieval-Augmented Generation (RAG) AI assistant for DevOps troubleshooting using LangChain, Chroma, and OpenAI, enabling semantic search and intelligent automated responses.

---

## 📌 Author

Gopikrishna KM
DevOps Engineer → LLMOps / AI Platform Engineer
