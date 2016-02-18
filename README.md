# altera2eeschema

This is a script to convert a pinout file (.txt) for Altera FPGAs into a Kicad Library file (.lib).

The Altera pinouts are on this page: https://www.altera.com/support/literature/lit-dp.html

Check out the section '#PARAMS' in the script to get more options, i.e. grid size, pin groups, layout of device, ...

Type
```
python altera2eeschema.py -h
```
for help.

After conversion it can look like this:
http://i.imgur.com/Rsn7V07.png

or if you're weird like me and prefer it to be only 1 device, you can deactivate single groups:
http://i.imgur.com/SiuUeO4.png


I provide this because I hope it can be useful to someone, but of course I don't guarantee proper funcitonality. It should be common sense to at least check basic reasonableness of the pin mappings before mailing the 12 layer board to a manufacturer.

Also, there is no guarantee that Altera will keep their file format. I don't even know if it is consistent for all FPGA families right now, because I only checked a few (e.g. some Cyclone Vs, Stratix and more).

So if you find an issue, let me know so I can fix it. Or better yet, fix it and create a pull request.

Also, I'm not a very good python programmer, so I don't know the 'python way'. It is just convenient and it works.

Also you can do whatever you like with this.
