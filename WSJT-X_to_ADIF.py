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

# Inline grid/report extraction into parse_wsjtx_log for clarity

# Function to extract and parse lines from ALL.TXT that are valid QSOs
def parse_wsjtx_log(file_path, my_call):
    qso_data = []
    # Track QSO states: {callsign: {'state': 'heard'|'replied'|'complete', 'report': str, 'datetime': str, 'time': str, 'freq': str, 'band': str, 'mode': str}}
    qso_states = {}
    valid_qso_count = 0
    non_contributing_count = 0
    invalid_lines_count = 0

    with open(file_path, 'r') as f:
        lines = f.readlines()

        # Pattern to match QSO lines in the ALL.TXT file
        qso_pattern = re.compile(r"(\d{6})_(\d{6})\s+([\d.]+)\s+(Rx|Tx)\s+(\w+)\s+(-?\d+)\s+(-?\d+\.\d+)\s+(\d+)\s+(.*)")

        # Store grid squares seen in CQ messages (first field is grid for the transmitting station)
        # Key: callsign, Value: their grid square (from when they called CQ and I heard it)
        seen_grids = {}

        for line in lines:
            match = qso_pattern.match(line.strip())
            if match:
                date_str, time_str, freq_mhz, direction, mode, rst_rcvd, _, _, message = match.groups()
                frequency = float(freq_mhz)

                # Extract grid and report from message
                parts = message.split()
                sender = parts[0]
                recipient = parts[1] if len(parts) > 1 else ""

                # Find grid square (Maidenhead format)
                message_grid = None
                for part in parts:
                    if re.match(r'^[A-Z]{2}\d{2}([A-Z0-9]{0,4})?$', part, re.IGNORECASE):
                        message_grid = part.upper()
                        break

                # Find RST report (numeric, optional negative)
                report = None
                for part in parts:
                    if re.match(r'^-?\d{2,4}$', part):
                        report = part
                        break

                # Determine the other station's callsign and capture grids from CQ calls
                # Do this BEFORE filtering non-contributing lines to ensure we capture grids from CQ messages
                other_station = None
                if sender == 'CQ' and recipient != my_call and message_grid:
                    # We received a CQ call from another station: "CQ THEIRCALL THEIRGRID"
                    # Capture their grid even if our callsign is not in the message
                    other_station = recipient
                    seen_grids[other_station] = message_grid
                elif sender == my_call:
                    # We transmitted to them
                    other_station = recipient
                elif recipient == my_call:
                    # They transmitted to us
                    other_station = sender

                # Only process lines that mention my_call (unless it's a CQ we just captured)
                if my_call not in message and other_station is None:
                    non_contributing_count += 1
                    continue

                if other_station is None or other_station == my_call:
                    continue

                # Initialize QSO state if not already tracked
                if other_station not in qso_states:
                    qso_states[other_station] = {
                        'state': 'none',
                        'report_received': None,
                        'their_report': None,
                        'qso_datetime': None,
                        'qso_time': None,
                        'freq': None,
                        'band': None,
                        'mode': None,
                        'their_grid': None,
                        'our_grid': None
                    }

                state = qso_states[other_station]
                is_tx = (direction == 'Tx')

                # When we transmit and include a grid, that's our grid
                if is_tx and message_grid:
                    state['our_grid'] = message_grid

                # When we receive a message from them with a grid, that's their grid
                if not is_tx and message_grid and sender == other_station:
                    state['their_grid'] = message_grid

                # Track their report
                if not is_tx and report:
                    state['their_report'] = report
                    if state['qso_datetime'] is None:
                        qso_datetime = datetime.strptime(date_str + time_str, "%y%m%d%H%M%S")
                        state['qso_datetime'] = qso_datetime.strftime("%Y%m%d")
                        state['qso_time'] = qso_datetime.strftime("%H%M")
                        state['freq'] = freq_mhz
                        state['band'] = get_band(frequency)
                        state['mode'] = mode

                # QSO is complete when we have their report
                if state['their_report'] and state['state'] != 'complete':
                    state['state'] = 'complete'
                    # Use their_grid from reply if available, otherwise fallback to seen grid from CQ call
                    their_actual_grid = state['their_grid'] if state['their_grid'] else seen_grids.get(other_station)
                    qso_data.append({
                        'call': other_station,
                        'band': state['band'],
                        'freq': state['freq'],
                        'mode': state['mode'],
                        'qso_date': state['qso_datetime'],
                        'time_on': state['qso_time'],
                        'rst_sent': '599',
                        'rst_rcvd': state['their_report'],
                        'my_grid': state['our_grid'] if state['our_grid'] else 'AA00aa',
                        'grid': their_actual_grid if their_actual_grid else 'unknown',
                    })
                    valid_qso_count += 1

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

# Function to validate grid square format
def validate_grid(grid):
    # Maidenhead grid square: 2-6 characters, pattern AA00, AA00aa, AA00aa11
    pattern = r'^[A-Z]{2}\d{2}([A-Z0-9]{0,4})?$'
    if not re.match(pattern, grid.upper()):
        return False
    return True

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
