# production-api

An API that wraps a chat workflow with production-grade security, caching, logging, monitoring, and an agent layer built with LangGraph.

## Features

- FastAPI service for chat and operational endpoints
- LangGraph-based agent with primary and fallback LLM calls
- Input security checks for prompt injection and PII patterns
- Output validation to mask or block sensitive content
- In-memory response cache with TTL
- Structured JSON logging
- Basic request metrics and health checks
- Rate limiting through `slowapi`

## LangGraph Flow

The agent is implemented as a small LangGraph state machine in `app/agent.py`.

1. `START -> process`
2. `process` calls the primary OpenAI chat model
3. If the primary model succeeds, the graph ends and returns that response
4. If the primary model fails, the graph routes to `fallback`
5. `fallback` calls the fallback OpenAI chat model
6. If the fallback also fails, the graph routes to `error`
7. `error` returns a safe apology message and ends the run

The graph stores a few fields in state:

- `messages`: conversation history passed through the graph
- `error`: the latest error string, if any
- `retry_count`: reserved for retry logic
- `model_used`: records whether the primary, fallback, or error handler produced the result

This makes the agent behavior explicit: try the primary model first, degrade to fallback on failure, and return a safe response if both models fail.
