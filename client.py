import re
import yt_dlp
import random
from dotenv import load_dotenv
import os
from discord.ext import commands
import discord
intents = discord.Intents.default()
intents.message_content = True
intents.typing = False
intents.presences = False

bot = commands.Bot(command_prefix='!', intents=intents)

valid_dice = {2, 3, 4, 6, 8, 10, 12, 20, 100}


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
    error_msg = f"Format: !roll d<number>\nValid numbers are {valid_dice}"
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

            ctx.voice_client.play(discord.FFmpegPCMAudio(url2))
            await ctx.send(f"Now playing: **{title}**")
    except yt_dlp.utils.DownloadError:
        await ctx.send("Download error: Invalid URL or content unavailable!")
    except Exception as e:
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
