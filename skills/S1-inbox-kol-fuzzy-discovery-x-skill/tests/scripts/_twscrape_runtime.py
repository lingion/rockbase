import asyncio
import json
from contextlib import aclosing
from pathlib import Path

from twscrape import API

DB_PATH = Path(__file__).resolve().parents[1] / "results" / "twscrape_accounts.db"
COOKIES = "auth_token=fab0e14d5c1fc18989cbfa86458013d71f6a1c7f; ct0=b3bfce33dc9b3b30eccec3bff699cb01d9eafa375a0c109ae4733336e8cc7bef79beab56597b1db0c5c100a991793012078ce745c391fd56e08144a0e9241ef38461ae0ee5a6a60696ba53f85a6ffe06"
QUERY = '"OpenClaw" (AI OR "AI agents" OR automation OR "developer tools") lang:en'

async def main():
    api = API(str(DB_PATH))
    await api.pool.add_account("layer1_probe", "x", "<YOUR_ACCOUNT_EMAIL>", "x", cookies=COOKIES)
    user = await api.user_by_login("OpenAI")
    out = {"probe_user": user.username if user else None, "probe_user_id": user.id if user else None}
    async with aclosing(api.search(QUERY, limit=20)) as gen:
        tweets = []
        async for tw in gen:
            tweets.append({
                "id": tw.id,
                "username": getattr(tw.user, "username", None),
                "likes": getattr(tw, "likeCount", None),
                "text": getattr(tw, "rawContent", "")[:280],
            })
            if len(tweets) >= 5:
                break
    out["tweets"] = tweets
    print(json.dumps(out, ensure_ascii=False))

asyncio.run(main())
