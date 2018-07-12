# ibc
Front end for BBC iPlayer

![ibc menu](https://github.com/jaxke/ibc/blob/master/ibc_menu.png)

## Features  
* List programmes from the iPlayer home or A-Z lists  
* Search using keywords  
* List by categories  
* Subtitles  

## Installation
```  
git clone https://github.com/jaxke/ibc  
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
And download the script from the link from above. Place the script into tools/.

## Note
You need to be located in the UK to view iPlayer content