# TODO: Implement offline pipeline:
#       1. Load documents from data/docs/ (PDF, TXT, MD).
#       2. Implement recursive character chunking (512 tokens, 50 overlap).
#       3. Generate embeddings using engine.embeddings.
#       4. Save/Update index in data/vector_store/ (Chroma/FAISS).