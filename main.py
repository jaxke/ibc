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


''' 
Dev notes:
aria-label holds important bits of info in iPlayer's HTML
'''


# Return the bs4 object that is used by nearly all of the functions
def get_soup(url):
    r = requests.get(url=url, headers=hdr)
    soup = BeautifulSoup(r.content, "html.parser")
    return soup


# Lists all categories from the top menu
def get_categories():
    categories = []
    soup = get_soup(iplayer_url)
    u_lists = soup.find_all("ul", {"class": ["tvip-cats", "tvip-nav-clearfix"]})
    for ul in u_lists:
        cats_in_ul = ul.find_all("a", {"class": ["typo", "typo--canary", "stat"]})
        for cat in cats_in_ul:
            c = BBCCategory()
            c.href = base_url + cat.get("href")
            c.title = cat.contents[0]
            categories.append(c)
    return categories


# Get "all" items from a given category(under "View all Comedy/drama A-Z")
def get_cats_a_z(cats_href):
    soup = get_soup(cats_href)
    view_az = base_url + soup.find("a", {"class": ["button", "button--clickable"]}).get("href")
    return listing_index(view_az)


# Lists any index page(home and links after a category). However not A-Z pages(see a_z())
def listing_index(index_url):
    items = []
    soup = get_soup(index_url)
    it = 0
    while True:
        if it > 20: # TODO Remove this
            print("DEBUG: Iterator has reached 20, breaking")
            break
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
            # DISABLED == lnk pagination__direction pagination__direction--next pagination__direction--large lnk--disabled
        # Suck data from every page
        next_page = soup.find("a", {"class": ["pagination__direction--next"]})
        if next_page is None or 'lnk--disabled' in next_page.attrs['class']:    # Last page
            break
        else:
            r = requests.get(url=index_url + next_page.get("href"), headers=hdr)
            soup = BeautifulSoup(r.content, "html.parser")
        it += 1
    return items


# Once a serie is chosen, this will gather all episodes from it
# TODO Does not work for a serie with no View all button
def listing_serie(parent_serie):
    episodes = []
    soup = get_soup(parent_serie[0].href)
    try:
        view_all = soup.find("a", {"class": ["button", "section__header__cta", "button--clickable"]}).get("href")
        r = requests.get(url=base_url + view_all, headers=hdr)
    except AttributeError:
        return parent_serie    # This is not a serie or there is no View all button
    soup = BeautifulSoup(r.content, "html.parser")
    eps_found = get_eps_in_page(soup)
    if eps_found:
        episodes += get_eps_in_page(soup)
    else:   # if that method returns False, it didn't find any episodes
        return parent_serie
    # Shows are distributed within pages(if there are more than x episodes), this will loop through each page and collect episodes from them
    for i in range(6):  # TODO Fix this
        try:
            # This is the link that the "next" button refers to.
            next_page = soup.find("a", {"class": ["lnk pagination__direction", "pagination__direction--next", "pagination__direction--large"]}).get("href")
        # None was returned(no more pages or no additional pages at all) and .get() raises AE
        except AttributeError:
            break
        r_next = requests.get(url=r.url + next_page, headers=hdr)
        next_soup = BeautifulSoup(r_next.content, "html.parser")
        episodes += get_eps_in_page(next_soup)
    return episodes


# This is used by listing_serie and will return episodes from a page
def get_eps_in_page(soup):
    episodes = []
    show_name = soup.find("title").text.split("- ")[1]
    try:
        div_content = soup.find("div", {"class": ["grid", "list__grid"]}).find_all("a", {"class": ["content-item__link", "gel-layout", "gel-layout--flush"]}) # grid list__grid
        for content in div_content:
            el_info = content.get("aria-label")
            ep = BBCEpisode()
            ep.href = base_url + content.get("href")
            ep.title = el_info.split("Description")[0]
            ep.duration = el_info.split("Duration: ")[1].split(".")[0]
            ep.show_name = show_name
            episodes.append(ep)
        # return episodes[::-1]
        return episodes
    except AttributeError:
        return    # This is a one-part show


# One-episode shows have this special type of link that has to be dug from the source once again(the href in its parameter is not a video link)
# <link rel="canonical" href="..." > We want this href.
def extract_link(href):
    soup = get_soup(href)
    r = requests.get(url=href, headers=hdr)
    soup = BeautifulSoup(r.content, "html.parser")
    links = soup.find_all("link")
    for link in links:
        if link.get("rel", None):
            if link.get("rel")[0] == "canonical":
                return link.get("href")


def play(episodes, all_eps):
    # Is a one part "show", maybe a documentary etc... OR autoplay is disabled
    if isinstance(episodes, BBCShow) or not all_eps:
        real_link = extract_link(episodes.href)
        play_msg(episodes)
        subprocess.call(["mpv", real_link], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        # If more than one episode was selected, play them back to back
        if len(episodes) > 1:
            for ep in episodes:
                play_msg(ep)
                subprocess.call(["mpv", ep.href], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if ep == episodes[-1]:  # If episode was not the last on the list, continue loop
                    return
        # ... Otherwise autoplay next episode
        else:
            ep_index = all_eps.index(episodes[0])
            for i in range(ep_index, len(all_eps)):
                play_msg(all_eps[i])
                subprocess.call(["mpv", all_eps[i].href], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if i != len(all_eps) - 1:
                    if str(input("Watch next episode Y/N: ")).lower() == "y":
                        continue
                    else:
                        return

def play_msg(episode):
    try:
        print("PLAYING {0} - {1}. Press Q to STOP playback.".format(episode.show_name, episode.title))
    except AttributeError:  # If it's a one part show
        print("PLAYING {0}. Press Q to STOP playback.".format(episode.title))

# TODO Not working
def download(episode):
    ydl_opts = {"hls_prefer_native": True}
    ydl_opts['outtmpl'] = "%(title)s.%(ext)s"
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        ydl.download([episode.href])


# TODO Only finds items in first page, rest are usually irrelevant(and dev is lazy)
# List all shows returned by a search
def search(phrase):
    search_url = "https://www.bbc.co.uk/iplayer/search?q=" + phrase.replace(" ", "+")
    found_items = []
    soup = get_soup(search_url)
    r = requests.get(url=search_url, headers=hdr)
    soup = BeautifulSoup(r.content, "html.parser")
    found_items += cycle_over_search_page(soup)
    return found_items


# Pagination function can be added by improving this function but... dev == "lazy"
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


# Scaper for the A-Z page: list every show in iPlayer by letters.
def a_z(letter):
    series = []
    az_url = "https://www.bbc.co.uk/iplayer/a-z/" + letter
    soup = get_soup(az_url)
    r = requests.get(url=az_url, headers=hdr)
    soup = BeautifulSoup(r.content, "html.parser")
    items_found = soup.find_all("a", {"class": "tleo"})
    for item in items_found:
        iplayer_item = BBCShow()
        iplayer_item.title = item.find("span", {"class": "title"}).text
        iplayer_item.href = base_url + item.get("href")
        series.append(iplayer_item)
    return series
    '''
    for i, serie in enumerate(series):
        print("{0}: {1}".format(i + 1, serie.title))
    c = input("> ")
    ind = c.split(" ")
    try:
        ind = [int(j) - 1 for j in ind]  # Make selection array into integers
        return [series[i] for i in ind]  # Pick items by selected indices
    except (ValueError, IndexError):  # At least one item is not an int or the selection can't be matched with the series list
        print("Invalid selection")
        return
    '''


# This function formats and lists "results" and asks for the input. Merely there to reduce redundancy in __main__
def results(items):
    # "items" is a singular BBCShow and therefore there are no episodes of it, it's playable by itself(maybe 1-part documentary)
    if isinstance(items, BBCShow):
        return items
    else:   # Play first EPISODE if only one exists
        if len(items) == 1:
            return items[0]
    for i, ser in enumerate(items):
        print("{0}: {1}({2})".format(i + 1, ser.title, ser.duration))
    c = input("> ")
    if c == "c":
        return
    ind = c.split(" ")
    try:
        ind = [int(j) - 1 for j in ind]  # Make selection array into integers
        return [items[i] for i in ind]  # Pick items by selected indices
    except (ValueError, IndexError):  # At least one item is not an int or the selection can't be matched with the series list
        print("Invalid selection")
        return


# TODO Fix download() and make it usable
if __name__ == "__main__":
    index = iplayer_url
    autoplay = True
    while True:
        print("1) Index\n2) Search\n3) View categories\n4) A-Z\nQ) Quit (C cancels selection and returns this menu)")
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
            index = cats[c - 1].href
            items = get_cats_a_z(index)
            chosen_serie = results(items)
        elif c == "4":
            letter = input("[A...Z]: ")
            items = a_z(letter.lower())
            chosen_serie = results(items)
        elif c.lower() == "q":
            break
        elif c.lower() == "c":
            continue
        else:
            print("Invalid option")
            continue
        if len(chosen_serie) > 1:
            print("Only one series can be chosen at once!")
            continue
        episodes = listing_serie(chosen_serie)
        chosen_episode = results(episodes)
        if not chosen_episode:
            continue
        if autoplay:
            play(chosen_episode, episodes)
        else:
            play(chosen_episode, False)
