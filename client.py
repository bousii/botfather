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
async def play(ctx, message):
    await ctx.send("Hello!")


load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
