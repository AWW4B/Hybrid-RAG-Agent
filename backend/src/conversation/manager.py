# TODO: Implement handle_message(session_id, message) logic:
#       1. Retrieve session history from Memory/CRM.
#       2. Perform RAG search via retrieval.search (if context is needed).
#       3. Construct Prompt (History + RAG Context + Tool Guidelines).
#       4. Query LLM and check for Tool Calls.
#       5. If Tool Call: Execute via Tool Orchestrator, get result, re-query LLM.
#       6. Finalize response and update CRM/Memory.