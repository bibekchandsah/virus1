# URL Email & Person Name Scraper 

## 🎯 Goal

Build a **web page / web app** that accepts a **specific webpage URL** as input, scrapes the page content, and intelligently extracts:

* ✅ Valid email addresses
* ✅ Associated person/user names (if available)

The system should be **accurate, respectful of web rules, scalable, and intelligent**.

---

## 🧩 Core Features (Must-Have)

### 1. URL Input

* Accept a single webpage URL as input
* Validate URL format before processing
* Allow only `http://` and `https://`
* Reject private/local IPs (security)

### 2. Web Page Scraping

* Fetch HTML content safely
* Handle:

  * Static HTML pages
  * Pages with minimal JS rendering
* Extract:

  * csv, txt, xls
  * Visible text
  * Meta tags
  * Footer & contact sections

> ❗ Do NOT bypass authentication, paywalls, or CAPTCHAs

---

## 📄 Content Extraction Logic

### 3. Email Extraction

* Use robust regex for email detection
* Normalize emails:

  * lowercase
  * trim punctuation
* Remove duplicates

### 4. De-Obfuscation (Important)

Handle common obfuscation patterns:

* `name [at] domain [dot] com`
* `name(at)domain.com`
* `name@domain(dot)com`
* HTML entities (`&#64;`, `&#46;`)

Apply heuristic replacements before regex extraction.

---

## 🧠 Intelligent Name Detection

### 5. Person / Username Extraction

Attempt to find names using multiple strategies:

#### A. Proximity-Based Matching

* Look for text near email addresses
* Common patterns:

  * `Name – email@example.com`
  * `email@example.com (John Doe)`

#### B. HTML Semantics

* Extract names from:

  * `<h1>`, `<h2>`, `<strong>` near emails
  * Author sections
  * Team or Contact sections

#### C. Metadata

* Check:

  * `meta[name=author]`
  * OpenGraph (`og:title`)

#### D. NLP / Heuristic Detection

* Detect **proper nouns** near emails
* Filter out:

  * Generic words (admin, support, info)
  * Company-only names unless marked

---

## ✅ Validation & Scoring

### 6. Email Validation

* Regex validation
* Domain format validation
* Optional DNS/MX lookup (configurable)

### 7. Confidence Scoring

Assign confidence scores based on:

* Email syntax
* Known domain
* Name proximity
* Section relevance (Contact/About pages score higher)

Example:

```
John Doe – john@company.com (92%)
```

---

## 📊 Output & UI

### 8. Results Display

Show results in a structured table:

| Name | Email | Confidence | Source Section |
| ---- | ----- | ---------- | -------------- |

### 9. Export Options

* `.csv`
* `.json`
* `.txt`

---

## 🛠️ Technical Stack (Suggested)

### Backend

* Python (FastAPI / Flask)
* Libraries:

  * `requests` / `httpx`
  * `BeautifulSoup4`
  * `lxml`
  * `re`
  * `email-validator`
  * Optional: `spaCy` (NER)

### Frontend (Optional)

* Simple HTML + JS
* Or React for better UX

---

## 🔐 Legal, Ethics & Safety (Mandatory)

* Respect `robots.txt`
* Rate-limit requests
* User must confirm they have permission to scrape
* Do not scrape:

  * Login-protected pages
  * Private dashboards

Add disclaimer in UI.

---

## ⚡ Performance & Reliability

* Timeout handling
* Retry logic (limited)
* Asynchronous scraping
* Cache results per URL (short-lived)

---

## 🧪 Testing Scenarios

Test with:

* Company contact pages
* Blog author pages
* University faculty pages
* Pages with obfuscated emails
* Pages with no emails

---

## 📁 Suggested Project Structure

```
project/
├── backend/
│   ├── main.py
│   ├── scraper.py
│   ├── email_extractor.py
│   ├── name_detector.py
│   ├── validator.py
│   └── utils/
├── frontend/
├── cache/
└── README.md
```

---

## 🚀 Future Enhancements

* Crawl multiple internal pages (depth-limited)
* Social profile linking (LinkedIn, Twitter)
* Company-level aggregation
* Chrome extension
* AI-based relationship inference

---

## ✅ Final Instruction 

Build the system **ethically**, **modularly**, and **intelligently**.

If multiple names are possible, prefer **accuracy over guessing** and return `Unknown` instead of wrong data.

Document assumptions clearly and keep the system extensible.

