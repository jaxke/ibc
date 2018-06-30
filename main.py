import subprocess
from bs4 import BeautifulSoup
import youtube_dl
from pdb import set_trace as st
import requests
import sys

# TODO geo-bypass in ytdl?

hdr = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) \
                Chrome/42.0.2311.90 Safari/537.36'}
iplayer_url = "https://www.bbc.co.uk/iplayer"
base_url = "https://www.bbc.co.uk"


class BBCShow:
    href = ""
    title = ""
    category = ""
    additional = ""
    duration = ""


class BBCEpisode:
    href = ""
    show_name = ""
    title = ""
    episode_number = 0
    duration = ""

class BBCCategory:
    href = ""
    title = ""


# tvip-cats tvip-nav-clearfix
def get_categories():
    categories = []
    r = requests.get(url=iplayer_url, headers=hdr)
    soup = BeautifulSoup(r.content, "html.parser")
    u_lists = soup.find_all("ul", {"class": ["tvip-cats", "tvip-nav-clearfix"]})
    for ul in u_lists:
        cats_in_ul = ul.find_all("a", {"class": ["typo", "typo--canary", "stat"]})
        for cat in cats_in_ul:
            c = BBCCategory()
            c.href = base_url + cat.get("href")
            c.title = cat.contents[0]
            categories.append(c)
    return categories


def listing_index(index_url):
    items = []
    r = requests.get(url=index_url, headers=hdr)
    soup = BeautifulSoup(r.content, "html.parser")
    el = soup.find_all("a", {"class": ["content-item__link", "gel-layout", "gel-layout--flush"]})
    for e in el:
        if e.get("data-object-type") == "editorial-promo":
            continue
        el_info = e.get("aria-label")
        el_href = e.get("href")
        iplayer_item = BBCShow()
        iplayer_item.href = base_url + el_href
        iplayer_item.title = el_info.split("Description")[0][:-2]
        iplayer_item.category = el_info.split("Description")[1].split(".")[0][2:]
        iplayer_item.additional = el_info.split("Description")[1].split(".")[1][1:]
        iplayer_item.duration = el_info.split("Duration")[1].split(".")[0][2:]
        items.append(iplayer_item)
    return items


# TODO Does not work for a serie with no View all button
def listing_serie(parent_serie):
    episodes = []
    r = requests.get(url=parent_serie.href, headers=hdr)
    soup = BeautifulSoup(r.content, "html.parser")
    try:
        view_all = soup.find("a", {"class": ["button", "section__header__cta", "button--clickable"]}).get("href")
        r = requests.get(url=base_url + view_all, headers=hdr)
    except AttributeError:
        pass    # This is not a serie or there is no View all button
    soup = BeautifulSoup(r.content, "html.parser")
    eps_found = get_eps_in_page(soup)
    if eps_found:
        episodes += get_eps_in_page(soup)
    else:   # if that method returns False, it didn't find any episodes
        return parent_serie
    for i in range(6):  # TODO Fix this
        try:
            next_page = soup.find("a", {"class": ["lnk pagination__direction", "pagination__direction--next", "pagination__direction--large"]}).get("href")
        # Nonetype was not returned and .get() raises AE
        except AttributeError:
            break
        r_next = requests.get(url=r.url + next_page, headers=hdr)
        next_soup = BeautifulSoup(r_next.content, "html.parser")
        episodes += get_eps_in_page(next_soup)
    return episodes


def get_eps_in_page(soup):
    episodes = []
    try:
        div_content = soup.find("div", {"class": ["grid", "list__grid"]}).find_all("a", {"class": ["content-item__link", "gel-layout", "gel-layout--flush"]}) # grid list__grid
        for content in div_content:
            el_info = content.get("aria-label")
            ep = BBCEpisode()
            ep.href = base_url + content.get("href")
            #ep.show_name = parent_serie.title
            ep.title = el_info.split("Description")[0]
            ep.duration = el_info.split("Duration: ")[1].split(".")[0]
            episodes.append(ep)
        # return episodes[::-1]
        return episodes
    except AttributeError:
        return    # This is a one-part show

def extract_link(href):
    r = requests.get(url=href, headers=hdr)
    soup = BeautifulSoup(r.content, "html.parser")
    links = soup.find_all("link")
    for link in links:
        if link.get("rel", None):
            if link.get("rel")[0] == "canonical":
                return link.get("href")

def play(episode, all_eps):
    # Is a one part "show", maybe a documentary etc... OR autoplay is disabled
    if isinstance(episode, BBCShow) or not all_eps:
        real_link = extract_link(episode.href)
        print("PLAYING " + episode.title + ". Press Q to STOP playback.")
        #subprocess.call(["mpv", episode.href], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.call(["mpv", episode.href])
    else:
        ep_index = all_eps.index(episode)
        for i in range(ep_index, len(all_eps)):
            print("PLAYING " + all_eps[i].title + ". Press Q to STOP playback.")
            subprocess.call(["mpv", all_eps[i].href], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if i != len(all_eps) - 1:
                if str(input("Watch next episode Y/N: ")).lower() == "y":
                    continue
                else:
                    return


# TODO Not working
def download(episode):
    ydl_opts = {"hls_prefer_native": True}
    ydl_opts['outtmpl'] = "%(title)s.%(ext)s"
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        ydl.download([episode.href])


# Only finds items in first page, rest are usually irrelevant(and dev is lazy)
def search(phrase):
    search_url = "https://www.bbc.co.uk/iplayer/search?q=" + phrase.replace(" ", "+")
    found_items = []
    r = requests.get(url=search_url, headers=hdr)
    soup = BeautifulSoup(r.content, "html.parser")
    found_items += cycle_over_search_page(soup)
    return found_items


def cycle_over_search_page(soup):
    found_items = []
    a = soup.find_all("a", {"class": ["content-item__link", "gel-layout", "gel-layout--flush"]})
    for el in a:
        el_info = el.get("aria-label")
        if "Description: Not available." in el_info:    # Is upcoming == not playable ATM
            continue
        serie = BBCShow()
        serie.href = base_url + el.get("href")
        serie.title = el_info.split("Description")[0]
        serie.category = el_info.split("Description")[1].split(".")[0][2:]
        serie.additional = el_info.split("Description")[1].split(".")[1][1:]
        ser = el_info.split("Duration")[1].split(".")[0][2:]
        found_items.append(serie)
    return found_items


def results(items):
    # "items" is a singular BBCShow and therefore there are no episodes of it, it's playable by itself(maybe 1-part documentary)
    if isinstance(items, BBCShow):
        return items
    for i, ser in enumerate(items):
        print("{0}: {1}({2})".format(i + 1, ser.title, ser.duration))
    c = input("> ")
    if c == "c":
        return False
    elif c.isnumeric():
        return items[int(c) - 1]
    elif c == "q":
        sys.exit(0)
    else:
        print("\nDon't break my program!")
        return False


def a_z(letter):
    series = []
    az_url = "https://www.bbc.co.uk/iplayer/a-z/" + letter
    r = requests.get(url=az_url, headers=hdr)
    soup = BeautifulSoup(r.content, "html.parser")
    items_found = soup.find_all("a", {"class": "tleo"})
    for item in items_found:
        iplayer_item = BBCShow()
        iplayer_item.title = item.find("span", {"class": "title"}).text
        iplayer_item.href = base_url + item.get("href")
        series.append(iplayer_item)
    for i, serie in enumerate(series):
        print("{0}: {1}".format(i + 1, serie.title))
    c = input("> ")
    if c.isnumeric():
        return series[int(c) - 1]
    else:
        return


# TODO Fix download() and make it usable
if __name__ == "__main__":
    print(extract_link('https://www.bbc.co.uk/iplayer/brand/p067bnvw'))
    sys.exit(0)
    index = iplayer_url

    autoplay = True
    while True:
        print("1) Index\n2) Search\n3) View categories\n4) A-Z\nQ) Quit")
        c = input("> ")
        if c == "1":
            items = listing_index(index)
            chosen_serie = results(items)
        elif c == "2":
            items = search(str(input("Enter search query: ")))
            chosen_serie = results(items)
        elif c == "3":
            cats = get_categories()
            for i, cat in enumerate(cats):
                print("{0}: {1}".format(i + 1, cat.title))
            c = int(input("> "))
            index = cats[c].href
            items = listing_index(index)
            chosen_serie = results(items)
        elif c == "4":
            letter = input("[A...Z]: ")
            chosen_serie = a_z(letter.lower())
        elif c.lower() == "q":
            break
        if not chosen_serie:
            continue
        serie_view = chosen_serie
        episodes = listing_serie(chosen_serie)
        eps_view = chosen_serie
        chosen_episode = results(episodes)
        if not chosen_episode:
            continue

        if autoplay:
            play(chosen_episode, episodes)
        else:
            play(chosen_episode, False)
