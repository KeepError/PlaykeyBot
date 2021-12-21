#!/usr/bin/env python3
# -*- coding: utf8 -*-

import configparser
import json
import sys

import discord
from discord.ext import commands


def get_config():
    config_path = "config"
    config = configparser.ConfigParser()
    config.read([f"{config_path}/common.ini", f"{config_path}/{sys.argv[1]}.ini"], encoding="UTF-8")
    return config


config = get_config()

client = commands.Bot(command_prefix=config["Client"]["Prefix"])
client.config = config


@client.event
async def on_ready():
    print("Logged on as {0}!".format(client.user))
    await client.change_presence(activity=discord.Game(client.config["Client"]["Activity"]))

    await client.get_channel(int(client.config["Client"]["InfoChannelId"])).send("Bot is ready")


@client.event
async def on_message(message):
    print("Message from {0.author}: {0.content}".format(message))
    await client.process_commands(message)


def main():
    cogs = json.loads(client.config["Client"]["Cogs"])
    for cog in cogs:
        try:
            client.load_extension(f"cogs.{cog}")
            print("Cog", cog, "loaded")
        except Exception as e:
            print("Loading", cog, "failed")

    client.run(client.config["Client"]["Token"])


if __name__ == "__main__":
    main()
