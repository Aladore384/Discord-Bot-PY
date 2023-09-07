Discord Bot PY

This is a Discord Bot offering basic moderation, role management and fun features.

My first time ever coding anything, and I used AIs to do most of the work. I also talked with various more experienced friends for input. And then I edited stuff based on hunchs, trying to figure it out through trial and error. I also ran main.py through pylint and got a score of 9.40/10.

Anyway, it somehow works as intended!

I am posting it here for two reasons:
1. Allow anyone to use it for their server, using their own token (and thus their own custom name and avatar).
2. Work as a community to improve and/or expand the code.

---

Dependencies

asyncio
aiohttp
Pillow

---

Rich Presence

Rich Presence Activity for Bots has yet to be fully implemented by the Discord API.
For now, things that do work: type, and name.

I already made room for future updates: assets with game icon and icon text.
I also included code for start time: in main.py I hardcoded to "now": datetime.datetime.utcnow().isoformat().
But in the config.json, I made room for a "start" time as well, so you can replace datetime.datetime.utcnow().isoformat() with config['activity']['start'].

---

XXX
