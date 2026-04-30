"""Quick test: try each FB insight metric individually on a single post to see which ones work."""
import asyncio
import os
import sys
sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, r'd:\Codes_Projects\reports')

from social_reports.graph_client import GraphClient, GraphApiError
from social_reports.base_client import PlatformApiError

async def main():
    # Use the actual token from clients.json (the organic access_token)
    access_token = "EAAP9joBN7vIBRcxrttWHfoHKoj1rrQGZBmhMADTZB4av4mjKMtZAnYAR6vbped5GJQHcgX7pWnZA7iOJuCB0jLuFmvtwzL1x1DqSnKu3K15xviw1ZBJFEdoddh4Kn8wDKF8AbmzksowhYi82IeduFcEPzc667v1tpvWpjAT9zn3IJq1YD6MsvZCXq6PmZBh"
    page_id = "359509670571259"
    api_version = "v25.0"
    
    print(f"Token (first 20 chars): {access_token[:20]}...")
    
    # Get page token  
    graph = GraphClient(access_token=access_token, api_version=api_version)
    try:
        result = await graph.get(f"/{page_id}", {"fields": "access_token,name"})
        page_token = result.get("access_token", "")
        page_name = result.get("name", "?")
        print(f"Page name: {page_name}")
        print(f"Page token obtained: {'YES' if page_token else 'NO'}")
    except Exception as e:
        print(f"ERROR getting page token: {e}")
        page_token = access_token
    
    if not page_token:
        print("No page token, using user token as fallback.")
        page_token = access_token
    
    page_graph = GraphClient(access_token=page_token, api_version=api_version)
    
    # Get first few posts
    try:
        posts = await page_graph.get(f"/{page_id}/posts", {
            "fields": "id,message,reactions.summary(true).limit(0),comments.summary(true).limit(0),shares",
            "limit": "3"
        })
        for p in posts.get("data", []):
            print(f"\nPost: {p['id']}")
            print(f"  msg: {(p.get('message') or '')[:50]}")
            print(f"  reactions: {p.get('reactions',{}).get('summary',{}).get('total_count','?')}")
            print(f"  comments: {p.get('comments',{}).get('summary',{}).get('total_count','?')}")
            print(f"  shares: {p.get('shares',{}).get('count','?')}")
    except Exception as e:
        print(f"ERROR fetching posts: {e}")
        return
    
    post_id = posts["data"][0]["id"]
    
    metrics_to_test = [
        "post_impressions",
        "post_impressions_unique",
        "post_media_view",
        "post_clicks",
        "post_video_views",
        "post_video_views_organic",
        "post_engaged_users",
        "post_reactions_by_type_total",
    ]
    
    print(f"\n{'='*60}")
    print(f"Testing metrics on post: {post_id}")
    print("=" * 60)
    
    for metric in metrics_to_test:
        try:
            result = await page_graph.get(f"/{post_id}/insights", {"metric": metric})
            data = result.get("data", [])
            if data:
                val = data[0].get("values", [{}])[0].get("value", "N/A")
                print(f"  ✅ {metric}: {val}")
            else:
                print(f"  ⚠️  {metric}: no data returned")
        except (GraphApiError, PlatformApiError) as e:
            err_str = str(e)
            if "not a valid" in err_str.lower() or "invalid" in err_str.lower():
                print(f"  ❌ {metric}: DEPRECATED/INVALID")
            else:
                print(f"  ❌ {metric}: {e}")
        except Exception as e:
            print(f"  ❌ {metric}: {type(e).__name__}: {e}")

asyncio.run(main())
