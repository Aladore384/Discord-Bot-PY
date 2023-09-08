"""Discord Bot

This module implements a Discord bot for your community. It provides various features, including
moderation commands, role management, and fun utilities for your server."""

# -------------------------------------------------------------------------------------------------
# Import statements
# -------------------------------------------------------------------------------------------------

# Standard Library Imports
import json
import datetime
import time
import re
import random
from io import BytesIO
import smtplib
from email.message import EmailMessage
import asyncio

# Third-Party Library Imports
import aiohttp
from PIL import Image, ImageFont, ImageDraw

# Discord Library Imports
import discord
from discord.ext import commands

# -------------------------------------------------------------------------------------------------
# Read configuration from config.json
# -------------------------------------------------------------------------------------------------

def load_config():

    """Load the configuration from config.json"""

    with open('config.json', 'r', encoding='utf-8') as configuration:
        return json.load(configuration)

def save_config(config):

    """Save the configuration to config.json"""

    with open('config.json', 'w', encoding='utf-8') as configuration:
        json.dump(config, configuration, indent=4)

config = load_config()

# -------------------------------------------------------------------------------------------------
# Read database from data.json
# -------------------------------------------------------------------------------------------------

def load_data():

    """Load the database from data.json"""

    with open('data.json', 'r', encoding='utf-8') as database:
        return json.load(database)

def save_data(data):

    """Save the database to data.json"""

    with open('data.json', 'w', encoding='utf-8') as database:
        json.dump(data, database, indent=4)

data = load_data()

# -------------------------------------------------------------------------------------------------
# Extract configuration values
# -------------------------------------------------------------------------------------------------

TOKEN = config["bot"]["token"]
PREFIX = config["bot"]["prefix"]

# -------------------------------------------------------------------------------------------------
# Initialize the bot
# -------------------------------------------------------------------------------------------------

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=(PREFIX), intents=intents)

# -------------------------------------------------------------------------------------------------
# Event: Bot ready
# -------------------------------------------------------------------------------------------------

@bot.event
async def on_ready():

    """Actions on bot ready"""

    print(f"Bot connected: {bot.user}")

    activity_type = config['activity']['type']
    activity_name = config['activity']['name']
    activity_start = datetime.datetime.utcnow().isoformat()

    assets = {}
    assets['large_image'] = config['activity']['assets']['large_image']
    assets['large_text'] = config['activity']['assets']['large_text']

    activity = discord.Activity(
        type=discord.ActivityType[activity_type],
        name=activity_name,
        start=activity_start,
        assets=assets
    )

    await bot.change_presence(activity=activity)

    bot.loop.create_task(daily_decrease())

# -------------------------------------------------------------------------------------------------
# Handler: Errors
# -------------------------------------------------------------------------------------------------

@bot.event
async def on_command_error(ctx, error):

    """Handling errors"""

    if isinstance(error, commands.CommandNotFound):
        await ctx.message.delete()
        return

    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.message.delete()
        timeout_message = await ctx.send("Missing required arguments.")
        await asyncio.sleep(5)
        await timeout_message.delete()
        return

    if isinstance(error, commands.BadArgument):
        await ctx.message.delete()
        timeout_message = await ctx.send("One or more arguments are invalid.")
        return

    if isinstance(error, commands.CommandInvokeError):
        await ctx.message.delete()
        timeout_message = await ctx.send("Command aborted.")
        await asyncio.sleep(5)
        await timeout_message.delete()
        return

    await ctx.message.delete()
    error_message = f"Error: {error}"
    timeout_message = await ctx.send(error_message)
    await asyncio.sleep(5)
    await timeout_message.delete()
    return

# -------------------------------------------------------------------------------------------------
# Handler: Role update
# -------------------------------------------------------------------------------------------------

async def role_update():

    """Actions on role update"""

    server = bot.get_guild(config["bot"]["server"])
    active_role = server.get_role(config["score"]["active_role"])
    passive_role = server.get_role(config["score"]["passive_role"])

    for user_score in data["score"]:
        user = server.get_member(user_score["user"])

        if user:
            user_score["points"] = min(
                user_score["points"], config["score"]["limit"]
            )

            if user_score["points"] >= config["score"]["threshold"]:
                if active_role not in user.roles:
                    await user.add_roles(active_role)
                    await user.remove_roles(passive_role)
            else:
                if passive_role not in user.roles:
                    await user.remove_roles(active_role)
                    await user.add_roles(passive_role)

# -------------------------------------------------------------------------------------------------
# Handler: Daily score decrease
# -------------------------------------------------------------------------------------------------

async def daily_decrease():

    """Daily score decrease"""

    await bot.wait_until_ready()
    while not bot.is_closed():

        now = datetime.datetime.now()

        print(f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S')}")

        last_daily_value = data.get("last_daily", None)

        if last_daily_value != now.date().strftime('%Y-%m-%d'):
            print("Starting daily task...")

            limit = config["score"]["limit"]

            for user_score in data["score"]:
                if "user" in user_score and "points" in user_score:
                    points = user_score["points"]
                    if points >= limit:
                        continue
                    new_points = max(0, points - config["score"]["daily"])
                    user_score["points"] = new_points

            data["last_daily"] = now.date().strftime('%Y-%m-%d')
            save_data(data)

        await role_update()
        print("Daily decrease completed.")

        await asyncio.sleep(21600)

# -------------------------------------------------------------------------------------------------
# Event: Membership
# -------------------------------------------------------------------------------------------------

# Member Joined -----------------------------------------------------------------------------------

@bot.event
async def on_member_join(member):

    """Actions on member join"""

    autoroles = data.get('roles', {}).get('autoroles', [])

    for role_id in autoroles:
        role = member.guild.get_role(role_id)
        if role:
            await member.add_roles(role)


    joinlogs_channel_id = config['channels']['joinlogs']
    joinlogs_channel = bot.get_channel(joinlogs_channel_id)

    if joinlogs_channel:
        join_message = f"{member.mention} joined."
        await joinlogs_channel.send(join_message)

# Member Remove -----------------------------------------------------------------------------------

@bot.event
async def on_member_remove(member):

    """Actions on member remove"""

    joinlogs_channel_id = config['channels']['joinlogs']
    joinlogs_channel = bot.get_channel(joinlogs_channel_id)

    if joinlogs_channel:
        leave_message = None

        async for entry in member.guild.audit_logs(limit=1):
            if entry.target == member:
                if entry.action == discord.AuditLogAction.kick:
                    leave_message = f"{member.mention} was kicked."
                elif entry.action == discord.AuditLogAction.ban:
                    leave_message = f"{member.mention} was banned."
                break
        if not leave_message:
            leave_message = f"{member.mention} left."

        await joinlogs_channel.send(leave_message)

# Member Unbanned ---------------------------------------------------------------------------------

@bot.event
async def on_member_unban(guild, user):

    """Actions on member unbanned"""

    joinlogs_channel_id = config['channels']['joinlogs']
    joinlogs_channel = bot.get_channel(joinlogs_channel_id)

    if joinlogs_channel:
        unban_message = f"{user.mention} unbanned."
        await joinlogs_channel.send(unban_message)

# -------------------------------------------------------------------------------------------------
# Event: Message
# -------------------------------------------------------------------------------------------------

# Incoming messages -------------------------------------------------------------------------------

@bot.event
async def on_message(message):

    """Actions on new messages"""

    user_entry = next(
        (entry for entry in data["score"] if entry["user"] == message.author.id),
        None
    )

    if user_entry is None:
        data["score"].append({"user": message.author.id, "points": config["score"]["reward"]})
    else:
        user_entry["points"] += config["score"]["reward"]
        if user_entry["points"] > config["score"]["limit"]:
            user_entry["points"] = config["score"]["limit"]

    save_data(data)

    await role_update()

    if message.author == bot.user:
        return

    if message.content.startswith(PREFIX):
        await bot.process_commands(message)

# Deleted messages --------------------------------------------------------------------------------

@bot.event
async def on_raw_message_delete(payload):

    """Actions on individual message deletion"""

    message_id = payload.message_id
    reactmessages = data['roles']['reactmessages']

    index_to_remove = None

    for index, reactmessage in enumerate(reactmessages):
        if reactmessage['messageID'] == message_id:
            index_to_remove = index
            break

    if index_to_remove is not None:
        reactmessages.pop(index_to_remove)
        save_data(data)

# Purged messages  --------------------------------------------------------------------------------

@bot.event
async def on_raw_bulk_message_delete(payload):

    """Actions on masse messages deletion"""

    deleted_message_ids = payload.message_ids
    reactmessages = data['roles']['reactmessages']

    messages_to_remove = []

    for message_id in deleted_message_ids:
        for reactmessage in reactmessages:
            if message_id == reactmessage['messageID']:
                messages_to_remove.append(reactmessage)

    for reactmessage in messages_to_remove:
        data['roles']['reactmessages'].remove(reactmessage)

    save_data(data)

# -------------------------------------------------------------------------------------------------
# Event: Reaction
# -------------------------------------------------------------------------------------------------

# Raw reaction add --------------------------------------------------------------------------------

@bot.event
async def on_raw_reaction_add(payload):

    """Actions on reaction added"""

    if payload.user_id == bot.user.id:
        return

    guild = bot.get_guild(payload.guild_id)
    channel = bot.get_channel(payload.channel_id)
    member = guild.get_member(payload.user_id)
    message = await channel.fetch_message(payload.message_id)

    for reactmessage in data['roles']['reactmessages']:
        if reactmessage['messageID'] == payload.message_id and reactmessage['type'] == "mono":
            for reaction in message.reactions:
                for reactlink in data['roles']['reactlinks']:
                    if reactlink['reactemoji'] == str(reaction.emoji):
                        if guild.get_role(reactlink['reactrole']) in member.roles:
                            role_id = reactlink['reactrole']
                            role = guild.get_role(role_id)
                            if role:
                                await message.remove_reaction(payload.emoji, member)
                                return

    for reactmessage in data['roles']['reactmessages']:
        if reactmessage['messageID'] == payload.message_id:
            for reactlink in data['roles']['reactlinks']:
                if reactlink['reactemoji'] == str(payload.emoji):
                    role_id = reactlink['reactrole']
                    role = guild.get_role(role_id)
                    if role:
                        await member.add_roles(role)

# Raw reaction remove -----------------------------------------------------------------------------

@bot.event
async def on_raw_reaction_remove(payload):

    """Actions on reaction deleted"""

    if payload.user_id == bot.user.id:
        return

    guild = bot.get_guild(payload.guild_id)
    channel = bot.get_channel(payload.channel_id)
    member = guild.get_member(payload.user_id)
    message = await channel.fetch_message(payload.message_id)

    for reactmessage in data['roles']['reactmessages']:
        if reactmessage['messageID'] == payload.message_id:
            for reactlink in data['roles']['reactlinks']:
                if reactlink['reactemoji'] == str(payload.emoji):
                    role_id = reactlink['reactrole']
                    role = guild.get_role(role_id)
                    if role:
                        await member.remove_roles(role)

# -------------------------------------------------------------------------------------------------
# Command: Help
# -------------------------------------------------------------------------------------------------

class CustomHelpCommand(commands.MinimalHelpCommand):

    """Help command customization"""

# -------------------------------------------------------------------------------------------------

    async def send_bot_help(self, mapping):

        custom_command_order = [
            "help", "invite", "say", "edit", "clear", "timeout", "kick", "ban", "unban",
            "autorole", "reactrole", "score", "verify", "code", "avatar", "duel", "love", "rate"
        ]

        command_list = []
        for command_name in custom_command_order:
            if (command := self.context.bot.get_command(command_name)):
                try:
                    can_run = await command.can_run(self.context)
                except commands.CommandError:
                    can_run = False

                if can_run:
                    signature = f"{PREFIX}{command_name} {command.signature}"
                    if isinstance(command, commands.Group) and command.commands:
                        signature += "[subcommands]"
                    command_list.append(
                        f"**{(PREFIX)}{command_name}** | *{command.help}* | ``{signature}``"
                    )

        if command_list:
            command_list_text = "\n".join(command_list)
            embed = discord.Embed(
                description=f"**Prefix: {(PREFIX)}**\n\nList of commands:\n\n"
                            f"{command_list_text}\n\n End of list"
            )
            await self.get_destination().send(embed=embed)

# -------------------------------------------------------------------------------------------------

    async def send_command_help(self, command):

        try:
            can_run = await command.can_run(self.context)
        except commands.CommandError:
            can_run = False

        if can_run:
            command_help_embed = discord.Embed(
                description=(
                    f"**{PREFIX}{command.qualified_name}** | "
                    f"*{command.help}* | "
                    f"``{PREFIX}{command.qualified_name} {command.signature}``\n"
                )
            )
            await self.get_destination().send(embed=command_help_embed)
        else:
            missing_permission_embed = discord.Embed(
                description=f"Missing permission for: **{PREFIX}{command.qualified_name}**"
            )
            await self.get_destination().send(embed=missing_permission_embed)

# -------------------------------------------------------------------------------------------------

    async def send_group_help(self, group):

        subcommand_list = []

        for command in group.commands:
            try:
                can_run = await command.can_run(self.context)
            except commands.CommandError:
                can_run = False

            if can_run:
                signature = f"{PREFIX}{group.qualified_name} {command.name} {command.signature}"
                subcommand_list.append({
                    "name": command.name,
                    "help": command.help,
                    "signature": signature
                })

        subcommand_order = {
            "autorole": ["add", "remove", "list", "clear"],
            "reactrole": ["link", "unlink", "list", "clear", "mono", "multi"],
            "score": ["view", "set"]
        }

        desired_order = subcommand_order.get(group.qualified_name, [])

        sorted_subcommands = sorted(
            subcommand_list,
            key=lambda x: (
                desired_order.index(x["name"])
                if x["name"] in desired_order
                else len(desired_order)
            )
        )

        subcommand_list_text = "\n".join([
            f"**{(PREFIX)}{group.qualified_name} {subcommand['name']}** | "
            f"*{subcommand['help']}* | ``{subcommand['signature']}``"
            for subcommand in sorted_subcommands
        ])

        if subcommand_list_text:
            embed = discord.Embed(
                description=f"**Prefix: {(PREFIX)}**\n\n"
                            f"List of subcommands for {group.qualified_name}:\n\n"
                            f"*{group.help}*\n\n{subcommand_list_text}\n\nEnd of list"
            )
            await self.get_destination().send(embed=embed)

bot.help_command = CustomHelpCommand()

# -------------------------------------------------------------------------------------------------
# Command: Invite
# -------------------------------------------------------------------------------------------------

@bot.command()
@commands.has_permissions(manage_messages=True)
async def invite(ctx):

    """Create an invite link"""

    await ctx.message.delete()

    invite_channel_id = int(config['channels']['invite'])
    invite_channel = bot.get_channel(invite_channel_id)
    invite = await invite_channel.create_invite()

    await ctx.send(invite)

# -------------------------------------------------------------------------------------------------
# Command: Say
# -------------------------------------------------------------------------------------------------

@bot.command()
@commands.has_permissions(manage_messages=True)
async def say(ctx, channel_or_message: commands.Greedy[commands.TextChannelConverter], *, message):

    """Send a message"""

    await ctx.message.delete()

    if not channel_or_message:
        target_channel = ctx.channel
    else:
        target_channel = channel_or_message[0]

    await target_channel.send(message)

# -------------------------------------------------------------------------------------------------
# Command: Edit
# -------------------------------------------------------------------------------------------------

@bot.command()
@commands.has_permissions(manage_messages=True)
async def edit(ctx, message_id: int, *, new_content):

    """Edit a message"""

    await ctx.message.delete()

    for channel in ctx.guild.text_channels:
        try:
            message = await channel.fetch_message(message_id)
            await message.edit(content=new_content)
            return
        except discord.NotFound:
            pass

    await ctx.send("Message not found in any channel.")

# -------------------------------------------------------------------------------------------------
# Command: Clear
# -------------------------------------------------------------------------------------------------

@bot.command()
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int):

    """Clear messages"""

    await ctx.message.delete()

    if amount <= 0:
        await ctx.send("Please provide a valid number of messages to clear.")
        return

    deleted = await ctx.channel.purge(limit=amount)
    timeout_message = await ctx.send(f"Cleared {len(deleted)} messages.")
    await asyncio.sleep(5)
    await timeout_message.delete()

# -------------------------------------------------------------------------------------------------
# Command: Avatar
# -------------------------------------------------------------------------------------------------

@bot.command()
async def avatar(ctx, user: discord.Member=None):

    """Display member avatar"""

    if user is None:
        user = ctx.author

    if user.guild_avatar:
        avatar_url = user.guild_avatar.url
        await ctx.send(avatar_url)

    elif user.avatar:
        avatar_url = user.avatar.url
        await ctx.send(avatar_url)

    else:
        await ctx.send("This user does not have an avatar set!")

# -------------------------------------------------------------------------------------------------
# Command: Timeout
# -------------------------------------------------------------------------------------------------

@bot.command(aliases=['to'])
@commands.has_permissions(moderate_members=True)
async def timeout(ctx, member: discord.Member, duration: str = '60m', *, reason: str = None):

    """Timeout a user"""

    units = {'d': 86400, 'h': 3600, 'm': 60, 's': 1}

    default_unit = 'm'

    if not duration:
        duration = '1' + default_unit
    elif duration.isdigit():
        duration += default_unit

    numeric_duration = int(duration[:-1])
    unit = duration[-1]

    if unit in units:
        timeout_seconds = numeric_duration * units[unit]
    else:
        await ctx.send(
            "Invalid duration unit. Use 'd' (days), 'h' (hours), "
            "'m' (minutes), or 's' (seconds)."
        )
        return

    combined_duration = re.findall(r'(\d+[dhms])', duration)
    total_seconds = 0
    for part in combined_duration:
        unit = part[-1]
        value = int(part[:-1])
        total_seconds += value * units[unit]

    max_duration = datetime.timedelta(days=7)

    if datetime.timedelta(seconds=total_seconds) > max_duration:
        await ctx.send("Duration too long!")
        return

    timeout = datetime.timedelta(seconds=total_seconds)

    def seconds_to_time(seconds):
        days, seconds = divmod(seconds, 86400)
        hours, seconds = divmod(seconds, 3600)
        minutes, seconds = divmod(seconds, 60)
        return days, hours, minutes, seconds

    days, hours, minutes, seconds = seconds_to_time(total_seconds)
    duration_str = f"{days:02d}d {hours:02d}h {minutes:02d}m {seconds:02d}s"

    try:
        if reason:
            await member.timeout(timeout, reason=reason)
        else:
            await member.timeout(timeout)

        if reason:
            message = (
                f"{member.mention} has been timed out for {duration_str}.\n"
                f"Reason: {reason}"
            )
        else:
            message = f"{member.mention} has been timed out for {duration_str}"

        await ctx.send(message)

    except discord.Forbidden:
        await ctx.send(f"Cannot time out {member.mention}.")

    except discord.HTTPException:
        await ctx.send(f"Error trying to time out {member.mention}.")

# -------------------------------------------------------------------------------------------------
# Command: Kick
# -------------------------------------------------------------------------------------------------

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member):

    """Kick a member"""

    try:
        await member.kick()
        await ctx.send(f"{member.mention} has been kicked.")

    except discord.Forbidden:
        await ctx.send(f"Cannot kick {member.mention}.")

    except discord.HTTPException:
        await ctx.send(f"Error trying to kick {member.mention}.")

# -------------------------------------------------------------------------------------------------
# Command: Ban
# -------------------------------------------------------------------------------------------------

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member):

    """Ban a member"""

    try:
        await member.ban()
        await ctx.send(f"{member.mention} has been banned.")

    except discord.Forbidden:
        await ctx.send(f"Cannot ban {member.mention}.")

    except discord.HTTPException:
        await ctx.send(f"Error trying to ban {member.mention}.")

# -------------------------------------------------------------------------------------------------
# Command: Unban
# -------------------------------------------------------------------------------------------------

@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, member_input):

    """Unban a member"""

    try:
        member = await commands.MemberConverter().convert(ctx, member_input)
    except commands.MemberNotFound:
        member_id = member_input
    else:
        member_id = str(member.id)

    member_id = member_id.replace('<@','').replace('>','')

    banned_users = []
    async for entry in ctx.guild.bans():
        banned_users.append(entry.user.id)

    if int(member_id) not in banned_users:
        await ctx.send("User not banned.")
        return

    try:
        banned_member = await bot.fetch_user(int(member_id))
    except discord.NotFound:
        await ctx.send("User not found.")
        return

    try:
        await ctx.guild.unban(banned_member)
        await ctx.send(f"{banned_member.mention} has been unbanned.")

    except discord.Forbidden:
        await ctx.send(f"Cannot unban {banned_member.mention}.")

    except discord.HTTPException:
        await ctx.send(f"Error trying to unban {banned_member.mention}.")

# -------------------------------------------------------------------------------------------------
# Command: Autorole
# -------------------------------------------------------------------------------------------------

@bot.group()
@commands.has_permissions(manage_roles=True)
async def autorole(ctx):

    """Manage autoroles"""

    if ctx.invoked_subcommand is None:
        await ctx.send("Invalid subcommand. Use `add`, `remove`, `list`, or `clear`.")

# Subcommand: add ---------------------------------------------------------------------------------

@autorole.command()
async def add(ctx, *roles: discord.Role):

    """Add an autorole"""

    autoroles = data['roles']['autoroles']

    for role in roles:
        if role.id in autoroles:
            await ctx.send(f"Role {role.mention} is already in autoroles.")
        else:
            autoroles.append(role.id)
            save_data(data)
            await ctx.send(f"Role {role.mention} added to autoroles.")

# Subcommand: remove ------------------------------------------------------------------------------

@autorole.command()
async def remove(ctx, *roles: discord.Role):

    """Remove an autorole"""

    autoroles = data['roles']['autoroles']

    for role in roles:
        if role.id in autoroles:
            autoroles.remove(role.id)
            save_data(data)
            await ctx.send(f"Role {role.mention} removed from autoroles.")
        else:
            await ctx.send(f"Role {role.mention} not found in autoroles.")

# Subcommand: list --------------------------------------------------------------------------------

@autorole.command()
async def list(ctx):

    """List autoroles"""

    autoroles = data['roles']['autoroles']
    autorole_list = [f'<@&{role_id}>' for role_id in autoroles]

    if autorole_list:
        autorole_list_text = '\n'.join(autorole_list)
        message = 'Autoroles:\n\n' + autorole_list_text + '\n\nEnd of list'
        await ctx.send(message)
    else:
        await ctx.send("No autoroles set up.")

# Subcommand: clear -------------------------------------------------------------------------------

@autorole.command()
async def clear(ctx):

    """Clear autoroles"""

    await ctx.message.delete()

    data['roles']['autoroles'] = []

    save_data(data)

    timeout_message = await ctx.send("Autoroles cleared.")
    await asyncio.sleep(5)
    await timeout_message.delete()

# -------------------------------------------------------------------------------------------------
# Command: Reactrole
# -------------------------------------------------------------------------------------------------

@bot.group()
@commands.has_permissions(manage_roles=True)
async def reactrole(ctx):

    """Manage reactroles"""

    if ctx.invoked_subcommand is None:
        await ctx.send("Invalid subcommand passed.")

# Subcommand: link --------------------------------------------------------------------------------

@reactrole.command()
async def link(ctx, role: discord.Role, emoji: str):

    """Link a role to an emoji"""

    reactlinks = data['roles']['reactlinks']

    for reactlink in reactlinks:
        if reactlink['reactrole'] == role.id or reactlink['reactemoji'] == emoji:
            await ctx.send("Role or emoji already exists in data.")
            return

    reactlinks.append({
        'reactrole': role.id,
        'reactemoji': emoji
    })

    save_data(data)

    await ctx.send(f"Reactlink added: | {emoji} | {role.mention}.")

# Subcommand: unlink ------------------------------------------------------------------------------

@reactrole.command()
async def unlink(ctx, role: discord.Role):

    """Unlink a role from an emoji"""

    reactlinks = data['roles']['reactlinks']

    role_exists = any(reactlink['reactrole'] == role.id for reactlink in reactlinks)
    if not role_exists:
        await ctx.send("Role does not exist in reactlinks.")
        return

    data['roles']['reactlinks'] = [
        reactlink for reactlink in reactlinks if reactlink['reactrole'] != role.id
    ]

    save_data(data)

    await ctx.send(f"Reactlink removed for role: {role.mention}.")

# Subcommand: list --------------------------------------------------------------------------------

@reactrole.command()
async def list(ctx):

    """List roles linked to an emoji"""

    reactlinks = data['roles']['reactlinks']

    if not reactlinks:
        await ctx.send("No reactlinks set up.")
        return

    reactrole_list = "\n".join([
        f"| {reactlink['reactemoji']} | {ctx.guild.get_role(reactlink['reactrole']).mention}"
        for reactlink in reactlinks
    ])

    await ctx.send("Reactlinks list:\n\n" + reactrole_list + "\n\nEnd of list")

# Subcommand: clear -------------------------------------------------------------------------------

@reactrole.command()
async def clear(ctx):

    """Clear roles linked to an emoji"""

    await ctx.message.delete()

    data['roles']['reactlinks'] = []

    save_data(data)

    timeout_message = await ctx.send("Reactlinks cleared.")
    await asyncio.sleep(5)
    await timeout_message.delete()

# Subcommand: mono --------------------------------------------------------------------------------

@reactrole.command()
async def mono(ctx, *roles: discord.Role):

    """Send a reactrole message (mono)"""

    await ctx.message.delete()
    await _handle_reactrole(ctx, roles, False)

# Subcommand: multi -------------------------------------------------------------------------------

@reactrole.command()
async def multi(ctx, *roles: discord.Role):

    """Send a reactrole message (multi)"""

    await ctx.message.delete()
    await _handle_reactrole(ctx, roles, True)

# Handler: Reactrole logic ------------------------------------------------------------------------
async def _handle_reactrole(ctx, roles, allow_multi):

    reactlinks = data['roles']['reactlinks']

    if not roles:
        timeout_message = await ctx.send("Please provide at least one role.")
        await asyncio.sleep(5)
        await timeout_message.delete()
        return

    reactlinks = data['roles']['reactlinks']

    valid_roles = {reactlink['reactrole']: reactlink['reactemoji'] for reactlink in reactlinks}

    invalid_roles = [role.id for role in roles if role.id not in valid_roles]

    if invalid_roles:
        await ctx.send("One or more provided roles are not eligible for reactlinks.")
        return

    message_type = "multi" if allow_multi else "mono"

    ordered_roles = [valid_roles[role.id] for role in roles]

    message_content = "React to this message to choose your role:\n\n"
    message_content += "\n".join([
        f"| {emoji} | {ctx.guild.get_role(role_id).mention}"
        for emoji, role_id in zip(ordered_roles, [role.id for role in roles])
    ])

    if allow_multi:
        message_content += "\n\nCan select **multiple** roles."
    else:
        message_content += "\n\nCan select **only one** role."

    message = await ctx.send(message_content)

    for emoji in ordered_roles:
        await message.add_reaction(emoji)

    data['roles']['reactmessages'].append({
        "messageID": message.id,
        "type": message_type
    })
    save_data(data)

# -------------------------------------------------------------------------------------------------
# Command: Score
# -------------------------------------------------------------------------------------------------

@bot.group(name='score')
async def score_group(ctx):

    """Manage score"""

    if ctx.invoked_subcommand is None:
        await ctx.send('Invalid score command. Use `score set` or `score view`.')

# Subcommand: set ---------------------------------------------------------------------------------

@score_group.command(name='set')
@commands.has_permissions(moderate_members=True)
async def set_score(ctx, member: discord.Member, points: int):

    """Set member score"""

    if points < 0:
        await ctx.send("Points must be a positive value.")
        return

    limit = config["score"]["limit"]

    if points > limit:
        await ctx.send(f"Points cannot exceed {limit}.")
        return

    user_scores = {entry["user"]: entry["points"] for entry in data["score"]}
    user_id = member.id
    user_scores[user_id] = points
    data["score"] = [{"user": user, "points": score} for user, score in user_scores.items()]

    save_data(data)

    await ctx.send(f"{member.mention} now has {points} points.")

    await role_update()

# Subcommand: view --------------------------------------------------------------------------------

@score_group.command(name='view')
async def view_score(ctx, member: discord.Member):

    """View member score"""

    user_scores = {entry["user"]: entry["points"] for entry in data["score"]}
    user_id = member.id
    points = user_scores.get(user_id, 0)

    await ctx.send(f"{member.mention} has {points} points.")

# -------------------------------------------------------------------------------------------------
# Command: Duel
# -------------------------------------------------------------------------------------------------

@bot.command()
async def duel(ctx, attacker: discord.Member, defender: discord.Member):

    """Watch a duel between two members"""

    async with aiohttp.ClientSession() as session:

        background = Image.open("duel_background.jpg")
        avatars = []

        mask_size = (256, 256)

        circular_mask = Image.new("L", mask_size, 0)
        draw = ImageDraw.Draw(circular_mask)
        draw.ellipse((0, 0, mask_size[0], mask_size[1]), fill=255)

        for user in [attacker, defender]:
            avatar_url = user.guild_avatar.url if user.guild_avatar else user.avatar.url

            async with session.get(avatar_url) as response:
                avatar_data = await response.read()
                avatar = Image.open(BytesIO(avatar_data))
                avatar = avatar.resize(mask_size)

                avatar = avatar.convert("RGBA")
                avatar.putalpha(circular_mask)

                avatars.append(avatar)

        result_image = background.copy()

        result_image.paste(avatars[0], (0, 128), avatars[0])
        result_image.paste(avatars[1], (768, 128), avatars[1])

        overlay = Image.new("RGBA", result_image.size, (0, 0, 0, 64))
        result_image = Image.alpha_composite(result_image.convert("RGBA"), overlay)

        font_path = "ariblk.ttf"
        default_font_size = 48

        duel_results = []
        attacker_wins = 0
        defender_wins = 0

        while attacker_wins < 3 and defender_wins < 3:

            round_winner = random.choice([0, 1])
            duel_results.append(round_winner)

            if round_winner == 0:
                attacker_wins += 1
                winner = (f"{attacker.display_name}", 256, "red", default_font_size)
            else:
                defender_wins += 1
                winner = (f"{defender.display_name}", 256, "blue", default_font_size)

        text_image = Image.new("RGBA", (result_image.width, result_image.height), (0, 0, 0, 0))
        text_draw = ImageDraw.Draw(text_image)

        texts = [
            (f"{attacker_wins}", 95, 0, "red", 84),
            (f"{defender_wins}", 865, 0, "blue", 84),
            ("Winner: ", None, 200, "white", default_font_size),
            (winner[0], None, 256, winner[2], default_font_size)
        ]

        for text, x_pos, y_pos, color, size in texts:
            font = ImageFont.truetype(font_path, size)

            if x_pos is None:
                text_box = font.getbbox(text)
                text_width = text_box[2] - text_box[0]
                x_pos = (result_image.width - text_width) / 2

            text_box = font.getbbox(text)
            text_width = text_box[2] - text_box[0]
            text_draw.text((x_pos, y_pos), text, font=font, fill=color)

        result_image = Image.alpha_composite(result_image.convert("RGBA"), text_image)

        result_image.save("duel_result.png")

        await ctx.send(file=discord.File("duel_result.png"))

# -------------------------------------------------------------------------------------------------
# Command: Love
# -------------------------------------------------------------------------------------------------

@bot.command()
async def love(ctx, member_1: discord.Member, member_2: discord.Member):

    """Check love compatibility two members"""

    async with aiohttp.ClientSession() as session:

        background = Image.open("love_background.jpg")
        avatars = []

        mask_size = (256, 256)

        circular_mask = Image.new("L", mask_size, 0)
        draw = ImageDraw.Draw(circular_mask)
        draw.ellipse((0, 0, mask_size[0], mask_size[1]), fill=255)

        for user in [member_1, member_2]:
            avatar_url = user.guild_avatar.url if user.guild_avatar else user.avatar.url

            async with session.get(avatar_url) as response:
                avatar_data = await response.read()
                avatar = Image.open(BytesIO(avatar_data))
                avatar = avatar.resize(mask_size)

                avatar = avatar.convert("RGBA")
                avatar.putalpha(circular_mask)

                avatars.append(avatar)

        result_image = background.copy()

        result_image.paste(avatars[0], (0, 128), avatars[0])
        result_image.paste(avatars[1], (768, 128), avatars[1])

        overlay = Image.new("RGBA", result_image.size, (0, 0, 0, 64))
        result_image = Image.alpha_composite(result_image.convert("RGBA"), overlay)

        font_path = "ariblk.ttf"
        default_font_size = 32

        love_points = random.randint(1, 10)

        love_meter = "♥" * love_points

        love_spot = random.randint(0, 8)
        love_spot_text = config["love"]["love_spot_text"][love_spot]

        love_compatibility = random.randint(0, 8)
        love_compatibility_text_1 = config["love"]["love_compatibility_text_1"][love_compatibility]
        love_compatibility_text_2 = config["love"]["love_compatibility_text_2"][love_compatibility]

        text_image = Image.new("RGBA", (result_image.width, result_image.height), (0, 0, 0, 0))
        text_draw = ImageDraw.Draw(text_image)

        texts = [
            ("Love Meter", 50, "deeppink", default_font_size),
            (love_meter, 50, "hotpink", 84),
            ("Love Spot", 200, "deeppink", default_font_size),
            (love_spot_text, 230, "white", default_font_size),
            ("Love Compatibility", 320, "deeppink", default_font_size),
            (love_compatibility_text_1, 350, "white", default_font_size),
            (love_compatibility_text_2, 380, "white", default_font_size)
        ]

        for text, y_pos, color, size in texts:
            font = ImageFont.truetype(font_path, size)

            text_box = font.getbbox(text)
            text_width = text_box[2] - text_box[0]

            x_pos = (result_image.width - text_width) / 2

            text_draw.text((x_pos, y_pos), text, font=font, fill=color)

        result_image.paste(text_image, (0, 20), text_image)

        result_image.save("love_result.png")

        await ctx.send(file=discord.File("love_result.png"))

# -------------------------------------------------------------------------------------------------
# Command: Rate
# -------------------------------------------------------------------------------------------------

@bot.command()
async def rate(ctx, *, thing_to_rate):

    """Rating for anything"""

    rating = random.randint(1, 10)
    meter = "⭐" * rating

    await ctx.send(f"*{thing_to_rate}*: **{rating}**/10\n\n{meter}")

# ----------------------------------------------------------------------------
# Command: Verify
# ----------------------------------------------------------------------------

@bot.command()
async def verify(ctx, email: str):

    """Get verification code"""

    await ctx.message.delete()

    try:
        verified_role = ctx.guild.get_role(config['email']['VERIFIED_ROLE_ID'])
        if verified_role in ctx.author.roles:
            timeout_message = await ctx.send('You are already verified.')
            await asyncio.sleep(5)
            await timeout_message.delete()
            return

        if email.split('@')[-1] not in config['email']['ALLOWED_DOMAIN']:
            timeout_message = await ctx.send('Domain name is not allowed!')
            await asyncio.sleep(5)
            await timeout_message.delete()
            return

        code = str(random.randint(0, 999999)).zfill(6)
        user_id = str(ctx.author.id)
        
        codes = data.get("codes", {})
        codes[user_id] = {
            'code': code,
            'expiration': time.time() + 1800
        }
        data["codes"] = codes
        
        save_data(data)

        msg = EmailMessage()
        msg['Subject'] = f'Discord Verification Code: {code}'
        sender_name = config['email']['EMAIL_NAME']
        sender_email = config['email']['EMAIL_ADDRESS']
        msg['From'] = f'{sender_name} <{sender_email}>'
        msg['To'] = email

        msg.set_content(f'''
        Hello,<br>
        <br>
        Your Verification Code is <b>{code}</b>.<br>
        <br>
        Use the &lt;!code&gt; command with this code, and your role shall be updated.<br>
        <br>
        <code>&lt;!code <b>{code}</b>&gt;</code><br>
        <br>
        This code is active for the next 30 minutes.<br>
        <br>
        Remember, this is a noreply address.<br>
        <br>
        Welcome aboard!<br>
        <br>
        Best regards,<br>
        {sender_name}<br>
        ''', subtype='html')

        with smtplib.SMTP(config['email']['SMTP_SERVER'], config['email']['SMTP_PORT']) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(config['email']['EMAIL_ADDRESS'], config['email']['EMAIL_PASSWORD'])
            smtp.send_message(msg)

        timeout_message = await ctx.send('Verification code sent!')
        await asyncio.sleep(5)
        await timeout_message.delete()

        await schedule_cleanup(user_id, code)

    except Exception as error:
        print(f"An error occurred: {error}")

async def schedule_cleanup(user_id, code):

    """Cleanup codes"""

    try:
        await asyncio.sleep(1800)
        codes = data.get("codes", {})
        if user_id in codes and codes[user_id]['code'] == code:
            codes.pop(user_id)
            data["codes"] = codes
            save_data(data)
    except Exception as error:
        print(f"An error occurred during cleanup: {error}")

# ----------------------------------------------------------------------------
# Command: Code
# ----------------------------------------------------------------------------

@bot.command()
async def code(ctx, user_code: str):

    """Input verification code"""

    await ctx.message.delete()

    try:
        member = ctx.author
        unverified_role = ctx.guild.get_role(config['email']['UNVERIFIED_ROLE_ID'])
        verified_role = ctx.guild.get_role(config['email']['VERIFIED_ROLE_ID'])

        if unverified_role in member.roles:
            user_id = str(member.id)
            
            codes = data.get("codes", {})
            user_data = codes.get(user_id)

            if user_data is not None:
                stored_code = user_data.get('code')
                expiration_time = user_data.get('expiration')

                if stored_code == user_code and time.time() < expiration_time:
                    await member.remove_roles(unverified_role)
                    await member.add_roles(verified_role)
                    timeout_message = await ctx.send(
                        f"Congratulations, {member.mention}! Your role has been verified."
                    )
                    await asyncio.sleep(5)
                    await timeout_message.delete()
                    codes.pop(user_id, None)
                    data["codes"] = codes
                    save_data(data)
                else:
                    await ctx.send("Invalid code or code has expired. Please check and try again.")
            else:
                timeout_message = await ctx.send(
                    "No verification data found for you. Please request a new code."
                )
                await asyncio.sleep(5)
                await timeout_message.delete()
        else:
            timeout_message = await ctx.send("You are already verified.")
            await asyncio.sleep(5)
            await timeout_message.delete()
    except Exception as error:
        print(f"An error occurred: {error}")

# -------------------------------------------------------------------------------------------------
# Run the bot
# -------------------------------------------------------------------------------------------------

async def main():

    """Start the bot using the async loop"""

    await bot.start(TOKEN)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
