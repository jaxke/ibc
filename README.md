# ibc
Front end for BBC iPlayer

![ibc menu](https://github.com/jaxke/ibc/blob/master/ibc_menu.png)

## Features  
* List programmes from the iPlayer home or A-Z lists  
* Search using keywords  
* List by categories  
* Subtitles  
* Watch history  

## Installation
```  
git clone https://github.com/jaxke/ibc  
cd ibc  
python main.py  
```

## Requirements
* mpv  
* youtube-dl  
* BeautifulSoup4  
* [OPTIONAL] [ttml2srt by codingcatgirl](https://github.com/codingcatgirl/ttml2srt) for subtitles when streaming(dependency not needed for downloads)
  
## Usage  
The menu is straight-forward, but there are some catches due to it being completely text based. An X marks seen episodes:  
![Seen episodes](https://github.com/jaxke/ibc/blob/master/extra/imgx.png)  
It is possible to mark programmes as favourites by adding an f letter to your selection:  
![Add to favourites](https://github.com/jaxke/ibc/blob/master/extra/imgf.png)  


## Activating subtitles on streams  
In conf.txt:
```
downloadsubs = 1  
```  
or enable them directly from the main menu. You need to have the script from above as tools/ttml2srt.py.  

## Note
You need to be located in the UK to view iPlayer content