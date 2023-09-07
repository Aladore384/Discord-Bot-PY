Discord Bot PY

This is a Discord Bot offering basic moderation, role management and fun features.

My first time ever coding anything, and I used AIs to do most of the work. I also talked with various more experienced friends for input. And then I edited stuff based on hunchs, trying to figure it out through trial and error. I also ran main.py through pylint and got a score of 9.40/10.

Anyway, it somehow works as intended!

I am posting it here for two reasons:
1. Allow anyone to use it for their server, using their own token (and thus their own custom name and avatar).
2. Work as a community to improve and/or expand the code.

---

Dependencies

asyncio, aiohttp, Pillow

---

Rich Presence

Rich Presence Activity for Bots has yet to be fully implemented by the Discord API.
For now, things that do work: type, and name.

I already made room for future updates: assets with game icon and icon text.
I also included code for start time: in main.py I hardcoded to "now": datetime.datetime.utcnow().isoformat().
But in the config.json, I made room for a "start" time as well, so you can replace datetime.datetime.utcnow().isoformat() with config['activity']['start'].

---

User Score and Role

One of the main features is to register a score for each member, and update their roles accordingly. You have to define a passive and an active role for this to work, and then copy their IDs into config.json. While in config.json, you can also change the default options if you will.

- reward is the amount of points you give to a member each time they post a message,
- daily is the amount of points everyone will lose everyday except for those who reached the limit,
- threshold is the amount of points needed to be granted the active role,
- limit is the maximum amount of points a member can have.

---

Joinlogs

I made room for a tracking system to check new arrivals and departures. These will be logged into your "joinlogs" channel (which I recommend making Admin only).

---

- help | Shows this message | help (command)
- invite | Create an invite link | invite

- say | Send a message | say (channel) [message]
- edit | Edit a message | edit edit [message_id] [new_content]
- clear | Clear messages | clear [amount]

- timeout | Timeout a member | timeout OR to [@member] (duration) (reason)
- kick | Kick a member | kick (@member)
- ban | Ban a member | ban (@member)
- unban | Unban a member | unban [member_input]

- autorole | Manage autoroles | autorole [subcommand]
- reactrole | Manage reactroles | reactrole [subcommand]
- score | Manage score | score [subcommand]

- avatar | Display member avatar | avatar (@member)
- duel | Watch a duel between two members | duel [@member1] [@member2]
- love | Check love compatibility two members | love [@member1] [@member2]
- rate | Rating for anything | rate (anything)

---

XXX
