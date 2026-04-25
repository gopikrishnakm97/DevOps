from fastapi import FastAPI
from pydantic import BaseModel
from rag_app import ask_question

app = FastAPI()

class QueryRequest(BaseModel):
    question: str

@app.get("/")
def root():
    return {"message": "DevOps AI Assistant is running"}

@app.post("/ask")
def ask(req: QueryRequest):
    response = ask_question(req.question)
    return response
