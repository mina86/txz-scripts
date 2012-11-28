#!/usr/bin/python

import collections
import csv
import os
import re
import traceback
import urllib
import xml.etree.ElementTree as ET


### Configuration

OUTPUT_DIR = 'data/'

KERNEL_RSS_URL = 'http://www.kernel.org/kdist/rss.xml'

SLACKWARE_URLS = (
    'http://ftp5.gwdg.de/pub/linux/slackware/slackware/',
    'http://mirror.netcologne.de/slackware/slackware/'
)

FAIF_URL = 'http://faif.us/feeds/cast-ogg/'


### Common

SHORT_URL = 'http://ur1.ca/'
WS_RE = re.compile(r'\s+')

def getXMLRoot(url, *args, **kw):
    return ET.parse(urllib.urlopen(url, *args, **kw)).getroot()


def normaliseString(text):
    return WS_RE.sub(' ', text.strip())


def saveData(filename, data):
    with open(filename + '~', 'w') as fd:
        fd.write(data)
        fd.flush()
        os.fsync(fd.fileno())
    os.rename(filename + '~', filename)

def readCSV(filename):
    if not os.path.isfile(filename):
        return
    with open(filename) as fd:
        reader = csv.reader(fd)
        for row in reader:
            yield tuple(v.decode('utf-8') for v in row)

def writeCSV(filename, rows):
    with open(filename + '~', 'w') as fd:
        writer = csv.writer(fd)
        for row in rows:
            writer.writerow(tuple(v.encode('utf-8') for v in row))
        fd.flush()
        os.fsync(fd.fileno())
    os.rename(filename + '~', filename)

def getShortLink(url):
    query = urllib.urlencode([('longurl', url)])
    root = getXMLRoot(SHORT_URL, query)
    for a in root.findall(".//p[@class='success']a"):
        return a.attrib.get('href')


### Kernel

KERNEL_TITLE_CHECK = re.compile(r'^(.*): (.*)$').search
KERNEL_TYPE_ORDER = ( 'mainline', 'stable' )
KERNEL_SORT_KEY = re.compile(r'[-.]').split

def getKernelTypes(url):
    types = collections.defaultdict(set)
    root = getXMLRoot(url)
    for title in root.findall('.//{http://purl.org/rss/1.0/}title'):
        m = KERNEL_TITLE_CHECK(title.text)
        if not m:
            continue
        types[m.group(2)].add(m.group(1))

    return types

def buildKernelTopic(types):
    topic = []
    for tp in KERNEL_TYPE_ORDER:
        versions = types.pop(tp, None)
        if versions:
            versions = sorted(versions, key=KERNEL_SORT_KEY, reverse=True)
            topic.append(', '.join(versions))
    return '; '.join(topic)

def kernel(_):
    types = getKernelTypes(KERNEL_RSS_URL)
    return buildKernelTopic(types)
    if topic:
        saveTopic(KERNEL_OUTPUT_FILE, topic)


### Slackware

SLACK_DATA_CHECK = re.compile(r'ANNOUNCE\.([0-9._]*)').search

def getSlackwareVersion(url):
    m = SLACK_DATA_CHECK(urllib.urlopen(url).read())
    if m:
        return m.group(1).replace('_', '.')

def slackware(_):
    for url in SLACKWARE_URLS:
        try:
            data = getSlackwareVersion(url)
            if data:
                return data
        except:
            traceback.print_exc()


### FAIF

FAIF_TITLE_RE = re.compile(r'^(?:episode\s*)?0x([0-9a-f]+)', re.I)

def getFAIFVersions(url):
    root = getXMLRoot(FAIF_URL)
    for item in root.findall('.//item'):
        title = item.find('title')
        link = item.find('link')
        date = item.find('pubDate')
        if title is None or link is None:
            continue

        title = normaliseString(title.text)
        m = FAIF_TITLE_RE.search(title)
        if not m:
            continue

        ver = m.group(1).upper()
        title = '0x' + ver + title[m.end(1):]

        link = normaliseString(link.text)
        if date is not None:
            date = normaliseString(date.text)

        yield (ver, title, link, None, date)

def faif(filename):
    versions = dict()
    links = dict()

    for ver, title, full_link, short_link, date in readCSV(filename):
        versions[ver] = (ver, title, full_link, short_link, date)
        if short_link:
            links[full_link] = short_link

    for ver, title, full_link, _, date in getFAIFVersions(FAIF_URL):
        short_link = links.get(full_link)
        if not short_link:
            v = versions.get(ver)
            if v:
                short_link = v[3]
        if not short_link:
            short_link = getShortLink(full_link)
        versions[ver] = (ver, title, full_link, short_link or '', date)

    versions = versions.values()
    versions.sort(reverse=True)
    writeCSV(filename, versions)


### Main

MODULES = [
    ('kernel', kernel),
    ('slack', slackware),
    ('faif', faif),
]

def main():
    for filename, callback in MODULES:
        try:
            filename = os.path.join(OUTPUT_DIR, filename)
            data = callback(filename)
            if data:
                saveData(filename, data)
        except:
            traceback.print_exc()


if __name__ == '__main__':
    main()