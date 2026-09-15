# Design Document — SIH26069: National Weather Big Data Analytics Platform

## System Architecture

### High-Level Architecture Diagram (Text/Mermaid)

```mermaid
graph TB
    subgraph "Data Sources"
        A[Twitter/X Mock Feed]
        B[Citizen Web Form]
        C[IMD API / data.gov.in]
        D[OpenWeatherMap API]
    end

    subgraph "Ingestion Layer"
        E[Kafka Topic: weather-reports-raw]
    end

    subgraph "Processing Layer"
        F[FastAPI Consumer Service]
        G[Celery Workers + Redis Queue]
        H[ML Pipeline]
    end

    subgraph "ML Pipeline Components"
        H1[Event Classifier<br/>HuggingFace Zero-Shot]
        H2[Image pHash Deduplicator<br/>imagehash library]
        H3[Text Embedding Deduplicator<br/>sentence-transformers]
        H4[Ground-Truth Verifier<br/>IMD/OpenWeatherMap Cross-Check]
    end

    subgraph "Storage Layer"
        I[PostgreSQL + PostGIS<br/>weather_reports table]
        J[MinIO S3-Compatible<br/>Media Storage]
        K[Redis<br/>Cache & Celery Broker]
    end

    subgraph "Presentation Layer"
        L[Next.js Dashboard<br/>Map + Analytics]
        M[Admin Panel<br/>Review Queue]
    end

    A --> E
    B --> E
    C --> E
    D --> E

    E --> F
    F --> G
    G --> H

    H --> H1
    H --> H2
    H --> H3
    H --> H4

    H1 --> I
    H2 --> I
    H3 --> I
    H4 --> I

    B --> J
    J --> I

    I --> L
    I --> M

    F -.WebSocket.-> L
    K -.Cache.-> F
    K -.Broker.-> G
```

---

## Component Breakdown

### 1. Ingestion Layer

**Kafka (Single-Broker)**
- **Purpose:** Centralized message bus for all weather report sources
- **Topics:**
  - `weather-reports-raw` — All incoming reports before processing
  - `weather-reports-verified` — Reports that passed verification pipeline
- **Configuration:** 
  - Single broker (no cluster complexity)
  - Replication factor: 1
  - Retention: 7 days
- **Why Kafka?** Honest answer for jury: provides replay capability for demo, industry-standard ingestion pattern, scales horizontally when needed (even if demo doesn't need it yet)

**Source Connectors:**
- **Twitter/X Mock Feed:** Python script reads `data/mock_tweets.jsonl`, publishes to Kafka at configurable rate (default: 10 tweets/min)
- **Citizen Form:** Next.js API route → Kafka producer
- **IMD/OpenWeatherMap:** Cron job (every 6 hours) fetches district rainfall/forecast → publishes batch to Kafka
- **Manual Injection Endpoint:** FastAPI `/api/admin/inject-report` for demo control

---

### 2. Processing Layer

**FastAPI Consumer Service (`backend/app/ingestion/kafka_consumer.py`)**
- Subscribes to `weather-reports-raw`
- Parses each message → creates Celery task
- Returns immediately (non-blocking)

**Celery Task Queue**
- **Broker:** Redis
- **Workers:** 4 parallel workers (configurable via Docker Compose)
- **Task Flow:**
  ```
  1. save_raw_report(message) → insert into DB with status=pending
  2. verify_report(report_id)
     ├── ground_truth_check(report_id)  [Signal 1]
     ├── image_hash_check(report_id)    [Signal 2]
     └── text_dedup_check(report_id)    [Signal 3]
  3. classify_event(report_id) → ML classification
  4. compute_confidence_score(report_id) → weighted average of signals
  5. update_report_status(report_id) → verified/disputed/fake
  6. publish_to_verified_topic(report_id) → Kafka verified topic
  7. send_websocket_update(report_id) → notify dashboard
  ```

**Task Priorities:**
- High: Citizen form submissions (user expects immediate feedback)
- Medium: Social media (demo visibility)
- Low: Batch API imports (background refresh)

---

### 3. ML Pipeline

#### 3.1 Event Classifier

**Model:** `facebook/bart-large-mnli` (zero-shot classification via HuggingFace)

**Why zero-shot?** No time to collect/label training data in hackathon. Zero-shot lets us define categories as text prompts.

**Labels:**
```python
labels = [
    "heavy rainfall", "flooding", "thunderstorm and lightning",
    "extreme heat and heatwave", "dense fog", "dust storm", "strong winds"
]
```

**Input:** Report text (English/Hindi/regional language)

**Output:** 
```json
{
  "event_type": "flooding",
  "confidence": 0.87,
  "all_scores": { "flooding": 0.87, "rainfall": 0.65, ... }
}
```

**Fallback:** If confidence < 0.6, use user-declared category from form.

**Multilingual Support:**
- For Hindi/regional languages, use `ai4bharat/indic-bert` (optional stretch goal) or Google Translate API → English → BART

---

#### 3.2 Image pHash Deduplicator

**Library:** `imagehash` (Python, perceptual hashing)

**Algorithm:**
1. Compute pHash of uploaded image (produces 64-bit hash)
2. Query database for all existing image hashes
3. Compute Hamming distance between new hash and each existing hash
4. If Hamming distance < 10 → flag as near-duplicate

**Pre-Seeded Fake Hashes:**
- `data/known_fake_hashes.txt` contains pHashes of common "disaster stock photos" scraped from Google Images
- These are checked first before comparing against user-uploaded images

**Signal Output:**
```json
{
  "image_hash_signal": {
    "is_duplicate": false,
    "closest_match_distance": 15,
    "confidence": 1.0  // 1.0 = unique, 0.0 = exact duplicate
  }
}
```

---

#### 3.3 Text Embedding Deduplicator

**Model:** `sentence-transformers/all-MiniLM-L6-v2` (80MB, fast inference)

**Algorithm:**
1. Embed new report text → 384-dim vector
2. Query existing reports from same region + event type in last 24h
3. Compute cosine similarity between new embedding and each existing embedding
4. If similarity > 0.92 → merge into existing event cluster (don't create new record)

**Event Clustering:**
- Reports with >0.92 similarity are grouped into `event_clusters` table
- Each cluster gets a canonical `cluster_id` and representative text
- Dashboard shows clusters as single pin with count badge

**Signal Output:**
```json
{
  "text_dedup_signal": {
    "is_duplicate": false,
    "cluster_id": null,
    "closest_match_similarity": 0.78,
    "confidence": 0.95
  }
}
```

---

#### 3.4 Ground-Truth Verifier (Most Important)

**Data Sources:**
- **OpenWeatherMap API:** Current conditions + 5-day history (free tier: 1000 calls/day)
- **IMD Open Data:** District-wise daily rainfall CSVs (scraped/downloaded)
- **MOSDAC (ISRO):** Satellite rainfall estimates (GeoTIFF files, downloaded weekly for demo)

**Algorithm:**
1. Extract location (lat/lon) and timestamp from report
2. Query OpenWeatherMap historical weather for that location in ±48h window
3. Check event plausibility:
   - **Flooding:** Requires >50mm rainfall in 24h within 50km radius
   - **Heatwave:** Requires temperature >40°C for 3+ consecutive days
   - **Thunderstorm:** Requires precipitation + wind speed >20 km/h
   - **Dust storm:** Requires wind speed >40 km/h + low humidity
4. Compute plausibility score (0.0–1.0)

**Signal Output:**
```json
{
  "ground_truth_signal": {
    "plausible": true,
    "recorded_rainfall_mm": 78.5,
    "expected_rainfall_mm": 60.0,
    "confidence": 0.85,
    "data_source": "OpenWeatherMap",
    "query_timestamp": "2026-09-14T08:30:00Z"
  }
}
```

**Fallback:** If API is down, mark report as `unverified` with confidence = 0.5, don't block ingestion.

---

#### 3.5 Confidence Score Calculation

**Formula:**
```python
confidence = (
    0.5 * ground_truth_signal.confidence +
    0.3 * image_hash_signal.confidence +
    0.2 * text_dedup_signal.confidence
)
```

**Thresholds:**
- `confidence > 0.7` → `verified` (green)
- `0.4 <= confidence <= 0.7` → `disputed` (yellow)
- `confidence < 0.4` → `fake` (red)

**Edge Cases:**
- Missing image → use only ground_truth + text_dedup (renormalize weights to 0.7 + 0.3)
- Missing GPS → reduce ground_truth weight by 50%, add location_confidence penalty

---

### 4. Storage Layer

#### 4.1 PostgreSQL + PostGIS Schema

**Table: `weather_reports`**
```sql
CREATE TABLE weather_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type VARCHAR(50) NOT NULL, -- 'twitter' | 'citizen_form' | 'imd_api' | 'openweather'
    source_id VARCHAR(255),            -- tweet_id, form_submission_id, etc.
    
    -- Content
    raw_text TEXT NOT NULL,
    event_type VARCHAR(50),            -- rainfall, flooding, thunderstorm, etc.
    event_type_confidence FLOAT,
    
    -- Location
    location GEOGRAPHY(Point, 4326),   -- PostGIS point (lat, lon)
    city VARCHAR(100),
    state VARCHAR(100),
    location_source VARCHAR(50),       -- 'gps_verified' | 'text_inferred' | 'gps_suspicious'
    location_confidence VARCHAR(20),   -- 'high' | 'medium' | 'low'
    
    -- Media
    media_urls TEXT[],                 -- Array of MinIO URLs
    image_hashes TEXT[],               -- Array of pHash strings
    
    -- Verification
    verification_status VARCHAR(20),   -- 'verified' | 'disputed' | 'unverified' | 'fake'
    confidence_score FLOAT,
    signals JSONB,                     -- Stores all three signal outputs
    
    -- Clustering
    cluster_id UUID,                   -- FK to event_clusters table
    
    -- Admin
    admin_override BOOLEAN DEFAULT FALSE,
    admin_notes TEXT,
    admin_user_id UUID,
    
    -- Timestamps
    reported_at TIMESTAMP NOT NULL,
    ingested_at TIMESTAMP DEFAULT NOW(),
    verified_at TIMESTAMP,
    
    -- Indexes
    CONSTRAINT valid_confidence CHECK (confidence_score BETWEEN 0.0 AND 1.0)
);

CREATE INDEX idx_location ON weather_reports USING GIST(location);
CREATE INDEX idx_reported_at ON weather_reports(reported_at);
CREATE INDEX idx_verification_status ON weather_reports(verification_status);
CREATE INDEX idx_event_type ON weather_reports(event_type);
CREATE INDEX idx_cluster_id ON weather_reports(cluster_id);
```

**Table: `event_clusters`**
```sql
CREATE TABLE event_clusters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(50),
    canonical_text TEXT,               -- Representative text for cluster
    centroid GEOGRAPHY(Point, 4326),   -- Geographic center of cluster
    report_count INT DEFAULT 1,
    first_reported_at TIMESTAMP,
    last_reported_at TIMESTAMP
);
```

**Table: `verification_logs`**
```sql
CREATE TABLE verification_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id UUID REFERENCES weather_reports(id),
    verification_step VARCHAR(100),    -- 'ground_truth_check', 'image_hash', etc.
    result JSONB,
    executed_at TIMESTAMP DEFAULT NOW()
);
```

**Table: `admin_users`** (simple auth for demo)
```sql
CREATE TABLE admin_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

#### 4.2 MinIO Object Storage

**Bucket:** `weather-media`

**Folder Structure:**
```
weather-media/
├── images/
│   ├── 2026/09/14/
│   │   ├── <uuid>.jpg
│   │   └── <uuid>.png
└── videos/
    └── 2026/09/14/
        └── <uuid>.mp4
```

**Access:** Pre-signed URLs with 7-day expiration, stored in `media_urls` array in Postgres.

---

#### 4.3 Redis

**Use Cases:**
1. **Celery Broker:** Task queue for verification pipeline
2. **Cache:** Geocoding results (city name → lat/lon) to avoid repeated API calls
3. **Rate Limiting:** Track API call counts to OpenWeatherMap (stay under 1000/day free tier)

**Key Patterns:**
```
geocode:<city_name> → { "lat": 28.7041, "lon": 77.1025 }
api_calls:openweather:<date> → 847
```

---

### 5. Presentation Layer

#### 5.1 Next.js Dashboard (`frontend/app/page.tsx`)

**Components:**
- **Map (Leaflet.js):**
  - Clustered markers (MarkerClusterGroup)
  - Color-coded by verification status
  - Click → popup with report details
  - Heatmap layer toggle
  
- **Filter Panel:**
  - Date range picker (react-datepicker)
  - Event type checkboxes
  - State/city autocomplete (react-select)
  - Verification status checkboxes
  
- **Analytics Panel:**
  - Time-series bar chart (Recharts): reports per day
  - Pie chart: event type distribution
  - Stat cards: total reports, verified %, fake %

**Real-Time Updates:**
- Socket.io client subscribes to `report:new` event
- Backend emits event after each verified report
- New marker animates onto map without refresh

**API Endpoints (consumed by frontend):**
```
GET /api/reports?date_from=X&date_to=Y&event_type=Z&state=W&status=V
GET /api/analytics/time-series?interval=day
GET /api/analytics/breakdown?by=event_type
```

---

#### 5.2 Admin Panel (`frontend/app/admin/page.tsx`)

**Features:**
- **Login:** Simple JWT auth (username/password)
- **Review Queue:** Table of disputed reports (0.4 < confidence < 0.7)
- **Per-Report View:**
  - Full text, images, location
  - Confidence breakdown (3 signals visualized as progress bars)
  - Ground-truth data panel (shows IMD rainfall records)
  - Action buttons: Mark as Verified / Mark as Fake / Add Note
  
**API Endpoints:**
```
POST /api/admin/login → JWT token
GET /api/admin/review-queue
POST /api/admin/reports/:id/verify
POST /api/admin/reports/:id/reject
```

---

#### 5.3 Citizen Report Form (`frontend/app/submit/page.tsx`)

**Form Fields:**
- Event type (dropdown)
- Description (textarea, max 500 chars)
- City (autocomplete from Indian cities list)
- State (dropdown)
- GPS (auto-filled from browser, optional)
- Photo/video upload (optional, max 10MB)

**Submission Flow:**
1. Form validation (Zod schema)
2. Upload media to MinIO (if present)
3. POST to `/api/reports/submit`
4. Backend publishes to Kafka
5. Return to user: "Report submitted! Track status on dashboard."

---

## API Contracts

### Public Endpoints

**POST /api/reports/submit**
```json
Request:
{
  "event_type": "flooding",
  "description": "Heavy waterlogging near Marine Drive, vehicles stranded",
  "city": "Mumbai",
  "state": "Maharashtra",
  "gps": { "lat": 18.9432, "lon": 72.8234 },
  "media_files": ["<base64_encoded_image>"]
}

Response:
{
  "report_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Report submitted successfully"
}
```

**GET /api/reports**
```json
Query Params:
?date_from=2026-09-01&date_to=2026-09-14
&event_type=flooding,rainfall
&state=Maharashtra
&status=verified,disputed
&limit=100&offset=0

Response:
{
  "reports": [
    {
      "id": "...",
      "event_type": "flooding",
      "description": "...",
      "location": { "lat": 18.9432, "lon": 72.8234 },
      "city": "Mumbai",
      "verification_status": "verified",
      "confidence_score": 0.85,
      "reported_at": "2026-09-14T10:30:00Z",
      "media_urls": ["https://minio.local/..."]
    }
  ],
  "total": 1247,
  "limit": 100,
  "offset": 0
}
```

---

### Admin Endpoints

**POST /api/admin/login**
```json
Request:
{
  "username": "admin",
  "password": "demo123"
}

Response:
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user_id": "...",
  "expires_in": 3600
}
```

**GET /api/admin/review-queue**
```json
Response:
{
  "reports": [
    {
      "id": "...",
      "description": "...",
      "confidence_score": 0.55,
      "signals": {
        "ground_truth": { "confidence": 0.6, "recorded_rainfall_mm": 15 },
        "image_hash": { "confidence": 0.5, "is_duplicate": false },
        "text_dedup": { "confidence": 0.8, "is_duplicate": false }
      },
      "reported_at": "2026-09-14T08:00:00Z"
    }
  ]
}
```

**POST /api/admin/reports/:id/verify**
```json
Request:
{
  "admin_notes": "Cross-checked with local news, confirmed real event"
}

Response:
{
  "report_id": "...",
  "verification_status": "verified",
  "confidence_score": 0.85  // recalculated with admin override weight
}
```

---

## Deployment Architecture (Docker Compose)

**Services:**
```yaml
services:
  postgres:
    image: postgis/postgis:15-3.3
    ports: ["5432:5432"]
    volumes:
      - ./scripts/init_postgis.sql:/docker-entrypoint-initdb.d/init.sql
  
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
  
  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    ports: ["9000:9000", "9001:9001"]
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
  
  kafka:
    image: confluentinc/cp-kafka:7.5.0
    ports: ["9092:9092"]
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
  
  zookeeper:
    image: confluentinc/cp-zookeeper:7.5.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
  
  backend:
    build: ./backend
    ports: ["8000:8000"]
    depends_on: [postgres, redis, kafka]
    environment:
      DATABASE_URL: postgresql://user:pass@postgres:5432/weather
      REDIS_URL: redis://redis:6379
      KAFKA_BROKER: kafka:9092
  
  celery-worker:
    build: ./backend
    command: celery -A app.celery_worker worker --loglevel=info --concurrency=4
    depends_on: [redis, postgres, kafka]
  
  frontend:
    build: ./frontend
    ports: ["3000:3000"]
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000
```

**Total Containers:** 8 (can run on a single 16GB RAM laptop with Docker Desktop)

---

## What's Real vs. Mocked for Demo

| Component | Status | Notes |
|---|---|---|
| Kafka ingestion | ✅ Real | Single-broker, production-ready pattern |
| PostgreSQL + PostGIS | ✅ Real | Full geospatial queries |
| pHash image deduplication | ✅ Real | `imagehash` library, 100% functional |
| Text embedding dedup | ✅ Real | sentence-transformers, works offline |
| Ground-truth verification | ✅ Real | OpenWeatherMap API (free tier) |
| Event classifier | ✅ Real | HuggingFace zero-shot, pre-trained |
| Twitter/X stream | ⚠️ Mocked | Replay from `mock_tweets.jsonl` (API cost) |
| Video analysis | ❌ Not implemented | Metadata only, future work |
| Image location inference | ❌ Not implemented | Future work |
| Spark/Flink processing | ❌ Not needed | Celery sufficient for demo scale |

**Key Message for Jury:** Everything verification-related is real and functional. The only mock is the Twitter data source (due to API cost), but the verification logic doesn't care — it processes mock tweets identically to live ones.

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|---|---|---|
| OpenWeatherMap API quota exceeded | High | Cache all responses in Redis; pre-download 7 days of data |
| Kafka fails to start | High | Docker Compose health checks; fallback to direct DB writes |
| ML model inference too slow | Medium | Use quantized models; cache results |
| GPS spoofing not detected | Medium | Already handled via location_confidence field |
| Time runs out before demo | High | Incremental tasks in tasks.md ensure partial demo works |

---

## Success Metrics

**Technical:**
- ✅ End-to-end latency (form submit → dashboard) < 10 seconds
- ✅ Confidence score accuracy: 80%+ precision on manually labeled test set (50 reports)
- ✅ Duplicate detection: catches 90%+ of recycled images

**Demo:**
- ✅ All 7 success criteria from requirements.md
- ✅ Jury can't break the verification logic with adversarial inputs (they'll try)
- ✅ System visibly scales (Kafka replay shows 50 reports/min without lag)

---

## Next Steps → tasks.md

The design is complete. Now break this into 30–40 incremental tasks that a team can parallelize and build in hackathon order (infra → backend → ML → frontend → integration).
