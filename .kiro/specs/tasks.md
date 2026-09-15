# Task List — SIH26069: National Weather Big Data Analytics Platform

**Team Size:** 3–6 people  
**Timeline:** 36 hours (standard hackathon)  
**Strategy:** Build in vertical slices — each phase ends with a demoable increment.

---

## Phase 0: Project Setup (2 hours)

**Goal:** Get the entire team unblocked with a working dev environment.

### Task 0.1: Initialize Project Structure
- Create folder structure as per design.md
- Initialize Git repo with `.gitignore` (exclude `node_modules/`, `__pycache__/`, `.env`)
- Create `docker-compose.yml` with all 8 services (Postgres, Redis, MinIO, Kafka, Zookeeper, backend, celery, frontend)
- Create `.env.example` with all required environment variables

**Owner:** DevOps lead  
**Deliverable:** `docker-compose up` starts all containers without errors

---

### Task 0.2: Database Schema Setup
- Write `scripts/init_postgis.sql` with:
  - PostGIS extension enable
  - `weather_reports` table
  - `event_clusters` table
  - `verification_logs` table
  - `admin_users` table
  - All indexes
- Seed one admin user (`username: admin`, `password: demo123`)

**Owner:** Backend developer  
**Deliverable:** `psql` connection shows all tables + PostGIS enabled

---

### Task 0.3: MinIO Bucket Initialization
- Create `weather-media` bucket via MinIO console
- Set bucket policy to public-read for demo simplicity
- Create folder structure: `images/`, `videos/`

**Owner:** Backend developer  
**Deliverable:** Upload test image via MinIO console, retrieve via URL

---

### Task 0.4: Kafka Topic Creation
- Create topics: `weather-reports-raw`, `weather-reports-verified`
- Set retention: 7 days
- Verify with `kafka-console-consumer`

**Owner:** Backend developer  
**Deliverable:** Publish test message to topic, consume it successfully

---

## Phase 1: Backend Core (6 hours)

**Goal:** FastAPI server running with database CRUD operations.

### Task 1.1: FastAPI Project Scaffold
- Initialize FastAPI app in `backend/app/main.py`
- Add database connection with SQLAlchemy + asyncpg
- Add CORS middleware (allow `http://localhost:3000`)
- Add health check endpoint: `GET /health`

**Owner:** Backend developer  
**Deliverable:** `curl http://localhost:8000/health` returns 200

---

### Task 1.2: SQLAlchemy Models
- Create `backend/app/models/weather_report.py` with WeatherReport ORM model
- Add relationships for `event_clusters`, `verification_logs`
- Add Alembic migration (optional if time allows, else use raw SQL)

**Owner:** Backend developer  
**Deliverable:** Import model in Python shell, no errors

---

### Task 1.3: Pydantic Schemas
- Create `backend/app/schemas/report.py`:
  - `ReportCreate` (input schema for citizen form)
  - `ReportResponse` (output schema for API)
  - `ReportFilter` (query params for filtering)

**Owner:** Backend developer  
**Deliverable:** Schemas validate sample JSON without errors

---

### Task 1.4: Reports CRUD API
- `POST /api/reports/submit` → insert into DB with `status=pending`
- `GET /api/reports` → query with filters (date, event_type, state, status)
- `GET /api/reports/{id}` → single report details

**Owner:** Backend developer  
**Deliverable:** Postman/curl test all 3 endpoints successfully

---

### Task 1.5: Media Upload to MinIO
- Add endpoint `POST /api/media/upload` → accepts multipart file
- Upload to MinIO, return pre-signed URL
- Store URL in `media_urls` array when creating report

**Owner:** Backend developer  
**Deliverable:** Upload image via Postman, URL works in browser

---

## Phase 2: Kafka Ingestion Pipeline (4 hours)

**Goal:** All data sources flow into Kafka, consumed by backend.

### Task 2.1: Kafka Producer Library
- Create `backend/app/ingestion/kafka_producer.py` with:
  - `publish_report(topic, message)` function
  - Serialization: JSON

**Owner:** Backend developer  
**Deliverable:** Call function from Python shell, message appears in Kafka topic

---

### Task 2.2: Citizen Form → Kafka
- Modify `POST /api/reports/submit` to:
  - Validate input
  - Upload media to MinIO (if present)
  - Publish to `weather-reports-raw` Kafka topic
  - Return `report_id` immediately (don't wait for processing)

**Owner:** Backend developer  
**Deliverable:** Submit report via Postman, appears in Kafka topic

---

### Task 2.3: Mock Twitter Feed Script
- Create `scripts/kafka_replay.py`:
  - Read `data/mock_tweets.jsonl` (create sample file with 100 tweets)
  - Publish to Kafka at configurable rate (default: 10 tweets/min)
  - Command-line arg: `--rate 50` for demo acceleration

**Owner:** Backend developer  
**Deliverable:** Run script, tweets flow into Kafka visible in console consumer

---

### Task 2.4: OpenWeatherMap Batch Fetcher
- Create `backend/app/ingestion/openweather_fetcher.py`:
  - Fetch current weather for 20 major Indian cities
  - Publish as "official observation" reports to Kafka
  - Run as cron job (every 6 hours) or manual trigger for demo

**Owner:** Backend developer  
**Deliverable:** Run script, 20 reports appear in Kafka

---

### Task 2.5: Kafka Consumer Service
- Create `backend/app/ingestion/kafka_consumer.py`:
  - Subscribe to `weather-reports-raw`
  - For each message:
    - Insert into DB with `status=pending`
    - Create Celery task: `verify_report(report_id)`
  - Run as background process (not in main FastAPI app)

**Owner:** Backend developer  
**Deliverable:** Publish to Kafka, row appears in Postgres with `status=pending`

---

## Phase 3: ML Verification Pipeline (8 hours — CORE DIFFERENTIATOR)

**Goal:** All three verification signals working end-to-end.

### Task 3.1: Celery Worker Setup
- Create `backend/celery_worker.py`:
  - Configure Celery app with Redis broker
  - Define task: `verify_report(report_id)`
- Add Dockerfile for celery worker
- Test with dummy task

**Owner:** Backend ML engineer  
**Deliverable:** `celery -A backend.celery_worker worker` starts without errors

---

### Task 3.2: Ground-Truth Verification (Signal 1)
- Create `backend/app/ml/verifier.py`:
  - Function: `ground_truth_check(report_id) → confidence_score`
  - Query OpenWeatherMap API for location + timestamp ±48h
  - Implement plausibility rules:
    - Flooding → check rainfall > 50mm
    - Heatwave → check temp > 40°C for 3 days
    - Thunderstorm → check precipitation + wind > 20 km/h
  - Store result in `verification_logs` table
  - Cache API responses in Redis (key: `weather:<lat>:<lon>:<date>`)

**Owner:** Backend ML engineer  
**Deliverable:** Call function with test `report_id`, returns confidence 0.0–1.0

---

### Task 3.3: Image pHash Deduplication (Signal 2)
- Create `backend/app/ml/image_hash.py`:
  - Install `imagehash` library
  - Function: `image_hash_check(report_id) → confidence_score`
  - Compute pHash of report's images
  - Query DB for all existing image hashes
  - Compute Hamming distance, flag if distance < 10
  - Check against `data/known_fake_hashes.txt`
  - Store result in `verification_logs`

**Owner:** Backend ML engineer  
**Deliverable:** Upload duplicate image, function returns confidence < 0.5

---

### Task 3.4: Text Embedding Deduplication (Signal 3)
- Create `backend/app/ml/deduplicator.py`:
  - Install `sentence-transformers` library
  - Load model: `all-MiniLM-L6-v2`
  - Function: `text_dedup_check(report_id) → confidence_score`
  - Embed report text
  - Query DB for reports in same region + event type in last 24h
  - Compute cosine similarity
  - If similarity > 0.92 → merge into `event_clusters` table
  - Store result in `verification_logs`

**Owner:** Backend ML engineer  
**Deliverable:** Submit two similar reports, second one merges into cluster

---

### Task 3.5: Event Type Classifier
- Create `backend/app/ml/classifier.py`:
  - Load HuggingFace model: `facebook/bart-large-mnli`
  - Function: `classify_event(report_id) → event_type, confidence`
  - Define labels: [rainfall, flooding, thunderstorm, heatwave, fog, dust storm, strong wind]
  - Zero-shot classification on report text
  - Update `event_type` and `event_type_confidence` in DB

**Owner:** Backend ML engineer  
**Deliverable:** Submit report with text "heavy rain in Mumbai", classified as "rainfall"

---

### Task 3.6: Confidence Score Calculation
- Create `backend/app/ml/confidence.py`:
  - Function: `compute_confidence_score(report_id)`
  - Fetch all 3 signal results from `verification_logs`
  - Weighted average: `0.5 * ground_truth + 0.3 * image_hash + 0.2 * text_dedup`
  - Handle missing signals (e.g., no image → renormalize weights)
  - Determine `verification_status`: verified/disputed/fake based on threshold
  - Update report in DB

**Owner:** Backend ML engineer  
**Deliverable:** Report shows final confidence score + status

---

### Task 3.7: GPS Spoofing Detection
- Create `backend/app/ml/location_verifier.py`:
  - Function: `verify_location(report_id)`
  - Check if GPS is within India bounding box (lat: 8–37°N, lon: 68–97°E)
  - Check if GPS is within 500km of declared city (use geopy)
  - If suspicious, set `location_source=gps_suspicious`
  - Fallback: use spaCy NER to extract place names from text
  - Geocode via Nominatim → set `location_source=text_inferred`

**Owner:** Backend ML engineer  
**Deliverable:** Submit report with GPS in Atlantic Ocean, flagged as suspicious

---

### Task 3.8: Integrate All Signals into Celery Task
- Modify `verify_report(report_id)` to call all functions in sequence:
  1. `ground_truth_check(report_id)`
  2. `image_hash_check(report_id)` (if image present)
  3. `text_dedup_check(report_id)`
  4. `classify_event(report_id)`
  5. `verify_location(report_id)`
  6. `compute_confidence_score(report_id)`
  7. Publish to `weather-reports-verified` Kafka topic
  8. Send WebSocket update to frontend

**Owner:** Backend ML engineer  
**Deliverable:** Submit report, wait 5 seconds, report auto-updates with verified status

---

## Phase 4: Frontend Dashboard (8 hours)

**Goal:** Interactive map + analytics, real-time updates.

### Task 4.1: Next.js Project Setup
- Initialize Next.js 14 (App Router) with TypeScript
- Install dependencies: `leaflet`, `react-leaflet`, `recharts`, `socket.io-client`, `tailwindcss`
- Add API client: `frontend/lib/api.ts` (axios wrapper)

**Owner:** Frontend developer  
**Deliverable:** `npm run dev` shows blank Next.js page

---

### Task 4.2: API Client Implementation
- Create functions in `lib/api.ts`:
  - `fetchReports(filters) → Promise<Report[]>`
  - `fetchAnalytics(type) → Promise<AnalyticsData>`
  - `submitReport(data) → Promise<{report_id}>`

**Owner:** Frontend developer  
**Deliverable:** Call from browser console, data returned

---

### Task 4.3: Leaflet Map Component
- Create `components/Map.tsx`:
  - Leaflet map centered on India (lat: 20.5937, lon: 78.9629)
  - Load reports from API on mount
  - Display markers clustered by density (use `react-leaflet-cluster`)
  - Color-code markers: green/yellow/red/grey by verification status
  - Click marker → open popup with report details

**Owner:** Frontend developer  
**Deliverable:** Map loads with markers from Postgres

---

### Task 4.4: Filter Panel Component
- Create `components/FilterPanel.tsx`:
  - Date range picker (react-datepicker)
  - Event type checkboxes (multi-select)
  - State dropdown (autocomplete)
  - Verification status checkboxes
  - Apply button → calls `fetchReports(filters)`, updates map

**Owner:** Frontend developer  
**Deliverable:** Change filters, map updates with filtered reports

---

### Task 4.5: Time-Series Chart
- Create `components/TimeSeriesChart.tsx`:
  - Bar chart using Recharts
  - X-axis: date (daily or hourly granularity)
  - Y-axis: report count
  - Fetch data from `GET /api/analytics/time-series`

**Owner:** Frontend developer  
**Deliverable:** Chart shows report volume over last 7 days

---

### Task 4.6: Event Type Pie Chart
- Create `components/EventBreakdown.tsx`:
  - Pie chart using Recharts
  - Fetch data from `GET /api/analytics/breakdown?by=event_type`

**Owner:** Frontend developer  
**Deliverable:** Pie chart shows percentage distribution of event types

---

### Task 4.7: Real-Time WebSocket Integration
- Add Socket.io client in `app/page.tsx`:
  - Connect to backend WebSocket endpoint: `ws://localhost:8000/ws`
  - Subscribe to `report:new` event
  - On new report → add marker to map without refresh, animate entrance

**Owner:** Frontend developer  
**Deliverable:** Submit report via backend, map updates within 5 seconds

---

### Task 4.8: Dashboard Layout
- Create `app/page.tsx`:
  - Top: Filter panel
  - Left: Map (70% width)
  - Right: Analytics panel (time-series + pie chart + stat cards)
  - Responsive layout (Tailwind CSS)

**Owner:** Frontend developer  
**Deliverable:** Dashboard looks polished, all components integrated

---

## Phase 5: Admin Panel (4 hours)

**Goal:** Review queue for disputed reports, manual verification.

### Task 5.1: Admin Login Page
- Create `app/admin/login/page.tsx`:
  - Simple form: username + password
  - Call `POST /api/admin/login`
  - Store JWT token in localStorage
  - Redirect to review queue on success

**Owner:** Frontend developer  
**Deliverable:** Login with `admin/demo123`, redirected to admin panel

---

### Task 5.2: Admin Authentication Middleware
- Add `backend/app/api/admin.py`:
  - `POST /api/admin/login` → verify credentials, return JWT
  - Protect admin endpoints with `@require_admin` decorator

**Owner:** Backend developer  
**Deliverable:** Call admin endpoint without token → 401 Unauthorized

---

### Task 5.3: Review Queue API
- Add `GET /api/admin/review-queue`:
  - Query reports with `0.4 <= confidence_score <= 0.7`
  - Return sorted by timestamp (oldest first)
  - Include all signal details in response

**Owner:** Backend developer  
**Deliverable:** API returns list of disputed reports

---

### Task 5.4: Review Queue UI
- Create `app/admin/page.tsx`:
  - Table with columns: ID, Description, Confidence, Location, Timestamp
  - Click row → expand to show full details (images, signals breakdown)
  - Action buttons: Verify / Reject / Add Note

**Owner:** Frontend developer  
**Deliverable:** Table loads disputed reports, expandable rows work

---

### Task 5.5: Manual Verification Actions
- Add endpoints:
  - `POST /api/admin/reports/{id}/verify`
  - `POST /api/admin/reports/{id}/reject`
- Update report: set `admin_override=true`, recalculate confidence with admin signal (weight: 0.8)
- Log action in `verification_logs`

**Owner:** Backend developer  
**Deliverable:** Click "Verify" in admin panel, report status changes to verified

---

## Phase 6: Citizen Report Form (2 hours)

**Goal:** Public-facing form for citizen submissions.

### Task 6.1: Report Submission Form
- Create `app/submit/page.tsx`:
  - Form fields: event type, description, city, state, GPS (auto-fill), photo upload
  - Validation with Zod
  - On submit → call `POST /api/reports/submit`
  - Show success message with report ID

**Owner:** Frontend developer  
**Deliverable:** Fill form, submit, report appears in dashboard

---

### Task 6.2: GPS Auto-Fill from Browser
- Use `navigator.geolocation.getCurrentPosition()` to get user's lat/lon
- Auto-fill GPS fields when page loads (ask for permission)

**Owner:** Frontend developer  
**Deliverable:** Open form on phone, GPS fields auto-populate

---

## Phase 7: Analytics API Endpoints (2 hours)

**Goal:** Backend endpoints for dashboard charts.

### Task 7.1: Time-Series Aggregation
- Add `GET /api/analytics/time-series`:
  - Query param: `interval=hour|day`
  - SQL: `GROUP BY DATE_TRUNC(interval, reported_at)`
  - Return: `[{date, count}]`

**Owner:** Backend developer  
**Deliverable:** API returns daily report counts for last 7 days

---

### Task 7.2: Event Type Breakdown
- Add `GET /api/analytics/breakdown?by=event_type`:
  - SQL: `GROUP BY event_type`
  - Return: `[{event_type, count, percentage}]`

**Owner:** Backend developer  
**Deliverable:** API returns pie chart data

---

### Task 7.3: Verification Status Stats
- Add `GET /api/analytics/stats`:
  - Return: `{total_reports, verified_count, fake_count, disputed_count, verified_percentage}`

**Owner:** Backend developer  
**Deliverable:** API returns stat card data for dashboard

---

## Phase 8: Demo Data Preparation (2 hours)

**Goal:** Create realistic mock data for impressive demo.

### Task 8.1: Mock Twitter Dataset
- Create `data/mock_tweets.jsonl`:
  - 200 tweets with hashtags (#IMD, #MumbaiRains, #DelhiHeat, etc.)
  - Mix of real events (verifiable) and fake reports (recycled images)
  - Include GPS metadata (50% accurate, 50% spoofed/missing)

**Owner:** Content curator (any team member)  
**Deliverable:** File exists, valid JSON format

---

### Task 8.2: Known Fake Image Hashes
- Create `data/known_fake_hashes.txt`:
  - Download 10 common "disaster stock photos" from Google Images
  - Compute pHash for each
  - Save as text file (one hash per line)

**Owner:** Backend ML engineer  
**Deliverable:** File exists, hashes computed

---

### Task 8.3: Database Seeding Script
- Create `scripts/seed_db.py`:
  - Insert 50 pre-verified reports (ground-truth aligned)
  - Insert 20 disputed reports (borderline confidence)
  - Insert 10 fake reports (recycled images, no rainfall)
  - Cover all Indian states

**Owner:** Backend developer  
**Deliverable:** Run script, Postgres has 80 reports

---

## Phase 9: Integration Testing (2 hours)

**Goal:** End-to-end smoke tests for demo day.

### Task 9.1: Happy Path Test
- Test flow:
  1. Submit citizen report via form (with image)
  2. Wait 10 seconds
  3. Verify report appears on dashboard map (green marker)
  4. Check confidence breakdown in popup

**Owner:** QA lead (any team member)  
**Deliverable:** Document test result

---

### Task 9.2: Fake Report Detection Test
- Test flow:
  1. Submit report: "Flooding in Delhi" with no rainfall in last 48h
  2. Upload recycled image (from `known_fake_hashes.txt`)
  3. Wait 10 seconds
  4. Verify report is flagged as fake (red marker, confidence < 0.4)

**Owner:** QA lead  
**Deliverable:** Document test result

---

### Task 9.3: Admin Panel Test
- Test flow:
  1. Login to admin panel
  2. Verify disputed report appears in queue
  3. Click "Verify", add note
  4. Refresh dashboard → report is now green

**Owner:** QA lead  
**Deliverable:** Document test result

---

### Task 9.4: Kafka Replay Test
- Test flow:
  1. Run `scripts/kafka_replay.py --rate 50`
  2. Watch dashboard map for 2 minutes
  3. Verify new markers animate onto map in real-time
  4. Verify no crashes, all reports processed

**Owner:** QA lead  
**Deliverable:** Record screen capture of live demo

---

## Phase 10: Demo Polish (2 hours)

**Goal:** Make it jury-ready.

### Task 10.1: UI Polish
- Add loading spinners, error states
- Add success/error toasts (react-hot-toast)
- Mobile responsiveness check
- Dark mode toggle (optional, nice-to-have)

**Owner:** Frontend developer  
**Deliverable:** UI feels polished, no broken layouts

---

### Task 10.2: Demo Script
- Create `docs/demo_script.md`:
  - Step-by-step walkthrough for jury
  - Talking points for each feature
  - Answers to anticipated questions:
    - "Why not just use Twitter API?" → Cost/access, but architecture is real
    - "How do you prevent GPS spoofing?" → location_confidence field, text inference
    - "Why Kafka for small scale?" → Replay capability, honest architecture

**Owner:** Team lead  
**Deliverable:** 2-page script, rehearsed

---

### Task 10.3: Architecture Diagram Slide
- Create presentation slide with:
  - High-level architecture (same Mermaid diagram from design.md)
  - Tech stack badges (React, FastAPI, Postgres, Kafka, etc.)
  - Key differentiator callout: "Verification layer = our moat"

**Owner:** Designer / Team lead  
**Deliverable:** 1 slide, export as PNG for demo booth

---

### Task 10.4: Error Handling & Logging
- Add try-catch blocks in all Celery tasks
- Add structured logging (Python `logging` module)
- Add Sentry (optional) or log to file for post-demo debugging

**Owner:** Backend developer  
**Deliverable:** Backend doesn't crash if API is down

---

## Phase 11: Final Rehearsal (2 hours before submission)

### Task 11.1: Full Stack Restart
- `docker-compose down -v` (wipe everything)
- `docker-compose up --build`
- Run `seed_db.py`
- Verify all services are healthy

**Owner:** DevOps lead  
**Deliverable:** Clean slate works

---

### Task 11.2: Demo Dry Run
- Full 5-minute walkthrough with timer
- Assign speaking roles
- Practice handling jury questions

**Owner:** Entire team  
**Deliverable:** Smooth demo, under 5 minutes

---

## Task Ownership Matrix (Suggested)

| Role | Primary Tasks | Backup Tasks |
|---|---|---|
| **Backend Lead** | 1.1–1.5, 2.1–2.5, 7.1–7.3 | 3.1, 5.2 |
| **ML Engineer** | 3.1–3.8 | 8.2 |
| **Frontend Lead** | 4.1–4.8, 6.1–6.2 | 10.1 |
| **Frontend #2** | 5.1, 5.4, 10.1 | 4.5, 4.6 |
| **DevOps/Full-Stack** | 0.1–0.4, 11.1 | 9.1–9.4 |
| **Content/QA** | 8.1–8.3, 9.1–9.4, 10.2–10.3 | Any overflow |

---

## Critical Path (Tasks That Can't Be Parallelized)

```
0.1 → 0.2 → 1.1 → 1.2 → 1.4 → 2.2 → 2.5 → 3.1 → 3.8 → 4.3 → 4.7 → 9.1
```

**Estimated Critical Path Time:** 18 hours  
**Total Parallel Time Available:** 36 hours  
**Buffer:** 18 hours for debugging, polish, sleep

---

## Risk Mitigation: If Running Out of Time

**Drop these tasks (in order):**
1. Task 5.1–5.5 (Admin panel) → Manual DB queries as fallback
2. Task 6.2 (GPS auto-fill) → Manual entry only
3. Task 10.1 (UI polish) → Functional > pretty
4. Task 3.7 (GPS spoofing detection) → Demo without it, mention in "future work"
5. Task 3.5 (Event classifier) → Use user-declared category

**Don't drop these:**
- Tasks 3.2, 3.3, 3.4 (verification signals) — this is the core value prop
- Task 4.3 (map) — no map = no demo
- Task 9.2 (fake detection test) — proves it works

---

## Post-Hackathon Improvements (If You Win & Continue)

1. Fine-tune event classifier on labeled Indian weather tweets
2. Add video metadata extraction (thumbnail, duration)
3. Implement image-based location inference (vision model)
4. Scale to multi-region Kafka cluster + Spark processing
5. Build mobile app (React Native)
6. Partner with IMD for official data access
7. Add SMS/WhatsApp bot for report submission

---

**Total Tasks:** 44  
**Estimated Total Effort:** 42 person-hours (with 6 people = 7 hours each if perfectly parallelized, realistically 12–16 hours each with debugging)

**Next Step:** Team kickoff meeting, assign tasks from ownership matrix, start with Phase 0.
