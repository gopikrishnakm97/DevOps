# DevOps AI Assistant (RAG-based)

This project demonstrates a basic Retrieval-Augmented Generation (RAG) pipeline using LangChain, Chroma, and OpenAI.

## Features

- Semantic search using embeddings
- Vector database using Chroma
- AI-powered responses using LLM
- DevOps-focused knowledge base

## Architecture

User Query → Embedding → Vector DB → Retrieve Docs → LLM → Response

## Tech Stack

- LangChain
- OpenAI
- Chroma DB

## How to Run

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=your-key
python app/rag_app.py
