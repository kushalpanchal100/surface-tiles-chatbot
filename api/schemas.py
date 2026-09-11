import uuid
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, AliasChoices, field_validator


class ChatMessage(BaseModel):
    role: str = Field(
        ...,
        description="Role of the sender: 'user' or 'assistant' / 'model'",
        examples=["user", "assistant"]
    )
    content: str = Field(
        ...,
        validation_alias=AliasChoices("content", "message", "text"),
        description="Text content of the message",
        examples=["I need grey floor tiles for my bathroom."]
    )

    model_config = {
        "populate_by_name": True
    }


class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        validation_alias=AliasChoices("message", "query", "text", "prompt"),
        description="The customer question or tile requirement query.",
        examples=["What sizes are available in those?"]
    )
    session_id: Optional[str] = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Session UUID for automatic server-side conversational memory. Auto-generated as UUIDv4 if omitted.",
        examples=["123e4567-e89b-12d3-a456-426614174000"]
    )
    history: Optional[List[ChatMessage]] = Field(
        default=None,
        description="Optional client-supplied conversation history (overrides or seeds session memory).",
        examples=[[{"role": "user", "content": "Hello"}]]
    )

    @field_validator("session_id", mode="before")
    @classmethod
    def validate_or_generate_session_uuid(cls, v: Any) -> str:
        if v is None or (isinstance(v, str) and not v.strip()):
            return str(uuid.uuid4())
        try:
            return str(uuid.UUID(str(v).strip()))
        except (ValueError, AttributeError):
            raise ValueError("session_id must be a valid UUID string.")

    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "example": {
                "message": "What sizes are available in those?",
                "session_id": "123e4567-e89b-12d3-a456-426614174000"
            }
        }
    }


class ProductCardItem(BaseModel):
    id: str = Field(..., description="Shopify product ID")
    title: str = Field(..., description="Product name")
    handle: Optional[str] = Field(default=None, description="Shopify product handle")
    url: str = Field(..., description="Full URL to product on surfacestiles.co.uk")
    price: str = Field(..., description="Price string (e.g. £19.99)")
    price_per_m2: Optional[str] = Field(default=None, description="Price per square metre (e.g. £19.99 / m²)")
    image_url: Optional[str] = Field(default=None, description="Primary tile product image URL")
    images: Optional[List[str]] = Field(default=None, description="Product image gallery URLs")
    dimensions: Optional[str] = Field(default=None, description="Tile size / dimensions (e.g. 30X60 CM)")
    finish: Optional[str] = Field(default=None, description="Tile surface finish (e.g. Polished, Matt)")
    material: Optional[str] = Field(default=None, description="Tile material (e.g. Porcelain, Ceramic)")
    category: Optional[str] = Field(default=None, description="Tile category or suitability")
    sku: Optional[str] = Field(default=None, description="Product SKU")
    available: bool = Field(default=True, description="Whether product is in stock")
    variant_id: Optional[str] = Field(default=None, description="Shopify variant ID for Add to Cart & Checkout")
    variants: Optional[List[Dict[str, Any]]] = Field(default=None, description="All product variants")
    checkout_url: Optional[str] = Field(default=None, description="Direct Shopify checkout permalink")
    add_to_cart_url: Optional[str] = Field(default=None, description="Shopify add to cart endpoint URL")
    description_snippet: Optional[str] = Field(default=None, description="Key description highlights")


class SourceItem(BaseModel):
    title: str = Field(..., description="Title of the matched product, page, or article")
    url: str = Field(..., description="Direct link on surfacestiles.co.uk")
    category: Optional[str] = Field(default=None, description="Category or topic")
    content_type: Optional[str] = Field(default=None, description="Type: product, policy, faq, blog, page")
    price: Optional[str] = Field(default=None, description="Price string if applicable")
    relevance_score: Optional[float] = Field(default=None, description="Cosine similarity score (0.0 to 1.0)")
    image_url: Optional[str] = Field(default=None, description="Primary image URL if available")
    variant_id: Optional[str] = Field(default=None, description="Shopify variant ID if product")
    checkout_url: Optional[str] = Field(default=None, description="Direct checkout URL if product")


class ResponseMeta(BaseModel):
    status: int = Field(default=1, description="Status indicator (1 for success)")
    message: str = Field(
        default="Successfully processed user measurements and preferences",
        description="Response status message"
    )


class ChatData(BaseModel):
    Response: str = Field(..., description="Main response generated by the chatbot")
    products: Optional[List[ProductCardItem]] = Field(default=None, description="Visual tile product cards with image, price, Add to Cart & Checkout")
    sources: Optional[List[SourceItem]] = Field(default=None, description="Referenced website sources")
    session_id: Optional[str] = Field(default=None, description="Active session ID")


class ChatResponse(BaseModel):
    meta: ResponseMeta = Field(default_factory=ResponseMeta, description="Response metadata")
    data: ChatData = Field(..., description="Response data payload containing Response")
    statusCode: int = Field(default=200, description="HTTP status code")


class HealthResponse(BaseModel):
    status: str
    document_count: int
    gemini_configured: bool
    embedding_model: str
    llm_model: str
    version: str = "1.0.0"


class ScrapeRequest(BaseModel):
    run_in_background: bool = Field(default=False, description="Run scrape asynchronously in background")


class ScrapeResponse(BaseModel):
    status: str
    message: str
    counts: Optional[Dict[str, int]] = None


class IngestRequest(BaseModel):
    force_reset: bool = Field(default=True, description="Whether to clear existing vector store before re-indexing")
    run_in_background: bool = Field(default=False, description="Run ingestion in background task")


class IngestResponse(BaseModel):
    status: str
    message: str
    chunks_indexed: int


class SessionDetailResponse(BaseModel):
    session_id: str
    message_count: int
    history: List[ChatMessage]


class SessionListResponse(BaseModel):
    total_sessions: int
    sessions: List[str]


class JobStatusResponse(BaseModel):
    scrape_running: bool
    ingest_running: bool
    last_scrape: Optional[Dict[str, Any]] = None
    last_ingest: Optional[Dict[str, Any]] = None


class VoiceChatData(BaseModel):
    user_transcript: str = Field(..., description="Transcribed text of the user's voice message")
    Response: str = Field(..., description="Main response generated by the chatbot")
    audio_base64: str = Field(..., description="Base64 data URI of the synthesized voice response (MP3)")
    audio_format: str = Field(default="mp3", description="Audio format, e.g., 'mp3'")
    session_id: str = Field(..., description="Active session UUID")
    products: Optional[List[ProductCardItem]] = Field(default=None, description="Tile product cards with images, Add to Cart, and Checkout")
    sources: Optional[List[SourceItem]] = Field(default=None, description="Referenced tile product or page sources")
    timings: Optional[Dict[str, float]] = Field(default=None, description="Latency breakdown in seconds")


class VoiceChatResponse(BaseModel):
    meta: ResponseMeta = Field(default_factory=ResponseMeta, description="Response metadata")
    data: VoiceChatData = Field(..., description="Voice chat response payload")
    statusCode: int = Field(default=200, description="HTTP status code")


class TranscribeResponse(BaseModel):
    text: str = Field(..., description="Transcribed speech text")
    language: str = Field(default="en", description="Detected language code")
    duration: float = Field(..., description="Audio duration in seconds")
    latency_seconds: float = Field(..., description="STT inference processing time in seconds")


class SynthesizeRequest(BaseModel):
    text: str = Field(..., description="Text content to synthesize into natural speech")
    voice: Optional[str] = Field(default=None, description="Optional Edge-TTS voice (default: en-GB-SoniaNeural)")


class SynthesizeResponse(BaseModel):
    audio_base64: str = Field(..., description="Base64 data URI of synthesized MP3 audio")
    audio_format: str = Field(default="mp3", description="Audio format")
    clean_text: str = Field(..., description="Normalized speech text used for synthesis")
    latency_seconds: float = Field(..., description="Synthesis duration in seconds")


