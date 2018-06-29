import subprocess
from bs4 import BeautifulSoup
import youtube_dl
from pdb import set_trace as st
import requests

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


def listing_index(index_url):
    items = []
    r = requests.get(url=index_url, headers=hdr)
    soup = BeautifulSoup(r.content, "html.parser")
    el = soup.find_all("a", {"class": ["content-item__link", "gel-layout", "gel-layout--flush"]})
    for e in el: # TODO CLEAN THE SHIT OUT OF THIS
        el_info = e.get("aria-label")
        el_title = el_info.split("Description")[0][:-2]
        el_category = el_info.split("Description")[1].split(".")[0][2:]
        el_additional = el_info.split("Description")[1].split(".")[1][1:]
        el_duration = el_info.split("Duration")[1].split(".")[0][2:]
        el_href = e.get("href")
        iplayer_item = BBCShow()
        iplayer_item.href = base_url + el_href
        iplayer_item.title = el_title
        iplayer_item.category = el_category
        iplayer_item.additional = el_additional
        iplayer_item.duration = el_duration
        items.append(iplayer_item)
    return items


# TODO Does not work for a serie with no View all button
# TODO Does not find anything beyond first page
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
    try:
        div_content = soup.find("div", {"class": ["grid", "list__grid"]}).find_all("a", {"class": ["content-item__link", "gel-layout", "gel-layout--flush"]}) # grid list__grid
        for content in div_content:
            el_info = content.get("aria-label")
            ep = BBCEpisode()
            ep.href = base_url + content.get("href")
            ep.show_name = parent_serie.title
            ep.title = el_info.split("Description")[0]
            episodes.append(ep)
        return episodes[::-1]
    except AttributeError:
        return parent_serie    # This is a one-part show


def play(episode):
     '''for n in range(first_to_play, len(episodes)):
        subprocess.call(["mpv", episodes[n].href])'''
     subprocess.call(["mpv", episode.href])


def search(phrase):
    search_url = "https://www.bbc.co.uk/iplayer/search?q=" + phrase.replace(" ", "+")
    found_items = []
    r = requests.get(url=search_url, headers=hdr)
    soup = BeautifulSoup(r.content, "html.parser")
    found_items += cycle_over_search_page(soup)
    return found_items
    # TODO only one search page is used now because the rest seems rubbish and would take time to cycle over each page


def cycle_over_search_page(soup):
    found_items = []
    a = soup.find_all("a", {"class": ["content-item__link", "gel-layout", "gel-layout--flush"]})
    for el in a:
        serie = BBCShow()
        serie.href = base_url + el.get("href")  # TODO There should be a method for this
        el_info = el.get("aria-label")
        if "Description: Not available." in el_info:
            continue
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
        print("{0}: {1}".format(i + 1, ser.title))
    c = int(input("> "))
    return items[c - 1]


if __name__ == "__main__":
    print("1) Index\n2) Search")
    c = int(input("> "))
    if c == 1:
        items = listing_index(iplayer_url)
    elif c == 2:
        items = search(str(input("Enter search query: ")))

    chosen_serie = results(items)
    episodes = listing_serie(chosen_serie)
    chosen_episode = results(episodes)
    play(chosen_episode)