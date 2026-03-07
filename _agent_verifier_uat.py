import urllib.request
import time

def check_service(url, name, retries=30):
    for i in range(retries):
        try:
            resp = urllib.request.urlopen(url)
            if resp.status == 200:
                print(f"{name} is UP at {url}")
                return True
        except Exception as e:
            pass
        time.sleep(1)
    print(f"{name} is DOWN at {url}")
    return False

if __name__ == "__main__":
    backend = check_service("http://localhost:8000/health", "Backend")
    frontend = check_service("http://localhost:3000", "Frontend")
    if backend and frontend:
        print("PASS")
        exit(0)
    else:
        print("FAIL")
        exit(1)
