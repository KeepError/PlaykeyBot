import asyncio
import re

import discord
import vk_api
from discord.ext import commands, tasks

from consts import DatabaseKeys


class VkPost:
    def __init__(self, data, post):
        self.data = data
        self.post = post
        self.repost = None
        if 'copy_history' in post:
            self.repost = VkPost(data, post['copy_history'][0])
        self.doc_types = ['Текстовый документ', 'Архив', 'GIF-анимация', 'Изображение', 'Аудио', 'Видео',
                          'Электронная книга', 'Неизвестно']

    def get_max_size(self, sizes, url_key='url'):
        return sorted(sizes, key=lambda x: x['width'] * x['height'])[-1][url_key]

    @property
    def post_text(self):

        def formatting_text(text):

            def hashtags(substr):
                substring = substr[1]
                spl = substring.split('@')
                if len(spl) < 2:
                    url = f'https://vk.com/feed?section=search&q=%23{substring}'
                else:
                    url = f'https://vk.com/{spl[1]}/{spl[0]}'
                return f'[#{substring}]({url})'

            text = re.sub(r'#(\S+)', hashtags, text)
            text = re.sub(r'\[([^\]\[]+)\|([^\]\[]+)\]', lambda x: f'[{x[2]}](https://vk.com/{x[1]})', text)
            # text = re.sub(r'(\s)(\w+\.\S+)', lambda x: f'{x[1]}[{x[2]}](https://{x[2]})', ' ' + text)[1:]

            return text

        result = formatting_text(self.post['text'])
        return result

    @property
    def attachments(self):
        attachments_list = self.post.get('attachments', [])
        photos_count = 0
        result = []

        for attachment in attachments_list:
            if attachment['type'] == 'photo':
                photos_count += 1

            elif attachment['type'] == 'album':
                result.append(f'`Альбом` {attachment["album"]["title"]}')

            elif attachment['type'] == 'doc':
                doc = attachment['doc']
                result.append(f'`Документ ({self.doc_types[doc["type"] - 1]})` {doc["title"]}')

            elif attachment['type'] == 'link':
                link = attachment["link"]
                result.append(f'`Ссылка` [{link["title"]}]({link["url"]})')

            elif attachment['type'] == 'video':
                result.append(f'`Видео` {attachment["video"]["title"]}')

            elif attachment['type'] == 'poll':
                result.append(f'`Опрос` {attachment["poll"]["question"]}')

            elif attachment['type'] == 'audio':
                result.append(f'`Аудио` {attachment["audio"]["artist"]} - {attachment["audio"]["title"]}')

        if photos_count >= 2:
            result.append(f'`Изображения [{photos_count}]`')

        return result

    @property
    def image(self):
        attachments_list = self.post.get('attachments', [])
        not_photos = []

        for attachment in attachments_list:
            if attachment['type'] == 'photo':
                return self.get_max_size(attachment['photo']['sizes'])

            elif attachment['type'] == 'album':
                image_url = self.get_max_size(attachment['album']['thumb']['sizes'])
                not_photos.append(image_url)

            elif attachment['type'] == 'doc' and 'preview' in attachment['doc'] and 'photo' in attachment['doc']['preview']:
                image_url = self.get_max_size(attachment['doc']['preview']['photo']['sizes'], url_key='src')
                not_photos.append(image_url)

            elif attachment['type'] == 'link' and 'photo' in attachment['link']:
                image_url = self.get_max_size(attachment['link']['photo']['sizes'])
                not_photos.append(image_url)

            elif attachment['type'] == 'video':
                image_url = self.get_max_size(attachment['video']['image'])
                not_photos.append(image_url)

        if not_photos:
            return not_photos[0]

        return None

    @property
    def group(self):
        result = [x for x in self.data['groups'] + self.data['profiles'] if str(x['id']) == str(self.post['owner_id'])[1:]][0]
        return result

    @property
    def url(self):
        group = self.group
        result = f'https://vk.com/{group["screen_name"]}?w=wall-{group["id"]}_{self.post["id"]}'
        return result

    def generate_discord_embed(self, community={}):
        def quote_text(text):
            result = '\n'.join(['> ' + x for x in text.split('\n')])
            return result

        embed = discord.Embed(
            title='Открыть на стене',
            url=self.url,
            colour=0x167ffc
        )

        embed.description = self.post_text

        if self.repost:
            embed.description += '\n\n'
            repost_text = f'[Репост]({self.repost.url}) | [{self.repost.group["name"]}](https://vk.com/{self.repost.group["screen_name"]})\n\n{self.repost.post_text}'
            if self.repost.attachments:
                repost_text += '\n\n' + '\n'.join(self.repost.attachments)
            embed.description += quote_text(repost_text)

        attachments = self.attachments
        if attachments:
            embed.description += '\n\n' + '\n'.join(attachments)

        if self.image:
            embed.set_image(url=self.image)
        elif self.repost and self.repost.image:
            embed.set_image(url=self.repost.image)

        group = self.group
        embed.set_footer(text=group['name'], icon_url=group['photo_50'])

        return embed


class Vk(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.vk_data = client.data[DatabaseKeys.vk]

        self.waiting_time = int(client.config['VK']['WaitingTime'])

        vk_session = vk_api.VkApi(token=client.config['VK']['AccessToken'], api_version='5.131')
        self.vk = vk_session.get_api()

    def initialize_community(self, community_name: str):
        community = {}
        try:
            data = self.vk.wall.get(domain=community_name, count=3, extended=1)
        except Exception as e:
            print(f'{community_name} wall.. failed')
            return

        if not (data['groups']) or data['groups'][0]['screen_name'].lower() != community_name.lower():
            print(f'{community_name} ...failed')
            return

        max_post_by_date = max(data['items'], key=lambda x: x['date'])
        community['last_post_timestamp'] = max_post_by_date['date']
        community['posts'] = {}
        print(f'{community_name} ...passed')
        return community

    @commands.Cog.listener()
    async def on_ready(self):
        self.check_groups.start()

    @commands.command(name='vksend')
    async def vksend(self, ctx, vk_post_url, channel: discord.TextChannel = None):
        """Sends vk post (using link to the post)"""

        channel = channel or ctx.channel

        vk_post_url = re.findall(r'wall(-\d+_\d+)', vk_post_url)[-1]

        try:
            data = self.vk.wall.getById(posts=vk_post_url, extended=1, copy_history_depth=2)
            post = data['items'][0]
        except vk_api.exceptions.ApiError as e:
            return await ctx.send(f'⚠ Произошла ошибка `{e}`')

        vk_post = VkPost(data, post)
        embed = vk_post.generate_discord_embed()

        await channel.send(embed=embed)

    @commands.command(name='vklist')
    async def vklist(self, ctx):
        """Shows list of VK communities in database"""

        communities = self.vk_data[DatabaseKeys.vk_communities]

        max_fields = 25
        pages_count = (len(communities) - 1) // max_fields + 1

        for page in range(pages_count):
            embed = discord.Embed(
                title=f'VK Communities (Page {page + 1} of {pages_count})'
            )
            for community in communities[max_fields * page:max_fields * (page + 1)]:
                field_value = f'Channel: **<#{community["channel_id"]}> ({community["channel_id"]})**\n'
                embed.add_field(name=community['name'], value=field_value, inline=True)
            await ctx.send(embed=embed)

        if pages_count == 0:
            embed = discord.Embed(
                title='VK Communities',
                description='Empty...'
            )
            await ctx.send(embed=embed)

    @commands.command(name='vkadd')
    async def vkadd(self, ctx, channel_id: int, community_name):
        """Adds VK community to database"""

        community = self.initialize_community(community_name)
        if not community:
            return await ctx.message.add_reaction('❌')
        community['channel_id'] = channel_id
        community['name'] = community_name
        try:
            self.vk_data[DatabaseKeys.vk_communities].append(community)
            self.client.save_data()
        except Exception as e:
            return await ctx.message.add_reaction('❌')
        await ctx.message.add_reaction('✅')

    @commands.command(name='vkremove')
    async def vkremove(self, ctx, channel_id: int, community_name):
        """Removes VK community from database"""

        deleted = False
        for i, community in enumerate(self.vk_data[DatabaseKeys.vk_communities]):
            if community["channel_id"] == channel_id and community["name"] == community_name:
                self.vk_data[DatabaseKeys.vk_communities].pop(i)
                deleted = True

        await ctx.message.add_reaction("✅" if deleted else "❌")
        self.client.save_data()

    async def check_community(self, community):
        channel = self.client.get_channel(community['channel_id'])
        if not channel:
            await self.client.log_error(f'getting channel {community["channel_id"]} for {community["name"]} failed')
            return

        try:
            data = self.vk.wall.get(domain=community['name'], count=3, extended=1)
        except Exception as e:
            await self.client.log_error(f'getting wall of {community["name"]} failed', e)
            return
        if not (data['groups']) or data['groups'][0]['screen_name'].lower() != community['name'].lower():
            await self.client.log_error(f'getting data of {community["name"]} failed')
            return

        for post in data['items']:
            edited = post.get('edited', post['date'])
            post_id = str(post['id'])

            if post_id not in community['posts'] and post['date'] > community['last_post_timestamp']:

                try:
                    community['last_post_timestamp'] = post['date']

                    vk_post = VkPost(data, post)
                    embed = vk_post.generate_discord_embed(community)
                    message = await channel.send(embed=embed)

                    community['posts'][post_id] = {
                        'message_id': message.id,
                        'edited': edited
                    }

                    return community

                except Exception as e:
                    await self.client.log_error(f'sending post {post["id"]} by {community["name"]} failed', e)

            elif post_id in community['posts'] and edited > community['posts'][post_id]['edited']:

                try:
                    community['posts'][post_id]['edited'] = edited

                    vk_post = VkPost(data, post)
                    embed = vk_post.generate_discord_embed(community)
                    message_id = community['posts'][post_id]['message_id']
                    message = await channel.fetch_message(message_id)
                    await message.edit(embed=embed)

                    return community

                except Exception as e:
                    await self.client.log_error(f'editing post {post["id"]} by {community["name"]} failed', e)

    @tasks.loop(seconds=120)
    async def check_groups(self):
        try:
            for community in self.vk_data[DatabaseKeys.vk_communities]:
                await asyncio.sleep(self.waiting_time)
                try:
                    print(f'Time to... {community["name"]}')
                    result = await self.check_community(community)
                    if result:
                        self.client.save_data()
                except Exception as e:
                    print(e)
                    await self.client.log_error(f'checking {community["name"]} failed', e)
        except Exception as e:
            print('Checking groups failed')

        print('Checking groups completed')


def setup(client):
    client.add_cog(Vk(client))
