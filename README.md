# 3dWiFiSend
Qidi X-Pro Network Script


This is a python script I threw together to allow me to send my gcode file from my pc to my printer over the network.

The Qidi X-Pro 3D printer has network built in and allows you to send your files and start printing from Qidi's own software. I wanted to use Simplify 3D instead and also not have to walk to and from my printer so this script came out.

I am not a python person. I absolutely hate python with a burning passion so this code is ugly and does not error-check. Basically, it is not written to really be distributed but I figured I'd share so that someone who actually has the patience to deal with python can improve it or whatever.

I've tried to keep it simple to use. There are 2 files. One is the python script, the other is a compressor. For now, this script works only under windows because of the compression. Maybe with wine or whatever mac's equivalent is, I can make it a bit more cross-platform. Or I can just remove the compression. Not sure yet. Either way make sure the two files are in the same directory and that you have a flash drive plugged into the printer. I find it is a lot more reliable over ethernet than over wifi but YMMV. 

Here is how to use it:
"python 3DWiFiSendFile.py IPADDRESS FILE.GCODE [PRINT yes/no]"

The first argument is the ip address of the printer. Second argument is the name/path to the gcode file. Third arg is an optional print flag. If you add 'yes' as the third arg, the printer will also print the file after copying it. If you don't put anything there, it will just copy the file over without printing.

If you have any improvements to this, Please let me know.


youtube video:   https://youtu.be/agJc9IzfyQk