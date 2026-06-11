

from pydantic import BaseModel, Field
from datetime import datetime, timezone

class ChatRequest(BaseModel):
    message: str = Field(..., min_length = 1, max_length = 1000, description="The user's message to the chatbot")

    thread_id: str = Field( default = "default", description="Unique identifier for the conversation thread")

class ChatResponse(BaseModel):
    response: str = Field(..., description="The chatbot's response to the user's message")
    thread_id: str = Field(..., description="Unique identifier for the conversation thread")
    model_used: str
    cached: bool
    processed_time_ms: float
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of when the response was generated")

class HealthResponse(BaseModel):
    status: str = Field(..., description="Health status of the API")
    environment: str = Field(..., description="Current environment (development, production, etc.)")
    version: str = Field(..., description="Version of the API")
    checks: dict = Field(..., description="Detailed health checks for dependencies and services")

class MetricsResponse(BaseModel):
    total_requests: int = Field(..., description="Total number of requests received by the API")
    total_errors: int = Field(..., description="Total number of errors encountered by the API")
    error_rate: str = Field(..., description="Error rate as a percentage")
    average_response_time_ms: float = Field(..., description="Average response time in milliseconds")
    model_usage: dict = Field(..., description="Usage statistics for each model")
    cache_hit_rate: float = Field(..., description="Cache hit rate as a percentage")
    total_input_tokens: int = Field(..., description="Total number of input tokens processed")
    total_output_tokens: int = Field(..., description="Total number of output tokens generated")

class ErrorResponse(BaseModel):
    error: str | None = Field(..., description="Error message describing what went wrong")
    details: str | None = Field(..., description="Detailed information about the error for debugging purposes") 
    request_id: str | None = Field(..., description="Unique identifier for the request that caused the error") 