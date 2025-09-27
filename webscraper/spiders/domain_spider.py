#!/usr/bin/env python3
"""
Domain Spider - Advanced web scraper for external domain extraction
Features: Asynchronous processing, targeted crawling, user-agent rotation, polite scraping
"""

import scrapy
import random
import re
import time
from urllib.parse import urljoin, urlparse
from scrapy.utils.response import get_base_url
import sys
import os

# Add project root to path for DNS checker import
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from src.dns_checker import AsyncDNSChecker


class DomainSpider(scrapy.Spider):
    """
    Advanced spider for crawling websites and extracting external domains
    """
    
    name = 'domain_spider'
    
    # User-agent strings for rotation
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/91.0.864.59',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0'
    ]
    
    def __init__(self, start_url=None, allowed_domain=None, max_concurrent=200, 
                 delay_min=0, delay_max=0, exclude_subdomains=True, min_chars=1, max_chars=100,
                 exclude_extensions='', target_extensions='', excluded_words='', hidden_words='', 
                 check_dns=True, *args, **kwargs):
        super(DomainSpider, self).__init__(*args, **kwargs)
        
        # Configuration from arguments
        self.start_urls = [start_url] if start_url else ['https://example.com']
        
        # Store the allowed domain for our own logic, but don't set self.allowed_domains
        # This prevents Scrapy's built-in domain filtering from blocking external requests
        self.base_allowed_domains = [allowed_domain] if allowed_domain else ['example.com']
        
        # DO NOT set self.allowed_domains - this allows Scrapy to crawl any domain
        
        # Convert string arguments to appropriate types
        self.max_concurrent = int(max_concurrent)
        self.delay_min = int(delay_min)
        self.delay_max = int(delay_max)
        self.exclude_subdomains = str(exclude_subdomains).lower() == 'true'
        self.min_chars = int(min_chars)
        self.max_chars = int(max_chars)
        
        # Process extension filters
        self.exclude_extensions = [ext.strip().lower() for ext in str(exclude_extensions).split(',') if ext.strip()]
        self.target_extensions = [ext.strip().lower() for ext in str(target_extensions).split(',') if ext.strip()]
        
        # Process excluded words filter
        self.excluded_words = [word.strip().lower() for word in str(excluded_words).split(',') if word.strip()]
        
        # Process hidden words filter  
        self.hidden_words = [word.strip().lower() for word in str(hidden_words).split(',') if word.strip()]
        
        # Storage for external domains
        self.external_domains = set()
        self.failed_domains = set()  # Store domains that failed DNS resolution
        self.crawled_urls = set()
        
        # DNS checker for domain validation (controlled by GUI checkbox)
        self.dns_checker = AsyncDNSChecker(timeout=3.0, max_workers=20)
        self.check_dns = str(check_dns).lower() == 'true'  # Controlled by GUI checkbox
        
        # Statistics
        self.total_requests = 0
        self.external_domains_found = 0
        self.failed_domains_found = 0
        
        # Configure spider settings - OPTIMIZED FOR MAXIMUM SPEED
        self.custom_settings = {
            'CONCURRENT_REQUESTS': self.max_concurrent,
            'CONCURRENT_REQUESTS_PER_DOMAIN': self.max_concurrent // 2,
            'DOWNLOAD_DELAY': 0,  # NO DELAYS FOR MAXIMUM SPEED
            'RANDOMIZE_DOWNLOAD_DELAY': False,  # NO RANDOM DELAYS
            'AUTOTHROTTLE_ENABLED': False,  # DISABLE THROTTLING FOR SPEED
            'ROBOTSTXT_OBEY': False,  # IGNORE ROBOTS.TXT FOR SPEED
            'USER_AGENT': random.choice(self.USER_AGENTS),
            'REACTOR_THREADPOOL_MAXSIZE': 200,
            'DNSCACHE_ENABLED': True,
            'DNSCACHE_SIZE': 10000,
            'DOWNLOAD_TIMEOUT': 15,
            'DOWNLOADER_MIDDLEWARES': {
                'webscraper.middlewares.UserAgentRotationMiddleware': 400,
                # DISABLED ALL SLOW MIDDLEWARES FOR MAXIMUM SPEED
                'scrapy.downloadermiddlewares.offsite.OffsiteMiddleware': None,  # Disable offsite filtering
            },
            'SPIDER_MIDDLEWARES': {
                'scrapy.spidermiddlewares.offsite.OffsiteMiddleware': None,  # Disable offsite filtering
            }
        }
        
        self.logger.info(f"Spider initialized for domain: {allowed_domain}")
        self.logger.info(f"Start URL: {start_url}")
        self.logger.info(f"Max concurrent requests: {self.max_concurrent}")
        self.logger.info(f"SPEED MODE: NO DELAYS - MAXIMUM PERFORMANCE")
        
        # Add performance tracking
        self.start_time = time.time()
    
    async def start(self):
        """Generate initial requests (modern async method)"""
        for url in self.start_urls:
            yield scrapy.Request(
                url=url,
                callback=self.parse,
                headers={'User-Agent': random.choice(self.USER_AGENTS)},
                meta={'download_delay': random.uniform(self.delay_min, self.delay_max)}
            )
    
    def start_requests(self):
        """Generate initial requests (legacy method for compatibility) - NO DELAYS"""
        for url in self.start_urls:
            yield scrapy.Request(
                url=url,
                callback=self.parse,
                headers={'User-Agent': random.choice(self.USER_AGENTS)},
                # REMOVED DELAY FOR MAXIMUM SPEED
                # meta={'download_delay': random.uniform(self.delay_min, self.delay_max)}
            )
    
    def parse(self, response):
        """
        Parse the response and extract links and external domains
        """
        self.total_requests += 1
        current_url = response.url
        
        if current_url in self.crawled_urls:
            return
            
        self.crawled_urls.add(current_url)
        
        self.logger.info(f"Parsing: {current_url}")
        
        # Extract all links from the page
        links = response.css('a::attr(href)').getall()
        
        for link in links:
            if not link:
                continue
                
            # Convert relative URLs to absolute URLs
            absolute_url = urljoin(response.url, link)
            parsed_url = urlparse(absolute_url)
            
            # Skip non-http protocols and fragments
            if parsed_url.scheme not in ['http', 'https']:
                continue
                
            domain = parsed_url.netloc.lower()
            if not domain:
                continue
            
            # Check if this is an external domain
            is_external = self.is_external_domain(domain)
            
            if is_external and parsed_url.scheme in ['http', 'https']:
                # Universal Mode: Capture all external domains (but filter excluded words)
                processed_domain = self.process_domain_for_subdomains(domain)
                
                if processed_domain and processed_domain not in self.external_domains:
                    # Check if domain contains any excluded words
                    if self.contains_excluded_words(processed_domain):
                        continue  # Skip this domain entirely
                    
                    # Check if domain contains hidden words
                    is_hidden = self.contains_hidden_words(processed_domain)
                    
                    # Extract domain extension
                    domain_extension = self.extract_domain_extension(processed_domain)
                    
                    # Apply advanced filters
                    if self.passes_advanced_filters(processed_domain, domain_extension):
                        self.external_domains.add(processed_domain)
                        self.external_domains_found += 1
                        
                        # Only log and yield if domain is not hidden
                        if not is_hidden:
                            # Check DNS status if DNS checking is enabled
                            dns_status = None
                            if self.check_dns:
                                try:
                                    dns_result = self.dns_checker.check_domain_sync(processed_domain)
                                    dns_status = dns_result['status']
                                    if not dns_status:
                                        self.failed_domains.add(processed_domain)
                                        self.failed_domains_found += 1
                                except Exception as e:
                                    self.logger.debug(f"DNS check failed for {processed_domain}: {e}")
                                    dns_status = False
                                    self.failed_domains.add(processed_domain)
                                    self.failed_domains_found += 1
                            
                            # Log in format expected by GUI: domain|protocol|extension
                            # Include DNS status in log for GUI processing
                            if dns_status is not None:
                                self.logger.info(f"External domain found: {processed_domain}|{parsed_url.scheme}|{domain_extension}")
                                self.logger.info(f"DNS status: {processed_domain}|{dns_status}")
                            else:
                                self.logger.info(f"External domain found: {processed_domain}|{parsed_url.scheme}|{domain_extension}")
                            
                            # Yield the external domain for pipeline processing
                            yield {
                                'type': 'external_domain',
                                'domain': processed_domain,
                                'protocol': parsed_url.scheme,
                                'extension': domain_extension,
                                'source_url': current_url,
                                'full_url': absolute_url,
                                'dns_status': dns_status
                            }
                        else:
                            # Hidden domain - don't log or yield, but still count it
                            self.logger.debug(f"Hidden domain processed but not displayed: {processed_domain}")
            
            elif not is_external:
                # This is an internal link - follow it for more crawling - NO DELAYS
                if absolute_url not in self.crawled_urls:
                    yield scrapy.Request(
                        url=absolute_url,
                        callback=self.parse,
                        headers={'User-Agent': random.choice(self.USER_AGENTS)},
                        # REMOVED DELAY FOR MAXIMUM SPEED
                        # meta={'download_delay': random.uniform(self.delay_min, self.delay_max)},
                        dont_filter=False
                    )
            
            elif is_external:
                # Check if this external domain should be crawled (if it contains hidden words) - NO DELAYS
                processed_domain = self.process_domain_for_subdomains(domain)
                if processed_domain and self.contains_hidden_words(processed_domain):
                    # This is a hidden domain - crawl it but don't display results
                    if absolute_url not in self.crawled_urls:
                        yield scrapy.Request(
                            url=absolute_url,
                            callback=self.parse,
                            headers={'User-Agent': random.choice(self.USER_AGENTS)},
                            # REMOVED DELAY FOR MAXIMUM SPEED
                            # meta={'download_delay': random.uniform(self.delay_min, self.delay_max)},
                            dont_filter=False
                        )
        
        # Yield page statistics
        yield {
            'type': 'page_stats',
            'url': current_url,
            'links_found': len(links),
            'timestamp': response.headers.get('Date', b'').decode('utf-8', 'ignore')
        }
    
    def is_external_domain(self, domain):
        """
        Check if a domain is external (not in base_allowed_domains)
        """
        # Remove www. prefix for comparison
        clean_domain = domain.replace('www.', '')
        
        for allowed in self.base_allowed_domains:
            allowed_clean = allowed.replace('www.', '')
            
            # Check exact match or subdomain
            if (clean_domain == allowed_clean or 
                clean_domain.endswith('.' + allowed_clean)):
                return False
                
        return True
    
    def process_domain_for_subdomains(self, domain):
        """
        Process domain based on subdomain exclusion setting
        Returns the main domain if excluding subdomains, or the full domain otherwise
        """
        if not self.exclude_subdomains:
            return domain
        
        # Remove www. prefix
        clean_domain = domain.replace('www.', '')
        
        # Split domain into parts
        parts = clean_domain.split('.')
        
        # If domain has more than 2 parts, extract main domain
        if len(parts) > 2:
            # Handle special cases like .co.uk, .com.au, etc.
            common_tlds = ['co.uk', 'com.au', 'co.jp', 'co.nz', 'co.za', 'org.uk', 'net.au']
            
            # Check if it ends with a common multi-part TLD
            domain_suffix = '.'.join(parts[-2:])
            if domain_suffix in common_tlds and len(parts) > 3:
                # Return domain.tld for multi-part TLDs
                return '.'.join(parts[-3:])
            else:
                # Return domain.tld for standard TLDs
                return '.'.join(parts[-2:])
        
        return clean_domain
    
    def extract_domain_extension(self, domain):
        """
        Extract the top-level domain extension from a domain
        """
        parts = domain.split('.')
        if len(parts) >= 2:
            # Handle multi-part TLDs
            if len(parts) >= 3:
                potential_tld = '.'.join(parts[-2:])
                common_tlds = ['co.uk', 'com.au', 'co.jp', 'co.nz', 'co.za', 'org.uk', 'net.au']
                if potential_tld in common_tlds:
                    return potential_tld
            
            return parts[-1]  # Return the last part as TLD
        
        return 'unknown'
    
    def passes_advanced_filters(self, domain, extension):
        """
        Check if domain passes all advanced filtering criteria
        """
        # Extract domain name without extension for character count
        domain_without_ext = domain
        if '.' in domain:
            parts = domain.split('.')
            # Remove extension parts
            if len(parts) > 1:
                # Handle multi-part TLDs
                common_tlds = ['co.uk', 'com.au', 'co.jp', 'co.nz', 'co.za', 'org.uk', 'net.au']
                domain_suffix = '.'.join(parts[-2:])
                if domain_suffix in common_tlds and len(parts) > 2:
                    domain_without_ext = '.'.join(parts[:-2])
                else:
                    domain_without_ext = '.'.join(parts[:-1])
        
        # Count characters in domain name (excluding extension)
        char_count = len(domain_without_ext)
        
        # Check character count filter
        if char_count < self.min_chars or char_count > self.max_chars:
            return False
        
        # Check exclusion filter
        if self.exclude_extensions:
            extension_lower = f'.{extension.lower()}' if not extension.startswith('.') else extension.lower()
            for excluded_ext in self.exclude_extensions:
                if not excluded_ext.startswith('.'):
                    excluded_ext = f'.{excluded_ext}'
                if extension_lower == excluded_ext:
                    return False
        
        # Check target extensions filter (only if specified)
        if self.target_extensions:
            extension_lower = f'.{extension.lower()}' if not extension.startswith('.') else extension.lower()
            matched = False
            for target_ext in self.target_extensions:
                if not target_ext.startswith('.'):
                    target_ext = f'.{target_ext}'
                if extension_lower == target_ext:
                    matched = True
                    break
            if not matched:
                return False
        
        return True
    
    def contains_excluded_words(self, domain):
        """
        Check if domain contains any of the excluded words
        """
        if not self.excluded_words:
            return False  # No excluded words defined, allow domain
        
        domain_lower = domain.lower()
        for excluded_word in self.excluded_words:
            if excluded_word in domain_lower:
                self.logger.debug(f"Skipping domain '{domain}' - contains excluded word '{excluded_word}'")
                return True
        
        return False
    
    def contains_hidden_words(self, domain):
        """
        Check if domain contains any of the hidden words
        """
        if not self.hidden_words:
            return False  # No hidden words defined, domain is not hidden
        
        domain_lower = domain.lower()
        for hidden_word in self.hidden_words:
            if hidden_word in domain_lower:
                self.logger.debug(f"Hidden domain '{domain}' - contains hidden word '{hidden_word}'")
                return True
        
        return False
    
    def closed(self, reason):
        """
        Called when the spider is closed - with performance statistics
        """
        duration = time.time() - getattr(self, 'start_time', time.time())
        rate = self.total_requests / duration if duration > 0 else 0
        
        self.logger.info(f"Spider closed: {reason}")
        self.logger.info(f"PERFORMANCE STATS:")
        self.logger.info(f"Duration: {duration:.2f} seconds")
        self.logger.info(f"Total requests made: {self.total_requests}")
        self.logger.info(f"Request rate: {rate:.2f} requests/second")
        self.logger.info(f"Total URLs crawled: {len(self.crawled_urls)}")
        self.logger.info(f"External HTTP domains found: {self.external_domains_found}")
        self.logger.info(f"Failed DNS domains found: {self.failed_domains_found}")
        self.logger.info(f"Unique external domains: {list(self.external_domains)}")
        self.logger.info(f"Unique failed domains: {list(self.failed_domains)}")
        
        # Save final results
        final_results = {
            'type': 'final_results',
            'duration': duration,
            'request_rate': rate,
            'total_requests': self.total_requests,
            'total_urls_crawled': len(self.crawled_urls),
            'external_domains_count': self.external_domains_found,
            'failed_domains_count': self.failed_domains_found,
            'unique_external_domains': list(self.external_domains),
            'unique_failed_domains': list(self.failed_domains),
            'crawled_urls': list(self.crawled_urls),
            'allowed_domains': self.base_allowed_domains,
            'reason': reason
        }
        
        return final_results