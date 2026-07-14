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

from KartikMusic.plugins.downloaders import download_cached_track

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


# BINA COMMAND (Bina /) KE BHI CHALNE KE LIYE: Yahan humne filters.text bhi add kar diya hai
@app.on_message(
    (
        filters.command(["play", "playforce", "vplay", "vplayforce"]) 
        | (filters.text & ~filters.command([]))  # Agar sirf normal text message ho toh bhi utha le
    )
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

    if media:
        setattr(sent, "lang", m.lang)
        file = await tg.download(m.reply_to_message, sent)

    elif m3u8:
        file = await tg.process_m3u8(url, sent.id, video)

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

    # Agar user ne /play likha ho ya sirf text likha ho dono case handle karega
    elif (m.command and len(m.command) >= 2) or (m.text and not m.text.startswith(("/", "!"))):
        if m.command and len(m.command) >= 2:
            query = " ".join(m.command[1:])
        else:
            query = m.text  # Agar bina slash ke bheja hai toh pura text query ban jayega

        file = await yt.search(query, sent.id, video=video)
        if not file:
            return await sent.edit_text(
                m.lang["play_not_found"].format(config.SUPPORT_CHAT)
            )

    if not file:
        return await sent.edit_text(m.lang["play_usage"])

    if file.duration_sec > config.DURATION_LIMIT:
        return await sent.edit_text(
            m.lang["play_duration_limit"].format(config.DURATION_LIMIT // 60)
        )

    if await db.is_logger():
        await utils.play_log(m, sent.link, file.title, file.duration)

    file.user = mention
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

    if not file.file_path:
        fname = f"downloads/{file.id}.{'mp4' if video else 'webm'}"
        if Path(fname).exists():
            file.file_path = str(Path(fname).absolute())
        else:
            await sent.edit_text(m.lang["play_downloading"])
            
            if getattr(file, "url", None) and ("t.me/" in file.url):
                platform_type = "telegram"
            elif getattr(file, "url", None) and file.url.startswith(("http://", "https://")):
                platform_type = "direct_link"
            else:
                platform_type = "external"

            cached_obj = CachedTrackWrapper(
                platform=platform_type, 
                url=getattr(file, "url", f"https://www.youtube.com/watch?v={file.id}"), 
                track_id=getattr(file, "id", None), 
                is_video=video
            )
            
            try:
                file.file_path = await download_cached_track(cached_obj, app)
            except Exception:
                file.file_path = await yt.download(file.id, video=video)

    # Aapke purane logic ke hisab se os import hata diya hai (Path module already upar imported hai toh error nahi aayega)
    if file.file_path and Path(file.file_path).exists():
        file.url = file.file_path

    await Kartik.play_media(chat_id=m.chat.id, message=sent, media=file)
    if not tracks:
        return
    added = playlist_to_queue(m.chat.id, tracks)
    await app.send_message(
        chat_id=m.chat.id,
        text=m.lang["playlist_queued"].format(len(tracks)) + added,
        )
    
