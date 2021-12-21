from datetime import datetime
import io
import json
import platform
import textwrap
import traceback
from contextlib import redirect_stdout

import discord
import pkg_resources
import psutil
from discord.ext import commands


class Commands(commands.Cog):
    def __init__(self, client):
        self.client = client
        commands_allowed_users = json.loads(client.config["Commands"]["AllowedUsers"])
        self.client.add_check(lambda ctx: ctx.author.id in commands_allowed_users)
        self.started = datetime.now()

    @commands.command()
    async def ping(self, ctx):
        """Ping? Pong!"""
        await ctx.send("pong")

    @commands.command(name="addreaction")
    async def add_reactions(self, ctx, channel_id: int, message_id, *emotes: discord.PartialEmoji):
        """Adds reactions"""
        channel = self.client.get_channel(channel_id)
        message = await channel.fetch_message(message_id)
        for emote in emotes:
            await message.add_reaction(emote)
        await ctx.message.add_reaction("✅")

    @commands.command(name="removereaction")
    async def remove_reaction(self, ctx, channel_id: int, message_id, *emotes: discord.PartialEmoji):
        """Removes reaction"""
        channel = self.client.get_channel(channel_id)
        message = await channel.fetch_message(message_id)
        for emote in emotes:
            await message.remove_reaction(emote, self.client.user)
        await ctx.message.add_reaction("✅")

    @commands.command(name="posthook")
    async def post_hook(self, ctx, *channels: int):
        """Sends embed messages (json exported at Discohook)"""
        attachment_content = await ctx.message.attachments[0].read()
        data = json.loads(attachment_content)["backups"][0]["message"]

        content = data.get("content", "")
        for number, embed in enumerate(data["embeds"]):
            channel = self.client.get_channel(channels[min(number, len(channels) - 1)])
            await channel.send(content, embed=discord.Embed.from_dict(embed))
            content = ""

        await ctx.message.add_reaction("✅")

    # Discohook post and pin
    @commands.command(name="postpinhook")
    async def post_pin_hook(self, ctx, *channels: int):
        """Sends and pins embed messages (json exported at Discohook)"""
        attachment_content = await ctx.message.attachments[0].read()
        data = json.loads(attachment_content)["backups"][0]["message"]

        content = data.get("content", "")
        for number, embed in enumerate(data["embeds"]):
            channel = self.client.get_channel(channels[min(number, len(channels) - 1)])
            message = await channel.send(content, embed=discord.Embed.from_dict(embed))
            await message.pin()
            content = ""

        await ctx.message.add_reaction("✅")

    @commands.command(name="edithook")
    async def edit_hook(self, ctx, channel_id: int, message_id: int):
        """Edits embed message (json exported at Discohook)"""
        attachment_content = await ctx.message.attachments[0].read()
        data = json.loads(attachment_content)["backups"][0]["message"]

        content = data.get("content", "")
        embed = data.get("embeds", [{}])[0]
        channel = self.client.get_channel(channel_id)
        message = await channel.fetch_message(message_id)
        await message.edit(content=content, embed=discord.Embed.from_dict(embed))

        await ctx.message.add_reaction("✅")

    @commands.command(name="eval")
    async def eval(self, ctx, *, body: str):
        """Evaluates python code"""
        env = {
            "client": self.client,
            "ctx": ctx,
            "channel": ctx.channel,
            "author": ctx.author,
            "guild": ctx.guild,
            "message": ctx.message
        }

        env.update(globals())

        if body.startswith("```") and body.endswith("```"):
            body = "\n".join(body.split("\n")[1:-1])
        stdout = io.StringIO()

        to_compile = f"async def func():\n{textwrap.indent(body, '  ')}"

        try:
            exec(to_compile, env)
        except Exception as e:
            return await ctx.send(f"```py\n{e.__class__.__name__}: {e}\n```")

        func = env["func"]
        try:
            with redirect_stdout(stdout):
                ret = await func()
        except Exception as e:
            value = stdout.getvalue()
            await ctx.send(f"```py\n{value}{traceback.format_exc()}\n```")
        else:
            value = stdout.getvalue()
            await ctx.message.add_reaction("✅")

            if ret is None:
                if value:
                    await ctx.send(f"```py\n{value}\n```")

    @commands.command(name="status")
    async def status(self, ctx):
        """Shows bot status"""

        def ver(module):
            version = pkg_resources.get_distribution(module).version
            return version

        py_version = platform.python_version()
        memory = psutil.virtual_memory()

        embed = discord.Embed(
            title=self.client.user.name,
            description="Started: {0.day}.{0.month}.{0.year} {0.hour}:{0.minute}".format(self.started)
        )

        libraries = ["discord.py", "vk-api", "psutil", "dnspython"]
        libraries_text = "\n".join([f"{lib}: **{ver(lib)}**" for lib in libraries])

        embed.add_field(name="Used",
                        value=f"Python: **{py_version}**\n{libraries_text}")

        embed.add_field(name="System",
                        value=f"OS: **{platform.system()} {platform.version()}**\n"
                              f"CPU: **{psutil.cpu_percent()}%**\n"
                              f"RAM: **{memory.percent}% ({memory.used / 1000000000:.1f}/{memory.total / 1000000000:.1f} ГБ)**")

        await ctx.send(embed=embed)


def setup(client):
    client.add_cog(Commands(client))
