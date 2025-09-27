#!/usr/bin/env python3
"""
Indexing Checker Module
Google Search API integration for checking HTTP domain indexing status
"""

import http.client
import json
import threading
import time
from typing import Dict, List, Optional, Callable
from urllib.parse import quote
import logging


class IndexingChecker:
    """
    Check domain indexing status using RapidAPI Google Search API
    Only processes HTTP domains (not HTTPS)
    """
    
    def __init__(self, api_key: str = None, timeout: float = 10.0):
        """
        Initialize the indexing checker
        
        Args:
            api_key: RapidAPI key for Google Search API
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.timeout = timeout
        self.api_host = "google-search116.p.rapidapi.com"
        
        # Statistics
        self.checked_count = 0
        self.indexed_count = 0
        self.not_indexed_count = 0
        
        self.logger = logging.getLogger(__name__)
        
    def set_api_key(self, api_key: str):
        """Set the RapidAPI key"""
        self.api_key = api_key
        
    def check_domain_indexing(self, domain: str, protocol: str = "http") -> Dict[str, any]:
        """
        Check if a domain is indexed in Google
        Only processes HTTP domains
        
        Args:
            domain: Domain name to check
            protocol: Protocol (only 'http' will be processed)
            
        Returns:
            Dictionary with indexing status and details
        """
        start_time = time.time()
        
        # Only check HTTP domains
        if protocol.lower() != "http":
            return {
                'domain': domain,
                'protocol': protocol,
                'indexed': False,
                'skipped': True,
                'reason': 'Not HTTP protocol',
                'response_time': 0,
                'results_count': 0,
                'error': None
            }
        
        if not self.api_key:
            return {
                'domain': domain,
                'protocol': protocol,
                'indexed': False,
                'skipped': True,
                'reason': 'No API key configured',
                'response_time': 0,
                'results_count': 0,
                'error': 'API key not set'
            }
        
        try:
            # Clean domain name
            domain = domain.strip().lower()
            if not domain:
                return {
                    'domain': domain,
                    'protocol': protocol,
                    'indexed': False,
                    'skipped': True,
                    'reason': 'Empty domain',
                    'response_time': 0,
                    'results_count': 0,
                    'error': 'Empty domain name'
                }
            
            # Create search query using site: operator for HTTP domain
            query = f"site:{domain}"
            encoded_query = quote(query)
            
            # Make API request
            conn = http.client.HTTPSConnection(self.api_host, timeout=self.timeout)
            
            headers = {
                'x-rapidapi-key': self.api_key,
                'x-rapidapi-host': self.api_host
            }
            
            endpoint = f"/?query={encoded_query}"
            conn.request("GET", endpoint, headers=headers)
            
            res = conn.getresponse()
            data = res.read()
            
            response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            if res.status == 200:
                # Parse JSON response
                response_data = json.loads(data.decode("utf-8"))
                
                # Check if results exist
                results = response_data.get('results', [])
                results_count = len(results)
                
                # Domain is indexed if we get search results
                indexed = results_count > 0
                
                if indexed:
                    self.indexed_count += 1
                else:
                    self.not_indexed_count += 1
                
                self.checked_count += 1
                
                return {
                    'domain': domain,
                    'protocol': protocol,
                    'indexed': indexed,
                    'skipped': False,
                    'reason': f"{results_count} results found" if indexed else "No results found",
                    'response_time': round(response_time, 2),
                    'results_count': results_count,
                    'results': results[:3] if results else [],  # Return first 3 results
                    'error': None
                }
            
            else:
                # Handle API errors
                error_msg = f"API Error: {res.status} - {res.reason}"
                self.not_indexed_count += 1
                self.checked_count += 1
                
                return {
                    'domain': domain,
                    'protocol': protocol,
                    'indexed': False,
                    'skipped': False,
                    'reason': 'API Error',
                    'response_time': round(response_time, 2),
                    'results_count': 0,
                    'error': error_msg
                }
                
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            self.not_indexed_count += 1
            self.checked_count += 1
            
            return {
                'domain': domain,
                'protocol': protocol,
                'indexed': False,
                'skipped': False,
                'reason': 'Exception occurred',
                'response_time': round(response_time, 2),
                'results_count': 0,
                'error': str(e)
            }
        
        finally:
            try:
                conn.close()
            except:
                pass
    
    def test_api_connection(self) -> Dict[str, any]:
        """
        Test API connection with a known domain
        
        Returns:
            Dictionary with test results
        """
        if not self.api_key:
            return {
                'success': False,
                'error': 'No API key configured',
                'message': 'Please set your RapidAPI key first'
            }
        
        try:
            # Test with a well-known HTTP domain that should be indexed
            test_result = self.check_domain_indexing("example.com", "http")
            
            if test_result.get('error'):
                return {
                    'success': False,
                    'error': test_result['error'],
                    'message': f"API test failed: {test_result['error']}"
                }
            
            return {
                'success': True,
                'error': None,
                'message': f"API test successful. Response time: {test_result['response_time']}ms",
                'test_result': test_result
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': f"API test failed with exception: {str(e)}"
            }
    
    def check_domains_batch(self, domains_data: List[Dict], callback: Callable = None) -> Dict[str, Dict]:
        """
        Check multiple domains for indexing status
        Only processes HTTP domains
        
        Args:
            domains_data: List of domain dictionaries with 'domain' and 'protocol' keys
            callback: Optional callback function called for each result
            
        Returns:
            Dictionary mapping domain names to their indexing results
        """
        if not domains_data:
            return {}
        
        results = {}
        
        for domain_info in domains_data:
            domain = domain_info.get('domain', '')
            protocol = domain_info.get('protocol', 'http')
            
            # Only process HTTP domains
            if protocol.lower() == 'http':
                result = self.check_domain_indexing(domain, protocol)
                results[domain] = result
                
                # Call callback if provided
                if callback:
                    callback(domain, result)
                
                # Add small delay to be polite to the API
                time.sleep(0.1)
            else:
                # Skip non-HTTP domains
                results[domain] = {
                    'domain': domain,
                    'protocol': protocol,
                    'indexed': False,
                    'skipped': True,
                    'reason': 'Not HTTP protocol',
                    'response_time': 0,
                    'results_count': 0,
                    'error': None
                }
                
                if callback:
                    callback(domain, results[domain])
        
        return results
    
    def get_statistics(self) -> Dict[str, int]:
        """
        Get indexing check statistics
        
        Returns:
            Dictionary with checking statistics
        """
        success_rate = (self.indexed_count / self.checked_count * 100) if self.checked_count > 0 else 0
        
        return {
            'total_checked': self.checked_count,
            'indexed': self.indexed_count,
            'not_indexed': self.not_indexed_count,
            'success_rate': round(success_rate, 2)
        }
    
    def reset_statistics(self):
        """Reset all statistics counters"""
        self.checked_count = 0
        self.indexed_count = 0
        self.not_indexed_count = 0


class IndexingCheckerThread(threading.Thread):
    """
    Thread wrapper for running indexing checks in the background
    """
    
    def __init__(self, domains_data: List[Dict], api_key: str, callback: Callable = None):
        """
        Initialize indexing checker thread
        
        Args:
            domains_data: List of domain dictionaries to check
            api_key: RapidAPI key
            callback: Callback function for each result
        """
        super().__init__(daemon=True)
        self.domains_data = domains_data
        self.api_key = api_key
        self.callback = callback
        self.indexing_checker = IndexingChecker(api_key=api_key)
        self.results = {}
        self.is_running = False
        
    def run(self):
        """Run the indexing checking process"""
        self.is_running = True
        try:
            self.results = self.indexing_checker.check_domains_batch(
                self.domains_data, 
                self.callback
            )
        finally:
            self.is_running = False
    
    def get_statistics(self):
        """Get indexing checking statistics"""
        return self.indexing_checker.get_statistics()


if __name__ == "__main__":
    # Test the indexing checker
    print("Testing Indexing Checker...")
    
    # Test with empty API key
    checker = IndexingChecker()
    test_result = checker.test_api_connection()
    print(f"Test without API key: {test_result}")
    
    # Test domains (would need real API key for actual testing)
    test_domains = [
        {'domain': 'example.com', 'protocol': 'http'},
        {'domain': 'httpbin.org', 'protocol': 'http'},
        {'domain': 'google.com', 'protocol': 'https'},  # Should be skipped
    ]
    
    print(f"\nTesting {len(test_domains)} domains (requires API key)...")
    results = checker.check_domains_batch(test_domains)
    
    for domain, result in results.items():
        status = "✓ Indexed" if result['indexed'] else ("⚠ Skipped" if result['skipped'] else "✗ Not Indexed")
        print(f"  {domain}: {status} - {result['reason']}")
    
    print(f"\nStatistics: {checker.get_statistics()}")