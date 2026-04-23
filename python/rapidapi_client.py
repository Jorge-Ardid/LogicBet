import requests
import json
from datetime import datetime, timedelta

class RapidAPIClient:
    def __init__(self, api_key="PLACEHOLDER_KEY", base_url=None, service_name="Generic"):
        self.api_key = api_key
        self.service_name = service_name
        self.base_url = base_url
        self.headers = {
            "x-rapidapi-host": self._extract_host(base_url) if base_url else "",
            "x-rapidapi-key": self.api_key,
            "Content-Type": "application/json"
        }
        self.is_mock = (api_key == "PLACEHOLDER_KEY")
        self.requests_remaining = None

    def _extract_host(self, url):
        """Extract host from URL for RapidAPI header"""
        if not url:
            return ""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc
        except:
            return ""

    def _make_request(self, endpoint, method="GET", data=None):
        """Make API request with error handling"""
        if self.is_mock:
            return self._get_mock_response(endpoint)
        
        url = f"{self.base_url}/{endpoint}" if endpoint else self.base_url
        
        try:
            if method.upper() == "POST":
                response = requests.post(url, headers=self.headers, json=data)
            else:
                response = requests.get(url, headers=self.headers, params=data)
            
            # Rate limit handling
            remaining = response.headers.get("x-ratelimit-requests-remaining")
            if remaining:
                self.requests_remaining = int(remaining)
            
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            print(f"{self.service_name} API Error ({endpoint}): {e}")
            return None

    def _get_mock_response(self, endpoint):
        """Mock response for testing"""
        return {
            "message": f"Mock response for {endpoint}",
            "status": "success",
            "data": {}
        }

    def get_limit_left(self):
        return self.requests_remaining

    def test_connection(self):
        """Test API connection"""
        print(f"🧪 Testing {self.service_name} API connection...")
        
        if self.is_mock:
            print(f"❌ {self.service_name}: API key not set")
            return False
        
        try:
            # Try a simple request - adjust endpoint based on service
            test_result = self._make_request("", method="GET")
            
            if test_result:
                print(f"✅ {self.service_name}: Connection successful")
                return True
            else:
                print(f"❌ {self.service_name}: No response")
                return False
                
        except Exception as e:
            print(f"❌ {self.service_name}: Connection failed - {e}")
            return False

    def get_status(self):
        """Get API status information"""
        return {
            "service": self.service_name,
            "base_url": self.base_url,
            "is_active": not self.is_mock,
            "requests_remaining": self.requests_remaining,
            "api_key_set": self.api_key != "PLACEHOLDER_KEY"
        }

# Specific service configurations
class NetworkAsCodeClient(RapidAPIClient):
    def __init__(self, api_key="3725c32b04mshb942c2df0e3ab79p18f60djsn14472b9a742"):
        super().__init__(
            api_key=api_key,
            base_url="https://network-as-code.p.rapidapi.com/device-status/device-reachability-status-subscriptions/v0.7",
            service_name="Network-as-Code"
        )

    def create_device_subscription(self, phone_number, sink_url, max_events=5):
        """Create device reachability subscription"""
        endpoint = "subscriptions"
        data = {
            "sink": sink_url,
            "protocol": "HTTP",
            "types": [
                "org.camaraproject.device-reachability-status-subscriptions.v0.reachabilitydata"
            ],
            "config": {
                "subscriptionDetail": {
                    "device": {
                        "phoneNumber": phone_number
                    }
                },
                "subscriptionMaxEvents": max_events,
                "initialEvent": True
            }
        }
        
        return self._make_request(endpoint, method="POST", data=data)

class GenericRapidAPIFootballClient(RapidAPIClient):
    def __init__(self, api_key="PLACEHOLDER_KEY"):
        super().__init__(
            api_key=api_key,
            base_url="https://api-football-v1.p.rapidapi.com/v3",
            service_name="Generic-Football-API"
        )

    def get_football_data(self, endpoint, params=None):
        """Generic football data fetcher"""
        return self._make_request(endpoint, method="GET", data=params)

# Factory function for creating clients
def create_rapidapi_client(service_type, api_key=None):
    """Factory function to create appropriate RapidAPI client"""
    
    clients = {
        "network_as_code": NetworkAsCodeClient,
        "generic_football": GenericRapidAPIFootballClient,
    }
    
    if service_type in clients:
        if api_key:
            return clients[service_type](api_key=api_key)
        else:
            return clients[service_type]()
    else:
        raise ValueError(f"Unknown service type: {service_type}")

if __name__ == "__main__":
    # Test Network-as-Code client
    network_client = NetworkAsCodeClient()
    print("Network-as-Code Client Status:")
    print(network_client.get_status())
    
    # Test connection
    network_client.test_connection()
    
    # Example usage
    # subscription = network_client.create_device_subscription(
    #     phone_number="199999991000",
    #     sink_url="https://endpoint.example.com/sink"
    # )
    # print("Subscription created:", subscription)
