# TODO: Register all tools (CRM + Weather + 2 others).
# TODO: Implement parse_and_execute(llm_output):
#       - Detect if the LLM output contains a tool call (JSON format).
#       - Route the call to the appropriate tool function asynchronously.
#       - Handle timeouts/errors and return a "graceful failure" message if a tool crashes.