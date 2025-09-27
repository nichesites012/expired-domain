"""
High-speed settings for WebScraper - Optimized for VPS with 8GB RAM and 10Gbps connection
This file overrides the default settings for maximum scraping performance
"""

# Import base settings
from .settings import *

# ULTRA HIGH-SPEED CONFIGURATION FOR VPS ENVIRONMENT
CONCURRENT_REQUESTS = 200  # Increased from 8 to utilize full VPS capacity
CONCURRENT_REQUESTS_PER_DOMAIN = 100  # Increased from 2 for aggressive crawling
DOWNLOAD_DELAY = 0  # NO DELAYS for maximum speed
RANDOMIZE_DOWNLOAD_DELAY = 0  # Disable all random delays
AUTOTHROTTLE_ENABLED = False  # Disable auto-throttling for speed
ROBOTSTXT_OBEY = False  # Ignore robots.txt for maximum coverage

# TCP/HTTP OPTIMIZATIONS
REACTOR_THREADPOOL_MAXSIZE = 200  # Large thread pool for VPS
DOWNLOAD_TIMEOUT = 15  # Quick timeout to avoid hanging
DOWNLOAD_MAXSIZE = 1048576  # 1MB max page size for faster processing
DNSCACHE_ENABLED = True  # Enable DNS caching
DNSCACHE_SIZE = 10000  # Large DNS cache for performance

# MEMORY OPTIMIZATIONS FOR 8GB RAM VPS
MEMUSAGE_ENABLED = True
MEMUSAGE_LIMIT_MB = 6000  # Use up to 6GB of 8GB RAM
MEMDEBUG_ENABLED = False  # Disable memory debugging for speed

# DISABLE SLOW MIDDLEWARES FOR MAXIMUM SPEED
DOWNLOADER_MIDDLEWARES = {
    "webscraper.middlewares.UserAgentRotationMiddleware": 400,
    # ALL OTHER MIDDLEWARES DISABLED FOR SPEED
    # "webscraper.middlewares.ExternalDomainMiddleware": None,
    # "webscraper.middlewares.PoliteScrapingMiddleware": None,
    # "webscraper.middlewares.WebscraperDownloaderMiddleware": None,
    "scrapy.downloadermiddlewares.offsite.OffsiteMiddleware": None,
}

# OPTIMIZE SPIDER MIDDLEWARES
SPIDER_MIDDLEWARES = {
    "webscraper.middlewares.WebscraperSpiderMiddleware": 543,
    "scrapy.spidermiddlewares.offsite.OffsiteMiddleware": None,
}

# CONNECTION OPTIMIZATIONS
DOWNLOAD_HANDLERS = {
    'http': 'scrapy.core.downloader.handlers.http.HTTPDownloadHandler',
    'https': 'scrapy.core.downloader.handlers.http.HTTPDownloadHandler',
}

# DISABLE UNNECESSARY FEATURES FOR SPEED
TELNETCONSOLE_ENABLED = False
COOKIES_ENABLED = False  # Disable cookies for speed
REDIRECT_ENABLED = True  # Keep redirects for coverage

# LOGGING OPTIMIZATIONS
LOG_LEVEL = 'INFO'  # Reduce logging for performance
LOG_STDOUT = False  # Don't duplicate logs to stdout

# ITEM PROCESSING OPTIMIZATIONS
ITEM_PIPELINES = {}  # Disable all pipelines for speed

# COMPRESSION SETTINGS
COMPRESSION_ENABLED = True  # Enable compression to save bandwidth

# RETRY SETTINGS - AGGRESSIVE FOR SPEED
RETRY_ENABLED = False  # Disable retries to avoid delays
RETRY_TIMES = 0  # No retries
RETRY_HTTP_CODES = []  # Don't retry any HTTP codes

# DUPEFILTER OPTIMIZATIONS
DUPEFILTER_DEBUG = False  # Disable dupefilter debugging
DUPEFILTER_CLASS = 'scrapy.dupefilters.RFPDupeFilter'

# SCHEDULER OPTIMIZATIONS
SCHEDULER_MEMORY_QUEUE = 'scrapy.squeues.LifoMemoryQueue'
SCHEDULER_DISK_QUEUE = 'scrapy.squeues.PickleLifoDiskQueue'

# DEFAULT REQUEST HEADERS - OPTIMIZED
DEFAULT_REQUEST_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
}

# EXTENSIONS - DISABLE UNNECESSARY ONES
EXTENSIONS = {
    'scrapy.extensions.telnet.TelnetConsole': None,
    'scrapy.extensions.corestats.CoreStats': None,  # Disable stats for speed
    'scrapy.extensions.memusage.MemoryUsage': 500 if MEMUSAGE_ENABLED else None,
}

print("SPEED SETTINGS LOADED: Maximum performance configuration active")