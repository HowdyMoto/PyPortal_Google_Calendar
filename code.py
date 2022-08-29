import time
from adafruit_oauth2 import OAuth2
from adafruit_display_shapes.line import Line
from adafruit_pyportal import PyPortal
import rtc

CALENDAR_ID = "fromsecrets"
MAX_EVENTS = 5
REFRESH_TIME = 5

BACKGROUND_COLOR = 0x000000
BACKGROUND_ERROR_COLOR = 0x000000
TITLE_COLOR = 0x00cc00
TIME_COLOR = 0xFFFFFF
EVENT_COLOR = 0xFFFFFF
FONT_EVENTS = "fonts/Arial-14.pcf"
FONT_TITLE = "fonts/Arial-18.pcf"

# TODO -------------------------------------
# Add audio
# Highlight upcoming and current meetings

LABEL_INDENT = 10

MONTHS = {
    1: "January",
    2: "February",
    3: "March",
    4: "April",
    5: "May",
    6: "June",
    7: "July",
    8: "August",
    9: "September",
    10: "October",
    11: "November",
    12: "December",
}

WEEKDAYS = {
    0: "Monday",
    1: "Tuesday",
    2: "Wednesday",
    3: "Thursday",
    4: "Friday",
    5: "Saturday",
    6: "Sunday",
}

# pylint: disable=no-name-in-module,wrong-import-order
try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise
CALENDAR_ID = secrets["google_email"]

pyportal = PyPortal()
realTimeClock = rtc.RTC()
pyportal.network.connect()

# Initialize an OAuth2 object with GCal API scope
scopes = ["https://www.googleapis.com/auth/calendar.readonly"]
google_auth = OAuth2(
    pyportal.network.requests,
    secrets["google_client_id"],
    secrets["google_client_secret"],
    scopes,
    secrets["google_access_token"],
    secrets["google_refresh_token"],
)

def get_current_time(time_max=False):
    pyportal.get_local_time(secrets["timezone"])        # Get local time from Adafruit IO
    cur_time = realTimeClock.datetime                   # Format as RFC339 timestamp
    if time_max:                                        # maximum time to fetch events is midnight (4:59:59UTC)
        cur_time_max = time.struct_time(
            (
                cur_time[0],
                cur_time[1],
                cur_time[2] + 1,
                4,
                59,
                59,
                cur_time[6],
                cur_time[7],
                cur_time[8],
            )
        )
        cur_time = cur_time_max
    cur_time = "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}{:s}".format(
        cur_time[0],
        cur_time[1],
        cur_time[2],
        cur_time[3],
        cur_time[4],
        cur_time[5],
        "Z",
    )
    return cur_time

def get_calendar_events(calendar_id, max_events, time_min):
    #Returns events on a specified calendar. Response is a list of events ordered by their start date/time in ascending order.
    time_max = get_current_time(time_max=True)
    print("Fetching calendar events from {0} to {1}".format(time_min, time_max))

    headers = {
        "Authorization": "Bearer " + google_auth.access_token,
        "Accept": "application/json",
        "Content-Length": "0",
    }
    url = (
        "https://www.googleapis.com/calendar/v3/calendars/{0}"
        "/events?maxResults={1}&timeMin={2}&timeMax={3}&orderBy=startTime"
        "&singleEvents=true".format(calendar_id, max_events, time_min, time_max)
    )
    resp = pyportal.network.requests.get(url, headers=headers)
    resp_json = resp.json()
    if "error" in resp_json:
        pyportal.set_background(BACKGROUND_ERROR_COLOR)
        raise RuntimeError("Error:", resp_json)
    resp.close()
    items = []                          # parse the 'items' array so we can iterate over it easier
    resp_items = resp_json["items"]
    if not resp_items:
        print("No events scheduled for today!")
    for event in range(0, len(resp_items)):
        items.append(resp_items[event])
    return items

def format_datetime(datetime, pretty_date=False):
    #   Formats ISO-formatted datetime returned by Google Calendar API into a struct_time.
    #   :param str datetime: Datetime string returned by Google Calendar API
    #   :return: struct_time
    times = datetime.split("T")
    the_date = times[0]
    the_time = times[1]
    year, month, mday = [int(x) for x in the_date.split("-")]
    the_time = the_time.split("-")[0]
    if "Z" in the_time:
        the_time = the_time.split("Z")[0]
    hours, minutes, _ = [int(x) for x in the_time.split(":")]
    am_pm = "am"
    if hours >= 12:
        am_pm = "pm"
        hours -= 12         # convert to 12hr time
    # via https://github.com/micropython/micropython/issues/3087
    formatted_time = "{:01d}:{:02d}{:s}".format(hours, minutes, am_pm)
    if pretty_date:         # return a nice date for header label
        formatted_date = "{} {} {:02d}".format(
            WEEKDAYS[realTimeClock.datetime[6]], 
            MONTHS[month], 
            mday, 
            year
        )
        return formatted_date
    # Event occurs today, return the time only
    return formatted_time

def create_event_labels():
    for event_idx in range(MAX_EVENTS):
        event_start_label = pyportal.add_text(
            text_font=FONT_EVENTS,
            text_position=(24, 72 + (event_idx * 40)),
            text_color=TIME_COLOR,
        )
        event_text_label = pyportal.add_text(
            text_font=FONT_EVENTS,
            text_position=(112, 72 + (event_idx * 40)),
            text_color=EVENT_COLOR,
            line_spacing=0.75,
        )
        event_labels.append((event_start_label, event_text_label))

def display_calendar_events(resp_events):
    # Display all calendar events
    for event_idx in range(len(resp_events)):
        event = resp_events[event_idx]
        event_name = PyPortal.wrap_nicely(event["summary"], 40)             # wrap event name around second line if necessary
        event_name = "\n".join(event_name[0:2])                             # only wrap 2 lines, truncate third..
        event_start = event["start"]["dateTime"]
        print("-" * 50)
        print("Event Description: ", event_name)
        print("Event Time:", format_datetime(event_start))
        print("-" * 50)
        pyportal.set_text(format_datetime(event_start), event_labels[event_idx][0])
        pyportal.set_text(event_name, event_labels[event_idx][1])

    # Clear any unused labels
    for event_idx in range(len(resp_events), MAX_EVENTS):
        pyportal.set_text("", event_labels[event_idx][0])
        pyportal.set_text("", event_labels[event_idx][1])

pyportal.set_background(BACKGROUND_COLOR)
line_header = Line(24, 50, 300, 50, color=TITLE_COLOR)
pyportal.splash.append(line_header)
label_header = pyportal.add_text(
    text_font=FONT_TITLE,
    text_position=(24, 30),
    text_color=TITLE_COLOR,
)
event_labels = []
create_event_labels()

if not google_auth.refresh_access_token():
    raise RuntimeError("Unable to refresh access token - has the token been revoked?")
access_token_obtained = int(time.monotonic())

events = []
while True:
    # check if we need to refresh token
    if ( int(time.monotonic()) - access_token_obtained >= google_auth.access_token_expiration ):
        print("Access token expired, refreshing...")
        if not google_auth.refresh_access_token():
            raise RuntimeError( "Unable to refresh access token - has the token been revoked?" )
        access_token_obtained = int(time.monotonic())

    # fetch calendar events!
    print("fetching local time...")
    now = get_current_time()
    pyportal.set_text(format_datetime(now, pretty_date=True), label_header)
    print("fetching calendar events...")
    events = get_calendar_events(CALENDAR_ID, MAX_EVENTS, now)
    print("displaying events")
    display_calendar_events(events)
    print("Sleeping for %d minutes" % REFRESH_TIME)
    time.sleep(REFRESH_TIME * 60)