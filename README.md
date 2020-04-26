Unofficial JW.ORG audio player for Kodi
==========================================

![screenshot](https://raw.githubusercontent.com/allejok96/plugin.audio.jwa-unofficial/master/resources/screenshot-02.jpg)

Play audio recordings from [JW.ORG](https://www.jw.org) on your Kodi box! Select one of the hundred languages, and listen to the Bible, the latest magazines or any of the available books or brochures.

*This add-on is not supported by the Watchtower Society. If you run in to any problems, do not contact jw.org for support. Instead please leave an issue here on GitHub.*

It would of course be better if you could access these publications using an officially supported method, like the JW Library app, or simply a web browser. The Watchtower Society urges people to use their official apps, instead of third-party software like Kodi add-ons ([w18 April page 30-31](https://wol.jw.org/en/wol/d/r1/lp-e/2018364)).

## Installation

There are multiple ways you can install this add-on. You could use `git clone` or Download ZIP from GitHub.

But the easiest way is to install it from my repo. This way you'll receive updates automatically (if I remember to upload them):

1. Download [this ZIP](https://github.com/allejok96/repository.allejok96/raw/master/downloads/repository.allejok96.zip)
1. In Kodi: click on "Add-ons"
1. Click on the little box icon in the upper left hand corner
1. "Install from zip file"
1. Browse to the directory with the zip and select it
1. Click on "Install from repository"
1. "allejok96's Repository > Music add-ons > JWA Unofficial > Install"

## Disclaimer

As the WT article above points out, there are some risks with third-party software:

* When jw.org improves, this add-on may break, misbehave or lag behind.
* If someone hacked my repo, they could forge the spiritual food (extremely unlikely).

But since you found this page I guess you know what you're doing.

## Questions

#### How to switch language?

The add-on will auto detect your language at first startup. You can change language in the add-on settings (press left if you're using the Estuary skin). You can also play a single recording in a different language by opening the context menu and selecting *Play in another language*.

#### Why are some books missing?

Under "Books & Brochures", you can do a "Auto scan" to get all books. There is currently no good way to get a list of all books, so I explicitly typed out the ones available at the time of making. Any new books will not be detected by "Auto scan". If you notice a book is missing, please drop an issue here, and I'll add it in the next release.

Meanwhile, you can manually add it by clicking on "Add more...", answering no, and typing in the two or three letter publication code. You find it inside the covers of, or at the back of the book, or at WOL.

#### Why not in Kodi official repository?

See [JWB Unofficial](https://github.com/allejok96/plugin.video.jwb-unofficial/)

#### Is this legal?

Yes. The [Terms of Service](http://www.jw.org/en/terms-of-use/) states:

> You may not ... create software ... made to download, extract, harvest, or scrape data, HTML, images, or text from this site. (This does not prohibit the distribution of free, non-commercial applications designed to download electronic files such as EPUB, PDF, MP3, and MP4 files from public areas of this site.)

As you can see, software like this add-on is very generously allowed for. But there's one part of this add-on that violates the terms...

#### What about *Translated menus?*

When selecting a language, the add-on extracts a few translated words from the HTML of a page at jw.org. This violates the terms above. But since it's a one time thing, I feel the aesthetic benefits outweighs the violation.

The funny thing, though, is that this extraction is much more prone to fail, compared to the rest of the add-on (the "allowed" usage). If you were to experience any problems, you *can* turn it off. Just go to settings and disable *Translated menus*.
