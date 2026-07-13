import re
import os
import asyncio
from typing import Optional, Any

TG_MSG_REGEX = re.compile(r"t\.me/(c/)?\d+/\d+")
DL_BOT: Optional[Any] = None

class DirectLinkHandler:
    @staticmethod
    def is_valid(url: str) -> bool:
        return bool(url and url.startswith(("http://", "https://")))

    @staticmethod
    async def get_track(url: str) -> dict:
        return {"url": url}

    @staticmethod
    async def download_track(track: dict, is_video: bool) -> str:
        download_dir = "downloads"
        os.makedirs(download_dir, exist_ok=True)
        
        file_ext = "mp4" if is_video else "mp3"
        unique_id = int(os.urandom(4).hex(), 16)
        output_path = os.path.join(download_dir, f"kartik_{unique_id}.{file_ext}")
        url = track.get("url")
        
        if is_video:
            ydl_opts = "-f bestvideo+bestaudio/best --no-playlist"
        else:
            ydl_opts = "-f bestaudio --extract-audio --audio-format mp3 --no-playlist"
            
        cmd = f'yt-dlp {ydl_opts} -o "{output_path}" "{url}"'
        
        try:
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
        except Exception as e:
            raise RuntimeError(f"yt-dlp download failed: {str(e)}")
        
        if not os.path.exists(output_path):
            for file in os.listdir(download_dir):
                if file.startswith(f"kartik_{unique_id}"):
                    return os.path.join(download_dir, file)
            raise FileNotFoundError("Downloaded file not found on server.")
                    
        return output_path

async def download_cached_track(cached: Any, bot: Any) -> str:
    if not cached:
        raise ValueError("Cached track object is None")
        
    platform = str(getattr(cached, "platform", "")).strip().lower()

    if platform == "direct_link":
        return getattr(cached, "url", "")

    if platform == "telegram":
        return await download_telegram_file(cached, bot)

    dl_bot = DL_BOT if DL_BOT is not None else bot
    return await download_via_wrapper(cached, dl_bot)

async def download_via_wrapper(cached: Any, dl_bot: Any) -> str:
    url = getattr(cached, "url", "")
    if not DirectLinkHandler.is_valid(url):
        raise ValueError(f"Invalid cached URL: {url}")

    track = await DirectLinkHandler.get_track(url)
    is_video = getattr(cached, "is_video", False)
    path = await DirectLinkHandler.download_track(track, is_video)

    if TG_MSG_REGEX.search(path):
        return await download_from_telegram_message(dl_bot, path)

    return path

async def download_telegram_file(cached: Any, bot: Any) -> str:
    track_id = getattr(cached, "track_id", None)
    if not track_id:
        raise ValueError("Track ID missing for Telegram download.")

    file_path = await bot.download_media(track_id)
    if not file_path:
        raise RuntimeError("Failed to download Telegram file via track_id.")
        
    return str(file_path)

async def download_from_telegram_message(bot: Any, msg_url: str) -> str:
    try:
        clean_url = msg_url.replace("https://", "").replace("http://", "")
        parts = clean_url.split('/')
        message_id = int(parts[-1])
        
        if parts[1] == "c":
            chat_id = int(f"-100{parts[2]}")
        else:
            chat_id = int(parts[1]) if parts[1].replace('-', '').isdigit() else parts[1]

        msg = await bot.get_messages(chat_id, message_ids=message_id)
        if not msg:
            raise FileNotFoundError(f"Message not found in chat: {chat_id}")

        file_path = await bot.download_media(msg)
        if not file_path:
            raise RuntimeError("No media found inside this Telegram message.")
            
        return str(file_path)
        
    except Exception as e:
        raise RuntimeError(f"Message Downloader Error: {str(e)}")
        
