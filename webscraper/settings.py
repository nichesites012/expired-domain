# Scrapy settings for webscraper project
#
# For simplicity, this file contains only settings considered important or
# commonly used. You can find more settings consulting the documentation:
#
#     https://docs.scrapy.org/en/latest/topics/settings.html
#     https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
#     https://docs.scrapy.org/en/latest/topics/spider-middleware.html

BOT_NAME = "webscraper"

SPIDER_MODULES = ["webscraper.spiders"]
NEWSPIDER_MODULE = "webscraper.spiders"

ADDONS = {}


# Crawl responsibly by identifying yourself (and your website) on the user-agent
#USER_AGENT = "webscraper (+http://www.yourdomain.com)"

# Obey robots.txt rules - DISABLED FOR MAXIMUM SPEED
ROBOTSTXT_OBEY = False

# HIGH-SPEED CONCURRENCY SETTINGS FOR VPS WITH 8GB RAM AND 10GBPS
CONCURRENT_REQUESTS = 200
CONCURRENT_REQUESTS_PER_DOMAIN = 100
DOWNLOAD_DELAY = 0  # NO DELAY FOR MAXIMUM SPEED
RANDOMIZE_DOWNLOAD_DELAY = 0  # DISABLE RANDOM DELAYS

# Disable cookies (enabled by default)
#COOKIES_ENABLED = False

# Disable Telnet Console (enabled by default)
#TELNETCONSOLE_ENABLED = False

# Override the default request headers:
#DEFAULT_REQUEST_HEADERS = {
#    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
#    "Accept-Language": "en",
#}

# Enable or disable spider middlewares
# See https://docs.scrapy.org/en/latest/topics/spider-middleware.html
SPIDER_MIDDLEWARES = {
    "webscraper.middlewares.WebscraperSpiderMiddleware": 543,
    "scrapy.spidermiddlewares.offsite.OffsiteMiddleware": None,  # Disable offsite filtering
}

# Enable or disable downloader middlewares
# See https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
DOWNLOADER_MIDDLEWARES = {
    "webscraper.middlewares.UserAgentRotationMiddleware": 400,
    # DISABLED FOR MAXIMUM SPEED - These add delays and processing overhead
    # "webscraper.middlewares.ExternalDomainMiddleware": 500,
    # "webscraper.middlewares.PoliteScrapingMiddleware": 600,
    # "webscraper.middlewares.WebscraperDownloaderMiddleware": 543,
    "scrapy.downloadermiddlewares.offsite.OffsiteMiddleware": None,  # Disable offsite filtering
}

# Enable or disable extensions
# See https://docs.scrapy.org/en/latest/topics/extensions.html
#EXTENSIONS = {
#    "scrapy.extensions.telnet.TelnetConsole": None,
#}

# Configure item pipelines
# See https://docs.scrapy.org/en/latest/topics/item-pipeline.html
#ITEM_PIPELINES = {
#    "webscraper.pipelines.WebscraperPipeline": 300,
#}

# Enable and configure the AutoThrottle extension - DISABLED FOR MAXIMUM SPEED
# See https://docs.scrapy.org/en/latest/topics/autothrottle.html
AUTOTHROTTLE_ENABLED = False  # DISABLED FOR LIMITLESS SPEED
# AUTOTHROTTLE_START_DELAY = 1
# AUTOTHROTTLE_MAX_DELAY = 10
# AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0
# AUTOTHROTTLE_DEBUG = True

# HIGH-PERFORMANCE OPTIMIZATIONS FOR VPS
REACTOR_THREADPOOL_MAXSIZE = 200  # Increased thread pool for better performance
DNSCACHE_ENABLED = True  # Enable DNS caching
DNSCACHE_SIZE = 10000  # Large DNS cache
DOWNLOAD_TIMEOUT = 15  # Reasonable timeout
DOWNLOAD_MAXSIZE = 1048576  # 1MB max page size

# MEMORY OPTIMIZATION FOR 8GB RAM VPS
MEMUSAGE_ENABLED = True
MEMUSAGE_LIMIT_MB = 6000  # Use up to 6GB of RAM

# Enable and configure HTTP caching (disabled by default)
# See https://docs.scrapy.org/en/latest/topics/downloader-middleware.html#httpcache-middleware-settings
#HTTPCACHE_ENABLED = True
#HTTPCACHE_EXPIRATION_SECS = 0
#HTTPCACHE_DIR = "httpcache"
#HTTPCACHE_IGNORE_HTTP_CODES = []
#HTTPCACHE_STORAGE = "scrapy.extensions.httpcache.FilesystemCacheStorage"

# Set settings whose default value is deprecated to a future-proof value
FEED_EXPORT_ENCODING = "utf-8"
