import subprocess
from bs4 import BeautifulSoup
import youtube_dl
from pdb import set_trace as st
import requests
import sys
import os


hdr = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) \
                Chrome/42.0.2311.90 Safari/537.36'}
iplayer_url = "https://www.bbc.co.uk/iplayer"
base_url = "https://www.bbc.co.uk"


class Colours:
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    RED = '\033[91m'
    END = '\033[0m'


class BBCProgramme:
    href = ""
    title = ""
    category = ""
    additional = ""
    duration = ""
    channel = ""


class BBCEpisode:
    href = ""
    parent_programme = None  # BBCProgramme
    title = ""
    episode_number = 0
    duration = ""
    additional = ""
    channel = ""


class BBCCategory:
    href = ""
    title = ""


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


# Get "all" items from a given category(under "View all Comedy/drama/... A-Z")
def get_cats_a_z(cats_href):
    soup = get_soup(cats_href)
    view_az = base_url + soup.find("a", {"class": ["button", "button--clickable"]}).get("href")
    return listing_index(view_az)


# Lists any index page(home and links after a category). However not A-Z pages(see a_z())
def listing_index(index_url):
    items = []
    soup = get_soup(index_url)
    while True:
        el = soup.find_all("a", {"class": ["content-item__link", "gel-layout", "gel-layout--flush"]})
        for e in el:
            if e.get("data-object-type") == "editorial-promo":
                continue
            el_info = e.get("aria-label")
            el_href = e.get("href")
            iplayer_item = BBCProgramme()
            iplayer_item.href = base_url + el_href
            iplayer_item.title = el_info.split("Description")[0][:-2]
            iplayer_item.category = el_info.split("Description")[1].split(".")[0][2:]
            iplayer_item.additional = el_info.split("Description")[1].split(".")[1][1:]
            iplayer_item.duration = el_info.split("Duration")[1].split(".")[0][2:]
            items.append(iplayer_item)
        # Suck data from every page
        next_page = soup.find("a", {"class": ["pagination__direction--next"]})
        if next_page is None or 'lnk--disabled' in next_page.attrs['class']:  # Last page
            break
        else:
            r = requests.get(url=index_url + next_page.get("href"), headers=hdr)
            soup = BeautifulSoup(r.content, "html.parser")
    return items


# Once a serie is chosen, this will gather all episodes from it
# Parameter = BBCProgramme
# Returns: list of BBCEpisode objeccts under parent serie.
def listing_serie(parent_programme):
    episodes = []
    soup = get_soup(parent_programme.href)
    try:
        view_all = soup.find("a", {"class": ["button", "section__header__cta", "button--clickable"]}).get("href")
        r = requests.get(url=base_url + view_all, headers=hdr)
    except AttributeError:
        return parent_programme  # This is not a serie or there is no View all button
    soup = BeautifulSoup(r.content, "html.parser")
    eps_found = get_eps_in_page(soup, parent_programme)
    if eps_found:
        episodes += get_eps_in_page(soup, parent_programme)
    else:  # if that method returns False, it didn't find any episodes
        return parent_programme
    # programmes are distributed within pages(if there are more than x episodes), this will loop through each page and collect episodes from them
    while True:
        try:
            # This is the link that the "next" button refers to.
            next_page_a = soup.find("a", {"class": "pagination__direction--next"})
            # if "Next" has class lnk--disabled, we're on the last page
            if next_page_a is None or 'lnk--disabled' in next_page_a.attrs['class']:
                break
            next_page = next_page_a.get('href')
        # None was returned(no more pages or no additional pages at all) and .get() raises AE
        except AttributeError:
            break
        r_next = requests.get(url=r.url + next_page, headers=hdr)
        soup = BeautifulSoup(r_next.content, "html.parser")
        episodes += get_eps_in_page(soup, parent_programme)
    return episodes


# This is used by listing_serie and will return episodes from a page
def get_eps_in_page(soup, parent_programme):
    episodes = []
    channel = soup.find("img", {"class": "episodes-available__dog"}).get("alt")
    try:
        div_content = soup.find("div", {"class": ["grid", "list__grid"]}).find_all("a", {
            "class": ["content-item__link", "gel-layout", "gel-layout--flush"]})
        for content in div_content:
            el_info = content.get("aria-label")
            ep = BBCEpisode()
            ep.href = base_url + content.get("href")
            ep.title = el_info.split("Description")[0]
            ep.duration = el_info.split("Duration: ")[1].split(".")[0]
            ep.parent_programme = parent_programme
            ep.additional = el_info.split("Description: ")[1].split(" Duration:")[0]
            ep.channel = channel
            ep.parent_programme.channel = channel
            episodes.append(ep)
        return episodes
    except AttributeError:
        return  # This is a one-part programme


# One-episode programmes have a special type of link that has to be dug from the source once again(the href in its
# parameter is not a valid video link).
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
    DEBUG = True
    # Is a one part "programme", maybe a documentary etc... OR autoplay is disabled
    if isinstance(episodes, BBCProgramme) or not all_eps:
        real_link = extract_link(episodes.href)
        play_msg(episodes)
        subprocess.call(["mpv", real_link], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        # If more than one episode was selected, play them back to back
        if len(episodes) > 1:
            for ep in episodes:
                play_msg(ep)
                if DEBUG:
                    subprocess.call(["mpv", ep.href])
                else:
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
        print(
            "PLAYING " + Colours.GREEN + episode.parent_programme.upper() + Colours.END + " - " + Colours.BLUE + episode.title.upper() +
            Colours.END + "Press Q to STOP playback.")
    except AttributeError:  # If it's a one part programme
        print("PLAYING " + Colours.GREEN + episode.title.upper() + Colours.END + ". Press Q to STOP playback.".format(
            episode.title))


# TODO Only finds items in first page, rest are usually irrelevant(and dev is lazy)
# List all programmes returned by a search
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
        if "Description: Not available." in el_info:  # Is upcoming == not playable ATM
            continue
        serie = BBCProgramme()
        serie.href = base_url + el.get("href")
        serie.title = el_info.split("Description")[0]
        serie.category = el_info.split("Description")[1].split(".")[0][2:]
        serie.additional = el_info.split("Description")[1].split(".")[1][1:]
        ser = el_info.split("Duration")[1].split(".")[0][2:]
        found_items.append(serie)
    return found_items


# Scaper for the A-Z page: list every programme in iPlayer by letters.
def a_z(letter):
    series = []
    az_url = "https://www.bbc.co.uk/iplayer/a-z/" + letter
    soup = get_soup(az_url)
    r = requests.get(url=az_url, headers=hdr)
    soup = BeautifulSoup(r.content, "html.parser")
    items_found = soup.find_all("a", {"class": "tleo"})
    for item in items_found:
        iplayer_item = BBCProgramme()
        iplayer_item.title = item.find("span", {"class": "title"}).text
        iplayer_item.href = base_url + item.get("href")
        series.append(iplayer_item)
    return series


# This function formats and lists "results" and asks for the input. Merely there to reduce redundancy in __main__
def results(items, item_type):
    # "items" is a singular BBCProgramme and therefore there are no episodes of it, it's playable by itself(maybe 1-part documentary)
    if isinstance(items, BBCProgramme):
        #print(items.title.upper() + ": " + items.additional)
        return items
    else:  # Play first EPISODE if only one exists
        if len(items) == 1:
            return items[0]
    for i, ser in enumerate(items):
        if ser.duration:
            print("{0}: {1}({2})".format(i + 1, Colours.RED + ser.title + Colours.END,
                                         Colours.BLUE + ser.duration + Colours.END))
        else:  # If series are from A-Z, there's no clean way to find out the duration
            print("{0}: {1}".format(i + 1, Colours.RED + ser.title + Colours.END))
    c = input("> ")
    if c == "c":
        return
    ind = c.split(" ")
    # If desc gets defined as True, user has chosen to programme descriptions for items and we need to return early(they
    # might want multiple descriptions at once so can't return from for loop)
    desc = False
    for i in ind:
        # If user enters "1d 2d 3d" instead of "1 2 3", programme them descriptions from those episodes instead of playing them
        # This completely ignores inputs without "d" so they won't be played
        if "d" in i:
            desc = True
            i = i.replace("d", "")
            if items[int(i)].additional is None:
                info = "No description available!"
            else:
                info = items[int(i)].additional
            print(items[int(i) - 1].title.upper() + ": " + info + "\n")
    if desc:  # Early return in case of above
        return
    if item_type == "programme":
        if len(ind) > 1:
            print("Only one programme can be chosen at once.")
        else:
            try:
                index = int(ind[0])
            except TypeError:
                print("Input must be numeric unless you use the keyword \"d\"")
                return
            return items[index - 1]
    try:
        ind = [int(j) - 1 for j in ind]  # Make selection array into integers
        return [items[i] for i in ind]  # Pick items by selected indices -> ret = [items[n], items[x], items[y]]
    # At least one item is not an int or the selection can't be matched with the series list
    except (ValueError, IndexError):
        print("Invalid selection")
        return


def download(episodes):
    for episode in episodes:
        ydl_opts = {"hls_prefer_native": True}
        ydl_opts['outtmpl'] = "%(title)s.%(ext)s"
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            ydl.download([episode.href])


if __name__ == "__main__":
    index = iplayer_url
    autoplay = True
    mode = "PLAY"
    while True:
        # os.system('clear')
        print("1) Index\n2) Search\n3) View categories\n4) A-Z\nQ) Quit (C cancels selection and returns this menu)\n"
              "0) Change mode(currently " + mode + ")")
        c = input("> ")
        if c == "0":
            if mode == "PLAY":
                mode = "DOWNLOAD"
            else:
                mode = "PLAY"
            continue
        if c == "1":
            items = listing_index(index)
            chosen_serie = results(items, "programme")
        elif c == "2":
            items = search(str(input("Enter search query: ")))
            chosen_serie = results(items, "programme")
        elif c == "3":
            cats = get_categories()
            for i, cat in enumerate(cats):
                print("{0}: {1}".format(i + 1, cat.title))
            try:
                c = int(input("> "))
            except ValueError:
                print("Input must be numeric!")
            index = cats[c - 1].href
            items = get_cats_a_z(index)
            chosen_serie = results(items, "programme")
        elif c == "4":
            letter = input("[A...Z]: ")
            items = a_z(letter.lower())
            chosen_serie = results(items, "programme")
        elif c.lower() == "q":
            break
        elif c.lower() == "c":
            continue
        else:
            print("Invalid option")
            continue
        if not chosen_serie:  # User cancelled from results()
            continue
        episodes = listing_serie(chosen_serie)
        chosen_episodes = results(episodes, "eps")
        if not chosen_episodes:
            continue
        if mode == "PLAY":
            if autoplay:
                play(chosen_episodes, episodes)
            else:
                play(chosen_episodes, False)
        else:
            download(chosen_episodes)
