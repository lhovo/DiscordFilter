import discord
import re
import logging
import yaml
import argparse

# you need to install discord and yaml python packages 
# pip3 install discord PyYAML

class DiscordClient(discord.Client):
    async def on_ready(self):
        logging.info('Python Discord Version {}'.format(discord.__version__))
        logging.info('Logged in as')
        logging.info(self.user.name)
        logging.info('Invite: https://discordapp.com/oauth2/authorize?client_id={}&scope=bot&permissions=1024'.format(self.user.id))
        logging.info('------')
        logging.debug(self.user.id)

        for index, filters in enumerate(settings['filters']):
            if len(filters['read_channel']) == 0:
                logging.error("You must specify a read_channel in your config")
                await client.close() 

            for read_channel in filters['read_channel']:
                if not client.get_channel(read_channel):
                    logging.error("Unable to find channel, please check permissions and config {}".format(read_channel))
                    await client.close()

            send_channels = []
            for c in filters['default']:
                found = client.get_channel(c)
                if found:
                    send_channels.append(found)
                else:
                    logging.error("Unable to find channel {}".format(c))
            settings['filters'][index]['default'] = send_channels

            # Find each channel we need to post to
            for regex, channel_list in filters['filter'].items():
                send_channels = []
                for c in channel_list:
                    found = client.get_channel(c)
                    if found:
                        send_channels.append(found)
                    else:
                        logging.error("Unable to find channel {}".format(c))
                        await client.close()
                settings['filters'][index]['filter'][regex] = send_channels

        logging.info("Starting...")
        logging.info('------')

    async def on_message(self, message):
        logging.debug("Author ID: {}, User ID:{}".format(message.author.id, self.user.id))
        # dont post if we get a message we sent to a channel
        # this stops some spaming behaviour
        if message.author.id == self.user.id:
            return

        logging.info('Message from {0.author} - {0.channel.server} - {0.channel}'.format(message))

        channel_count = 0

        # find the message channel id from the config then try and match the filters
        for index, filters in enumerate(settings['filters']):
            if message.channel.id in filters['read_channel']:
                counter = 0
                # Loop through each of the channel filters
                for find, channel in filters['filter'].items():
                    counter += await self.proccess_message(message, find, channel, filter_settings=filters)

                # if we didnt post to any other channel post to the default
                if counter == 0:
                    await self.proccess_message(message, find, channel=filters['default'], filter_settings=filters, default_post=True)

                channel_count += 1

        if channel_count == 0:
            logging.info('Mesage not found in any read_channels {0.channel.server} - {0.channel}'.format(message))

    async def proccess_message(self, message, find, channel, filter_settings, default_post=False):
        # If we have at least one channel to post to lets contiune
        if len(channel) > 0:
            # is this message a embeded message or a regular message
            if message.embeds:
                for embedMsg in message.embeds:
                    if 'description' in embedMsg and (find.search(embedMsg['description']) or default_post):
                        for ch in channel:
                            await self.send_embed_message(ch, embedMsg, filter_settings)

            elif find.search(message.content) or default_post:
                for ch in channel:
                    #await self.send_embed_message(ch, dict(description=message.content, thumbnail=dict(url='https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/20.png'), url='https://map.poketrack.xyz/?lat=-27.477498355998282&lon=153.02317410955516&name=Whiscash'), filter_settings)
                    await self.send_embed_message(ch, dict(description=message.content), filter_settings)
            else:
                return 0
            return 1
        else:
            logging.info("No channels for Search {}".format(find))
        return 0

    async def send_embed_message(self, channel, embed_content, filter_settings):
        values = dict(description=embed_content['description'])
        logDes = embed_content['description'].split('\n')[0]
        reConfig = {}

        # get all the values from the Regex
        if 'title' in embed_content and embed_content['title']:
            if 'title_re' in filter_settings and filter_settings['title_re']:
                regexSearch = filter_settings['title_re'].search(embed_content['title'])
                reConfig.update(regexSearch.groupdict())
            values['title'] = embed_content['title']

        if 'url' in embed_content and embed_content['url']:
            if 'url_re' in filter_settings and filter_settings['url_re']:
                regexSearch = filter_settings['url_re'].search(embed_content['url'])
                reConfig.update(regexSearch.groupdict())
            values['url'] = embed_content['url']

        # get all the values from the Regex
        if 'thumbnail' in embed_content and 'url' in embed_content['thumbnail'] and 'thumbnail_re' in filter_settings and filter_settings['thumbnail_re']:
            regexSearch = filter_settings['thumbnail_re'].search(embed_content['thumbnail']['url'])
            reConfig.update(regexSearch.groupdict())

        if 'image' in embed_content and 'url' in embed_content['image'] and 'image' in filter_settings and filter_settings['image']:
            regexSearch = filter_settings['image'].search(embed_content['image']['url'])
            reConfig.update(regexSearch.groupdict())

        # Convert values to a float or int as needed
        for key, value in reConfig.items():
            try:
                reConfig[key] = float(reConfig[key])
                if reConfig[key] == int(reConfig[key]):
                    reConfig[key] = int(reConfig[key])
            except ValueError:
                logging.debug("Not a float")
        logging.info(reConfig)

        if 'title' in filter_settings and filter_settings['title']:
            values['title'] = filter_settings['title'].format(**reConfig)

        # Start building up the embeded object with what we have so far
        embed = discord.Embed(**values)

        # Set the thumbnail image if found
        if 'thumbnail' in filter_settings and filter_settings['thumbnail']:
            embed.set_thumbnail(url=filter_settings['thumbnail'].format(**reConfig))
        elif 'thumbnail' in embed_content and 'url' in embed_content['thumbnail']:
            embed.set_thumbnail(url=embed_content['thumbnail']['url'])

        # Set the image if found
        if 'image' in filter_settings and filter_settings['image']:
            embed.set_image(url=filter_settings['image'].format(**reConfig))
        elif 'image' in embed_content and 'url' in embed_content['image']:
            embed.set_image(url=embed_content['image']['url'])

        logging.info('Posting to {channel.server} - {channel} - {description}'.format(channel=channel, description=logDes))
        await client.send_message(channel, embed=embed)

# https://discordpy.readthedocs.io/en/rewrite/intro.html
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Discord Fiter')
    parser.add_argument('-c', '--config', type=str, required=True,
                    help='location of the config file')
    args = parser.parse_args()

    logging.basicConfig(format='%(asctime)s - %(levelname)s:%(message)s', level=logging.INFO)
    with open(args.config, 'r') as f:
        settings = yaml.load(f)

    # Take all the regex and compile it before we go any futher
    for index, filters in enumerate(settings['filters']):
        for item in ['title_re', 'thumbnail_re', 'url_re', 'image_re']:
            if item in filters and filters[item]:
                settings['filters'][index][item] = re.compile(filters[item], re.M | re.I)

        newFilters = {}
        for key, val in filters['filter'].items():
            newKey = re.compile(key, re.M | re.I)
            newFilters[newKey] = val
        settings['filters'][index]['filter'] = newFilters

    client = DiscordClient()
    client.run(settings['discord_bot_token'])
