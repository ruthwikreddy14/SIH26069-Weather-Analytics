# Requirements — SIH26069: National Weather Big Data Analytics Platform

## Problem Statement (Official)

Design and develop a scalable National Weather Big Data Analytics Platform capable of collecting and processing real-time weather-related information for India from multiple internet-based sources including social media platforms, public datasets, websites, APIs, and citizen reports. The platform should automatically collect weather-related posts and information tagged with #IMD and other relevant weather hashtags, along with metadata such as date & time, city, state, GPS location, photos, videos, and event category, and store the information in a centralized database. The system should leverage big data technologies and open-source tools to support large-scale real-time data ingestion, processing, storage, and visualization. Use machine learning / AI techniques to identify fake or misleading reports, verify untrusted sources, remove duplicate entries, and automatically categorize weather events (rainfall, thunderstorms, flooding, heatwaves, fog, dust storms, strong winds). Deliver a web-based dashboard and Admin Panel with date-wise, event-wise, location-wise filtering, verification status tracking, and real-time visualization/analytics.

---

## Target Users

1. **Disaster Management Authorities** (NDRF, SDRF, State Emergency Operations Centers)
   - Need: Real-time corroboration of citizen disaster reports against official weather records during active events
   - Current pain point: Manual reconciliation of WhatsApp screenshots, phone calls, and PDF rainfall tables

2. **IMD Field Officers**
   - Need: Ground-truth validation of forecast accuracy using crowdsourced field observations
   - Current pain point: No structured system to aggregate citizen weather observations at scale

3. **State Government Emergency Response Teams**
   - Need: Location-tagged, verified weather event feed to prioritize resource deployment
   - Current pain point: Fragmented information sources with no verification layer

---

## Core Value Proposition

**What makes this different from consumer weather apps:**
- Consumer apps (Windy, Weather.com, IMD app) show forecasts; they don't verify citizen disaster reports against satellite/rainfall records
- No existing system cross-checks crowdsourced claims with IMD gridded data to assign confidence scores
- This platform treats verification and deduplication as first-class features, not afterthoughts

---

## Functional Requirements (EARS Format)

### FR1: Multi-Source Data Ingestion

**FR1.1** WHEN the system is running, IT SHALL continuously ingest weather reports from the following sources:
- Twitter/X hashtag streams (#IMD, #floods, #heatwave, #rainfall, #cyclone)
- Citizen-submitted web forms (manual report upload)
- IMD Open Data Portal (district rainfall, weather bulletins)
- OpenWeatherMap API (current conditions, forecasts)
- data.gov.in weather datasets

**Acceptance Criteria:**
- Each source feeds into a centralized Kafka ingestion topic
- Metadata captured: timestamp, source type, raw content, declared location, GPS (if present), media URLs
- System handles at least 50 reports/minute without dropped messages (demo scale)

**FR1.2** WHEN a citizen submits a weather report via the web form, THE SYSTEM SHALL accept:
- Event type (dropdown: rainfall, flooding, thunderstorm, heatwave, fog, dust storm, strong wind)
- Text description (max 500 characters)
- Optional photo/video upload (max 10MB per file)
- City/state (dropdown or autocomplete)
- Optional GPS coordinates (auto-filled from browser geolocation API)

**Acceptance Criteria:**
- Form validates required fields (event type, location, description)
- Media files are uploaded to MinIO and URL stored in database
- Submission triggers Kafka message for processing pipeline

---

### FR2: Verification and Confidence Scoring (Core Differentiator)

**FR2.1** WHEN a weather report is ingested, THE SYSTEM SHALL compute a confidence score (0.0–1.0) based on three signals:

**Signal 1 — Ground-truth cross-check (weight: 0.5)**
- IF report claims event X in location Y at time T, query OpenWeatherMap/IMD data for location Y in the ±48h window around T
- IF recorded rainfall/temperature/conditions align with claimed event → score += 0.5
- IF zero recorded activity contradicts claim (e.g., "flooding" but zero rainfall) → score -= 0.3

**Signal 2 — Image perceptual hash deduplication (weight: 0.3)**
- Compute pHash of uploaded image using `imagehash` library
- IF Hamming distance to existing image < 10 → potential recycled disaster photo → score -= 0.3
- IF hash matches pre-seeded "known fake disaster photo" database → flag as fake, score = 0.0

**Signal 3 — Text near-duplicate detection (weight: 0.2)**
- Embed report text using `sentence-transformers` (all-MiniLM-L6-v2)
- IF cosine similarity with existing report > 0.92 → merge into event cluster, don't create duplicate record
- IF report is unique → score += 0.2

**Acceptance Criteria:**
- Each report stored with `confidence_score`, `verification_status` (verified/disputed/unverified/fake), and `signals` JSON object
- Threshold: confidence > 0.7 = verified, 0.4–0.7 = disputed, < 0.4 = fake
- Admin panel shows confidence breakdown per report

**FR2.2** WHERE GPS metadata is missing or suspicious, THE SYSTEM SHALL infer location from text:
- Use spaCy NER to extract place names from report description
- Geocode extracted names via Nominatim API → lat/lon
- Store `location_source` (gps_verified | gps_suspicious | text_inferred | unknown) and `location_confidence` (high | medium | low)

**Acceptance Criteria:**
- GPS outside India bounding box (lat: 8–37°N, lon: 68–97°E) is flagged as suspicious
- Text-inferred locations show "inferred from text, city-level precision" tag in dashboard
- Reports with `location_confidence: low` are deprioritized in map view but not discarded

---

### FR3: Event Classification

**FR3.1** WHEN a report is ingested, THE SYSTEM SHALL classify it into one of the following event types:
- Rainfall
- Flooding
- Thunderstorm
- Heatwave
- Fog
- Dust storm
- Strong wind

**FR3.2** THE SYSTEM SHALL support multilingual classification for at least:
- English
- Hindi
- (Optional: One regional language — Tamil, Bengali, or Marathi)

**Acceptance Criteria:**
- Use pre-trained HuggingFace zero-shot classifier or fine-tuned lightweight transformer
- Classification accuracy > 80% on test dataset
- Fallback: if confidence < 0.6, use user-declared category from form

---

### FR4: Centralized Storage

**FR4.1** THE SYSTEM SHALL store all weather reports in a PostgreSQL database with PostGIS extension, supporting:
- Geospatial queries (`ST_DWithin` for radius search)
- Full-text search on report descriptions
- Time-series aggregation (reports per hour/day/region)

**FR4.2** THE SYSTEM SHALL store media files (photos, videos) in MinIO object storage, with URLs referenced in PostgreSQL.

**Acceptance Criteria:**
- Database schema includes: `weather_reports`, `event_clusters`, `verification_logs`
- Each report has a `geography(Point)` column for PostGIS queries
- Media files are retrievable via signed URLs

---

### FR5: Real-Time Dashboard

**FR5.1** THE DASHBOARD SHALL display a live map with:
- Clustered markers for reports (grouped by geographic proximity)
- Color-coded by verification status:
  - Green = verified (confidence > 0.7)
  - Yellow = disputed (0.4–0.7)
  - Red = fake (< 0.4)
  - Grey = unverified (pending processing)
- Click on marker → popup with report details (timestamp, description, verification breakdown, media preview)

**FR5.2** THE DASHBOARD SHALL provide filters:
- Date range picker
- Event type (multi-select)
- State/city (autocomplete)
- Verification status (multi-select)
- Source type (social media, citizen, official API)

**FR5.3** THE DASHBOARD SHALL display time-series analytics:
- Bar chart: reports per hour/day
- Pie chart: event type breakdown
- Heatmap layer: report density overlay on map

**FR5.4** THE DASHBOARD SHALL update in real-time:
- New reports appear on map within 5 seconds of ingestion
- Use WebSocket connection for live updates (no page refresh required)

**Acceptance Criteria:**
- Dashboard loads within 3 seconds for 1000 reports
- Map clustering prevents UI lag with 10,000+ markers
- All filters are combinable (e.g., "flooding in Tamil Nadu, verified, last 7 days")

---

### FR6: Admin Review Panel

**FR6.1** THE ADMIN PANEL SHALL display a review queue of reports with disputed status (0.4 < confidence < 0.7).

**FR6.2** FOR EACH REPORT, admins can:
- View full details (text, images, location, confidence breakdown)
- See the ground-truth data used for verification (IMD rainfall records, satellite data)
- Manually override verification status → mark as verified/fake
- Add admin notes

**FR6.3** Manual overrides SHALL update the confidence score and trigger re-classification if needed.

**Acceptance Criteria:**
- Queue is sorted by timestamp (oldest first)
- Admin actions are logged with user ID and timestamp
- Overridden reports are excluded from future review queue

---

### FR7: Big Data Architecture (Demo-Realistic)

**FR7.1** THE SYSTEM SHALL use Apache Kafka (single-broker) for:
- Ingestion topic: all sources publish to `weather-reports-raw`
- Processing topic: verified reports published to `weather-reports-verified`

**FR7.2** THE SYSTEM SHALL use Celery + Redis for:
- Async background tasks: verification, classification, deduplication
- Task prioritization: citizen reports > social media > batch API imports

**Acceptance Criteria:**
- Kafka runs in Docker (single container, no cluster complexity)
- Celery workers scale to 4 workers in parallel
- End-to-end latency (ingestion → dashboard) < 10 seconds for 95th percentile

---

## Non-Functional Requirements

**NFR1: Performance**
- Dashboard loads map view within 3 seconds for 1000 reports
- Verification pipeline processes 50 reports/minute minimum
- API response time < 500ms for filter queries

**NFR2: Scalability (Demo Scope)**
- System handles 10,000 total reports in database without performance degradation
- Kafka + Celery architecture is horizontally scalable (though demo runs on single machine)

**NFR3: Usability**
- Dashboard is mobile-responsive (jury may test on phone)
- No user training required — UI is self-explanatory
- Color-coding and icons make verification status instantly recognizable

**NFR4: Reliability**
- If verification API (OpenWeatherMap) is down, system degrades gracefully → marks reports as unverified, doesn't block ingestion
- MinIO media storage has fallback → if upload fails, report is still saved with text only

**NFR5: Security (Hackathon Scope)**
- Admin panel requires login (simple JWT auth, no OAuth complexity)
- API endpoints rate-limited to prevent abuse
- No PII stored beyond user-submitted location and description

---

## Out of Scope for MVP (Future Work)

- Video content analysis (metadata only for MVP)
- Image-based location inference using vision models
- Full Twitter/X live stream (use mock replay for demo)
- Spark/Flink for distributed processing (Kafka + Celery sufficient for demo scale)
- Advanced NLP: sarcasm detection, multi-hop reasoning
- Mobile app (web-responsive dashboard is sufficient)

---

## Success Criteria for Hackathon Demo

1. ✅ Jury can submit a fake flood report via citizen form → system flags it as fake within 10 seconds (because no rainfall recorded in that location)
2. ✅ Jury can submit a verified report with ground-truth alignment → appears on map as green marker
3. ✅ Live Kafka replay of mock tweets streams reports onto dashboard in real-time during demo
4. ✅ Admin panel shows 5+ disputed reports in review queue, jury can manually verify one
5. ✅ Dashboard filters work: "Show only verified flooding events in Maharashtra last 7 days"
6. ✅ Time-series chart shows report spike during simulated event
7. ✅ Duplicate image upload is detected and flagged

If all 7 work, the demo proves the verification layer is real, not vaporware.
