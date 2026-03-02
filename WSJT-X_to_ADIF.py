#!/usr/bin/env python3
import argparse
import re
import sys
from datetime import datetime

# Constants
BANDS = (
    ('160m', 1810, 2000),
    ('80m', 3500, 3800),
    ('60m', 5258.5, 5406.5),
    ('40m', 7000, 7200),
    ('30m', 10100, 10150),
    ('20m', 14000, 14350),
    ('17m', 18068, 18168),
    ('15m', 21000, 21450),
    ('12m', 24890, 24990),
    ('10m', 28000, 29700),
    ('6m', 50000, 52000),
    ('4m', 70000, 70500),
    ('2m', 144000, 146000),
    ('70m', 430000, 440000),
)

# Define a template for ADIF format
ADIF_HEADER = """\
ADIF Export from WSJT-X ALL.TXT
<EOH>
"""

ADIF_QSO_TEMPLATE = """\
<CALL:{call_len}>{call}<BAND:{band_len}>{band}<FREQ:{freq_len}>{freq}<MODE:{mode_len}>{mode}<QSO_DATE:{qso_date_len}>{qso_date}<TIME_ON:{time_on_len}>{time_on}<RST_SENT:{rst_len}>{rst_sent}<RST_RCVD:{rst_len}>{rst_rcvd}<MY_GRIDSQUARE:{my_grid_len}>{my_grid}<GRIDSQUARE:{grid_len}>{grid}<EOR>
"""

# Function to get band based on frequency
def get_band(frequency):
    for band in BANDS:
        if band[1] <= frequency * 1000 < band[2]:  # Convert frequency from MHz to kHz
            return band[0]
    return "unknown"

# Function to parse a QSO message and return a dictionary with details
def parse_message(message):
    parts = message.split()
    if len(parts) < 2:
        return None

    sender = parts[0]
    recipient = parts[1] if len(parts) > 1 else ""

    # Determine if this is a 73 or RR73 message
    if "73" in message:
        qso_complete = True
    else:
        qso_complete = False

    return {
        'sender': sender,
        'recipient': recipient,
        'qso_complete': qso_complete,
        'message': message
    }

# Function to extract and parse lines from ALL.TXT that are valid QSOs
def parse_wsjtx_log(file_path, my_call):
    qso_data = []
    ongoing_qsos = {}  # To track ongoing exchanges by recipient
    valid_qso_count = 0
    non_contributing_count = 0
    invalid_lines_count = 0

    with open(file_path, 'r') as f:
        lines = f.readlines()

        # Pattern to match QSO lines in the ALL.TXT file
        qso_pattern = re.compile(r"(\d{6})_(\d{6})\s+([\d.]+)\s+(Rx|Tx)\s+(\w+)\s+(-?\d+)\s+(-?\d+\.\d+)\s+(\d+)\s+(.*)")

        for line in lines:
            match = qso_pattern.match(line.strip())
            if match:
                date_str, time_str, freq_mhz, direction, mode, rst_rcvd, _, _, message = match.groups()
                frequency = float(freq_mhz)

                # Parse the message and check if it's part of a valid QSO
                parsed_msg = parse_message(message)
                if not parsed_msg:
                    non_contributing_count += 1
                    continue

                sender = parsed_msg['sender']
                recipient = parsed_msg['recipient']
                qso_complete = parsed_msg['qso_complete']

                if my_call in message:
                    if sender == my_call or recipient == my_call:
                        # Track conversation between my_call and other station
                        other_station = recipient if sender == my_call else sender

                        if qso_complete:
                            # Log valid QSO if we have a complete message
                            qso_datetime = datetime.strptime(date_str + time_str, "%y%m%d%H%M%S")
                            qso_date = qso_datetime.strftime("%Y%m%d")
                            qso_time = qso_datetime.strftime("%H%M")

                            # Determine band using frequency
                            band = get_band(frequency)

                            # Add the QSO data to the list
                            qso_data.append({
                                'call': other_station,
                                'band': band,
                                'freq': freq_mhz,
                                'mode': mode,
                                'qso_date': qso_date,
                                'time_on': qso_time,
                                'rst_sent': '599',  # Assuming standard report
                                'rst_rcvd': rst_rcvd.strip(),
                                'my_grid': 'AA00aa',  # Placeholder for your grid square
                                'grid': 'unknown',  # No grid data available
                            })
                            valid_qso_count += 1
                        else:
                            # Track incomplete conversation
                            ongoing_qsos[other_station] = parsed_msg
                else:
                    non_contributing_count += 1
            else:
                invalid_lines_count += 1

    return qso_data, valid_qso_count, non_contributing_count, invalid_lines_count

# Function to write the ADIF file
def write_adif(qso_data, output_file, my_call):
    global ADIF_HEADER
    ADIF_HEADER = f"""\
ADIF Export from WSJT-X ALL.TXT for {my_call}
<EOH>
"""
    with open(output_file, 'w') as adif_file:
        adif_file.write(ADIF_HEADER)

        for qso in qso_data:
            adif_qso = ADIF_QSO_TEMPLATE.format(
                call=qso['call'], call_len=len(qso['call']),
                band=qso['band'], band_len=len(qso['band']),
                freq=qso['freq'], freq_len=len(qso['freq']),
                mode=qso['mode'], mode_len=len(qso['mode']),
                qso_date=qso['qso_date'], qso_date_len=len(qso['qso_date']),
                time_on=qso['time_on'], time_on_len=len(qso['time_on']),
                rst_sent=qso['rst_sent'], rst_rcvd=qso['rst_rcvd'], rst_len=len(qso['rst_sent']),
                my_grid=qso['my_grid'], my_grid_len=len(qso['my_grid']),
                grid=qso['grid'], grid_len=len(qso['grid']),
            )
            adif_file.write(adif_qso)

# Function to validate callsign format
def validate_callsign(callsign):
    # Basic amateur radio callsign regex pattern
    pattern = r'^[A-Z]{1,2}[0-9][A-Z]{0,2}(\/[A-Z0-9]{1,3})?$'
    if not re.match(pattern, callsign.upper()):
        print(f"Error: Invalid callsign format '{callsign}'")
        print("Expected format: 2-5 alphanumeric characters, starting with letters, containing a digit")
        print("Examples: K1ABC, WA1XYZ, VE2K")
        sys.exit(1)
    return callsign.upper()

# Main logic to parse the ALL.TXT and write to ADIF
def main():
    parser = argparse.ArgumentParser(
        description='Convert WSJT-X ALL.TXT log file to ADIF format',
        epilog='Required arguments:\n'
               '  callsign      Your amateur radio callsign (e.g., K1ABC, WA1XYZ)\n'
               '  all_txt_path  Path to WSJT-X ALL.TXT log file',
        formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument(
        'callsign',
        help='Your amateur radio callsign (required)'
    )

    parser.add_argument(
        'all_txt_path',
        help='Path to WSJT-X ALL.TXT log file (required)'
    )

    parser.add_argument(
        '-o', '--output',
        default='output_log.adi',
        help='Output ADIF file name (default: output_log.adi)'
    )

    args = parser.parse_args()

    # Validate callsign
    my_call = validate_callsign(args.callsign)

    # Check if ALL.TXT file exists
    import os
    if not os.path.exists(args.all_txt_path):
        print(f"Error: ALL.TXT file not found at '{args.all_txt_path}'")
        sys.exit(1)

    qso_data, valid_qso_count, non_contributing_count, invalid_lines_count = \
        parse_wsjtx_log(args.all_txt_path, my_call)

    write_adif(qso_data, args.output, my_call)

    print(f"ADIF log written to {args.output}")
    print(f"Valid QSOs logged: {valid_qso_count}")
    print(f"Non-contributing lines: {non_contributing_count}")
    print(f"Invalid lines (not matching regex): {invalid_lines_count}")

if __name__ == "__main__":
    main()
