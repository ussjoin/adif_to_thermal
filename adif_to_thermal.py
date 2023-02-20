import adif_io  # Package: adif-io
import gridtools
import socket

UDP_IP = "0.0.0.0"
UDP_PORT = 12345

# Thanks to https://gist.github.com/RobertSudwarts/acf8df23a16afdb5837f for this
def degrees_to_cardinal(d):
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
    ix = int((d + 11.25) / 22.5 - 0.02)
    return dirs[ix % 16]


# Taken from http://www.arrl.org/section-abbreviations
def section_abbrev_to_section(abbrev):
    sections = {
        "CT": "Connecticut",
        "EMA": "Eastern Massachusetts",
        "ME": "Maine",
        "NH": "New Hampshire",
        "RI": "Rhode Island",
        "VT": "Vermont",
        "WMA": "Western Massachusetts",
        "ENY": "Eastern New York",
        "NLI": "New York City - Long Island",
        "NNJ": "Northern New Jersey",
        "NNY": "Northern New York",
        "SNJ": "Southern New Jersey",
        "WNY": "Western New York",
        "DE": "Delaware",
        "EPA": "Eastern Pennsylvania",
        "MDC": "Maryland-DC",
        "WPA": "Western Pennsylvania",
        "AL": "Alabama",
        "GA": "Georgia",
        "KY": "Kentucky",
        "NC": "North Carolina",
        "NFL": "Northern Florida",
        "SC": "South Carolina",
        "SFL": "Southern Florida",
        "WCF": "West Central Florida",
        "TN": "Tennessee",
        "VA": "Virginia",
        "PR": "Puerto Rico",
        "VI": "Virgin Islands",
        "AR": "Arkansas",
        "LA": "Louisiana",
        "MS": "Mississippi",
        "NM": "New Mexico",
        "NTX": "North Texas",
        "OK": "Oklahoma",
        "STX": "South Texas",
        "WTX": "West Texas",
        "EB": "East Bay",
        "LAX": "Los Angeles",
        "ORG": "Orange",
        "SB": "Santa Barbara",
        "SCV": "Santa Clara Valley",
        "SDG": "San Diego",
        "SF": "San Francisco",
        "SJV": "San Joaquin Valley",
        "SV": "Sacramento Valley",
        "PAC": "Pacific",
        "AZ": "Arizona",
        "EWA": "Eastern Washington",
        "ID": "Idaho",
        "MT": "Montana",
        "NV": "Nevada",
        "OR": "Oregon",
        "UT": "Utah",
        "WWA": "Western Washington",
        "WY": "Wyoming",
        "AK": "Alaska",
        "MI": "Michigan",
        "OH": "Ohio",
        "WV": "West Virginia",
        "IL": "Illinois",
        "IN": "Indiana",
        "WI": "Wisconsin",
        "CO": "Colorado",
        "IA": "Iowa",
        "KS": "Kansas",
        "MN": "Minnesota",
        "MO": "Missouri",
        "NE": "Nebraska",
        "ND": "North Dakota",
        "SD": "South Dakota",
        "MAR": "Maritime",
        "NL": "Newfoundland/Labrador",
        "PE": "Prince Edward Island",
        "QC": "Quebec",
        "ONE": "Ontario East",
        "ONN": "Ontario North",
        "ONS": "Ontario South",
        "GTA": "Greater Toronto Area",
        "MB": "Manitoba",
        "SK": "Saskatchewan",
        "AB": "Alberta",
        "BC": "British Columbia",
        "NT": "Northern Territories",
    }
    
    if abbrev in sections:
        return f"{sections[abbrev]} ({abbrev})"
    else:
        return f"Unknown ({abbrev})"
    


def thermal_print(qso):
    qso_time = adif_io.time_off(qso)
    qso_time_str = qso_time.strftime("%Y-%m-%d %H:%M:%SZ")
    qso_call = qso["CALL"]
    qso_freq = qso["FREQ"]
    mode = qso["MODE"]

    # FT4 registers from WSJTX as mode MFSK, submode FT4
    if mode == "MFSK":
        if "SUBMODE" in qso:
            mode = qso["SUBMODE"]

    # TODO: Handle special Field Day ADIF logging (check 2021 logs)
    my_maid = qso["MY_GRIDSQUARE"]

    has_loc = False
    has_fd = False

    if "GRIDSQUARE" in qso:
        has_loc = True

        qso_maid = qso["GRIDSQUARE"]
        my_loc = gridtools.Grid(my_maid)
        qso_loc = gridtools.Grid(qso_maid)

        # Distance in km, bearing in degrees
        # https://gridtools.miaow.io/en/stable/
        distance, bearing = gridtools.grid_distance(my_loc, qso_loc)
        # convert to miles
        distance = distance * 0.621371
        distance = int(round(distance))
        bearing = int(round(bearing))

    if "CONTEST_ID" in qso:
        if qso["CONTEST_ID"] == "ARRL-FIELD-DAY":
            has_fd = True
            section = section_abbrev_to_section(qso["ARRL_SECT"])
            fd_class = qso["CLASS"]

    print("=========================")
    print(str(qso_time_str).center(25))
    print(f"{mode} QSO with {qso_call}".center(25))
    print(f"{qso_freq} MHz".center(25))
    if has_loc:
        print(
            f"{distance} mi at {bearing}° ({degrees_to_cardinal(bearing)})".center(25)
        )
    elif has_fd:
        print(f"Class {fd_class} team in {section}".center(25))
    else:
        print("No Location Received".center(25))
    print("=========================")


sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # Internet  # UDP
sock.bind((UDP_IP, UDP_PORT))

while True:
    data, addr = sock.recvfrom(1024)  # buffer size is 1024 bytes
    # print("received message: %s" % data)
    qsos, header = adif_io.read_from_string(str(data, "UTF-8"))
    # print("QSOs: {}\nADIF Header: {}".format(qsos, header))
    for qso in qsos:
        thermal_print(qso)
