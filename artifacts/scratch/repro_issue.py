import asyncio
import os
import sys

# Add backend/src to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from src.engine.llm import llm_engine
from src.conversation.memory import init_sessions_from_db

async def test_query():
    # Initialize DB (creates tables if needed)
    init_sessions_from_db()
    
    session_id = "test_session_123"
    user_message = "I want to buy the most expensive Khaadi Mens Product"
    
    print(f"User: {user_message}")
    print("--- Streaming Response ---")
    
    async for chunk in llm_engine.stream(session_id, user_message):
        if "token" in chunk:
            print(chunk["token"], end="", flush=True)
        if chunk.get("done"):
            print(f"\nDone. Latency: {chunk.get('latency_ms')}ms")
    
    # Second turn
    user_message_2 = "what is the price of that product"
    print(f"\nUser: {user_message_2}")
    print("--- Streaming Response ---")
    
    async for chunk in llm_engine.stream(session_id, user_message_2):
        if "token" in chunk:
            print(chunk["token"], end="", flush=True)
        if chunk.get("done"):
            print(f"\nDone. Latency: {chunk.get('latency_ms')}ms")

if __name__ == "__main__":
    # We need to set up environment for the test
    os.environ["REDIS_URL"] = "redis://localhost:6379/0" # Ensure redis is available or mock it
    os.environ["MODEL_PATH"] = "d:/FAST Tasks/6th Semester/NLP/Assignment_3/models/qwen2.5-3b-instruct-q4_k_m.gguf"
    
    try:
        asyncio.run(test_query())
    except Exception as e:
        print(f"Error: {e}")
