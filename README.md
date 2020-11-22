# BoseLifestyletoCEC
I have made this script to control my Bose Lifestyle 48 II to my Sony TV over HDMI cec.

The script is using LibCEC to recieve key inputs from the TV and send those to the Bose system. Besides that it is sending the current volume back to the TV, to get a feedback on the TV when the volume is changed. 

The Bose system has a serialport (3.5 mm jack) using RS232 logic levels. I have installed a RS232 header on a RPI W ZERO, which is connected to the Bose system using a DB9 to 3.5 jack cable. 

There is a bug on the bose system, where the system turns off, when turned on again before completely shutting down(which takes around 2:30 min). I have found out that when the system sends a ">" when shutting down completely, while the response from the bose system otherwise always contains some other chars. 

Since using a RPI for this purpose i might implement this on some microprocessor in the future. 
