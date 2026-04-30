import os
import urllib.parse
import urllib.request
import json
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler

# Your TikTok App Credentials
CLIENT_KEY = "sbawoa7wzny82wzdhg"
CLIENT_SECRET = "XMynUOC0D7qirq2RS99Mx3cQH3xc1LxW"
REDIRECT_URI = "https://google.com/"
SCOPES = "user.info.basic,user.info.stats,video.list"

def get_access_token(code):
    url = "https://open.tiktokapis.com/v2/oauth/token/"
    data = urllib.parse.urlencode({
        "client_key": CLIENT_KEY,
        "client_secret": CLIENT_SECRET,
        "code": code,
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
            return result
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code}")
        print(e.read().decode())
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def main():
    print("=" * 60)
    print("TikTok OAuth Authorization (Manual Flow)")
    print("=" * 60)
    print(f"\nIMPORTANT: Add this EXACT link to your Redirect URIs in TikTok:")
    print(f"-->  {REDIRECT_URI}  <--\n")
    
    auth_url = (
        f"https://www.tiktok.com/v2/auth/authorize/"
        f"?client_key={CLIENT_KEY}"
        f"&scope={SCOPES}"
        f"&response_type=code"
        f"&redirect_uri={urllib.parse.quote_plus(REDIRECT_URI)}"
        f"&state=xyz123"
    )
    
    print("1. Opening browser to authorize...")
    print(f"If browser doesn't open automatically, click here:\n{auth_url}\n")
    
    webbrowser.open(auth_url)
    
    print("2. After you click 'Authorize' on TikTok, it will redirect you to valuechat.app")
    print("3. The page might say 'Not Found' or blank, THAT IS OKAY!")
    print("4. Look at the URL bar in your browser. It will look like:")
    print("   https://valuechat.app/callback?code=YOUR_CODE_HERE&state=xyz123\n")
    
    redirected_url = input("👉 Paste the FULL redirected URL here and press Enter: ").strip()
    
    if "code=" not in redirected_url:
        print("❌ Invalid URL. Make sure you copied the whole URL containing 'code='.")
        return
        
    # Extract the code from the pasted URL
    parsed_url = urllib.parse.urlparse(redirected_url)
    query_params = urllib.parse.parse_qs(parsed_url.query)
    
    if "code" not in query_params:
        print("❌ Could not find 'code' in the URL.")
        return
        
    auth_code = query_params["code"][0]
    
    print("\n[+] Authorization code received! Exchanging for access token...")
    token_data = get_access_token(auth_code)
    
    if token_data and "access_token" in token_data:
        access_token = token_data["access_token"]
        print("\n" + "=" * 60)
        print("✅ SUCCESS! Here is your Access Token:")
        print("=" * 60)
        print(f"\n{access_token}\n")
        print("Copy this token and send it to me!")
        print("=" * 60)
    else:
        print("\n❌ Failed to get access token. See error above.")

if __name__ == "__main__":
    main()
