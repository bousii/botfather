import re
import yt_dlp
import random
import functools
import logging
from dotenv import load_dotenv
import os
from discord.ext import commands
import discord
import asyncio

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("musicbot")

intents = discord.Intents.default()
intents.message_content = True
intents.typing = False
intents.presences = False

bot = commands.Bot(command_prefix='!', intents=intents)

valid_dice = {2, 3, 4, 6, 8, 10, 12, 20, 100}

# These tell ffmpeg to automatically retry the connection instead of
# dying the moment it hits a dropped/bad packet on the stream. This is
# the single biggest fix for playback silently stopping mid-song.
FFMPEG_BEFORE_OPTIONS = (
    "-reconnect 1 "
    "-reconnect_streamed 1 "
    "-reconnect_delay_max 5"
)
FFMPEG_OPTIONS = "-vn"


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    print("Connected to these servers:")
    for guild in bot.guilds:
        print(f"- {guild.name} (ID: {guild.id})")


@bot.command()
async def hello(ctx):
    await ctx.send("Hello!")


@bot.command()
async def roll(ctx, message):
    error_msg = f"Format: !roll <quantity>d<number>\nValid numbers are {valid_dice}"
    if not re.fullmatch("[0-9]*d[0-9]+", message):
        await ctx.send(error_msg)
        return
    sides = int(message[message.find("d") + 1:])
    if sides not in valid_dice:
        await ctx.send(error_msg)
        return
    times = 1
    if message.find("d") != 0:
        times = int(message[0:int(message.find("d"))])

    value = random.randint(1, sides)
    output = "" + str(value)
    total = value
    if times > 1:
        for i in range(times - 1):
            value = random.randint(1, sides)
            output = output + " + " + str(value)
            total = total + value
        output = output + " = " + str(total)

    await ctx.send(output)


def _after_playback(error, ctx, title):
    """
    Called by discord.py's audio player thread when playback stops,
    whether it finished cleanly or ffmpeg died on a bad packet.

    Without this callback, discord.py just swallows the error and the
    bot goes silent with no logging and no way to recover.
    """
    if error is None:
        return  # finished normally, nothing to do

    log.error(f"Playback error during '{title}': {error}")

    # We're in a non-async thread here, so hop back onto the bot's
    # event loop to send a message / do any cleanup.
    coro = ctx.send(f"⚠️ Playback of **{title}** stopped due to an error "
                     f"({error}). Use `!play <url>` to try again.")
    fut = asyncio.run_coroutine_threadsafe(coro, bot.loop)
    try:
        fut.result(timeout=10)
    except Exception as e:
        log.error(f"Failed to send playback-error message: {e}")


@bot.command()
async def play(ctx, url):
    author = ctx.author
    if author.voice is None:
        await ctx.send("Join a voice channel first so you can hear audio!")
        return

    if not url:
        await ctx.send("Please provide a URL!")
        return

    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
        r'localhost|'  # localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # or IP
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

    if not url_pattern.match(url):
        await ctx.send("Invalid URL format!")
        return

    allowed_domains = ['youtube.com', 'youtu.be']
    if not any(domain in url for domain in allowed_domains):
        await ctx.send("Only YouTube links are supported!")
        return

    channel = author.voice.channel

    if ctx.voice_client is None:
        await channel.connect()
    elif ctx.voice_client.channel != channel:
        await ctx.voice_client.move_to(channel)
    else:
        pass

    if ctx.voice_client.is_playing():
        ctx.voice_client.stop()

    try:
        ydl_opts = {
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
            # Allows yt-dlp to fetch its JS-challenge solver script from
            # GitHub if the local yt-dlp-ejs package isn't installed/current.
            # Without this, YouTube extraction falls back to a weaker
            # client and frequently gets 403'd.
            "remote_components": ["ejs:github"],
            # As of Aug 2026, yt-dlp's default "android_vr" client is
            # hitting a YouTube-side 403 for everyone (upstream bug,
            # yt-dlp/yt-dlp#17456) - force known-working clients instead.
            # Remove this override once that issue is resolved upstream.
            "extractor_args": {
                "youtube": {"player_client": ["tv", "web_safari"]}
            },
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            if info is None:
                await ctx.send("Could not extract audio info!")
                return

            url2 = info.get("url")
            title = info.get("title", "Unknown")

            if not url2:
                await ctx.send("No audio stream found!")
                return

            try:
                source = discord.FFmpegPCMAudio(
                    url2,
                    before_options=FFMPEG_BEFORE_OPTIONS,
                    options=FFMPEG_OPTIONS,
                )
            except Exception as e:
                # Covers cases like ffmpeg not being found on PATH, or
                # failing to even start the process.
                log.error(f"Failed to create ffmpeg audio source: {e}")
                await ctx.send(f"Couldn't start audio playback: {e}")
                return

            after_callback = functools.partial(_after_playback, ctx=ctx, title=title)
            ctx.voice_client.play(source, after=after_callback)
            await ctx.send(f"Now playing: **{title}**")
    except yt_dlp.utils.DownloadError:
        await ctx.send("Download error: Invalid URL or content unavailable!")
    except Exception as e:
        log.error(f"Unexpected error in !play: {e}")
        await ctx.send(f"Error: {str(e)}")


@bot.command()
async def stop(ctx):
    if ctx.voice_client is None:
        await ctx.send("Not in voice channel")
        return

    if ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("Stopped!")
    else:
        await ctx.send("Nothing to stop!")


@bot.command()
async def pause(ctx):
    if ctx.voice_client is None:
        await ctx.send("Not in voice channel")
        return

    if ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("Paused!")
    else:
        await ctx.send("Nothing to pause!")


@bot.command()
async def resume(ctx):
    if ctx.voice_client is None:
        await ctx.send("Not in voice channel")
        return

    if ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("Resumed!")
    else:
        await ctx.send("Nothing to resume!")


@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("Left the voice channel")

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
