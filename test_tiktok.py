import urllib.parse
import urllib.request
import json

ACCESS_TOKEN = "act.w4I1Fmlr9vRj1YmdOGs1JcInbtriNmBDTdfYjWhhFhDi75JtKtuU8T4YzZlL!4819.s1"

# Test 1: Fetch user info
fields = "open_id,union_id,avatar_url,display_name,follower_count,following_count,likes_count,video_count"
url = f"https://open.tiktokapis.com/v2/user/info/?fields={fields}"

headers = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
}

req = urllib.request.Request(url, headers=headers, method="GET")
try:
    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode())
        print("USER INFO:")
        print(json.dumps(result, indent=2))
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code}")
    body = e.read().decode()
    print(body)

print("\n" + "="*60 + "\n")

# Test 2: Fetch video list
url2 = f"https://open.tiktokapis.com/v2/video/list/?fields=id,create_time,cover_image_url,share_url,video_description,like_count,comment_count,share_count,view_count"
body_data = json.dumps({"max_count": 5}).encode("utf-8")

req2 = urllib.request.Request(url2, data=body_data, headers={
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json"
}, method="POST")
try:
    with urllib.request.urlopen(req2) as response:
        result = json.loads(response.read().decode())
        print("VIDEO LIST:")
        print(json.dumps(result, indent=2))
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code}")
    body = e.read().decode()
    print(body)
