import os, csv, time, requests, datetime

webhook_url = os.environ['DISCORD_WEBHOOK']
csv_url = os.environ['CSV_URL']

def send_discord(text):
    if text and text.strip():
        payload = {
            "content": text.strip(),
            "allowed_mentions": {"parse": ["everyone", "roles", "users"]}
        }
        requests.post(webhook_url, json=payload)

now_utc = datetime.datetime.now(datetime.timezone.utc)

response = requests.get(csv_url)
response.encoding = 'utf-8'
lines = response.text.splitlines()
reader = csv.DictReader(lines)

for row in reader:
    sched_date = row.get('Date Scheduled', '').strip()
    sched_time = row.get('Time Scheduled', '').strip()

    if sched_date and sched_time:
        try:
            parsed_date = None
            for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%m/%d'):
                try:
                    parsed_date = datetime.datetime.strptime(sched_date, fmt)
                    if fmt == '%m/%d':
                        parsed_date = parsed_date.replace(year=now_utc.year)
                    break
                except ValueError:
                    continue

            if not parsed_date:
                continue

            time_parts = sched_time.split(':')
            event_datetime = datetime.datetime(
                parsed_date.year,
                parsed_date.month,
                parsed_date.day,
                int(time_parts[0]),
                int(time_parts[1]) if len(time_parts) > 1 else 0,
                tzinfo=datetime.timezone.utc
            )

            warning_60m_time = event_datetime - datetime.timedelta(hours=1)
            diff_seconds = (warning_60m_time - now_utc).total_seconds()

            if -900 <= diff_seconds <= 840:
                event_name = row.get('Event Name', 'Event')
                print(f"Matched scheduled event: {event_name} starting at {sched_time} UTC")

                if diff_seconds > 0:
                    print(f"Aligning to exact T-60m start... sleeping {diff_seconds:.0f}s")
                    time.sleep(diff_seconds)

                # Countdown Sequence
                send_discord(row.get('Msg60'))
                time.sleep(1800)  # 30m

                send_discord(row.get('Msg30'))
                time.sleep(900)   # 15m

                send_discord(row.get('Msg15'))
                time.sleep(600)   # 10m

                send_discord(row.get('Msg5'))
                time.sleep(300)   # 5m

                send_discord(row.get('Msg0'))
                break

        except Exception as e:
            print(f"Error evaluating row {row.get('Event Name')}: {e}")
