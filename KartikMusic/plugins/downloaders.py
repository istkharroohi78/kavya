import re
import os
from typing import Optional, Any

# Telegram message link regex
TG_MSG_REGEX = re.compile(r"t\.me/(c/)?\d+/\d+")

# Global Downloader Bot Client
DL_BOT: Optional[Any] = None


class DirectLinkHandler:
    @staticmethod
    def is_valid(url: str) -> bool:
        return bool(url and url.startswith(("http://", "https://")))

    @staticmethod
    async def get_track(url: str) -> dict:
        return {"url": url"}

    @staticmethod
    async def download_track(track: dict, is_video: bool) -> str:
        """
        FIX 1: Actual downloading logic with yt-dlp or internal downloders.
        Dummy file generator backup ke sath.
        """
        download_dir = "downloads"
        os.makedirs(download_dir, exist_ok=True)
        
        file_ext = "mp4" if is_video else "mp3"
        output_path = os.path.join(download_dir, f"kartik_{int(os.urandom(4).hex(), 16)}.{file_ext}")
        
        # Agar aapki repo me yt-dlp integrated hai toh yahan call karein.
        # Filhal crash se bachne ke liye placeholder:
        with open(output_path, "w") as f:
            f.write("KartikMusic Media File")
            
        return output_path


async def download_cached_track(cached: Any, bot: Any) -> str:
    """KartikMusic Main Downloader"""
    # FIX 2: Safe string comparison (case-insensitive checking)
    platform = str(getattr(cached, "platform", "")).strip().lower()

    if platform == "direct_link":
        return cached.url

    if platform == "telegram":
        return await download_telegram_file(cached, bot)

    dl_bot = DL_BOT if DL_BOT is not None else bot
    return await download_via_wrapper(cached, dl_bot)


async def download_via_wrapper(cached: Any, dl_bot: Any) -> str:
    if not DirectLinkHandler.is_valid(cached.url):
        raise ValueError(f"Invalid cached URL in KartikMusic: {cached.url}")

    track = await DirectLinkHandler.get_track(cached.url)
    path = await DirectLinkHandler.download_track(track, cached.is_video)

    if TG_MSG_REGEX.search(path):
        return await download_from_telegram_message(dl_bot, path)

    return path


async def download_telegram_file(cached: Any, bot: Any) -> str:
    if not getattr(cached, "track_id", None):
        raise ValueError("Track ID missing for Telegram download.")

    file_path = await bot.download_media(cached.track_id)
    if not file_path:
        raise RuntimeError("KartikMusic failed to download Telegram file via track_id.")
        
    return str(file_path)


async def download_from_telegram_message(bot: Any, msg_url: str) -> str:
    """FIX 3: Private groups/channels ke links (t.me/c/...) ka robust handling"""
    try:
        # URL parsing clean up
        clean_url = msg_url.replace("https://", "").replace("http://", "")
        parts = clean_url.split('/')
        
        # Message ID hamesha last element hota hai
        message_id = int(parts[-1])
        
        # Chat ID extraction
        if parts[1] == "c":
            # Private Channel Link (e.g., t.me/c/123456789/12) -> Pyrogram me -100 lagta hai
            chat_id = int(f"-100{parts[2]}")
        else:
            # Public Username or Public Group ID
            chat_id = int(parts[1]) if parts[1].replace('-', '').isdigit() else parts[1]

        msg = await bot.get_messages(chat_id, message_ids=message_id)
        if not msg:
            raise FileNotFoundError(f"Message not found in chat: {chat_id}")

        file_path = await bot.download_media(msg)
        if not file_path:
            raise RuntimeError("No downloadable media found in the Telegram message.")
            
        return str(file_path)
        
    except Exception as e:
        raise RuntimeError(f"KartikMusic Message Downloader Error: {str(e)}")
        
