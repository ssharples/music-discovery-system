# 🔥 Firecrawl Setup Guide

## Overview

Firecrawl is a web data extraction service that transforms websites into clean, LLM-ready data. The music discovery system uses Firecrawl to enhance artist profiles by scraping additional information from artist websites and social media pages.

## Features

- **Clean Data Extraction**: Converts web pages to markdown and structured data
- **Smart Web Scraping**: Handles JavaScript-rendered content and anti-bot measures  
- **Contact Information**: Automatically extracts emails, phone numbers, and social handles
- **Social Media Enrichment**: Gathers additional context from artist social profiles

## Installation

### 1. Install the Python Package

The Firecrawl Python SDK is already included in the requirements:

```bash
pip install firecrawl-py==2.8.0
```

### 2. Get an API Key

1. Sign up at [https://firecrawl.dev](https://firecrawl.dev)
2. Navigate to your dashboard to get your API key
3. Your API key will start with `fc-`

### 3. Configure Environment

Add your API key to your environment variables:

**Option A: Environment Variable**
```bash
export FIRECRAWL_API_KEY="fc-your-api-key-here"
```

**Option B: .env File**
```env
FIRECRAWL_API_KEY=fc-your-api-key-here
```

## Configuration Options

The system includes the following Firecrawl configuration options in `backend/app/core/config.py`:

```python
# Firecrawl Configuration
FIRECRAWL_API_KEY: str = Field("", env="FIRECRAWL_API_KEY")
FIRECRAWL_API_URL: str = Field("https://api.firecrawl.dev", env="FIRECRAWL_API_URL")
FIRECRAWL_TIMEOUT: int = Field(30000, env="FIRECRAWL_TIMEOUT")
FIRECRAWL_MAX_RETRIES: int = Field(3, env="FIRECRAWL_MAX_RETRIES")
```

## How It Works

### 1. Artist Website Discovery

When processing an artist, the system:
- Looks for website URLs in artist metadata
- Generates potential social media URLs based on artist name
- Attempts to scrape these URLs using Firecrawl

### 2. Data Extraction

For each successfully scraped URL, Firecrawl extracts:
- **Contact Information**: Emails, phone numbers, social handles
- **Content Analysis**: Word count, social media mentions
- **Metadata**: Page title, description, and other structured data

### 3. Enhancement Integration

The extracted data enhances the artist profile with:
```python
{
    "firecrawl_sources": ["https://artist-website.com"],
    "contact_info": {
        "email": "contact@artist.com",
        "social_handle": "@artistname"
    },
    "web_mentions": 250,
    "social_presence": {
        "https://artist-website.com": {
            "content_length": 1500,
            "social_mentions": 5,
            "metadata": {...}
        }
    }
}
```

## Testing

Use the test script to verify your setup:

```bash
cd backend
python test_firecrawl_fix.py
```

Expected output when properly configured:
```
🧪 Firecrawl Fix Test Suite
==================================================
✅ PASS Import Test
✅ PASS Configuration Test  
✅ PASS Initialization Test
✅ PASS Enhanced Agent Test

🎉 All tests passed! Firecrawl is ready to use.
```

## Troubleshooting

### Import Error
**Error**: `ImportError: No module named 'firecrawl'`
**Solution**: Install the package: `pip install firecrawl-py==2.8.0`

### Configuration Error  
**Error**: `Firecrawl API key not configured`
**Solution**: Set the `FIRECRAWL_API_KEY` environment variable

### API Key Invalid
**Error**: `Failed to initialize FirecrawlApp: Invalid API key`
**Solution**: Verify your API key starts with `fc-` and is correct

### Rate Limiting
The system automatically limits scraping to avoid quota issues:
- Maximum 2 URLs per artist
- Graceful fallback when Firecrawl is unavailable
- Detailed logging for monitoring usage

## Pricing

Firecrawl offers flexible pricing plans:
- **Starter**: Free tier with limited requests
- **Pro**: Pay-as-you-go for production usage
- **Enterprise**: Custom pricing for high volume

Visit [https://firecrawl.dev/pricing](https://firecrawl.dev/pricing) for current pricing.

## Integration Status

### ✅ Completed
- Python SDK installation and import
- API key configuration
- Basic scraping functionality
- Contact information extraction
- Error handling and graceful fallbacks

### 🚧 Optional Enhancements
- Advanced extraction schemas
- Bulk crawling for large datasets
- Custom parsing rules for specific artist websites
- Integration with additional social platforms

## Usage Example

```python
from app.agents.enhanced_enrichment_agent_simple import SimpleEnhancedEnrichmentAgent

# Initialize agent
agent = SimpleEnhancedEnrichmentAgent()

# Enrich artist profile (includes Firecrawl data if configured)
result = await agent.enrich_artist_basic(artist_profile, deps)

# Access Firecrawl data
firecrawl_data = result.get("basic_info", {})
contact_info = firecrawl_data.get("contact_info", {})
```

## Support

- **Documentation**: [https://docs.firecrawl.dev](https://docs.firecrawl.dev)
- **Community**: Discord support available
- **Issues**: Report issues via GitHub or Firecrawl support

---

**Note**: Firecrawl is optional for the music discovery system. The system will work without it, but artist profiles will have less enriched data. 