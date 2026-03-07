import urllib.request
import json
import ssl
import time
import sys

def verify_chat():
    url = "http://localhost:8000/api/v1/chat"
    headers = {"Content-Type": "application/json"}
    data = {"message": "Hello, what is your name?", "strategies": []}
    
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
    
    try:
        with urllib.request.urlopen(req) as response:
            if response.status != 200:
                print(f"HTTP Error: {response.status}")
                sys.exit(1)
            
            result = json.loads(response.read().decode('utf-8'))
            response_text = result.get('response', '')
            
            print("Response:", response_text)
            
            if "LLM Service Offline" in response_text or "unable to generate a real response" in response_text:
                print("FAIL: LLM fallback error message detected.")
                sys.exit(1)
            
            print("PASS: LLM response received successfully.")
            sys.exit(0)
    except Exception as e:
        print(f"Error during request: {e}")
        sys.exit(1)

if __name__ == "__main__":
    verify_chat()
