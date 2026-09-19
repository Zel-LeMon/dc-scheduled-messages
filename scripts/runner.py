import os, csv, time, requests, datetime

webhook_url = os.environ['DISCORD_WEBHOOK']
csv_url = os.environ['CSV_URL']

def send_discord(template_text, target_event_time, default_mins):
    if not template_text or not template_text.strip():
        return

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    
    # Calculate exact remaining minutes right now
    remaining_seconds = (target_event_time - now_utc).total_seconds()
    actual_mins = round(remaining_seconds / 60)

    # Prevent non-sensical times if delayed past start
    if actual_mins <= 0 and default_mins > 0:
        actual_mins = 1

    text = template_text.strip()

    # Dynamically replace minute placeholders if the run starts late
    if default_mins > 0:
        text = text.replace(f"{default_mins} MINUTES", f"{actual_mins} MINUTES")
        text = text.replace(f"{default_mins} minutes", f"{actual_mins} minutes")
        text = text.replace(f"{default_mins} MINS", f"{actual_mins} MINS")
        text = text.replace(f"{default_mins} mins", f"{actual_mins} mins")

    payload = {
        "content": text,
        "allowed_mentions": {"parse": ["everyone", "roles", "users"]}
    }
    requests.post(webhook_url, json=payload)

def sleep_until(target_dt):
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    delay = (target_dt - now_utc).total_seconds()
    if delay > 0:
        time.sleep(delay)

now_utc = datetime.datetime.now(datetime.timezone.utc)
print(f"DEBUG - Current Runner UTC Time: {now_utc}")

response = requests.get(csv_url)
response.encoding = 'utf-8'
lines = response.text.splitlines()
reader = csv.DictReader(lines)

for row in reader:
    sched_date = row.get('Date Scheduled', '').strip()
    sched_time = row.get('Time Scheduled', '').strip()
    event_name = row.get('Event Name', 'Event')

    print(f"DEBUG - Checking Row: '{event_name}' | Date: '{sched_date}' | Time: '{sched_time}'")

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
                print(f"DEBUG - Could not parse date format for '{sched_date}'")
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

            # Define target clock times for each sequence step
            t_60 = event_datetime - datetime.timedelta(minutes=60)
            t_30 = event_datetime - datetime.timedelta(minutes=30)
            t_15 = event_datetime - datetime.timedelta(minutes=15)
            t_5  = event_datetime - datetime.timedelta(minutes=5)
            t_0  = event_datetime

            diff_seconds = (t_60 - now_utc).total_seconds()
            print(f"DEBUG - Event: '{event_name}' | Target T-60m UTC: {t_60} | diff_seconds: {diff_seconds:.0f}s ({diff_seconds/60:.1f}m)")

            # Catch window: Trigger if check lands within -25m to +14m of T-60m
            if -1500 <= diff_seconds <= 840:
                print(f"MATCH FOUND for '{event_name}'! Starting sequence...")

                # If early, sleep until exact T-60m mark
                if diff_seconds > 0:
                    time.sleep(diff_seconds)

                # 1. Msg5 (~60 min alert)
                send_discord(row.get('Msg5'), event_datetime, 60)

                # 2. Msg4 (~30 min alert)
                sleep_until(t_30)
                send_discord(row.get('Msg4'), event_datetime, 30)

                # 3. Msg3 (~15 min alert)
                sleep_until(t_15)
                send_discord(row.get('Msg3'), event_datetime, 15)

                # 4. Msg2 (~5 min alert)
                sleep_until(t_5)
                send_discord(row.get('Msg2'), event_datetime, 5)

                # 5. Msg1 (Event Live alert)
                sleep_until(t_0)
                send_discord(row.get('Msg1'), event_datetime, 0)
                break

        except Exception as e:
            print(f"Error evaluating row {event_name}: {e}")
