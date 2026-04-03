# questions.md - Business Logic Questions Log
**Project:** Warehouse Intelligence & Offline Crawling Operations Platform

Record of all unclear business-level aspects while understanding the prompt.


### 1. Crawling Rule Canary Release
**Question:** How exactly should the canary release work? (e.g., 5% of tasks for 30 minutes)  
**My Understanding:** The prompt says rule changes can be canary-released to 5% of tasks for 30 minutes and rolled back if error rate > 2%.  
**Solution:** Implement a canary system where new rule version is applied to a percentage of crawl tasks, with automatic rollback based on error rate monitoring.

### 2. Safety Stock Alert Flapping Prevention
**Question:** How should the system prevent "flapping" of safety stock alerts?  
**My Understanding:** The prompt specifies alerts should trigger only when available quantity stays below threshold for 10 consecutive minutes.  
**Solution:** Use a sliding window of 10 minutes with persistent state to avoid rapid on/off alerts.

### 3. Crawling Task Idempotency
**Question:** How should idempotency be enforced for crawl tasks?  
**My Understanding:** The prompt mentions "idempotent via deterministic request fingerprints".  
**Solution:** Generate a unique fingerprint based on URL + parameters + headers to prevent duplicate processing.

### 4. Quota & Concurrency Control
**Question:** Should quota deduction happen before the request or after a successful response?  
**My Understanding:** Strong consistency is required using database transactions and row-level locking.  
**Solution:** Deduct quota inside a transaction before executing the request; release on failure or success with proper timeout handling.

### 5. Inventory Costing Methods
**Question:** Should the system support both FIFO and Moving Average costing simultaneously, or per SKU?  
**My Understanding:** The prompt says "supports FIFO and moving-average costing per SKU".  
**Solution:** Allow configuration per SKU for costing method.

### 6. Cycle Count Variance Confirmation
**Question:** What is the exact guided workflow for cycle count variance confirmation?  
**My Understanding:** Inventory Manager records cycle counts with guided variance confirmation.  
**Solution:** Implement a step-by-step wizard: scan/count → show expected vs actual → require reason for variance > threshold.

### 7. Offline Notification Delivery
**Question:** When local SMTP/SMS gateways are not present, how should notifications behave?  
**My Understanding:** The prompt says messaging is delivered in-app and to locally hosted gateways only when present.  
**Solution:** Always show in-app notifications; queue outbound messages for gateways and allow manual export if gateways are unavailable.

### 8. Sensitive Data Encryption Scope
**Question:** Which fields exactly need to be encrypted at rest (supplier credentials, rule secrets, etc.)?  
**My Understanding:** Prompt mentions "sensitive fields such as supplier credentials and rule secrets".  
**Solution:** Encrypt API keys, passwords, and any credential-like fields in crawl rules and supplier data.

### 9. Crawler Anti-Bot Strategies
**Question:** Should user-agent rotation and crawl delay be configurable per source or global?  
**My Understanding:** The prompt mentions rotating predefined user-agent strings and honoring crawl delays.  
**Solution:** Make both configurable per crawl source.

### 10. Audit Trail Retention
**Question:** Should all audit logs be retained for exactly 365 days, or can admins configure it?  
**My Understanding:** Prompt says "retained for 365 days".  
**Solution:** Hardcode 365 days retention with automatic cleanup job.

### 11. Barcode/RFID Scanning Workflow
**Question:** Should the React UI support real-time barcode/RFID scanning via device camera or external scanner?  
**My Understanding:** Inventory Manager needs to scan or enter barcode/RFID identifiers.  
**Solution:** Support both manual entry and browser-based scanning (using QuaggaJS or similar) with fallback.
