# Monte Carlo Nether Portals
Monte Carlo simulation for arranging nether portals optimally.
The ultimate goal is to find the perfect arrangement of nether portals to build a portal farm on Minecraft Bedrock Edition with simulation distance 4.

## Python version
To run the python version, you will need:
- python3
- numpy
- pygame

Simply run `main.py` using python3.
You can adjust the settings at the top of `main.py` before running it as well.
All it will try to do is fill it with as many portal tiles as possible.
Note that because this wasn't the original purpose, some parts may not make sense.
For example, `radius` determines the size of the overall frame, in the sense that the frame is `ceil(radius) * 2 + 1`, as that is sufficiently large for the original goal.
That being said, the python version will not be updated to accomplish the original goal, as it runs far too slowly, and was mostly just a proof of concept anyways.
