#!/usr/bin/env python3
"""
Asynchronous DNS Checker Module
Professional DNS resolution checking for web scraping applications
"""

import asyncio
import socket
import time
from typing import List, Dict, Optional, Tuple
import dns.resolver
import dns.exception
import threading
from concurrent.futures import ThreadPoolExecutor
import logging


class AsyncDNSChecker:
    """
    Asynchronous DNS checker for validating domain resolution
    """
    
    def __init__(self, timeout: float = 5.0, max_workers: int = 50):
        """
        Initialize DNS checker with configuration
        
        Args:
            timeout: DNS resolution timeout in seconds
            max_workers: Maximum number of concurrent DNS checks
        """
        self.timeout = timeout
        self.max_workers = max_workers
        self.resolver = dns.resolver.Resolver()
        self.resolver.timeout = timeout
        self.resolver.lifetime = timeout
        
        # Configure DNS servers for better performance
        self.resolver.nameservers = [
            '8.8.8.8',     # Google DNS
            '8.8.4.4',     # Google DNS Secondary
            '1.1.1.1',     # Cloudflare DNS
            '1.0.0.1',     # Cloudflare DNS Secondary
        ]
        
        self.logger = logging.getLogger(__name__)
        
        # Statistics
        self.checked_count = 0
        self.resolved_count = 0
        self.failed_count = 0
        
    def check_domain_sync(self, domain: str) -> Dict[str, any]:
        """
        Synchronous DNS check for a single domain
        
        Args:
            domain: Domain name to check
            
        Returns:
            Dictionary with domain, status, and error information
        """
        start_time = time.time()
        
        try:
            # Clean domain name
            domain = domain.strip().lower()
            if not domain:
                return {
                    'domain': domain,
                    'status': False,
                    'error': 'Empty domain',
                    'response_time': 0,
                    'resolver_used': 'none'
                }
            
            # Remove protocol prefixes if present
            domain = domain.replace('http://', '').replace('https://', '')
            domain = domain.split('/')[0]  # Remove path if present
            
            # Try A record resolution
            try:
                answers = self.resolver.resolve(domain, 'A')
                response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
                
                # Get the IP addresses
                ip_addresses = [str(answer) for answer in answers]
                
                self.resolved_count += 1
                return {
                    'domain': domain,
                    'status': True,
                    'error': None,
                    'response_time': round(response_time, 2),
                    'ip_addresses': ip_addresses,
                    'resolver_used': 'A_record'
                }
                
            except dns.resolver.NXDOMAIN:
                # Domain doesn't exist
                response_time = (time.time() - start_time) * 1000
                self.failed_count += 1
                return {
                    'domain': domain,
                    'status': False,
                    'error': 'NXDOMAIN',
                    'response_time': round(response_time, 2),
                    'resolver_used': 'A_record'
                }
                
            except dns.resolver.Timeout:
                # DNS timeout
                response_time = (time.time() - start_time) * 1000
                self.failed_count += 1
                return {
                    'domain': domain,
                    'status': False,
                    'error': 'TIMEOUT',
                    'response_time': round(response_time, 2),
                    'resolver_used': 'A_record'
                }
                
            except dns.resolver.NoAnswer:
                # No A record, but domain might exist - try AAAA
                try:
                    answers = self.resolver.resolve(domain, 'AAAA')
                    response_time = (time.time() - start_time) * 1000
                    ip_addresses = [str(answer) for answer in answers]
                    
                    self.resolved_count += 1
                    return {
                        'domain': domain,
                        'status': True,
                        'error': None,
                        'response_time': round(response_time, 2),
                        'ip_addresses': ip_addresses,
                        'resolver_used': 'AAAA_record'
                    }
                except:
                    # No IPv6 either
                    response_time = (time.time() - start_time) * 1000
                    self.failed_count += 1
                    return {
                        'domain': domain,
                        'status': False,
                        'error': 'NO_ANSWER',
                        'response_time': round(response_time, 2),
                        'resolver_used': 'AAAA_record'
                    }
                    
        except Exception as e:
            # General error
            response_time = (time.time() - start_time) * 1000
            self.failed_count += 1
            return {
                'domain': domain,
                'status': False,
                'error': str(e),
                'response_time': round(response_time, 2),
                'resolver_used': 'error'
            }
        finally:
            self.checked_count += 1
    
    def check_domains_batch(self, domains: List[str], callback=None) -> Dict[str, Dict]:
        """
        Check multiple domains using thread pool for better performance
        
        Args:
            domains: List of domain names to check
            callback: Optional callback function called for each result
            
        Returns:
            Dictionary mapping domain names to their check results
        """
        if not domains:
            return {}
        
        results = {}
        
        # Use ThreadPoolExecutor for concurrent DNS checks
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all DNS check tasks
            future_to_domain = {
                executor.submit(self.check_domain_sync, domain): domain 
                for domain in set(domains)  # Remove duplicates
            }
            
            # Process completed tasks as they finish
            for future in future_to_domain:
                domain = future_to_domain[future]
                try:
                    result = future.result()
                    results[domain] = result
                    
                    # Call callback if provided
                    if callback:
                        callback(domain, result)
                        
                except Exception as e:
                    # Handle executor errors
                    results[domain] = {
                        'domain': domain,
                        'status': False,
                        'error': f'Executor error: {str(e)}',
                        'response_time': 0,
                        'resolver_used': 'error'
                    }
                    
                    if callback:
                        callback(domain, results[domain])
        
        return results
    
    def get_statistics(self) -> Dict[str, int]:
        """
        Get DNS checking statistics
        
        Returns:
            Dictionary with checking statistics
        """
        success_rate = (self.resolved_count / self.checked_count * 100) if self.checked_count > 0 else 0
        
        return {
            'total_checked': self.checked_count,
            'resolved': self.resolved_count,
            'failed': self.failed_count,
            'success_rate': round(success_rate, 2)
        }
    
    def reset_statistics(self):
        """Reset all statistics counters"""
        self.checked_count = 0
        self.resolved_count = 0
        self.failed_count = 0


class DNSCheckerThread(threading.Thread):
    """
    Thread wrapper for running DNS checks in the background
    """
    
    def __init__(self, domains: List[str], callback=None, **kwargs):
        """
        Initialize DNS checker thread
        
        Args:
            domains: List of domains to check
            callback: Callback function for each result
            **kwargs: Additional arguments passed to AsyncDNSChecker
        """
        super().__init__(daemon=True)
        self.domains = domains
        self.callback = callback
        self.dns_checker = AsyncDNSChecker(**kwargs)
        self.results = {}
        self.is_running = False
        
    def run(self):
        """Run the DNS checking process"""
        self.is_running = True
        try:
            self.results = self.dns_checker.check_domains_batch(
                self.domains, 
                self.callback
            )
        finally:
            self.is_running = False
    
    def get_statistics(self):
        """Get DNS checking statistics"""
        return self.dns_checker.get_statistics()


def test_dns_checker():
    """
    Test function for DNS checker functionality
    """
    print("Testing DNS Checker...")
    
    # Test domains
    test_domains = [
        'google.com',
        'github.com', 
        'nonexistentdomain12345.com',
        'facebook.com',
        'invalid-domain-xyz.com'
    ]
    
    def result_callback(domain, result):
        status = "✓" if result['status'] else "✗"
        print(f"{status} {domain}: {result['status']} ({result.get('response_time', 0)}ms)")
    
    checker = AsyncDNSChecker(timeout=3.0)
    results = checker.check_domains_batch(test_domains, result_callback)
    
    print(f"\nStatistics: {checker.get_statistics()}")
    
    return results


if __name__ == "__main__":
    test_dns_checker()