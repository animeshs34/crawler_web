from fastapi import APIRouter, HTTPException
from datetime import datetime
import logging

from app.schemas.models import CrawlRequest, CrawlResponse, HealthResponse
from app.services.fetcher import get_fetcher
from app.services.extractor import get_extractor
from app.services.classifier import get_classifier
from app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    settings = get_settings()
    return HealthResponse(status="healthy", version=settings.app_version)


@router.post("/crawl", response_model=CrawlResponse, tags=["Crawler"])
async def crawl_url(request: CrawlRequest):
    url = str(request.url)
    logger.info(f"Crawl request: {url}")
    
    fetcher = get_fetcher()
    html, error = await fetcher.fetch(url)
    
    if error:
        return CrawlResponse(url=url, success=False, crawled_at=datetime.utcnow(), error=error)
    
    extractor = get_extractor()
    metadata = extractor.extract(html, url)
    
    classifier = get_classifier()
    classification = classifier.classify(metadata, html)
    
    return CrawlResponse(
        url=url,
        success=True,
        crawled_at=datetime.utcnow(),
        metadata=metadata,
        classification=classification
    )


@router.post("/batch", tags=["Crawler"])
async def batch_crawl(urls: list[str]):
    if len(urls) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 URLs per batch")
    
    results = []
    for url in urls:
        try:
            request = CrawlRequest(url=url)
            result = await crawl_url(request)
            results.append(result)
        except Exception as e:
            results.append(CrawlResponse(url=url, success=False, error=str(e)))
    
    return {"results": results, "total": len(results)}
