# Email & Name Scraper

A web application that extracts email addresses and associated person names from web pages.

## Features

- **Email Extraction**: Robust regex-based email detection with de-obfuscation support
- **Name Detection**: Multiple strategies including proximity matching, email parsing, and metadata analysis
- **Confidence Scoring**: Each result includes a confidence percentage based on multiple factors
- **Validation**: Email format and optional MX record validation
- **Export Options**: CSV, JSON, and TXT export formats
- **Ethical Scraping**: Respects robots.txt and includes rate limiting

## Project Structure

```
email scrapper/
├── backend/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── scraper.py           # Web scraping logic
│   ├── email_extractor.py   # Email extraction & de-obfuscation
│   ├── name_detector.py     # Name detection strategies
│   ├── validator.py         # Email validation
│   └── utils/
│       ├── __init__.py
│       └── helpers.py       # Utility functions
├── frontend/
│   └── index.html           # Web interface
├── requirements.txt
├── instructions.md
└── README.md
```

## Installation

1. **Create a virtual environment** (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Running the Server

Start the FastAPI server:

```bash
cd backend
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Or from the project root:

```bash
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

### Accessing the Application

1. **Web Interface**: Open `frontend/index.html` in your browser
2. **API Documentation**: Visit `http://127.0.0.1:8000/docs` for Swagger UI

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/scrape` | POST | Scrape a URL for emails |
| `/api/export/csv` | GET | Export results as CSV |
| `/api/export/json` | GET | Export results as JSON |
| `/api/export/txt` | GET | Export results as TXT |
| `/api/health` | GET | Health check |

### Example API Request

```bash
curl -X POST "http://127.0.0.1:8000/api/scrape" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://example.com/contact", "check_mx": false}'
```

## Features in Detail

### Email De-obfuscation

Handles common obfuscation patterns:
- `name [at] domain [dot] com`
- `name(at)domain.com`
- HTML entities (`&#64;`, `&#46;`)

### Name Detection Strategies

1. **Proximity Matching**: Finds names near email addresses
2. **HTML Semantics**: Extracts from author tags, headings, etc.
3. **Email Parsing**: Derives names from `john.doe@company.com`
4. **Metadata**: Checks meta tags and OpenGraph data

### Confidence Scoring

Scores are calculated based on:
- Email validation status
- MX record presence (if checked)
- Name detection confidence
- Source section relevance (contact pages score higher)

## Legal & Ethical Guidelines

- **Always obtain permission** before scraping websites
- The tool **respects robots.txt** by default
- **Rate limiting** is built-in to avoid overloading servers
- Does NOT bypass authentication or CAPTCHAs

## Configuration

Key settings can be adjusted in `backend/scraper.py`:

```python
WebScraper(
    timeout=30.0,        # Request timeout
    max_retries=3,       # Retry attempts
    check_robots=True,   # Respect robots.txt
    check_mx=False,      # MX validation
    cache_ttl=300        # Cache duration (seconds)
)
```

## Testing

Test with various page types:
- Company contact pages
- University faculty pages
- Blog author pages
- Pages with obfuscated emails

## Future Enhancements

- Multi-page crawling (depth-limited)
- Social profile linking
- Chrome extension
- AI-based relationship inference

## License

For educational and ethical use only. Always respect website terms of service.
