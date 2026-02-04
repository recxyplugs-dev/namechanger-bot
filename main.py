import os
import json
import asyncio
from datetime import datetime

from telethon import TelegramClient, events
from telethon.tl.functions.channels import EditTitleRequest

# ================== ENV CONFIG ==================
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("8533020463:AAFBmdt4ns8LCGlkQ1J9im9GFhvkA4TVSXI", "")

# Owner (only this person can add/remove bot admins)
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
# ===============================================

if not API_ID or not API_HASH or not BOT_TOKEN:
    raise ValueError("Missing API_ID / API_HASH / BOT_TOKEN env vars!")

if not OWNER_ID:
    raise ValueError("Missing OWNER_ID env var! Put your Telegram user id.")

client = TelegramClient("namechanger_session", API_ID, API_HASH).start(bot_token=BOT_TOKEN)

HEARTS = ["❤️", "🖤", "🤍", "💙", "💜", "💛", "💚", "🧡", "💖", "💘", "💝", "💕", "💞", "❣️", "💓", "💗"]
running_tasks = {}  # chat_id -> asyncio task

ADMINS_FILE = "admins.json"


# ------------------ Admin Storage ------------------
def load_admins():
    if not os.path.exists(ADMINS_FILE):
        data = {"admins": [OWNER_ID]}
        with open(ADMINS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return set(data["admins"])

    with open(ADMINS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    admins = set(data.get("admins", []))
    admins.add(OWNER_ID)
    return admins


def save_admins(admins_set):
    data = {"admins": sorted(list(admins_set))}
    with open(ADMINS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


BOT_ADMINS = load_admins()


def is_bot_admin(user_id: int) -> bool:
    return user_id in BOT_ADMINS


def get_time_text():
    return datetime.now().strftime("%I:%M %p")


async def resolve_user_id(event, arg: str):
    """
    arg can be:
    - @username
    - user_id
    - reply user
    """
    if arg:
        arg = arg.strip()
        if arg.isdigit():
            return int(arg)
        try:
            entity = await client.get_entity(arg)
            return entity.id
        except:
            return None

    # if no arg -> use reply
    if event.is_reply:
        msg = await event.get_reply_message()
        return msg.sender_id

    return None


# ------------------ Name Changer Loop ------------------
async def name_changer_loop(chat_id, base_name, delay):
    i = 0
    while True:
        heart = HEARTS[i % len(HEARTS)]
        time_text = get_time_text()
        new_title = f"{heart} {base_name} | {time_text} {heart}"

        try:
            await client(EditTitleRequest(channel=chat_id, title=new_title))
        except Exception as e:
            print("EditTitle error:", e)

        i += 1
        await asyncio.sleep(delay)


# ------------------ Commands ------------------
@client.on(events.NewMessage(pattern=r"^/help$"))
async def help_cmd(event):
    await event.reply(
        "**Bot Commands:**\n"
        "`/start poscoact 5` → start name changer\n"
        "`/stop` → stop name changer\n"
        "`/admins` → list bot admins\n\n"
        "**Owner only:**\n"
        "`/addadmin @user` or reply + /addadmin\n"
        "`/removeadmin @user` or reply + /removeadmin\n"
    )


@client.on(events.NewMessage(pattern=r"^/admins$"))
async def admins_list(event):
    admins_text = "\n".join([f"- `{aid}`" for aid in sorted(BOT_ADMINS)])
    await event.reply(f"✅ **Bot Admins:**\n{admins_text}")


@client.on(events.NewMessage(pattern=r"^/addadmin(?:\s+(.+))?$"))
async def add_admin(event):
    if event.sender_id != OWNER_ID:
        return await event.reply("❌ Only OWNER can add bot admins.")

    arg = event.pattern_match.group(1)
    user_id = await resolve_user_id(event, arg)

    if not user_id:
        return await event.reply("⚠️ Use: `/addadmin @username` or reply to user with `/addadmin`")

    BOT_ADMINS.add(user_id)
    save_admins(BOT_ADMINS)
    await event.reply(f"✅ Added bot admin: `{user_id}`")


@client.on(events.NewMessage(pattern=r"^/removeadmin(?:\s+(.+))?$"))
async def remove_admin(event):
    if event.sender_id != OWNER_ID:
        return await event.reply("❌ Only OWNER can remove bot admins.")

    arg = event.pattern_match.group(1)
    user_id = await resolve_user_id(event, arg)

    if not user_id:
        return await event.reply("⚠️ Use: `/removeadmin @username` or reply to user with `/removeadmin`")

    if user_id == OWNER_ID:
        return await event.reply("❌ You can't remove OWNER.")

    if user_id in BOT_ADMINS:
        BOT_ADMINS.remove(user_id)
        save_admins(BOT_ADMINS)
        return await event.reply(f"🗑 Removed bot admin: `{user_id}`")

    await event.reply("⚠️ This user is not in bot admin list.")


@client.on(events.NewMessage(pattern=r"^/start(?:\s+(.+))?$"))
async def start(event):
    if not is_bot_admin(event.sender_id):
        return await event.reply("❌ Bot-admin only.")

    if event.chat_id in running_tasks:
        return await event.reply("⚠️ Already running in this group. Use /stop first.")

    args = event.pattern_match.group(1)
    if not args:
        return await event.reply("Usage:\n`/start poscoact 5`\nExample:\n`/start poscoact 3`")

    delay = 5
    base_name = args.strip()

    parts = base_name.split()
    if len(parts) >= 2 and parts[-1].isdigit():
        delay = int(parts[-1])
        base_name = " ".join(parts[:-1])

    if delay < 2:
        delay = 2

    task = asyncio.create_task(name_changer_loop(event.chat_id, base_name, delay))
    running_tasks[event.chat_id] = task

    await event.reply(
        f"✅ Started!\n"
        f"📝 Name: `{base_name}`\n"
        f"⏳ Delay: `{delay}s`\n"
        f"🛑 Stop: `/stop`"
    )


@client.on(events.NewMessage(pattern=r"^/stop$"))
async def stop(event):
    if not is_bot_admin(event.sender_id):
        return await event.reply("❌ Bot-admin only.")

    task = running_tasks.get(event.chat_id)
    if not task:
        return await event.reply("⚠️ Not running in this group.")

    task.cancel()
    running_tasks.pop(event.chat_id, None)
    await event.reply("🛑 Stopped in this group.")


print("🤖 Multi-GC NameChanger Bot running...")
client.run_until_disconnected()
          
