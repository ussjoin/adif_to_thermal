from escpos.printer import Usb # For USB Thermal; swap for serial
# NOTE: Requires 3.0a8 or newer of python-escpos (https://github.com/python-escpos/python-escpos)

import adif_io
from gridtools import grid_distance, Grid
import ctyparser
import datetime
from typing import Iterator
from PIL import Image, ImageDraw, ImageFont

# Bus 001 Device 004: ID 0416:5011 Winbond Electronics Corp. Virtual Com Port
# ^^^^ is the TEROW printer
# It's a POS5890 printer (https://mike42.me/escpos-printer-db/#profiles/POS-5890)
# NOTE: First-time setup: https://python-escpos.readthedocs.io/en/latest/user/installation.html

FILENAME_TO_WATCH = "/home/pi/followme.adi"

callsign_font = ImageFont.truetype('orbitron-light-webfont.ttf', 72)
dx_font = ImageFont.truetype('LeagueGothic-Regular.ttf', 50)
details_font = ImageFont.truetype('LeagueGothic-Regular.ttf', 44)
sig_font = ImageFont.truetype('LeagueGothic-Regular.ttf', 32)
mode_font = ImageFont.truetype('LeagueGothic-Regular.ttf', 78)
black = (0,0,0)
white = (255,255,255)
width = 377
height = 225

def get_contact_count(lines):
    count = 0
    for line in lines:
        if line[0:6] == "<call:":
            count += 1
    return count

def follow(file, sleep_sec=0.1) -> Iterator[str]:
    """ Yield each line from a file as they are written.
    `sleep_sec` is the time to sleep after empty reads. """
    # Stolen from https://stackoverflow.com/a/54263201

    line = ''
    while True:
        tmp = file.readline()
        if tmp is not None:
            line += tmp
            if line.endswith("\n"):
                yield line
                line = ''
        elif sleep_sec:
            time.sleep(sleep_sec)

def find_country(call):
    # https://github.com/miaowware/qrm2/blob/master/exts/dxcc.py#L41-L57
    return "Narnia"

def degrees_to_cardinal(degrees):
    # Stolen with open gratitude from:
    # https://gist.github.com/RobertSudwarts/acf8df23a16afdb5837f
    dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    ix = int((degrees + 11.25)/22.5 - 0.02)
    return dirs[ix % 16]

def print_contact(line, line_count):
    qsos, header =  adif_io.read_from_string(line)

    # <call:5>AG6QV <gridsquare:4>CN87 <mode:3>FT8 <rst_sent:3>-13 <rst_rcvd:3>-10 <qso_date:8>20230101 <time_on:6>002230 <qso_date_off:8>20230101 <time_off:6>002330 <band:3>12m <freq:9>24.917699 <station_callsign:4>K3QB <my_gridsquare:6>CN87UM <tx_pwr:3>50w <comment:21>Aerial-51 807-HD 10ft <eor>
    qso = qsos[0]
    my_grid = qso['MY_GRIDSQUARE']
    their_grid = qso.get('GRIDSQUARE', None)
    their_call = qso['CALL']
    the_time = adif_io.time_off(qso)
    band = qso.get('BAND')
    power = qso.get('TX_PWR')
    mode = qso["MODE"]
    # FT4 registers from WSJTX as mode MFSK, submode FT4
    if mode == "MFSK":
        if "SUBMODE" in qso:
            mode = qso["SUBMODE"]
    rst_s = qso.get('RST_SENT', None)
    rst_r = qso.get('RST_RCVD', None)
    
    if their_grid:
        my_g = Grid(my_grid)
        their_g = Grid(their_grid)
        distance, bearing = grid_distance(my_g, their_g)
        distance = distance * 0.621371 # km to miles
        distance = int(round(distance))
        bearing = int(round(bearing))
        compass = degrees_to_cardinal(bearing)
    country = find_country(their_call)

    # TODO Re-integrate Field Day logging thingies

    #p.textln(f"Contact #{line_count}")
    #p.textln(f"{their_call}")
    #p.textln(f"{the_time.strftime('%Y-%m-%d %H:%M:%SZ')}")
    #p.textln(f"S {rst_s} R {rst_r}")
    #p.textln(f"Mode: {mode} Power: {power}")
    #p.textln(f"Band: {band}")
    #if their_grid:
    #    p.textln(f"{my_grid} to {their_grid}:")
    #    p.textln(f"{distance} mi bearing {bearing} {compass}")
    #p.textln("==========")
    #p.ln(count=3)

    img = Image.new('RGB', (width, height), color = (255, 255, 255))
    d = ImageDraw.Draw(img)

    # Callsign
    d.text((width/2,0.01*height), their_call, fill=black, font=callsign_font, anchor="mt")
    # (left, top, right, bottom) bounding box
    callsign_bbox = d.textbbox((width/2,0), their_call, font=callsign_font, anchor="mt")

    # Mode
    square_size = height * 0.4
    d.rectangle([(0, height-square_size), (square_size, height)], fill=white, outline=black, width=3)
    d.text((square_size/2,height*0.93), mode, fill=black, font=mode_font, anchor="ms")

    # Location
    if their_grid:
        d.text(((width-square_size)/2 + square_size,height*0.95), f"{distance}mi at {bearing}° ({compass})", fill=black, font=details_font, anchor="ms")
    loc_bbox = d.textbbox(((width-square_size)/2 + square_size,height*0.95), f"{distance}mi at {bearing}° ({compass})", font=details_font, anchor="ms")

    # Datetime (above location)
    d.text(((width-square_size)/2 + square_size,loc_bbox[1]-8), the_time.strftime('%Y-%m-%d %H:%M:%SZ'), fill=black, font=details_font, anchor="ms")

    # Grid and DX
    # Vertically centered between the bottom of the callsign and the top of the mode box
    # Horizonally centered in the left-over space to the right of the mode box
    dx_text = country
    if their_grid:
        # If for some reason we have their six-digit grid, trim to 4
        short_grid = their_grid[0:4]
        dx_text = f"{short_grid} {dx_text}"
    d.text(((width-square_size)/2 + square_size,(height-square_size+1.5*callsign_bbox[3])/2), dx_text, fill=black, font=details_font, anchor="ms")

    # Contact Count
    d.text((square_size/2,callsign_bbox[3] + 0.05*height), f"#{line_count}", fill=black, font=details_font, anchor="mt")

    # Signal Report
    d.text((square_size/2,height-square_size-0.02*height), f"S{rst_s} R{rst_r}", fill=black, font=sig_font, anchor="mb")

    # OK, print it!
    p.image(img, center=True)
    p.ln(count=3)

if __name__ == '__main__':
    p = Usb(0x0416, 0x5011, 0, profile="POS-5890")
    #p.text("Hello World\n")
    #p.cut()
    with open(FILENAME_TO_WATCH, 'r') as file:
        initial_lines = file.readlines()
        line_count = get_contact_count(initial_lines)
        print(f"Initial line count: {line_count}")
        for line in follow(file):
            #print(line, end='')
            line_count += 1
            print_contact(line, line_count)
