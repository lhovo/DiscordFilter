import discord
import re
import logging
import yaml
import argparse
import pycurl

# you need to install discord and yaml python packages 
# pip3 install discord PyYAML pycurl

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
                for find, channels in filters['filter'].items():
                    counter += await self.proccess_message(message, find, channels, filter_settings=filters)
                logging.info("Posted to {}".format(counter))
                # if we didnt post to any other channel post to the default
                if counter == 0:
                    await self.proccess_message(message, None, filters['default'], filter_settings=filters, default_post=True)

                channel_count += 1

        if channel_count == 0:
            logging.info('Mesage not found in any read_channels {0.channel.server} - {0.channel}'.format(message))
            if message.embeds:
                if 'description' in message.embeds[0]:
                    logging.info('Embed: {}'.format(message.embeds[0]['description']))
            else:
                logging.info('Content: {}'.format(message.content))

    async def proccess_message(self, message, find, channels, filter_settings, default_post=False):
        # If we have at least one channel to post to lets contiune
        postCount = 0
        if len(channels) > 0:
            # is this message a embeded message or a regular message
            if message.embeds:
                for embedMsg in message.embeds:
                    try:
                        logging.info(embedMsg)
                    except:
                        pass
                    if 'description' in embedMsg and (default_post or find.search(embedMsg['description'])):
                        for ch in channels:
                            await self.send_embed_message(ch, embedMsg, filter_settings)
                            postCount += 1

            elif default_post or find.search(message.content):
                for ch in channels:
                    #await self.send_embed_message(ch, dict(description=message.content, thumbnail=dict(url='https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/20.png'), url='https://map.poketrack.xyz/?lat=-27.477498355998282&lon=153.02317410955516&name=Whiscash'), filter_settings)
                    await self.send_embed_message(ch, dict(description=message.content), filter_settings)
                    postCount += 1
        else:
            logging.info("No channels for Search {}".format(find))
        return postCount

    async def send_embed_message(self, channel, embed_content, filter_settings):
        values = dict(description=embed_content['description'])
        logDes = embed_content['description'].split('\n')[0]
        reConfig = {}

        # get all the values from the Regex
        def re_serch(items):
            content = None
            filterStr = '{}_re'.format(items[0])

            if items[0] in embed_content:
                if len(items) > 1:
                    if items[1] in embed_content[items[0]] and embed_content[items[0]][items[1]]:
                        content = embed_content[items[0]][items[1]]
                elif embed_content[items[0]]:
                    content = embed_content[items[0]]
                    values[items[0]] = embed_content[items[0]]

                if content and filterStr in filter_settings:
                    regexSearch = filter_settings[filterStr].search(content)
                    if regexSearch:
                        return regexSearch.groupdict()
            logging.info("Unable to match {} {}".format(filterStr, content))
            return {}
        
        if filter_settings['url_follow'] and 'url' in embed_content and embed_content['url']:
            try:
                c = pycurl.Curl()
                c.setopt(pycurl.URL, embed_content['url'])
                c.setopt(pycurl.FOLLOWLOCATION, 1)
                c.setopt(pycurl.HEADER, 1)
                c.setopt(pycurl.NOBODY, 1) # header only, no body
                c.setopt(pycurl.USERAGENT, "Mozilla/5.0 (Windows; U; Windows NT 5.1; de; rv:1.9.2.3) Gecko/20100401 Firefox/3.6.3")
                c.setopt(pycurl.HTTPHEADER, [b'Content-Type: text/plain'])
                c.setopt(pycurl.WRITEFUNCTION, lambda x: None)
                c.perform()
                # print(c.getinfo(pycurl.HTTP_CODE)
                newUrl = c.getinfo(pycurl.EFFECTIVE_URL)
                if newUrl:
                    embed_content['url'] = newUrl
                    logging.info("Using new Url {}".format(newUrl))
            except pycurl.error as e:
                logging.error(e.args[0])

        reConfig.update(re_serch(['title']))
        reConfig.update(re_serch(['url']))
        reConfig.update(re_serch(['thumbnail', 'url']))
        reConfig.update(re_serch(['image','url']))

        # Convert values to a float or int as needed
        for key, value in reConfig.items():
            try:
                reConfig[key] = float(reConfig[key])
                if reConfig[key] == int(reConfig[key]):
                    reConfig[key] = int(reConfig[key])
            except ValueError:
                logging.debug("Not a float: {}".format(reConfig[key]))
        logging.info("re_values: {}".format(reConfig))

        # Check to se if we can insert gathered values into the given format
        def re_insert(item):
            if item in filter_settings and filter_settings[item]:
                try:
                    values[item] = filter_settings[item].format(**reConfig)
                except KeyError:
                    logging.info("Unable to substitute {} :for: {}".format(filter_settings[item], item))

        re_insert('title')
        re_insert('url')        

        logging.info("Vales: {}".format(values))
        # Start building up the embeded object with what we have so far
        embed = discord.Embed(**values)

        # Set the image if found
        def set_item(item, function):
            try:
                if item in filter_settings and filter_settings[item]:
                    newItem = filter_settings[item].format(**reConfig)
            except KeyError:
                newItem = None

            if newItem:
                function(url=newItem)
            elif item in embed_content and 'url' in embed_content[item]:
                function(url=embed_content[item]['url'])

        set_item('thumbnail', embed.set_thumbnail)
        set_item('image', embed.set_image)

        logging.info('Posting to {channel.server} - {channel} - {description}'.format(channel=channel, description=logDes))
        await client.send_message(channel, embed=embed)

logging.basicConfig(format='%(asctime)s - %(levelname)s:%(message)s', level=logging.INFO)

# https://discordpy.readthedocs.io/en/rewrite/intro.html
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Discord Fiter')
    parser.add_argument('-c', '--config', type=str, required=True,
                    help='location of the config file')
    args = parser.parse_args()

    with open(args.config, 'r') as f:
        settings = yaml.load(f)

    # Take all the regex and compile it before we go any futher
    for index, filters in enumerate(settings['filters']):
        for item in ['title_re', 'thumbnail_re', 'url_re', 'image_re']:
            if item in filters:
                if filters[item]:
                    settings['filters'][index][item] = re.compile(filters[item], re.M | re.I)
                else:
                    del(settings['filters'][index][item])

        newFilters = {}
        for key, val in filters['filter'].items():
            newKey = re.compile(key, re.M | re.I)
            newFilters[newKey] = val
        settings['filters'][index]['filter'] = newFilters

    client = DiscordClient()
    client.run(settings['discord_bot_token'])
