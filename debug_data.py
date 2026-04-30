import json, sys
sys.stdout.reconfigure(encoding='utf-8')

data = json.load(open(r'd:\Codes_Projects\reports\outputs\NASA International Schools\2026-04-01_to_2026-04-30\raw\organic_diagnostics.json', encoding='utf-8'))

# Check what metrics are returned for FB posts
insights = data.get('facebook_post_insights_raw', {})
posts = data.get('facebook_posts_raw', [])

print("=" * 60)
print(f"TOTAL FB POSTS: {len(posts)}")
print("=" * 60)

# Show all available insight keys across all posts
all_keys = set()
for pid, vals in insights.items():
    all_keys.update(vals.keys())
print(f"\nAll insight keys returned: {sorted(all_keys)}")

# Show each post with its raw data
for i, post in enumerate(posts[:5]):
    pid = post.get('id', '')
    msg = (post.get('message') or post.get('story') or '')[:50]
    reactions = post.get('reactions', {}).get('summary', {}).get('total_count', 0)
    comments = post.get('comments', {}).get('summary', {}).get('total_count', 0)
    shares = post.get('shares', {}).get('count', 0)
    
    attachments = post.get('attachments', {}).get('data', [])
    media_type = attachments[0].get('media_type', '?') if attachments else '?'
    
    post_insights = insights.get(pid, {})
    
    print(f"\n--- Post {i+1}: {pid} ---")
    print(f"  msg: {msg}")
    print(f"  media_type: {media_type}")
    print(f"  reactions: {reactions}, comments: {comments}, shares: {shares}")
    print(f"  insights: {post_insights}")
    
print("\n" + "=" * 60)
print("CONFIGURED METRICS TO FETCH:")
print("=" * 60)

# Check what metrics are configured
from social_reports.config import DEFAULT_FACEBOOK_POST_INSIGHT_METRICS
print(f"Default FB post metrics: {DEFAULT_FACEBOOK_POST_INSIGHT_METRICS}")

# Check IG metrics 
ig_insights = data.get('instagram_media_insights_raw', {})
ig_media = data.get('instagram_media_raw', [])

print(f"\n{'='*60}")
print(f"TOTAL IG POSTS: {len(ig_media)}")
print(f"{'='*60}")

all_ig_keys = set()
for mid, vals in ig_insights.items():
    all_ig_keys.update(vals.keys())
print(f"All IG insight keys: {sorted(all_ig_keys)}")

for i, media in enumerate(ig_media[:5]):
    mid = str(media.get('id', ''))
    caption = (media.get('caption') or '')[:50]
    likes = media.get('like_count', 0)
    comments = media.get('comments_count', 0)
    media_type = media.get('media_type', '?')
    product_type = media.get('media_product_type', '?')
    
    media_insights = ig_insights.get(mid, {})
    
    print(f"\n--- IG Media {i+1}: {mid} ---")
    print(f"  caption: {caption}")
    print(f"  type: {media_type} / product: {product_type}")
    print(f"  like_count: {likes}, comments_count: {comments}")
    print(f"  insights: {media_insights}")
