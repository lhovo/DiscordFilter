import discord
import re
import logging
import yaml
import argparse
import pycurl
import requests
import os

# you need to install discord and yaml python packages 
# pip3 install discord PyYAML pycurl requests

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

        if args.last:
            async for message in client.logs_from(client.get_channel(read_channel), limit=2):
                await self.on_message(message)

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
                embed = self.proccess_message(message, filters)
                for find, channels in filters['filter'].items():
                    if len(channels) > 0:
                        embedMsg = message.embeds[0]
                        for channel in channels:
                            if ('description' in embedMsg and find.search(embedMsg['description'])) or \
                               ('title' in embedMsg and find.search(embedMsg['title'])):
                                await self.postMessage(channel, embed)
                                counter += 1
                    else:
                        logging.info("No channels for Search {}".format(find))
                logging.info("Posted to {}".format(counter))
                # if we didnt post to any other channel post to the default
                if counter == 0:
                    for channel in filters['default']:
                        await self.postMessage(channel, embed)

                channel_count += 1

        if channel_count == 0:
            logging.info('Mesage not found in any read_channels {0.channel.server} - {0.channel}'.format(message))
            if message.embeds:
                if 'description' in message.embeds[0]:
                    logging.info('Embed: {}'.format(message.embeds[0]['description'].split('\n')[0]))
            else:
                logging.info('Content: {}'.format(message.content))

        logging.info('-------------------------------------------------')

    def proccess_message(self, message, filter_settings):
        # is this message a embeded message or a regular message
        if message.embeds:
            embedMsg = message.embeds[0]
            try:
                logging.info("EmbedMsg: {}".format(embedMsg))
            except:
                pass
            embed = self.create_embed_message(embedMsg, filter_settings)

        else:
            embed = self.create_embed_message(dict(description=message.content), filter_settings)
        return embed

    async def postMessage(self, channel, embed):
        logging.info('Posting to {channel.server} - {channel}'.format(channel=channel))
        await client.send_message(channel, embed=embed)

    def create_embed_message(self, embed_content, filter_settings):
        values = dict()
        reConfig = dict()

        # get all the values from the Regex
        def re_serch(items):
            content = None
            filterStr = '{}_re'.format(items[0])
            searchItems = {}

            if items[0] in embed_content:
                if len(items) > 1:
                    if items[1] in embed_content[items[0]] and embed_content[items[0]][items[1]]:
                        content = embed_content[items[0]][items[1]]
                elif embed_content[items[0]]:
                    content = embed_content[items[0]]
                    values[items[0]] = embed_content[items[0]]

                if content and filterStr in filter_settings:
                    for search in filter_settings[filterStr]:
                        regexSearch = search.search(content)
                        if regexSearch:
                            searchItems.update(regexSearch.groupdict())
            if searchItems == {} and content != None:
                logging.info("Unable to match {} {}".format(filterStr, content))
            return searchItems
        
        if 'url_follow' in filter_settings and filter_settings['url_follow'] and 'url' in embed_content and embed_content['url']:
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
                logging.debug("Curl HTTP_CODE: {}".format(c.getinfo(pycurl.HTTP_CODE)))
                newUrl = c.getinfo(pycurl.EFFECTIVE_URL)
                if newUrl:
                    embed_content['url'] = newUrl
                    logging.info("Using new Url {}".format(newUrl))
            except pycurl.error as e:
                logging.error("pycurl Error: {}".format(e.args[0]))

        reConfig.update(re_serch(['title']))
        reConfig.update(re_serch(['url']))
        reConfig.update(re_serch(['description']))
        reConfig.update(re_serch(['thumbnail', 'url']))
        reConfig.update(re_serch(['image','url']))

        # Convert values to a float or int as needed
        for key, value in reConfig.items():
            try:
                reConfig[key] = float(reConfig[key])
                if reConfig[key] == int(reConfig[key]):
                    reConfig[key] = int(reConfig[key])
            except (ValueError, TypeError):
                logging.debug("Not a Number: {}".format(reConfig[key]))
        reConfig.update(format_modules)
        logging.info("re_values: {}".format(reConfig))
        
        lookup_content = None
        if 'lookup_url' in filter_settings and 'lookup_type' in filter_settings and filter_settings['lookup_url']:
            try:
                response = requests.get(''.join(filter_settings['lookup_url']).format(**reConfig))
                if filter_settings['lookup_type'] == 'json':
                    lookup_content = response.json()

                    # try goto key from config
                    if 'lookup_keys' in filter_settings:
                        for data in filter_settings['lookup_keys']:
                            if data in lookup_content or isinstance(data, int):
                                lookup_content = lookup_content[data]
                                logging.debug("lookup_url: found key {}".format(data))
                            else:
                                logging.debug("lookup_url: unable to find {}".format(data))
                                break
            except (requests.exceptions.MissingSchema, requests.exceptions.ConnectionError) as e:
                logging.error("lookup: {}".format(e))
            except KeyError as e:
                logging.error("Lookup: Unable to find key {}".format(e))

        # parse the lookup data into the config
        if lookup_content:
            embed_content['lookup'] = lookup_content
            reConfig.update(re_serch(['lookup']))
        else:
            logging.info("no Lookup info found")

        # Check to see if we can insert gathered values into the given format
        def re_insert(item):
            if item in filter_settings and filter_settings[item]:
                newString = ''
                for search in filter_settings[item]:
                    try:
                        newString += search.format(**reConfig)
                    except KeyError:
                        logging.info("Unable to substitute {} :for: {}".format(search.strip(), item))

                if newString != '':
                    values[item] = newString

        re_insert('title')
        re_insert('url')
        re_insert('description')      

        logging.info("Values: {}".format(values))
        # Start building up the embeded object with what we have so far
        embed = discord.Embed(**values)

        # Set the image if found
        def set_item(item, function):
            try:
                if item in filter_settings and filter_settings[item]:
                    newItem = ''.join(filter_settings[item]).format(**reConfig)
            except KeyError:
                newItem = None

            if newItem:
                function(url=newItem)
            elif item in embed_content and 'url' in embed_content[item]:
                function(url=embed_content[item]['url'])

        set_item('thumbnail', embed.set_thumbnail)
        set_item('image', embed.set_image)

        return embed

logging.basicConfig(format='%(asctime)s - %(levelname)s:%(message)s', level=logging.INFO)

# https://discordpy.readthedocs.io/en/rewrite/intro.html
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Discord Fiter')
    parser.add_argument('-c', '--config', type=str, required=True,
                    help='location of the config file')
    parser.add_argument('-l', '--last', default=False, action="store_true",
                    help='grab the last message and proccess it, useful for debugging')
    args = parser.parse_args()

    # import all the formaters
    format_modules = {}
    fileRE = re.compile('format_(?P<file>.*)\.py$', re.M | re.I)
    for file in os.listdir('.'):
        found = fileRE.search(file)
        if found:
            format_import = __import__(file[:-3])
            exec("format_modules[found.groupdict()['file']] = format_import.{}()".format(found.groupdict()['file']))

    logging.info('Imported Modules: {}'.format(', '.join(format_modules.keys())))

    with open(args.config, 'r') as f:
        settings = yaml.load(f)

    # Take all the regex and compile it before we go any futher
    # This allows to pickup simple errors quickly
    for index, filters in enumerate(settings['filters']):
        for item in [re for re in filters.keys() if re.endswith('_re')]:
            if item.endswith('_re'):
                if filters[item]:
                    for reIndex, reItem in enumerate(filters[item]):
                        settings['filters'][index][item][reIndex] = re.compile(reItem, re.M | re.I)
                else:
                    del(settings['filters'][index][item])

        newFilters = {}
        for key, val in filters['filter'].items():
            newKey = re.compile(key, re.M | re.I)
            newFilters[newKey] = val
        settings['filters'][index]['filter'] = newFilters

    client = DiscordClient()
    client.run(settings['discord_bot_token'])
