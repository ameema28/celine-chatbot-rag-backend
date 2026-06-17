# app/database.py
import os
import json
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from app.config import settings

class VectorDatabase:
    def __init__(self):
        # Local model cache allocation
        self.encoder = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
        self.index = None
        self.documents = []
        self.load_and_index_knowledge()

    def load_and_index_knowledge(self):
        data_path = os.path.join(os.path.dirname(__file__), "..", "data", "salon_knowledge.json")
        
        if not os.path.exists(data_path):
            raise FileNotFoundError(f"Knowledge data missing at: {data_path}")
            
        with open(data_path, "r", encoding="utf-8") as f:
            self.documents = json.load(f)
            
        # Standardize RAG context chunk formatting
        corpus_texts = [
            f"Category: {doc['category']} | Question: {doc['question']} | Answer: {doc['answer']}"
            for doc in self.documents
        ]
        
        # Calculate embeddings
        embeddings = self.encoder.encode(corpus_texts, convert_to_numpy=True)
        dimension = embeddings.shape[1]
        
        # Construct an IndexFlatL2 distance tracker
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(embeddings.astype("float32"))
        print(f"Successfully indexed {self.index.ntotal} knowledge base segments into FAISS.")

    def search_context(self, query: str, top_k: int = 2):
        query_vector = self.encoder.encode([query], convert_to_numpy=True).astype("float32")
        distances, indices = self.index.search(query_vector, top_k)
        
        results = []
        for idx in indices[0]:
            if idx != -1 and idx < len(self.documents):
                results.append(self.documents[idx])
        return results

# Singleton database object
vector_db = VectorDatabase()