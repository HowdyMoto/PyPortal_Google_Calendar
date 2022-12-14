# SPDX-FileCopyrightText: 2021 Brent Rubell, written for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense
import time
from adafruit_oauth2 import OAuth2
from adafruit_display_shapes.line import Line
from adafruit_display_shapes.rect import Rect
from adafruit_pyportal import PyPortal
import rtc

CALENDAR_ID = "wrightbagwell@gmail.com"
MAX_EVENTS = 5
REFRESH_TIME_MINS = 1
BACKGROUND_COLOR = 0x000000
INDENT_TIME = 16
INDENT_EVENT = 96
INDENT_TITLE = 72
TOPINDENT_EVENT1 = 96
EVENT_SPACING_Y = 40
TRUNCATE_EVENTNAME_LENGTH = 42
TEXT_COLOR = 0XFFFFFF
TITLE_COLOR = 0XDDDDDD
GCAL_ICON = "./bitmaps/GCal_32.bmp"
FONT_EVENTS = "fonts/Arial-14.pcf"
FONT_TITLE = "fonts/Arial-18.pcf"

MONTHS = {
    1: "Jan",
    2: "Feb",
    3: "Mar",
    4: "Apr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Aug",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dec",
}

# Dict. of day names for pretty-printing the header
WEEKDAYS = {
    0: "Monday",
    1: "Tuesday",
    2: "Wednesday",
    3: "Thursday",
    4: "Friday",
    5: "Saturday",
    6: "Sunday",
}

# Get secrets from secrets.py
try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise

# Create the PyPortal object
pyportal = PyPortal()
r = rtc.RTC()

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
    """Gets local time from Adafruit IO and converts to RFC3339 timestamp."""
    print("fetching local time...")
    pyportal.get_local_time(secrets["timezone"])
    print("Time after fetching=", r.datetime.tm_hour, r.datetime.tm_min)
    # Format as RFC339 timestamp
    cur_time = r.datetime
    if time_max:  # maximum time to fetch events is midnight (4:59:59UTC)
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
    print("fetching calendar events...")

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
        raise RuntimeError("Error:", resp_json)
    resp.close()
    # parse the 'items' array so we can iterate over it easier
    items = []
    resp_items = resp_json["items"]
    if not resp_items:
        print("No events scheduled for today!")
    for event in range(0, len(resp_items)):
        items.append(resp_items[event])
    return items


def format_datetime(datetime, pretty_date=False):
    """Formats ISO-formatted datetime returned by Google Calendar API into a struct_time.
    :param str datetime: Datetime string returned by Google Calendar API
    :return: struct_time
    """
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
        # convert to 12hr time
        hours -= 12
    # via https://github.com/micropython/micropython/issues/3087
    formatted_time = "{:01d}:{:02d}{:s}".format(hours, minutes, am_pm)
    if pretty_date:  # return a nice date for header label
        formatted_date = "{} {}.{:02d}, {:04d} ".format(
            WEEKDAYS[r.datetime[6]], MONTHS[month], mday, year
        )
        return formatted_date
    # Event occurs today, return the time only
    return formatted_time


def create_event_labels():
    # Create n=MAX_EVENTS labels that will later be populated with calendar data.
    for event_idx in range(MAX_EVENTS):
        event_time_label = pyportal.add_text(
            text_font=FONT_EVENTS,
            text_position=(INDENT_TIME, TOPINDENT_EVENT1 + (event_idx * EVENT_SPACING_Y)),
            text_color=TEXT_COLOR,
            text = "00:00"
        )
        event_text_label = pyportal.add_text(
            text_font=FONT_EVENTS,
            text_position=(INDENT_EVENT, TOPINDENT_EVENT1 + (event_idx * EVENT_SPACING_Y)),
            text_color=TEXT_COLOR,
            text = "Temp event Name"
            # line_spacing=0.75,
        )
        event_labels.append((event_time_label, event_text_label))


def display_calendar_events(resp_events):
    print("displaying events")
    for event_idx in range(len(resp_events)):
        event = resp_events[event_idx]                              # one event from the array of events  
        event_name = event["summary"]      
        if (len(event_name) > TRUNCATE_EVENTNAME_LENGTH ):          # in case of very long event names, truncate and add an ellipsis. 
            event_name = event_name[:(TRUNCATE_EVENTNAME_LENGTH - 3)] + "..."                                  
        event_start = event["start"]["dateTime"]
        print("===", "Event Description:", event_name)
        print("===", "Event Time:", format_datetime(event_start))
        pyportal.set_text(
            format_datetime(event_start),   # The text to display
            event_labels[event_idx][0]      # The pyportal label index to display it in
        )
        pyportal.set_text(
            event_name,
            event_labels[event_idx][1]
        )

        # If an event is coming up soon, draw it inside of a box that grabs attention
        # rect_top = Rect(0, 0, 480, 64, fill=0x161616)
        # pyportal.splash.append(rect_top)

    # Clear any unused labels
    for event_idx in range(len(resp_events), MAX_EVENTS):
        pyportal.set_text("", event_labels[event_idx][0])
        pyportal.set_text("", event_labels[event_idx][1])

###### Set up UI ######
pyportal.set_background(BACKGROUND_COLOR)
pyportal.set_background(GCAL_ICON, position=(16, 16))

# The date label at the top of the screen
label_date_header = pyportal.add_text(
    text_font=FONT_TITLE,
    text_position=(INDENT_TITLE, 32),
    text_color=TITLE_COLOR,
)
event_labels = []           # Array of labels to display event data
create_event_labels()

if not google_auth.refresh_access_token():
    raise RuntimeError("Unable to refresh access token - has the token been revoked?")
access_token_obtained = int(time.monotonic())

events = []
while True:
    # check if we need to refresh token
    if (
        int(time.monotonic()) - access_token_obtained
        >= google_auth.access_token_expiration
    ):
        print("Access token expired, refreshing...")
        if not google_auth.refresh_access_token():
            raise RuntimeError(
                "Unable to refresh access token - has the token been revoked?"
            )
        access_token_obtained = int(time.monotonic())

    now = get_current_time()
    pyportal.set_text(format_datetime(now, pretty_date=True), label_date_header)
    events = get_calendar_events(CALENDAR_ID, MAX_EVENTS, now)
    display_calendar_events(events)

    print("Sleeping for %d minutes" % REFRESH_TIME_MINS)
    time.sleep(REFRESH_TIME_MINS * 60)