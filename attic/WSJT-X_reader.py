import re

# Constants
MyCall = "M7KCM"  # Your actual callsign

# Frequency bands
BANDS = [
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
    ('70cm', 430000, 440000)
]

# Regular expression pattern to match lines
qso_pattern = re.compile(
    r'(?P<date>\d{6})_(?P<time>\d{6})\s+(?P<freq>\d+\.\d+)\s+(?P<txrx>Rx|Tx)\s+(?P<mode>\w+)\s+'
    r'(?P<signal>-?\d+)\s+(?P<dt>-?\d+\.\d+)\s+(?P<offset>\d+)\s+(?P<message>.+)'
)

def get_band(freq):
    """Determine the band based on the frequency."""
    freq_khz = float(freq) * 1000  # Convert MHz to kHz
    for band, lower, upper in BANDS:
        if lower <= freq_khz <= upper:
            return band
    return "Unknown"

def process_all_txt(file_path):
    conversations = []  # To store ongoing conversations
    current_conversation = None
    contributing_lines = 0
    non_contributing_lines = 0
    unmatched_lines = 0
    total_conversations = 0

    with open(file_path, 'r') as f:
        for line in f:
            match = qso_pattern.match(line)
            if not match:
                unmatched_lines += 1
                continue

            data = match.groupdict()
            message = data['message'].strip()
            if MyCall not in message:
                non_contributing_lines += 1
                continue

            contributing_lines += 1
            parts = message.split()

            # Determine the band from the frequency
            band = get_band(data['freq'])

            # Check if this is the start of a new conversation
            if current_conversation is None or MyCall not in current_conversation['messages'][-1]:
                # Start new conversation
                current_conversation = {
                    'start_time': f"{data['date']}_{data['time']}",
                    'partner': parts[1] if parts[0] == MyCall else parts[0],
                    'location': parts[2] if len(parts) > 2 and parts[2] not in ['73', 'RR73'] else None,
                    'band': band,
                    'frequency_offset': data['offset'],
                    'signal_report_from_me': None,
                    'signal_report_to_me': None,
                    'end_time': None,
                    'messages': [message]
                }
                conversations.append(current_conversation)
                total_conversations += 1  # Count the new conversation
            else:
                # Add to ongoing conversation
                current_conversation['messages'].append(message)

            # Update signal reports if present
            if len(parts) >= 3:
                if parts[0] == MyCall and parts[2].startswith('+') or parts[2].startswith('-'):
                    current_conversation['signal_report_to_me'] = parts[2]
                elif parts[1] == MyCall and parts[2].startswith('+') or parts[2].startswith('-'):
                    current_conversation['signal_report_from_me'] = parts[2]

            # End conversation on '73' or 'RR73'
            if '73' in message:
                current_conversation['end_time'] = f"{data['date']}_{data['time']}"
                current_conversation = None  # Reset for next conversation

    return conversations, contributing_lines, non_contributing_lines, unmatched_lines, total_conversations

# Main processing
all_txt_file = 'ALL.TXT'

conversations, contrib_lines, non_contrib_lines, unmatched_lines, total_conversations = process_all_txt(all_txt_file)

# Display conversation details
for conv in conversations:
    print(f"Conversation with {conv['partner']}:")
    print(f"Start time: {conv['start_time']}")
    print(f"End time: {conv['end_time']}")
    print(f"Band: {conv['band']}")
    print(f"Frequency Offset: {conv['frequency_offset']}")
    print(f"Location: {conv['location']}")
    print(f"Signal report to me: {conv['signal_report_to_me']}")
    print(f"Signal report from me: {conv['signal_report_from_me']}")
    print(f"Messages: {conv['messages']}")
    print('-' * 40)

# Display results
print(f"Total conversations: {total_conversations}")
print(f"Contributing lines: {contrib_lines}")
print(f"Non-contributing lines: {non_contrib_lines}")
print(f"Unmatched lines: {unmatched_lines}")
