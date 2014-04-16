import urllib
import urllib2
import re
import json
import time
from datetime import datetime
from urlparse import urlparse, parse_qs
from traceback import format_exc

from bs4 import BeautifulSoup

import xbmcplugin
import xbmcgui
import xbmcaddon
import xbmcvfs

addon = xbmcaddon.Addon()
addon_version = addon.getAddonInfo('version')
addon_id = addon.getAddonInfo('id')
icon = addon.getAddonInfo('icon')
news_domain = 'http://video.foxnews.com'
business_domain = 'http://video.foxbusiness.com'


def addon_log(string):
    try:
        log_message = string.encode('utf-8', 'ignore')
    except:
        log_message = 'addonException: addon_log'
    xbmc.log("[%s-%s]: %s" %(addon_id, addon_version, log_message),level=xbmc.LOGDEBUG)


def make_request(url, data=None, headers=None):
    addon_log('Request URL: %s' %url)
    if headers is None:
        headers = {
            'User-agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:25.0) Gecko/20100101 Firefox/25.0',
            'Referer': 'http://video.foxnews.com'
            }
    try:
        req = urllib2.Request(url, data, headers)
        response = urllib2.urlopen(req)
        data = response.read()
        addon_log(str(response.info()))
        response.close()
        return data
    except urllib2.URLError, e:
        addon_log('We failed to open "%s".' %url)
        if hasattr(e, 'reason'):
            addon_log('We failed to reach a server.')
            addon_log('Reason: %s' %e.reason)
        if hasattr(e, 'code'):
            addon_log('We failed with error code - %s.' %e.code)


def get_soup(url):
    data = make_request(url)
    if data:
        return BeautifulSoup(data, 'html.parser')


def get_categories(url=None):
        add_dir('Fox News - Show Clips', 'http://video.foxnews.com/#show-clips', icon, 'get_sub_cat')
        add_dir('Fox News - News Clips', 'http://video.foxnews.com/#news-clips', icon, 'get_sub_cat')
        add_dir('Fox Business News - Show Clips', 'http://video.foxbusiness.com/#show-clips', icon, 'get_sub_cat')
        add_dir('Fox Business News - News Clips', 'http://video.foxbusiness.com/#news-clips', icon, 'get_sub_cat')

#    if url is None:
#        # live streams are still WIP
#        # add_dir('Watch Live', news_domain + '/playlist/live-landing-page/', icon, 'get_playlist')
#        add_dir('FoxBusiness.com', business_domain, icon, 'get_categories')
#        url = news_domain
#        cat_url = url
#        cat_url = url + '/playlist/featured-editors-picks/'
#    else:
#        cat_url = url + '/playlist/latest-video-latest-video/'
#    soup = get_soup(cat_url)
#    for i in soup.find('nav')('a'):
#        add_dir(i.string.encode('utf-8'), url + i['href'], icon, 'get_sub_cat')


def get_sub_categories(url):
    urlbase, utype = url.split('#')
    print "url = "+str(url)
    data = make_request(url)
#    print "data = "+str(data)
    sub_cats = re.compile('<div class="column footer-%s">(.+?)</div>' % (utype),re.DOTALL).findall(data)
    sub_cats = re.compile('href="(.+?)">(.+?)<',re.DOTALL).findall(sub_cats[0])
    for url,name in sub_cats:
      add_dir(name.encode('utf-8'), urlbase+url, icon, 'get_playlist')



#    soup = get_soup(url)
#    items_soup = soup('div', attrs={'id' : 'shows'})[0]('a')
#    items_soup = soup.find('div')('box box-4 sidebar')[0]('a')
#    current = False
#    items = []
#    for i in items_soup:
#        item_url = 'http:' + i['href']
#        if item_url == url:
#            current = (i.string.encode('utf-8'), item_url, icon, 'get_playlist')
#            continue
#        items.append((i.string.encode('utf-8'), item_url, icon, 'get_playlist'))
#    if not current:
#        current_name = soup.body.h1.contents[0].strip().encode('utf-8')
#        current = (current_name, url, icon, 'get_playlist')
#    items.insert(0, current)
#    for i in items:
#        add_dir(*i)


def get_video(video_id):
    url = news_domain + '/v/feed/video/%s.js?template=fox' %video_id
    data = json.loads(make_request(url))
    items = data['channel']['item']['media-group']['media-content']
    m3u8_url = [i['@attributes']['url'] for i in items if
            i['@attributes']['type'] == 'application/x-mpegURL']
    if m3u8_url:
        return m3u8_url[0]


def get_smil(video_id):
    if video_id.startswith('http'):
        smil_url = video_id
    else:
        smil_url = news_domain + '/v/feed/video/%s.smil' %video_id
    soup = get_soup(smil_url)
    try:
        base = soup.find('meta', attrs={'name': "rtmpAuthBase"})['content']
    except:
        base = soup.find('meta', attrs={'name': "httpBase"})['content']
    dict_list = [{'url': i['src'], 'bitrate': i['system-bitrate']} for i in soup('video')]
    path = user_select(dict_list)
    addon_log('Resolved from smil: %s' %base + path)
    return base + path.replace(' ', '')



def user_select(dict_list):
    dialog = xbmcgui.Dialog()
    ret = dialog.select('Choose a stream', ['Bitrate: %s' %i['bitrate'] for i in dict_list])
    if ret > -1:
        return dict_list[ret]['url']


def resolve_url(url):
    succeeded = False
    resolved_url = None
    if isinstance(url, list):
        resolved_url = user_select(url)
    elif url.endswith('smil'):
        resolved_url = get_smil(url)
    elif url.endswith('.mp4') or url.endswith('.m3u8'):
        resolved_url = url
    if resolved_url:
        succeeded = True
    else:
        resolved_url = ''
    item = xbmcgui.ListItem(path=resolved_url)
    xbmcplugin.setResolvedUrl(int(sys.argv[1]), succeeded, item)


def get_playlist(url):
    data = make_request(url)
    print "get_playlist data = "+str(data)
    pattern = 'playlistId: "(.+?)"'
    match = re.findall(pattern, data)
    if not match:
        addon_log('Did not find playlist id')
        return
    domain = news_domain
    if business_domain in url:
        domain = business_domain
    json_url = domain + '/v/feed/playlist/%s.js?template=fox' %match[0]
    print "json_url = "+str(json_url)
    json_data = json.loads(make_request(json_url), 'utf-8')
    items = json_data['channel']['item']
    for i in items:
        item_url = None
        state = i['media-status']['@attributes']['state']
        title = i['title'].encode('utf-8')
        if state != 'active':
            addon_log('item state: %s: %s' %(title, state))
            continue
        try:
            item_url = [x['@attributes']['url'] for
                            x in i['media-group']['media-content'] if
                                x['@attributes']['type'] == 'application/x-mpegURL'][0]
        except:
            addon_log('m3u8 url was not found: %s' %format_exc())
        if not item_url:
            try:
                mp4_items = [{'url': x['@attributes']['url'],
                              'bitrate':  x['@attributes']['bitrate']} for
                                  x in i['media-group']['media-content'] if
                                      x['@attributes']['type'] == 'video/mp4']
                if not mp4_items or len(mp4_items) < 1:
                    raise
                if len(mp4_items) == 1:
                    item_url = mp4_items[0]['url']
                else:
                    item_url = mp4_items
            except:
                addon_log('mp4 url was not found: %s' %format_exc())
        if not item_url:
            try:
                item_url = [x['@attributes']['url'] for
                                x in i['media-group']['media-content'] if
                                    x['@attributes']['type'] == 'application/smil+xml'][0]
            except:
                addon_log('smil url was not found: %s' %format_exc())
        if not item_url:
            try:
                enclosure_url = i['enclosure']['@attributes']['url']
                if enclosure_url:
                    item_url = enclosure_url
                else:
                    raise
            except:
                addon_log('addonException: get_playlist: unable to resolve url')
        if not item_url:
            continue
        thumb = i['media-group']['media-thumbnail']['@attributes']['url']
        date_time = datetime(*(time.strptime(i['pubDate'][:-6], '%a, %d %b %Y %H:%M:%S')[:6]))
        info = {
            'Title': title,
            'Date': date_time.strftime('%d.%m.%Y'),
            'Premiered': date_time.strftime('%d-%m-%Y'),
            'Duration': get_duration(i['itunes-duration']),
            'Plot': i['description'].encode('utf-8')
            }
        add_dir(title, item_url, thumb, 'resolve_url', info)


def get_duration(duration):
    if duration is None:
        return 1
    d_split = duration.split(':')
    if len(d_split) == 4:
        del d_split[-1]
    minutes = int(d_split[-2])
    if int(d_split[-1]) >= 30:
        minutes += 1
    if len(d_split) >= 3:
        minutes += (int(d_split[-3]) * 60)
    if minutes < 1:
        minutes = 1
    return minutes


def get_params():
    p = parse_qs(sys.argv[2][1:])
    for i in p.keys():
        p[i] = p[i][0]
    return p


def add_dir(name, url, iconimage, mode, info={}):
    params = {'name': name, 'url': url, 'mode': mode}
    url = '%s?%s' %(sys.argv[0], urllib.urlencode(params))
    listitem = xbmcgui.ListItem(name, iconImage="DefaultFolder.png", thumbnailImage=iconimage)
    isfolder = True
    if mode == 'resolve_url':
        isfolder = False
        listitem.setProperty('IsPlayable', 'true')
    listitem.setInfo(type="Video", infoLabels=info)
    xbmcplugin.addDirectoryItem(int(sys.argv[1]), url, listitem, isfolder)



params = get_params()

addon_log(repr(params))

try:
    mode = params['mode']
except:
    mode = None

if mode == None:
    get_categories()
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 'get_categories':
    get_categories(params['url'])
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 'get_sub_cat':
    get_sub_categories(params['url'])
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 'get_playlist':
    get_playlist(params['url'])
    xbmcplugin.setContent(int(sys.argv[1]), 'episodes')
    xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_DATE)
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 'resolve_url':
    resolve_url(params['url'])