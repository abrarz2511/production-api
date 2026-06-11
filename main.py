from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, HTTPException
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.extension import _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from langsmith import traceable
from dotenv import load_dotenv

load_dotenv()

from app.config import get_settings
from app.models import (
    ChatRequest, ChatResponse,
    HealthResponse, MetricsResponse, ErrorResponse
) 

from app.security import SecurityPipeline
from app.cache import ResponseCache
from app.monitoring import get_logger, MetricsCollector, RequestTimer
from app.agent import ProductionAgent

logger = get_logger()
security = None
cache = None
metrics = None
agent = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """ Initialize all at once, clean up on shutdown"""

    global security, cache, metrics, agent

    settings = get_settings()

    logger.info("startings Production API....", extra={"extra_data": {
        "environment" : settings.APP_ENV,
        "primary_model" : settings.primary_model,
        "tracing_enabled" : settings.LANGCHAIN_TRACING_V2,
    }})

    security = SecurityPipeline()
    cache = ResponseCache(ttl_seconds=settings.CACHE_TLL_SECONDS)
    metrics = MetricsCollector()
    agent = ProductionAgent()

    logger.info("All components intialized. Ready to serve requests.")

    yield

    logger.info("App shutting down")


limiter = Limiter(key_func=get_remote_address, headers_enabled=True)

app = FastAPI(
    title="production LangGraph API",
    description="A production-ready chat API with security, caching, and observability",
    version="1.0.0",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.get("/health", response_model=HealthResponse, tags=["operations"])
async def health_check():
    settings = get_settings()
    checks = {
        "security": security is not None,
        "cache": cache is not None,
        "metrics": metrics is not None,
        "agent": agent is not None,
    }
    is_healthy = all(checks.values())
    return HealthResponse(
        status="healthy" if is_healthy else "starting",
        environment=settings.APP_ENV,
        version=app.version,
        checks=checks,
    )


@app.get("/metrics", response_model=MetricsResponse, tags=["operations"])
async def metrics_check():
    if metrics is None:
        raise HTTPException(status_code=503, detail="Metrics collector is not ready")
    return MetricsResponse(**metrics.get_summary())


@app.get("/cache/stats", tags=["operations"])
async def cache_state_check():
    if cache is None:
        raise HTTPException(status_code=503, detail="Cache is not ready")
    return cache.stats()


@app.post("/chat", response_model=ChatResponse)
@limiter.limit(lambda: get_settings().RATE_LIMIT)
@traceable(name="chat_endpoint")
async def chat(request: Request, response: Response, body: ChatRequest):
    """ Main Chat Endpoint:
        1. Security check 
        2. Cache Lookup
        3. Langgraph agent invoke
        4. Ouptut validation
        5. Cache store
        6. Return Response
    """
    with RequestTimer() as timer:
        security_notes = []

        #Security check
        is_allowed, cleaned_message, notes = security.check_input(body.message)
        security_notes.extend(notes)

        if not is_allowed:
            logger.warning("Request blocked by security", extra={"extra_data": {
                "reason": notes,
                "thread_id": body.thread_id,
            }})
            metrics.record_request(latency_ms=0, error=True)
            raise HTTPException(
                status_code=400,
                detail="Message blocked by security filters"
            )

        #cache lookup
        cached_response = cache.get(cleaned_message)
        if cached_response is not None:
            metrics.record_request(latency_ms=0, cache_hit=True)
            logger.info("Cache hit", extra={"extra_data": {
                "thread_id" : body.thread_id,
            }})
            return ChatResponse(
                response=cached_response,
                thread_id=body.thread_id,
                model_used="cache",
                cached=True,
                processed_time_ms=0,
            )

        #invoke langgraph agent
        try:
            result = agent.invoke(cleaned_message)

        except Exception as e:
            logger.error(
                f"Agent invocation failed: {e}",
                extra={"extra_data": {
                    "thread_id": body.thread_id,
                    "error": str(e),
                }},
            )
            metrics.record_request(
                latency_ms=0,
                input_tokens=0,
                output_tokens=0,
                error=True,
            )
            raise HTTPException(
                status_code=500,
                detail="An error occurred while processing request",
            ) from e

        response_text = result["response"]
        model_used = result["model_used"]

        #AI output validation
        _, validated_response, output_warning = security.validate_output(response_text)
        output_warnings = [output_warning] if output_warning else []
        security_notes.extend(output_warnings)

        #Cache store
        cache.set(cleaned_message, validated_response)

    #log & record metrics
    input_tokens = int(len(cleaned_message.split()) * 1.3)
    output_tokens = int(len(validated_response.split()) * 1.3)

    metrics.record_request(
        latency_ms=timer.elapsed_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_hit=False,
    )

    if security_notes:
        logger.info("security notes", extra={"extra_data" : {
            "notes": security_notes,
            "thread_id": body.thread_id,
        }})
    
    return ChatResponse(
        response = validated_response,
        thread_id=body.thread_id,
        model_used=model_used,
        cached=False,
        processed_time_ms=round(timer.elapsed_ms, 2),
    )

    
