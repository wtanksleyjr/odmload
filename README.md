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

Make sure you have Docker, Docker Compose, and Python installed.
These instructions will assume you're using a Git supported command line; if
you're using Windows, you may want to use the Git Bash command line. I'll wait
for you to get that all done, and my apologies that you may have to dig a bit.

Clone this repository into a directory of your choice. Github has a
guide.

Run the following command to get the current tested versions of the two
dependencies this uses. This will be a patched version of odmpy, which
correctly logs into libby and can get the list of books you have checked out;
as well as odmpy-ng, which can actually fetch the books.
```bash
git submodule update --init --recursive
```

Use pip to install odmpy from the submodule of the same name. (Skip this if you
already have odmpy installed.)
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
odmpy libby
```

Next, create a config file for odmpy-ng. Add in all of your library websites
you have in Libby. You may also want to set some of the encoding options, I
always get all of the extra metadata, and I also prefer to skip reencoding
because it takes a long time (so that's the least tested part for me).
```bash
cp odmpy-ng/config/config.example.json odmpy-ng/config/config.json
vi odmpy-ng/config/config.json
```

TODO: check out books and use them to get the site-id

