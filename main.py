import subprocess
from bs4 import BeautifulSoup
import youtube_dl
from pdb import set_trace as st
from traceback import print_exc as pe
import requests
import sys
import os
import configparser
import json
import time


hdr = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) \
                Chrome/42.0.2311.90 Safari/537.36'}
iplayer_url = "https://www.bbc.co.uk/iplayer"
base_url = "https://www.bbc.co.uk"
conf_file = "conf.txt"
watched_list = "watched.json"
g_watched = None  # This will be filled out if processed to cache it, not generated automatically.
favourites_list = "favourites.json"


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
    pid = ""


class BBCEpisode:
    href = ""
    parent_programme = None  # BBCProgramme
    title = ""
    episode_number = 0
    duration = ""
    additional = ""
    channel = ""
    pid = ""


class BBCCategory:
    href = ""
    title = ""


class Config:
    autoplay = 1
    mode = "PLAY"


def get_config():
    config = Config()
    cp = configparser.ConfigParser()
    cp.read(conf_file)
    try:
        config.autoplay = bool(int(cp.get('General', 'Autoplay')))
        config.mode = cp.get('General', 'Mode')
    except configparser.NoSectionError:
        print("Can't read conf.txt. Using default values.")
    return config


def set_config(key, val):
    cp = configparser.ConfigParser()
    cp.read(conf_file)
    cp.set("General", key, val)
    with open(conf_file, "w") as conf_w:
        cp.write(conf_w)


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
            iplayer_item.id = index_url.split("/")[-2]
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


# Once a programme is chosen, this will gather all episodes from it
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
    # Loop through pages(break on attibute error or if next button has class disabled -> no pages remaining)
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
            ep.title = el_info.split(" Description")[0]
            ep.duration = el_info.split("Duration: ")[1].split(".")[0]
            ep.parent_programme = parent_programme
            ep.additional = el_info.split("Description: ")[1].split(" Duration:")[0]
            ep.channel = channel
            ep.parent_programme.channel = channel
            ep.pid = content.get("href").split("/")[3]
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
        return
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
    mark_watched(episode)
    try:
        print(
            "PLAYING " + Colours.GREEN + episode.parent_programme.upper() + Colours.END + " - " + Colours.BLUE + episode.title.upper() +
            Colours.END + "Press Q to STOP playback.")
    except AttributeError:  # If it's a one part programme
        print("PLAYING " + Colours.GREEN + episode.title.upper() + Colours.END + "Press Q to STOP playback.".format(
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
        serie.pid = serie.href.split("/")[-2]
        serie.title = el_info.split("Description")[0]
        serie.category = el_info.split("Description")[1].split(".")[0][2:]
        serie.additional = el_info.split("Description")[1].split(".")[1][1:]
        serie.duration = el_info.split("Duration")[1].split(".")[0][2:]
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
        if len(items) == 1 and item_type == "eps":
            return items[0]
    for i, ser in enumerate(items):
        watched = ""
        if item_type == "eps":
            watched_list = get_watched()
            if ser.pid in watched_list:
                watched = Colours.GREEN + "[X]" + Colours.END
        if ser.duration:
            print("{0}: {1}({2})".format(i + 1, Colours.RED + ser.title + Colours.END,
                                         Colours.BLUE + ser.duration + Colours.END), end="")
        else:  # If series are from A-Z, there's no clean way to find out the duration
            print("{0}: {1}".format(i + 1, Colours.RED + ser.title + Colours.END), end="")
        print(watched)  # Prints "[X]\n" if watched or "\n" if not
    c = input("> ")
    if c == "c":
        return
    ind = c.split(" ")
    if item_type == "programme" and "f" in ind[0]:
        push_to_fav_index = int(ind[0].replace("f", "")) - 1
        add_to_favourites(items[push_to_fav_index])
        return
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


def make_dict_from_json(json_file):
    open(json_file, "a").close()  # Make sure file exists before attempting to open it
    with open(json_file, "r") as json_r:
        try:
            json_contents = json.load(json_r)
        except json.decoder.JSONDecodeError:  # Bad data
            json_contents = {}
    return json_contents


def make_objects(objects_dict, type):
    obj_list = []
    for i, item in enumerate(objects_dict):
        try:
            dict_el = objects_dict[item]
            if type == "eps":
                obj = BBCEpisode()
                obj.href = dict_el['href']
                obj.pid = item
                obj.title = dict_el['title']
                obj.duration = dict_el['duration']
                obj.additional = dict_el['additional']
                obj.channel = dict_el['channel']
                par_prog = BBCProgramme()
                par_prog.title = dict_el['programme']
                obj.parent_programme = par_prog
                obj_list.append(obj)
            else:
                obj = BBCProgramme()
                obj.pid = dict_el['pid']
                obj.title = dict_el['title']
                obj.href = dict_el['href']
                obj.category = dict_el['category']
                obj.additional = dict_el['additional']
                obj.duration = dict_el['duration']
                obj.channel = dict_el['channel']
                obj_list.append(obj)
        except KeyError:
            continue
    return obj_list


def get_watched():
    watched_objs = make_dict_from_json(watched_list)
    #watched_objs = make_objects(dict_objs, "eps")
    global g_watched
    g_watched = watched_objs
    return watched_objs


def mark_watched(obj):
    watched = get_watched()
    now = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    # Use pids as the primary keys for this JSON
    if isinstance(obj, BBCEpisode):
        new_entry = {obj.pid: {"title": obj.title, "duration": obj.duration, "additional": obj.additional,
                                   "channel": obj.channel, "watched_at": now,
                                   "programme": obj.parent_programme.title, "href": obj.href, "pid": obj.pid}}
    else:
        new_entry = {obj.pid: {"title": obj.title, "duration": obj.duration, "additional": obj.additional,
                               "channel": obj.channel, "watched_at": now, "programme": "", "href": obj.href, "pid": obj.pid}}
    merged = dict(watched, **new_entry)
    #watched.append(new_entry)
    with open(watched_list, "w") as dump_json:
        json.dump(merged, dump_json, indent=4)  # using indent will make the json file look better(everything's not on one line)


# Feature disabled
def select_from_watched():
    global g_watched
    if g_watched is None:
        get_watched()   # Creates global var g_watched
    if g_watched:       # Test if anything was added in the block above
        return results(g_watched, "eps")
    else:
        print("You have not watched anything yet!")
        return


def get_favourites():
    return make_dict_from_json(favourites_list)


def add_to_favourites(programme):
    favourites = get_favourites()
    new_entry = {programme.title: {"title": programme.title, "category": programme.category, "additional": programme.additional,
                                   "duration": programme.duration, "channel": programme.channel, "href": programme.href, "pid": programme.pid}}

    merged = dict(favourites, **new_entry)
    with open(favourites_list, "w") as dump_json:
        json.dump(merged, dump_json, indent=4)
    print(programme.title + " added to favourites.")


if __name__ == "__main__":
    TEST = True
    conf = get_config()
    index = iplayer_url
    autoplay = conf.autoplay
    mode = conf.mode
    while True:
        chosen_serie = None
        # os.system('clear')
        print("1) Index\n2) Search\n3) View categories\n4) A-Z\n5) Favourites\nQ) Quit (C cancels selection and returns this menu)\n"
              "0) Change mode(currently " + mode + ")")
        c = input("> ")
        if c == "0":
            os.system('clear')
            if mode == "PLAY":
                mode = "DOWNLOAD"
                set_config("mode", "DOWNLOAD")
            else:
                mode = "PLAY"
                set_config("mode", "PLAY")
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
        elif c == "5":
            favs = get_favourites()
            if len(favs) != 0:
                favs = make_objects(favs, "programme")
                chosen_serie = results(favs, "programme")
            else:
                os.system('clear')
                print(Colours.RED + "You have not added anything to favourites!" + Colours.END)
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
