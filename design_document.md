# Web Crawler Scale Design Document

## Overview
This doc outlines how we're gonna scale our existing crawler from handling single URLs to processing billions of URLs monthly for major e-commerce sites. Currently we have a simple FastAPI app that works great for small scale, but we need to rethink everything for enterprise scale.

**Current state:** Single instance crawler, ~5-10 URLs/second
**Target state:** Distributed system handling 1B+ URLs/month (~400 URLs/second sustained)

---

## Part 1: High-Level Architecture

### Current Problems
- Single point of failure (one FastAPI instance)
- No queue management for billions of URLs
- Memory constraints with large batches
- No respect for robots.txt (this is bad!)
- No deduplication of URLs
- Can't handle retries properly

### Proposed Architecture

```
Input Sources                Processing Layer              Storage Layer
-------------               ------------------            --------------
Text Files  ----->
                  |---> URL Queue --> Worker Pool --> Data Lake (S3)
MySQL DB    ----->      (Kafka)      (K8s Pods)    --> Metadata DB (Postgres)
                                                    --> Search Index (Elasticsearch)
```

Main components:
1. **URL Ingestion Service** - handles bulk uploads from files/MySQL
2. **Queue System** (Kafka/RabbitMQ) - distributes work
3. **Worker Fleet** - actual crawling happens here
4. **Storage Systems** - where we keep everything

### Technology Choices

**Message Queue**: Kafka
- Can handle billions of messages
- Built-in partitioning for parallelization
- Replay capability if something goes wrong
- Actually tested at this scale

**Worker Orchestration**: Kubernetes
- Auto-scaling based on queue depth
- Self-healing when workers die
- Easy to deploy updates
- Good cost control with spot instances

**Primary Storage**:
- S3 for HTML content (cheap for large files)
- PostgreSQL for metadata (need fast queries)
- Redis for caching and dedup

---

## Part 2: System Components Detail

### 2.1 URL Ingestion Service

Handles bulk URL uploads from various sources.

```python
# Rough implementation idea
class URLIngestionService:
    def __init__(self):
        self.kafka_producer = KafkaProducer()
        self.dedup_cache = RedisCache()

    async def ingest_from_file(self, file_path):
        # Stream file, don't load all in memory!
        with open(file_path, 'r') as f:
            batch = []
            for line in f:
                url = line.strip()
                if not self.dedup_cache.exists(url):
                    batch.append(url)
                    if len(batch) >= 10000:
                        await self.kafka_producer.send_batch(batch)
                        batch = []
```

**Input formats supported:**
- CSV/TSV files with URLs
- MySQL bulk export
- S3 bucket uploads
- API endpoint for smaller batches

### 2.2 Queue Architecture

Using Kafka topics with smart partitioning:

```
Topic Structure:
- crawler.urls.priority.high    (time-sensitive URLs)
- crawler.urls.priority.normal  (regular crawling)
- crawler.urls.priority.low     (backfill, historical)
- crawler.urls.retry            (failed URLs for retry)
```

Partitioning strategy by domain to ensure politeness:
- Partition = hash(domain) % num_partitions
- This ensures same domain URLs go to same partition
- Workers can rate-limit per domain easier

### 2.3 Worker Pool Design

Each worker is a container running our crawler code with modifications:

```python
class DistributedCrawlerWorker:
    def __init__(self, worker_id):
        self.worker_id = worker_id
        self.rate_limiter = DomainRateLimiter()
        self.robots_checker = RobotsChecker()

    async def process_url(self, url):
        domain = extract_domain(url)

        # Check robots.txt first
        if not await self.robots_checker.can_fetch(url):
            return CrawlResult(url, blocked=True)

        # Rate limiting per domain
        await self.rate_limiter.wait_if_needed(domain)

        # Original crawl logic here
        result = await self.crawl(url)

        # Store results
        await self.store_results(result)
```

**Worker Scaling Strategy:**
- Minimum: 100 workers (handles baseline load)
- Maximum: 5000 workers (cost constraint)
- Scale based on queue depth and processing rate
- Use spot instances for 70% of workers (way cheaper)

---

## Part 3: Storage Design

### 3.1 Data Storage Architecture

**Hot Storage (Recent 7 days)**
- PostgreSQL for metadata
- Redis for frequently accessed content
- ~100TB expected

**Warm Storage (7-30 days)**
- PostgreSQL read replicas
- S3 Standard
- ~500TB expected

**Cold Storage (30+ days)**
- S3 Glacier for HTML content
- PostgreSQL partitioned tables (monthly)
- Compressed JSON exports

### 3.2 Unified Schema Design

Main tables structure:

```sql
-- Core crawl metadata
CREATE TABLE crawl_metadata (
    id BIGSERIAL PRIMARY KEY,
    url TEXT NOT NULL,
    domain VARCHAR(255) NOT NULL,
    crawled_at TIMESTAMP NOT NULL,
    status VARCHAR(50),
    response_time_ms INTEGER,
    content_hash VARCHAR(64),

    -- SEO fields
    title TEXT,
    description TEXT,
    keywords TEXT[],
    h1_tags TEXT[],
    word_count INTEGER,

    -- Classification
    primary_topic VARCHAR(100),
    topic_confidence DECIMAL(3,2),
    topics JSONB,

    -- Indexing
    INDEX idx_domain_date (domain, crawled_at DESC),
    INDEX idx_url_hash (md5(url))
) PARTITION BY RANGE (crawled_at);

-- HTML content storage reference
CREATE TABLE content_storage (
    url_hash VARCHAR(64) PRIMARY KEY,
    s3_bucket VARCHAR(100),
    s3_key TEXT,
    content_size_bytes BIGINT,
    compression_type VARCHAR(20),
    created_at TIMESTAMP
);

-- Domain statistics for monitoring
CREATE TABLE domain_stats (
    domain VARCHAR(255),
    date DATE,
    total_crawled INTEGER,
    success_count INTEGER,
    error_count INTEGER,
    avg_response_time_ms INTEGER,
    PRIMARY KEY (domain, date)
);
```

### 3.3 Data Retention Policy

- Metadata: Keep forever (relatively small)
- HTML Content:
  - Full HTML: 90 days
  - Compressed HTML: 1 year
  - Text extract only: Forever
- Logs: 30 days

---

## Part 4: Politeness & Robots.txt

### 4.1 Robots.txt Handling

Really important - we don't want to get blocked!

```python
class RobotsManager:
    def __init__(self):
        self.cache = {}  # domain -> rules
        self.cache_ttl = 3600  # 1 hour

    async def check_url(self, url):
        domain = get_domain(url)

        # Check cache first
        if domain not in self.cache or self.is_expired(domain):
            robots_url = f"https://{domain}/robots.txt"
            rules = await self.fetch_and_parse(robots_url)
            self.cache[domain] = rules

        return self.cache[domain].can_fetch("*", url)
```

### 4.2 Rate Limiting Configuration

Per-domain rate limits (configurable):

```yaml
rate_limits:
  default:
    requests_per_second: 10
    burst_size: 20

  # Special cases for big sites
  amazon.com:
    requests_per_second: 50  # they can handle it
    burst_size: 100

  walmart.com:
    requests_per_second: 30
    burst_size: 60

  # Be extra careful with small sites
  small_sites:
    requests_per_second: 2
    burst_size: 5
```

---

## Part 5: Performance Optimizations

### 5.1 Cost Optimization

1. **Spot Instances**: Use for 70% of workers (save ~60% on compute)
2. **S3 Intelligent Tiering**: Automatic cost optimization for storage
3. **Reserved Capacity**: For baseline load (save 30%)
4. **Compression**: gzip HTML before storing (save 70% storage)

Estimated monthly costs:
- Compute (EC2): ~$15,000
- Storage (S3): ~$5,000
- Database (RDS): ~$3,000
- Data Transfer: ~$2,000
- **Total: ~$25,000/month** for 1B URLs

### 5.2 Performance Targets

**Crawling Speed:**
- Average: 400 URLs/second
- Peak: 1000 URLs/second
- Minimum: 100 URLs/second

**Latency Targets:**
- P50: < 2 seconds per URL
- P95: < 10 seconds per URL
- P99: < 30 seconds per URL

### 5.3 Reliability Measures

1. **Retry Logic**: 3 retries with exponential backoff
2. **Circuit Breakers**: Stop hammering broken sites
3. **Dead Letter Queue**: For URLs that consistently fail
4. **Checkpointing**: Save progress every 1000 URLs

---

## Part 6: SLOs and SLAs

### Service Level Objectives (SLOs)

| Metric | Target | Measurement |
|--------|--------|-------------|
| Availability | 99.9% | Successful crawls / Total attempts |
| Data Freshness | < 24 hours | Time from URL submission to crawl |
| Processing Rate | > 400 URLs/sec | 5-minute average |
| Error Rate | < 5% | Failed crawls / Total crawls |
| Data Accuracy | > 95% | Spot-checked samples |

### Service Level Agreements (SLAs)

For internal consumers:
- **Availability SLA**: 99.5% uptime (allows ~3.5 hours downtime/month)
- **Performance SLA**: 90% of URLs processed within 6 hours
- **Data Quality SLA**: Less than 1% data corruption/loss

Penalties for SLA breach:
- Availability: Service credits for downtime
- Performance: Priority processing for delayed URLs
- Quality: Re-crawl affected URLs at no cost

---

## Part 7: Monitoring & Observability

### 7.1 Key Metrics to Track

**System Metrics:**
```
- URLs processed per second
- Queue depth (by priority)
- Worker utilization
- Error rate by domain
- Response time distribution
- Storage usage growth
```

**Business Metrics:**
```
- Cost per 1000 URLs
- Coverage by domain
- Data freshness
- Topic classification accuracy
```

### 7.2 Monitoring Stack

**Metrics Collection**: Prometheus + Grafana
- All workers emit metrics
- 1-minute scrape interval
- 90-day retention

**Logging**: ELK Stack (Elasticsearch, Logstash, Kibana)
- Structured JSON logs
- Centralized log aggregation
- Full-text search capability

**Tracing**: Jaeger
- Distributed tracing for debugging
- Sample 1% of requests

**Alerting**: PagerDuty + Slack
- Critical alerts → PagerDuty
- Warnings → Slack channel
- Daily summary reports

### 7.3 Dashboard Examples

Main Operations Dashboard should show:
1. Current crawl rate (real-time)
2. Queue depths by priority
3. Error rates by domain (top 10)
4. Worker pool status
5. Cost burn rate
6. Storage growth

### 7.4 Alert Thresholds

**Critical Alerts (wake someone up):**
- Crawl rate < 100 URLs/sec for 5 minutes
- Error rate > 20%
- Queue depth > 10M URLs
- Storage > 90% capacity

**Warning Alerts (Slack notification):**
- Crawl rate < 300 URLs/sec
- Error rate > 10%
- Specific domain error rate > 50%
- Cost overrun > 20%

---

## Open Questions & Concerns

1. **Legal considerations**: Do we need explicit permission for large-scale crawling?
2. **IP Rotation**: Should we use proxy services to avoid IP bans?
3. **International domains**: How do we handle non-English content classification?
4. **JavaScript rendering**: Current crawler doesn't handle JS-heavy sites
5. **Mobile vs Desktop**: Should we crawl both versions?

## Risks

- Getting blocked by major sites (need good relationships)
- Cost overruns if not carefully managed
- Data quality issues at scale
- Regulatory compliance (GDPR, etc)

---

## Appendix A: Cost Breakdown

Detailed AWS cost estimate for 1B URLs/month:

```
EC2 (Workers):
- 100 t3.medium reserved: $3,000/month
- 300 t3.medium spot (avg): $4,500/month
- Load balancers: $500/month

Storage:
- S3 Standard (100TB): $2,300/month
- S3 Glacier (1PB): $1,000/month
- EBS volumes: $500/month

Database:
- RDS PostgreSQL (r5.4xlarge): $2,000/month
- Read replicas: $1,000/month

Networking:
- Data transfer: $2,000/month
- CloudFront CDN: $500/month

Other:
- ElastiCache Redis: $800/month
- MSK (Kafka): $1,500/month
- Monitoring: $400/month

Total: ~$20,000/month
```
