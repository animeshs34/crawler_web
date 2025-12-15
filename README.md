# Web Crawler API

A modular web crawler for SEO metadata extraction and topic classification.

## Quick Start

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Server runs at http://localhost:8000

API docs: http://localhost:8000/docs

## API

### POST /api/v1/crawl

```bash
curl -X POST http://localhost:8000/api/v1/crawl \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.cnn.com/2013/06/10/politics/edward-snowden-profile/"}'
```

Response:
```json
{
  "url": "https://www.cnn.com/...",
  "success": true,
  "metadata": {
    "title": "...",
    "description": "...",
    "h1_tags": ["..."],
    "word_count": 1500
  },
  "classification": {
    "primary_topic": "Politics",
    "topics": ["Politics", "Technology"],
    "confidence": 0.85
  }
}
```

### GET /api/v1/health

Returns service health status.

## Architecture

```
API (FastAPI)
    │
    ▼
┌─────────────────────────────┐
│      Crawler Service        │
│  Fetcher → Extractor → Classifier
└─────────────────────────────┘
```

Each service module can be extracted to a microservice later.

## Docker

```bash
docker build -t web-crawler .
docker run -p 8000:8000 web-crawler
```

## Project Structure

```
app/
├── main.py          # entry point
├── config.py        # settings
├── api/routes.py    # endpoints
├── schemas/models.py
└── services/
    ├── fetcher.py
    ├── extractor.py
    └── classifier.py
```

## Environment Variables

- `DEBUG` - enable debug mode (default: false)
- `REQUEST_TIMEOUT` - HTTP timeout in seconds (default: 30)
- `MAX_CONTENT_LENGTH` - max HTML size in bytes (default: 10MB)
