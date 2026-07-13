#
# Copyright (C) 2025-present by TheAloneTeam@Github, < https://github.com/TheAloneTeam >.
#
# This file is part of < https://github.com/TheAloneTeam/KartikMusic > project,
# and is released under the "MIT License".
# Please see < https://github.com/TheAloneTeam/KartikMusic/blob/master/LICENSE >
#
# All rights reserved.
#

from pathlib import Path
from pyrogram import filters, types
from KartikMusic import Kartik, app, config, db, lang, queue, tg, yt
from KartikMusic.helpers import buttons, utils
from KartikMusic.helpers._play import checkUB

# Naya Downloader Module Import Kiya Bina Purane Imports Chhede
from KartikMusic.plugins.downloaders import download_cached_track

# Dummy wrapper class jo tumhare downloader ke liye custom track object banayegi
class CachedTrackWrapper:
    def __init__(self, platform: str, url: str = None, track_id: str = None, is_video: bool = False):
        self.platform = platform
        self.url = url
        self.track_id = track_id
        self.is_video = is_video


def playlist_to_queue(chat_id: int, tracks: list) -> str:
    text = "<blockquote expandable>"
    for track in tracks:
        pos = queue.add(chat_id, track)
        text += f"<b>{pos}.</b> {track.title}\n"
    text = text[:1948] + "</blockquote>"
    return text


@app.on_message(
    filters.command(["play", "playforce", "vplay", "vplayforce"])
    & filters.group
    & ~app.bl_users
)
@lang.language()
@checkUB
async def play_hndlr(
    _,
    m: types.Message,
    force: bool = False,
    m3u8: bool = False,
    video: bool = False,
    url: str = None,
) -> None:
    sent = await m.reply_text(m.lang["play_searching"])
    file = None
    mention = m.from_user.mention
    media = tg.get_media(m.reply_to_message) if m.reply_to_message else None
    tracks = []

    # 1. Agar reply me koi media file mili (Telegram native format)
    if media:
        setattr(sent, "lang", m.lang)
        file = await tg.download(m.reply_to_message, sent)

    # 2. Live stream m3u8 link processing
    elif m3u8:
        file = await tg.process_m3u8(url, sent.id, video)

    # 3. Direct URL ya YouTube Playlist link logic
    elif url:
        if "playlist" in url:
            await sent.edit_text(m.lang["playlist_fetch"])
            tracks = await yt.playlist(config.PLAYLIST_LIMIT, mention, url, video)

            if not tracks:
                return await sent.edit_text(m.lang["playlist_error"])

            file = tracks[0]
            tracks.remove(file)
            file.message_id = sent.id
        else:
            file = await yt.search(url, sent.id, video=video)

        if not file:
            return await sent.edit_text(
                m.lang["play_not_found"].format(config.SUPPORT_CHAT)
            )

    # 4. Normal query text search (e.g., /play tum hi ho)
    elif len(m.command) >= 2:
        query = " ".join(m.command[1:])
        file = await yt.search(query, sent.id, video=video)
        if not file:
            return await sent.edit_text(
                m.lang["play_not_found"].format(config.SUPPORT_CHAT)
            )

    # Basic initial checks (duration limit & usage error handling)
    if not file:
        return await sent.edit_text(m.lang["play_usage"])

    if file.duration_sec > config.DURATION_LIMIT:
        return await sent.edit_text(
            m.lang["play_duration_limit"].format(config.DURATION_LIMIT // 60)
        )

    if await db.is_logger():
        await utils.play_log(m, sent.link, file.title, file.duration)

    file.user = mention
    
    # Queue structure calculation (force play or standard queuing)
    if force:
        current = queue.get_current(m.chat.id)
        if current and current.message_id:
            try:
                await app.delete_messages(m.chat.id, current.message_id)
            except Exception:
                pass
        queue.force_add(m.chat.id, file)
    else:
        position = queue.add(m.chat.id, file)

        if position != 0 or await db.get_call(m.chat.id):
            await sent.edit_text(
                m.lang["play_queued"].format(
                    position,
                    file.url,
                    file.title,
                    file.duration,
                    m.from_user.mention,
                ),
                reply_markup=buttons.play_queued(
                    m.chat.id, file.id, m.lang["play_now"]
                ),
            )
            if tracks:
                added = playlist_to_queue(m.chat.id, tracks)
                await app.send_message(
                    chat_id=m.chat.id,
                    text=m.lang["playlist_queued"].format(len(tracks)) + added,
                )
            return

    # 🛠️ FIXED: Yahan par aapka naya custom dynamic downloader lagaya gaya hai
    if not file.file_path:
        fname = f"downloads/{file.id}.{'mp4' if video else 'webm'}"
        if Path(fname).exists():
            file.file_path = fname
        else:
            await sent.edit_text(m.lang["play_downloading"])
            
            # Aapke logic ke hisab se dynamically cached structure generate karna
            if getattr(file, "url", None) and ("t.me/" in file.url):
                platform_type = "telegram"
            elif getattr(file, "url", None) and file.url.startswith(("http://", "https://")):
                platform_type = "direct_link"
            else:
                platform_type = "external"

            # Wrapper object setup kiya bina system variables ko cheat kiye
            cached_obj = CachedTrackWrapper(
                platform=platform_type, 
                url=getattr(file, "url", f"ytsearch:{file.title}"), 
                track_id=getattr(file, "id", None), 
                is_video=video
            )
            
            try:
                # Naye downloader script se execution fire kiya
                file.file_path = await download_cached_track(cached_obj, app)
            except Exception:
                # Fallback: Agar kisi bina par custom loader fail ho, toh backup yt script run karega
                file.file_path = await yt.download(file.id, video=video)

    # Final execution to stream on VC
    await Kartik.play_media(chat_id=m.chat.id, message=sent, media=file)
    if not tracks:
        return
    added = playlist_to_queue(m.chat.id, tracks)
    await app.send_message(
        chat_id=m.chat.id,
        text=m.lang["playlist_queued"].format(len(tracks)) + added,
                )
    
