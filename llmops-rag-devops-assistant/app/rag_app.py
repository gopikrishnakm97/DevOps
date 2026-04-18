from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.vectorstores import Chroma
from langchain.chains import RetrievalQA
import os

# Load API Key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Sample DevOps Knowledge Base
docs = [
    "Kubernetes CrashLoopBackOff occurs when a container repeatedly fails to start.",
    "Terraform state lock error happens when another process is holding the lock.",
    "CI/CD pipeline failure can occur due to incorrect environment variables.",
    "Pod restart issues are often caused by memory limits or liveness probe failures."
]

# Step 1: Embeddings + Vector DB
embeddings = OpenAIEmbeddings()
vector_db = Chroma.from_texts(docs, embeddings)

# Step 2: Retriever
retriever = vector_db.as_retriever(search_kwargs={"k": 2})

# Step 3: LLM
llm = ChatOpenAI(temperature=0.2)

# Step 4: RAG Chain
qa_chain = RetrievalQA.from_chain_type(
    llm=llm,
    retriever=retriever,
    return_source_documents=True
)

# Step 5: Query
query = input("Ask your DevOps question: ")

result = qa_chain(query)

print("\nAnswer:\n", result["result"])
print("\nSources:\n", result["source_documents"])
