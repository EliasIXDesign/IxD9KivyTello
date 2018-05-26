# KivyTello

![Screenshot](KiviTello.png?raw=true "Screenshot")

Kivy app to control your Ryze Tello.

Very simple python app to drive your Ryze Tello from desktop or smartphone.
It uses [Kivy](https://kivy.org) to create a basic platform independent GUI.

I still haven't compiled KivyTello for Android due to lack of time,
all volunteers are welcome!

## Important update

**KiviTello finally works on Android!**

I used [Kivy Launcher](https://play.google.com/store/apps/details?id=org.kivy.pygame&hl=en).

Once the Kivy launcher is installed, you can put your Kivy
applications in the Kivy directory in your external storage directory
(often available at `/sdcard` even in devices where this memory
is internal), e.g. :

    /sdcard/kivy/<yourapplication>

**KivyTello waits 60 seconds before exiting if you don't connect Tello in the meantime.**

## Contributing

You're welcome!

## Credits

Many thanks to [TelloPy](https://github.com/hanyazou/TelloPy) for his great Tello library!
