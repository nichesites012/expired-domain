#!/usr/bin/env python3
"""
Domain Availability Checker Module
RapidAPI Domain Status integration for checking domain registration availability
"""

import http.client
import json
import time
from typing import Dict, List, Callable


class DomainAvailabilityChecker:
    """
    Check domain availability using RapidAPI domainstatus API
    Endpoint: domainstatus.p.rapidapi.com/v1/domain/available
    """
    def __init__(self, api_key: str = None, timeout: float = 10.0):
        self.api_key = api_key
        self.timeout = timeout
        self.api_host = "domainstatus.p.rapidapi.com"
        
        self.checked_count = 0
        self.available_count = 0
        self.unavailable_count = 0

    def set_api_key(self, api_key: str):
        self.api_key = api_key

    def _split_domain(self, domain: str) -> Dict[str, str]:
        domain = (domain or "").strip().lower()
        if not domain or '.' not in domain:
            return {"name": "", "tld": ""}
        parts = domain.split('.')
        name = parts[0]
        tld = '.' + '.'.join(parts[1:])
        return {"name": name, "tld": tld}

    def check_domain_availability(self, domain: str) -> Dict[str, any]:
        start_time = time.time()
        if not self.api_key:
            return {
                'domain': domain,
                'available': False,
                'skipped': True,
                'reason': 'No API key configured',
                'response_time': 0,
                'error': 'API key not set'
            }
        try:
            split = self._split_domain(domain)
            if not split['name'] or not split['tld']:
                return {
                    'domain': domain,
                    'available': False,
                    'skipped': True,
                    'reason': 'Invalid domain format',
                    'response_time': 0,
                    'error': 'Invalid domain'
                }

            conn = http.client.HTTPSConnection(self.api_host, timeout=self.timeout)

            payload = json.dumps({
                "name": split['name'],
                "tld": split['tld']
            })

            headers = {
                'x-rapidapi-key': self.api_key,
                'x-rapidapi-host': self.api_host,
                'Content-Type': 'application/json'
            }

            conn.request("POST", "/v1/domain/available", payload, headers)
            res = conn.getresponse()
            data = res.read()

            response_time = round((time.time() - start_time) * 1000, 2)

            if res.status == 200:
                response_data = json.loads(data.decode("utf-8"))
                available = bool(response_data.get('available', False))
                self.checked_count += 1
                if available:
                    self.available_count += 1
                else:
                    self.unavailable_count += 1
                return {
                    'domain': response_data.get('domain', domain),
                    'available': available,
                    'skipped': False,
                    'reason': 'Available' if available else 'Not available',
                    'response_time': response_time,
                    'raw': response_data,
                    'error': None
                }
            else:
                self.checked_count += 1
                self.unavailable_count += 1
                return {
                    'domain': domain,
                    'available': False,
                    'skipped': False,
                    'reason': 'API Error',
                    'response_time': response_time,
                    'error': f"API Error: {res.status} - {res.reason}"
                }
        except Exception as e:
            response_time = round((time.time() - start_time) * 1000, 2)
            self.checked_count += 1
            self.unavailable_count += 1
            return {
                'domain': domain,
                'available': False,
                'skipped': False,
                'reason': 'Exception occurred',
                'response_time': response_time,
                'error': str(e)
            }
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def check_domains_batch(self, domains: List[str], callback: Callable = None) -> Dict[str, Dict]:
        results: Dict[str, Dict] = {}
        for domain in domains:
            result = self.check_domain_availability(domain)
            results[domain] = result
            if callback:
                callback(domain, result)
            time.sleep(0.1)
        return results

    def test_api_connection(self) -> Dict[str, any]:
        """Test API connection with a known domain."""
        if not self.api_key:
            return {
                'success': False,
                'error': 'No API key configured',
                'message': 'Please set your RapidAPI key first'
            }
        try:
            test_result = self.check_domain_availability("example.com")
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


