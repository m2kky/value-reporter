import urllib.parse
import urllib.request
import json

CLIENT_KEY = "sbawoa7wzny82wzdhg"
CLIENT_SECRET = "XMynUOC0D7qirq2RS99Mx3cQH3xc1LxW"
REDIRECT_URI = "https://google.com/"
CODE = "Dnj1sWj_u_GOeblYb12ZM7EEyPDXX64VpeT-Nm5sjSfNmBDL7KpV3gpynr823gk4n7LWeuXhyK9il9pKjM0azN6nHwmXRrD6pGhuhpx-bFSV6-zUnm7RyhD6gr5AB-RKQ6wd0qQh30ViwuIhO3I72GIw-xxHF99QrVYt49wqUTFRSxfd8bqrUFBUlJrzCnOwR4pNzKZkwdyuHbe4*v!4792.s1"

def get_access_token():
    url = "https://open.tiktokapis.com/v2/oauth/token/"
    data = urllib.parse.urlencode({
        "client_key": CLIENT_KEY,
        "client_secret": CLIENT_SECRET,
        "code": CODE,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI
    }).encode("utf-8")
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Cache-Control": "no-cache"
    }
    
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode())
            print(json.dumps(result, indent=2))
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code}")
        print(e.read().decode())
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    get_access_token()
