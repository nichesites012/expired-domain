# Define here the models for your spider middleware
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/spider-middleware.html

from scrapy import signals
import random
import time

# useful for handling different item types with a single interface
from itemadapter import ItemAdapter


class WebscraperSpiderMiddleware:
    # Not all methods need to be defined. If a method is not defined,
    # scrapy acts as if the spider middleware does not modify the
    # passed objects.

    @classmethod
    def from_crawler(cls, crawler):
        # This method is used by Scrapy to create your spiders.
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_spider_input(self, response, spider):
        # Called for each response that goes through the spider
        # middleware and into the spider.

        # Should return None or raise an exception.
        return None

    def process_spider_output(self, response, result, spider):
        # Called with the results returned from the Spider, after
        # it has processed the response.

        # Must return an iterable of Request, or item objects.
        for i in result:
            yield i

    def process_spider_exception(self, response, exception, spider):
        # Called when a spider or process_spider_input() method
        # (from other spider middleware) raises an exception.

        # Should return either None or an iterable of Request or item objects.
        pass

    async def process_start(self, start):
        # Called with an async iterator over the spider start() method or the
        # maching method of an earlier spider middleware.
        async for item_or_request in start:
            yield item_or_request

    def spider_opened(self, spider):
        spider.logger.info("Spider opened: %s" % spider.name)


class UserAgentRotationMiddleware:
    """
    Middleware for rotating User-Agent strings to avoid detection
    """
    
    def __init__(self):
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/91.0.864.59',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:90.0) Gecko/20100101 Firefox/90.0'
        ]
        
    @classmethod
    def from_crawler(cls, crawler):
        return cls()
    
    def process_request(self, request, spider):
        """
        Rotate User-Agent for each request
        """
        # Select a random user agent
        user_agent = random.choice(self.user_agents)
        request.headers['User-Agent'] = user_agent
        
        # Add some randomization to headers to appear more human-like
        accept_headers = [
            'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8'
        ]
        
        request.headers['Accept'] = random.choice(accept_headers)
        request.headers['Accept-Language'] = 'en-US,en;q=0.9'
        request.headers['Accept-Encoding'] = 'gzip, deflate, br'
        request.headers['DNT'] = '1'
        request.headers['Connection'] = 'keep-alive'
        request.headers['Upgrade-Insecure-Requests'] = '1'
        
        spider.logger.debug(f"Using User-Agent: {user_agent[:50]}...")
        
        return None


class ExternalDomainMiddleware:
    """
    Middleware for processing external domains and implementing additional politeness
    """
    
    def __init__(self):
        self.request_times = {}
        self.domain_delays = {}
        
    @classmethod
    def from_crawler(cls, crawler):
        return cls()
    
    def process_request(self, request, spider):
        """
        Implement polite delays per domain
        """
        from urllib.parse import urlparse
        
        domain = urlparse(request.url).netloc
        current_time = time.time()
        
        # Check if we need to delay for this domain
        if domain in self.request_times:
            time_since_last = current_time - self.request_times[domain]
            min_delay = getattr(spider, 'delay_min', 1)
            
            if time_since_last < min_delay:
                delay_needed = min_delay - time_since_last
                spider.logger.debug(f"Delaying request to {domain} for {delay_needed:.2f} seconds")
                time.sleep(delay_needed)
        
        self.request_times[domain] = time.time()
        
        return None
    
    def process_response(self, request, response, spider):
        """
        Process response and extract additional metadata
        """
        # Log successful response
        spider.logger.debug(f"Response {response.status} from {request.url}")
        
        # Check for rate limiting responses
        if response.status == 429:  # Too Many Requests
            spider.logger.warning(f"Rate limited by {request.url} - Status 429")
            
        elif response.status >= 400:
            spider.logger.warning(f"HTTP Error {response.status} from {request.url}")
            
        return response
    
    def process_exception(self, request, exception, spider):
        """
        Handle exceptions and implement retry logic
        """
        spider.logger.error(f"Exception for {request.url}: {str(exception)}")
        return None


class PoliteScrapingMiddleware:
    """
    Additional middleware for implementing polite scraping practices
    """
    
    def __init__(self):
        self.request_count = 0
        self.start_time = time.time()
        
    @classmethod  
    def from_crawler(cls, crawler):
        return cls()
    
    def process_request(self, request, spider):
        """
        Monitor request rate and implement throttling
        """
        self.request_count += 1
        
        # Log progress every 10 requests
        if self.request_count % 10 == 0:
            elapsed_time = time.time() - self.start_time
            rate = self.request_count / elapsed_time if elapsed_time > 0 else 0
            spider.logger.info(f"Requests made: {self.request_count}, Rate: {rate:.2f} req/sec")
        
        # Respect robots.txt by default (handled by Scrapy's built-in middleware)
        return None
    
    def spider_opened(self, spider):
        """
        Log spider startup information
        """
        spider.logger.info("PoliteScrapingMiddleware: Spider started with politeness features enabled")
        spider.logger.info(f"Target domains: {getattr(spider, 'allowed_domains', 'Not specified')}")
        spider.logger.info(f"Concurrent requests: {getattr(spider, 'max_concurrent', 'Default')}")
        spider.logger.info(f"Delay range: {getattr(spider, 'delay_min', 1)}-{getattr(spider, 'delay_max', 5)} seconds")


class WebscraperDownloaderMiddleware:
    # Not all methods need to be defined. If a method is not defined,
    # scrapy acts as if the downloader middleware does not modify the
    # passed objects.

    @classmethod
    def from_crawler(cls, crawler):
        # This method is used by Scrapy to create your spiders.
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_request(self, request, spider):
        # Called for each request that goes through the downloader
        # middleware.

        # Must either:
        # - return None: continue processing this request
        # - or return a Response object
        # - or return a Request object
        # - or raise IgnoreRequest: process_exception() methods of
        #   installed downloader middleware will be called
        return None

    def process_response(self, request, response, spider):
        # Called with the response returned from the downloader.

        # Must either;
        # - return a Response object
        # - return a Request object
        # - or raise IgnoreRequest
        return response

    def process_exception(self, request, exception, spider):
        # Called when a download handler or a process_request()
        # (from other downloader middleware) raises an exception.

        # Must either:
        # - return None: continue processing this exception
        # - return a Response object: stops process_exception() chain
        # - return a Request object: stops process_exception() chain
        pass

    def spider_opened(self, spider):
        spider.logger.info("Spider opened: %s" % spider.name)


class UserAgentRotationMiddleware:
    """
    Middleware for rotating User-Agent strings to avoid detection
    """
    
    def __init__(self):
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/91.0.864.59',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:90.0) Gecko/20100101 Firefox/90.0'
        ]
        
    @classmethod
    def from_crawler(cls, crawler):
        return cls()
    
    def process_request(self, request, spider):
        """
        Rotate User-Agent for each request
        """
        # Select a random user agent
        user_agent = random.choice(self.user_agents)
        request.headers['User-Agent'] = user_agent
        
        # Add some randomization to headers to appear more human-like
        accept_headers = [
            'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8'
        ]
        
        request.headers['Accept'] = random.choice(accept_headers)
        request.headers['Accept-Language'] = 'en-US,en;q=0.9'
        request.headers['Accept-Encoding'] = 'gzip, deflate, br'
        request.headers['DNT'] = '1'
        request.headers['Connection'] = 'keep-alive'
        request.headers['Upgrade-Insecure-Requests'] = '1'
        
        spider.logger.debug(f"Using User-Agent: {user_agent[:50]}...")
        
        return None


class ExternalDomainMiddleware:
    """
    Middleware for processing external domains and implementing additional politeness
    """
    
    def __init__(self):
        self.request_times = {}
        self.domain_delays = {}
        
    @classmethod
    def from_crawler(cls, crawler):
        return cls()
    
    def process_request(self, request, spider):
        """
        Implement polite delays per domain
        """
        from urllib.parse import urlparse
        
        domain = urlparse(request.url).netloc
        current_time = time.time()
        
        # Check if we need to delay for this domain
        if domain in self.request_times:
            time_since_last = current_time - self.request_times[domain]
            min_delay = getattr(spider, 'delay_min', 1)
            
            if time_since_last < min_delay:
                delay_needed = min_delay - time_since_last
                spider.logger.debug(f"Delaying request to {domain} for {delay_needed:.2f} seconds")
                time.sleep(delay_needed)
        
        self.request_times[domain] = time.time()
        
        return None
    
    def process_response(self, request, response, spider):
        """
        Process response and extract additional metadata
        """
        # Log successful response
        spider.logger.debug(f"Response {response.status} from {request.url}")
        
        # Check for rate limiting responses
        if response.status == 429:  # Too Many Requests
            spider.logger.warning(f"Rate limited by {request.url} - Status 429")
            
        elif response.status >= 400:
            spider.logger.warning(f"HTTP Error {response.status} from {request.url}")
            
        return response
    
    def process_exception(self, request, exception, spider):
        """
        Handle exceptions and implement retry logic
        """
        spider.logger.error(f"Exception for {request.url}: {str(exception)}")
        return None


class PoliteScrapingMiddleware:
    """
    Additional middleware for implementing polite scraping practices
    """
    
    def __init__(self):
        self.request_count = 0
        self.start_time = time.time()
        
    @classmethod  
    def from_crawler(cls, crawler):
        return cls()
    
    def process_request(self, request, spider):
        """
        Monitor request rate and implement throttling
        """
        self.request_count += 1
        
        # Log progress every 10 requests
        if self.request_count % 10 == 0:
            elapsed_time = time.time() - self.start_time
            rate = self.request_count / elapsed_time if elapsed_time > 0 else 0
            spider.logger.info(f"Requests made: {self.request_count}, Rate: {rate:.2f} req/sec")
        
        # Respect robots.txt by default (handled by Scrapy's built-in middleware)
        return None
    
    def spider_opened(self, spider):
        """
        Log spider startup information
        """
        spider.logger.info("PoliteScrapingMiddleware: Spider started with politeness features enabled")
        spider.logger.info(f"Target domains: {getattr(spider, 'allowed_domains', 'Not specified')}")
        spider.logger.info(f"Concurrent requests: {getattr(spider, 'max_concurrent', 'Default')}")
        spider.logger.info(f"Delay range: {getattr(spider, 'delay_min', 1)}-{getattr(spider, 'delay_max', 5)} seconds")
