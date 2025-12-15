from pydantic import BaseModel, HttpUrl, Field
from typing import Optional
from datetime import datetime


class CrawlRequest(BaseModel):
    url: HttpUrl = Field(..., description="URL to crawl")
    
    class Config:
        json_schema_extra = {"example": {"url": "https://www.cnn.com/2013/06/10/politics/edward-snowden-profile/"}}


class PageMetadata(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    keywords: list[str] = Field(default_factory=list)
    author: Optional[str] = None
    canonical_url: Optional[str] = None
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    og_image: Optional[str] = None
    h1_tags: list[str] = Field(default_factory=list)
    h2_tags: list[str] = Field(default_factory=list)
    language: Optional[str] = None
    word_count: int = 0


class TopicClassification(BaseModel):
    primary_topic: Optional[str] = None
    topics: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class CrawlResponse(BaseModel):
    url: str
    success: bool
    crawled_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[PageMetadata] = None
    classification: Optional[TopicClassification] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
