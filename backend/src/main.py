# TODO: Initialize FastAPI app and global state (LLM, Embeddings, VectorDB).
# TODO: Implement WebSocket route:
#       - Handle connection/disconnection.
#       - Parse incoming JSON (session_id, user_message).
#       - Call ConversationManager.handle_message().
#       - Stream tokens back to frontend in real-time.
# TODO: Implement a REST endpoint for health checks (required for Cloud Deployment).