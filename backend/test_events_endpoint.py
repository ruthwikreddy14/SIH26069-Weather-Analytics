"""
Test script for events clustering endpoint
"""
import requests
import json

def test_events_endpoint():
    url = "http://localhost:8000/api/events/clusters"
    
    try:
        print(f"Testing: {url}")
        response = requests.get(url, params={"limit": 10})
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n✓ SUCCESS!")
            print(f"  Clusters: {data.get('total_clusters')}")
            print(f"  Reports Analyzed: {data.get('total_reports_analyzed')}")
            print(f"  Message: {data.get('message', 'N/A')}")
        else:
            print(f"\n✗ FAILED with status {response.status_code}")
            
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_events_endpoint()
