# odmload
Dockerized Over Drive Loader

## Purpose

odmload is a dockerized tool for downloading audiobooks from Over Drive. It's
intended to help you use Over Drive the same way as the old official program.

## Initial Setup

Before we start anything, make sure you have Libby up and running for all of
your libraries. Ask your library staff if you don't know how to do this. This
will also activate your Overdrive accounts for each library; you need to know
the websites and logins for each individual library. To look them up, go to
[the central Over Drive site](https://www.overdrive.com/libraries) and look up
your own libraries. As I mentioned, you will need to be able to log in; this is
usually something simple like your library card number and the last 4-5 digits
of your phone number, but your library staff will help you.

Make sure you have Docker, Docker Compose, and Python installed. These
instructions will assume you're using a Git supported command line; if you're
using Windows, you may want to use the Git Bash command line. I'll wait for you
to get that all done, and my apologies that you may have to dig a bit.

Clone this repository into a directory of your choice. Github has a guide.

And finally for setting up your machine, pick a place to store the books after
they're downloaded, and a place to store them while they're being downloaded. I
use Audiobookshelf, so I was able to simply use that for the final path. You will
want it to have enough space for the number of books you typically have checked
out at a time.

Books downloaded will be placed in the download directory under a subdirectory "libby",
with each book stored in a directory named only with its Libby ID (a simple way
to keep book folders short and unique - I am open to contributions of code with
better suggestions). Naturally, this means if you are using an audiobook
manager you will need to give it metadata since it's not in the folder
structure. I have implemented Audiobookshelf metadata and (as before) I'm open to
taking code contributions for other systems like Plex or Jellyfin.

NOTE: although Libby can report when loans are due, this program does not
currently implement automatic deletion of due books. You are responsible for
complying with the terms of service, and I have tagged the books as "Odmpy-NG"
to make that easy to do.

Run the following command to get the current tested versions of the two
dependencies this uses. This will be a patched version of odmpy, which
correctly logs into libby and can get the list of books you have checked out;
as well as odmpy-ng, which can actually fetch the books.
```bash
git submodule update --init --recursive
```

Use pip to install odmpy from the submodule of the same name. Even if you have
a patched version running this update is needed to get library websiteIds.
```bash
python3 -m pip install ./odmpy
```

You'll now need your Libby authentication code. Open a browser and go to your
own Libby config page and choose "Copy to another device", then choose one of
the devices listed, either Sonos or Android will work, [and here's a
link](https://libbyapp.com/interview/authenticate/setup-code#enterCode).

With that code in mind, run odmpy to get the list of books you have checked
out. If it isn't set up yet, not a problem; run it just like this and it will
prompt you for the Libby code, and once it's all set up, it'll display your
list of books.

Your libby code may time out ... if so, just run it again. No worries.

```bash
odmpy libby --reset
odmpy libby
```

Next, create a config file for odmpy-ng. If you've run odmpy-ng on its own
before, you'll want to copy the config file from the previous run; put it into
odmpy-ng/config/config.json. Don't worry if you don't have one.

The next step will write to odmpy-ng/config/config.json, so if you have
something there, make sure you have a safe copy.

Next, we'll run the configuration tool:
```bash
./odmload.py configure
```

Once that finishes, edit odmpy-ng/config/config.json and make sure you set the
login pins for each library (your librarians should be helpful here). Also, you
may also want to set some of the encoding options, I always get all of the
extra metadata, and I also prefer to skip reencoding because it takes a long
time (so that's the least tested part for me).

We're almost there. Now prepare two folders; one a temporary folder for in-progress
downloads, and one for completed downloads. 

