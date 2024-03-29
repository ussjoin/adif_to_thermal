from escpos.printer import Usb, Dummy  # For USB Thermal; swap for serial

# NOTE: Requires 3.0a8 or newer of python-escpos (https://github.com/python-escpos/python-escpos)

import adif_io
from gridtools import grid_distance, Grid
import ctyparser
import datetime
from typing import Iterator
from PIL import Image, ImageDraw, ImageFont

# FILENAME_TO_WATCH = "/home/pi/followme.adi"
FILENAME_TO_WATCH = "/home/ussjoin/.local/share/WSJT-X/wsjtx_log.adi"

TEST = False

class AdifToThermal:
    callsign_font = ImageFont.truetype("orbitron-light-webfont.ttf", 72)
    dx_font = ImageFont.truetype("LeagueGothic-Regular.ttf", 50)
    details_font = ImageFont.truetype("LeagueGothic-Regular.ttf", 44)
    sig_font = ImageFont.truetype("LeagueGothic-Regular.ttf", 32)
    mode_font = ImageFont.truetype("LeagueGothic-Regular.ttf", 78)
    BLACK = (0, 0, 0)
    WHITE = (255, 255, 255)
    THERMAL_WIDTH = 377
    THERMAL_HEIGHT = 225

    def __init__(self, printer=Dummy()):
        self.cty = None
        self.contact_count = 0
        self.printer = printer

    def load_cty(self, filepath):
        self.cty = ctyparser.BigCty()
        self.cty.import_dat(filepath)
        print(f"Loaded BigCTY, Version {self.cty.formatted_version}")

    def find_country(self, query):
        # Taken, with my gratitude, from
        # https://github.com/miaowware/qrm2/blob/master/exts/dxcc.py#L41-L57
        # By suggestion of the miaowware crew
        query = query.upper()
        full_query = query
        while query:
            if query in self.cty.keys():
                data = self.cty[query]
                return data["entity"]
            else:
                query = query[:-1]
        return "Unknown"

    def load_previous_contact_count(self, lines):
        count = 0
        for line in lines:
            if line[0:6] == "<call:":
                count += 1
        self.contact_count = count

    @staticmethod
    def degrees_to_cardinal(degrees):
        # Stolen with open gratitude from:
        # https://gist.github.com/RobertSudwarts/acf8df23a16afdb5837f
        dirs = [
            "N",
            "NNE",
            "NE",
            "ENE",
            "E",
            "ESE",
            "SE",
            "SSE",
            "S",
            "SSW",
            "SW",
            "WSW",
            "W",
            "WNW",
            "NW",
            "NNW",
        ]
        ix = int((degrees + 11.25) / 22.5 - 0.02)
        return dirs[ix % 16]

    def print_contact(self, line):
        qsos, header = adif_io.read_from_string(line)
        self.contact_count += 1
        # <call:5>AG6QV <gridsquare:4>CN87 <mode:3>FT8 <rst_sent:3>-13 <rst_rcvd:3>-10 <qso_date:8>20230101 <time_on:6>002230 <qso_date_off:8>20230101 <time_off:6>002330 <band:3>12m <freq:9>24.917699 <station_callsign:4>K3QB <my_gridsquare:6>CN87UM <tx_pwr:3>50w <comment:21>Aerial-51 807-HD 10ft <eor>
        qso = qsos[0]
        my_grid = qso["MY_GRIDSQUARE"]
        their_grid = qso.get("GRIDSQUARE", None)
        their_call = qso["CALL"]
        the_time = adif_io.time_off(qso)
        band = qso.get("BAND")
        power = qso.get("TX_PWR")
        freq = qso.get("FREQ")
        mode = qso["MODE"]
        # FT4 registers from WSJTX as mode MFSK, submode FT4
        if mode == "MFSK":
            if "SUBMODE" in qso:
                mode = qso["SUBMODE"]
        rst_s = qso.get("RST_SENT", None)
        rst_r = qso.get("RST_RCVD", None)

        if their_grid:
            my_g = Grid(my_grid)
            their_g = Grid(their_grid)
            distance, bearing = grid_distance(my_g, their_g)
            distance = distance * 0.621371  # km to miles
            distance = int(round(distance))
            bearing = int(round(bearing))
            compass = AdifToThermal.degrees_to_cardinal(bearing)

        # TODO Re-integrate Field Day logging thingies

        img = Image.new(
            "RGB",
            (AdifToThermal.THERMAL_WIDTH, AdifToThermal.THERMAL_HEIGHT),
            color=(255, 255, 255),
        )
        d = ImageDraw.Draw(img)

        # Callsign
        d.text(
            (AdifToThermal.THERMAL_WIDTH / 2, 0.01 * AdifToThermal.THERMAL_HEIGHT),
            their_call,
            fill=AdifToThermal.BLACK,
            font=AdifToThermal.callsign_font,
            anchor="mt",
        )
        # (left, top, right, bottom) bounding box
        callsign_bbox = d.textbbox(
            (AdifToThermal.THERMAL_WIDTH / 2, 0),
            their_call,
            font=AdifToThermal.callsign_font,
            anchor="mt",
        )

        # Mode
        square_size = AdifToThermal.THERMAL_HEIGHT * 0.4
        d.rectangle(
            [
                (0, AdifToThermal.THERMAL_HEIGHT - square_size),
                (square_size, AdifToThermal.THERMAL_HEIGHT),
            ],
            fill=AdifToThermal.WHITE,
            outline=AdifToThermal.BLACK,
            width=3,
        )
        d.text(
            (square_size / 2, AdifToThermal.THERMAL_HEIGHT * 0.93),
            mode,
            fill=AdifToThermal.BLACK,
            font=AdifToThermal.mode_font,
            anchor="ms",
        )

        # Location
        if their_grid:
            d.text(
                (
                    (AdifToThermal.THERMAL_WIDTH - square_size) / 2 + square_size,
                    AdifToThermal.THERMAL_HEIGHT * 0.95,
                ),
                f"{distance}mi at {bearing}° ({compass})",
                fill=AdifToThermal.BLACK,
                font=AdifToThermal.details_font,
                anchor="ms",
            )
        loc_bbox = d.textbbox(
            (
                (AdifToThermal.THERMAL_WIDTH - square_size) / 2 + square_size,
                AdifToThermal.THERMAL_HEIGHT * 0.95,
            ),
            f"{distance}mi at {bearing}° ({compass})",
            font=AdifToThermal.details_font,
            anchor="ms",
        )

        # Datetime (above location)
        d.text(
            (
                (AdifToThermal.THERMAL_WIDTH - square_size) / 2 + square_size,
                loc_bbox[1] - 7,
            ),
            the_time.strftime("%Y-%m-%d %H:%M:%SZ"),
            fill=AdifToThermal.BLACK,
            font=AdifToThermal.details_font,
            anchor="ms",
        )
        datetime_bbox = d.textbbox(
            (
                (AdifToThermal.THERMAL_WIDTH - square_size) / 2 + square_size,
                loc_bbox[1] - 7,
            ),
            the_time.strftime("%Y-%m-%d %H:%M:%SZ"),
            font=AdifToThermal.details_font,
            anchor="ms",
        )
        
        # Frequency (above datetime)
        d.text(
            (
                (AdifToThermal.THERMAL_WIDTH - square_size) / 2 + square_size,
                datetime_bbox[1] - 7,
            ),
            f"{freq} MHz",
            fill=AdifToThermal.BLACK,
            font=AdifToThermal.details_font,
            anchor="ms",
        )
        freq_bbox = d.textbbox(
            (
                (AdifToThermal.THERMAL_WIDTH - square_size) / 2 + square_size,
                datetime_bbox[1] - 7,
            ),
            f"{freq} MHz",
            font=AdifToThermal.details_font,
            anchor="ms",
        )

        # Grid and DX
        # Vertically centered between the bottom of the callsign and the top of the mode box
        # Horizonally centered in the left-over space to the right of the mode box
        dx_text = self.find_country(their_call)
        if their_grid:
            # If for some reason we have their six-digit grid, trim to 4
            short_grid = their_grid[0:4]
            dx_text = f"{short_grid} {dx_text}"
        d.text(
            (
                (AdifToThermal.THERMAL_WIDTH - square_size) / 2 + square_size,
                freq_bbox[1] - 7,
            ),
            dx_text,
            fill=AdifToThermal.BLACK,
            font=AdifToThermal.details_font,
            anchor="ms",
        )

        # Contact Count
        d.text(
            (square_size / 2, callsign_bbox[3] + 0.05 * AdifToThermal.THERMAL_HEIGHT),
            f"#{self.contact_count}",
            fill=AdifToThermal.BLACK,
            font=AdifToThermal.details_font,
            anchor="mt",
        )

        # Signal Report
        d.text(
            (
                square_size / 2,
                AdifToThermal.THERMAL_HEIGHT
                - square_size
                - 0.02 * AdifToThermal.THERMAL_HEIGHT,
            ),
            f"S{rst_s} R{rst_r}",
            fill=AdifToThermal.BLACK,
            font=AdifToThermal.sig_font,
            anchor="mb",
        )

        # OK, print it!
        
        if not TEST:
            self.printer.image(img, center=True)
            self.printer.ln(count=3)
        else:
            img.save("testimg.png")
        print(f"Printed contact with {their_call}")


def follow(file, sleep_sec=0.1) -> Iterator[str]:
    """Yield each line from a file as they are written.
    `sleep_sec` is the time to sleep after empty reads."""
    # Stolen from https://stackoverflow.com/a/54263201

    line = ""
    while True:
        tmp = file.readline()
        if tmp is not None:
            line += tmp
            if line.endswith("\n"):
                yield line
                line = ""
        elif sleep_sec:
            time.sleep(sleep_sec)


if __name__ == "__main__":
    
    # TEROW printer I have: printer=Usb(0x0416, 0x5011, 0, profile="POS-5890"
    # It's a POS5890 printer (https://mike42.me/escpos-printer-db/#profiles/POS-5890)
    # Bluetooth printer (I connect to over USB) I have: printer=Usb(0x0483, 0x5720, 0)
    # NOTE: First-time setup: https://python-escpos.readthedocs.io/en/latest/user/installation.html
    
    if not TEST:
        #instance = AdifToThermal(printer=Usb(0x0416, 0x5011, 0, profile="POS-5890"))
        instance = AdifToThermal(printer=Usb(0x0483, 0x5720, 0))
    else:
        instance = AdifToThermal()

    instance.load_cty("cty.dat")
    
    if TEST:
        instance.contact_count = 5
        instance.print_contact("<call:5>AG6QV <gridsquare:4>CN87 <mode:3>FT8 <rst_sent:3>-13 <rst_rcvd:3>-10 <qso_date:8>20230101 <time_on:6>002230 <qso_date_off:8>20230101 <time_off:6>002330 <band:3>12m <freq:9>24.917699 <station_callsign:4>K3QB <my_gridsquare:6>CN87UM <tx_pwr:3>50w <comment:21>Aerial-51 807-HD 10ft <eor>")
    else:
        with open(FILENAME_TO_WATCH, "r") as file:
            initial_lines = file.readlines()
            line_count = instance.load_previous_contact_count(initial_lines)
            print(f"Initial line count: {instance.contact_count}")
            for line in follow(file):
                instance.print_contact(line)
