

import re
import os
from typing import Optional, Any

# Telegram message link ko identify karne ke liye standard regex
TG_MSG_REGEX = re.compile(r"t\.me/(c/)?\d+/\d+")

# Global Downloader Bot Client (Agar primary bot ke alawa alag client use karna ho)
DL_BOT: Optional[Any] = None


class DirectLinkHandler:
    """External links (YouTube/Spotify/Direct Links) ko handle karne ke liye class"""
    
    @staticmethod
    def is_valid(url: str) -> bool:
        return bool(url and url.startswith(("http://", "https://")))

    @staticmethod
    async def get_track(url: str) -> dict:
        # Yahan aapki repo ka extra track info logic aa sakta hai
        return {"url": url}

    @staticmethod
    async def download_track(track: dict, is_video: bool) -> str:
        """
        External links ko local system me download karne ke liye.
        Yahan aap yt-dlp ya apna koi custom downloader laga sakte ho.
        """
        download_dir = "downloads"
        os.makedirs(download_dir, exist_ok=True)
        
        # Ek sample output path generate kar rahe hain
        file_ext = "mp4" if is_video else "mp3"
        output_path = os.path.join(download_dir, f"kartik_music_{int(os.urandom(4).hex(), 16)}.{file_ext}")
        
        # NOTA: Real implementation me yahan yt-dlp/wget download logic aayega
        # Example dummy file taaki code crash na ho testing me:
        with open(output_path, "w") as f:
            f.write("dummy data")
            
        return output_path


async def download_cached_track(cached: Any, bot: Any) -> str:
    """
    KartikMusic Main Downloader Function
    
    Parameters:
    - cached: Ek object jisme `platform`, `url`, `track_id`, `is_video` attributes hon.
    - bot: Telegram Client Instance (Pyrogram/Telethon).
    
    Returns:
    - str: Downloaded file ka local path ya direct URL.
    """
    # 1. Direct Link: Agar platform direct link hai toh download karne ki need nahi hai
    if getattr(cached, "platform", "").lower() == "direct_link":
        return cached.url

    # 2. Telegram File: Agar Telegram ke server par file pehle se save hai
    if getattr(cached, "platform", "").lower() == "telegram":
        return await download_telegram_file(cached, bot)

    # 3. External Wrapper: YouTube/Spotify links ke liye
    dl_bot = DL_BOT if DL_BOT is not None else bot
    return await download_via_wrapper(cached, dl_bot)


async def download_via_wrapper(cached: Any, dl_bot: Any) -> str:
    """External wrapper (like yt-dlp) ke throw download handle karta hai"""
    if not DirectLinkHandler.is_valid(cached.url):
        raise ValueError(f"Invalid cached URL passed to KartikMusic: {cached.url}")

    track = await DirectLinkHandler.get_track(cached.url)
    path = await DirectLinkHandler.download_track(track, cached.is_video)

    # Agar download path me koi Telegram message link milta hai, toh wahan se file uthao
    if TG_MSG_REGEX.search(path):
        return await download_from_telegram_message(dl_bot, path)

    return path


async def download_telegram_file(cached: Any, bot: Any) -> str:
    """Telegram ki file_id use karke media download karta hai"""
    if not getattr(cached, "track_id", None):
        raise ValueError("Track ID missing for Telegram download.")

    # Pyrogram standard media downloader
    file_path = await bot.download_media(cached.track_id)
    if not file_path:
        raise RuntimeError("KartikMusic failed to download Telegram file via file_id.")
        
    return str(file_path)


async def download_from_telegram_message(bot: Any, msg_url: str) -> str:
    """Telegram message link (t.me/xxx/xx) se media file extract karke download karta hai"""
    try:
        # URL ko split karke Chat ID aur Message ID nikalna
        parts = msg_url.split('/')
        chat_part = parts[-2]
        message_id = int(parts[-1])
        
        # Private channel/group link verification (c/ bypass)
        if chat_part == "c":
            # Private chat ids pyrogram me -100 se start hoti hain
            chat_id = int(f"-100{parts[-3]}")
        else:
            chat_id = int(chat_part) if chat_part.replace('-', '').isdigit() else chat_part

        # Message fetch karna
        msg = await bot.get_messages(chat_id, message_ids=message_id)
        if not msg:
            raise FileNotFoundError(f"Message not found at URL: {msg_url}")

        # Message se media download karna
        file_path = await bot.download_media(msg)
        if not file_path:
            raise RuntimeError("Failed to extract media from the target Telegram message.")
            
        return str(file_path)
        
    except Exception as e:
        raise RuntimeError(f"KartikMusic Message Downloader Error: {str(e)}")
  
