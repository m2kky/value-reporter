import urllib.parse
import urllib.request
import json

CLIENT_KEY = "sbawoa7wzny82wzdhg"
CLIENT_SECRET = "XMynUOC0D7qirq2RS99Mx3cQH3xc1LxW"
REFRESH_TOKEN = "rft.ClxFElQxjQH31ruIzGlFGJQr31oorLqcFRmTz8PA444DOvucWK7kUpbcSQz6!4786.s1"

def refresh_access_token():
    url = "https://open.tiktokapis.com/v2/oauth/token/"
    data = urllib.parse.urlencode({
        "client_key": CLIENT_KEY,
        "client_secret": CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": REFRESH_TOKEN,
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
            if "access_token" in result:
                print("\n✅ New Access Token:")
                print(result["access_token"])
                print(f"\nExpires in: {result.get('expires_in', '?')} seconds")
                if "refresh_token" in result:
                    print(f"\nNew Refresh Token (save this!):")
                    print(result["refresh_token"])
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code}")
        print(e.read().decode())

if __name__ == "__main__":
    refresh_access_token()
