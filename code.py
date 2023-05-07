import time
import board
import busio
from digitalio import DigitalInOut
from adafruit_esp32spi import adafruit_esp32spi
from adafruit_oauth2 import OAuth2
from adafruit_display_shapes.rect import Rect
from adafruit_pyportal import PyPortal
import adafruit_datetime as datetime
import rtc
try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise

CALENDAR_ID = secrets["google_email"]
MAX_TIME_OFFSET = 24
ZULU_TIME_OFFSET = secrets["timezone_offset"]
TWELVE_HOUR_CLOCK_FORMAT = True
MAX_EVENTS = 5
REFRESH_TIME = 60
BACKGROUND_COLOR = 0x000000
ERROR_COLOR = 0xCC0000
ERROR_COLOR2 = 0xCC00CC
INDENT_DATE = 72
INDENT_EVENT_TIME = 16
INDENT_EVENT_NAME = 96
TOPINDENT_EVENT1 = 96
EVENT_SPACING_Y = 40
TRUNCATE_EVENTNAME_LENGTH = 42
TEXT_COLOR = 0XFFFFFF
TITLE_COLOR = 0XFFFFFF
BACKLIGHT_INTENSITY = 0.6
GCAL_ICON = "bitmaps/GCal_32.bmp"
FONT_EVENTS = "fonts/Arial-14.pcf"
FONT_TITLE = "fonts/Arial-18.pcf"
ESP_DEBUG = False
PYPORTAL_DEBUG = False
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
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
SPI = busio.SPI(board.SCK, board.MOSI, board.MISO)
ESP32_CS = DigitalInOut(board.ESP_CS)
ESP32_READY = DigitalInOut(board.ESP_BUSY)
ESP32_RESET = DigitalInOut(board.ESP_RESET)

########## Functions ###########################################################################

# Create n=MAX_EVENTS labels that will later be populated with calendar data.
def create_event_labels():
    for i in range(MAX_EVENTS):
        event_time_label = pyportal.add_text(
            text_font=FONT_EVENTS,
            text_position=(INDENT_EVENT_TIME, TOPINDENT_EVENT1 + (i * EVENT_SPACING_Y)),
            text_color=TEXT_COLOR,
            text = "00:00"
        )
        event_text_label = pyportal.add_text(
            text_font=FONT_EVENTS,
            text_position=(INDENT_EVENT_NAME, TOPINDENT_EVENT1 + (i * EVENT_SPACING_Y)),
            text_color=TEXT_COLOR,
            text = "Temp event Name"
        )
        event_labels.append((event_time_label, event_text_label))

# Gets local time from Adafruit IO, sets device clock, and converts time_struct to RFC3339 timestamp.
def get_iso_time(time_max=False):    

    # First, retrieve internet time and set the hardware clock
    while True:
        try:
            pyportal.get_local_time(secrets["timezone"])
            print("Fetched time=", r.datetime )
            break
        except (ValueError, RuntimeError, ConnectionError, OSError) as e:
            print("Request for local time failed, retrying\n", e)
            # Uncomment below to see when the device encounters hardware errors that it recovers from.
            # pyportal.set_background(ERROR_COLOR)
            esp.reset()
            esp.disconnect()
            pyportal.network.connect()
            time.sleep(5)

    cur_datetime = datetime.datetime.now()

    if time_max:
        cur_datetime = cur_datetime + datetime.timedelta(hours=MAX_TIME_OFFSET)

    cur_iso_time = datetime.datetime.isoformat(cur_datetime) + ZULU_TIME_OFFSET
    print("CUR ISO TIME=", cur_iso_time)

    return cur_iso_time

# Get calendar data from Google
def get_calendar_events(current_time):
    time_max = get_iso_time(time_max=True)
    print("=== Fetching calendar events from {0} to {1}".format(current_time, time_max))

    headers = {
        "Authorization": "Bearer " + google_auth.access_token,
        "Accept": "application/json",
        "Content-Length": "0",
    }

    url = (
        "https://www.googleapis.com/calendar/v3/calendars/" + CALENDAR_ID + "/events"
        + "?maxResults=" + str(MAX_EVENTS)
        + "&timeMin=" + current_time
        + "&timeMax=" + time_max
        + "&orderBy=startTime" 
        + "&singleEvents=true"
    )

    calendar_items = []
    while True:
        try:
            response = pyportal.network.requests.get(url, headers=headers)
            break
        except (ValueError, RuntimeError, ConnectionError, OSError) as e:
            print("Request for Calendar data failed, retrying\n", e)
            # Uncomment below to see when the device encounters hardware errors that it recovers from.
            # pyportal.set_background(ERROR_COLOR2)
            esp.reset()
            esp.disconnect()
            pyportal.network.connect()
            time.sleep(5)

    resp_json = response.json()
    if "error" in resp_json:
        raise RuntimeError("Error:", resp_json)
    response.close()

    # parse the 'items' array so we can iterate over it easily
    resp_items = resp_json["items"]
    if not resp_items:
        print("No events scheduled for today!")
    for event in range(0, len(resp_items)):
        calendar_items.append(resp_items[event])

    return calendar_items

# Draw calendar data
def display_calendar_events(response_events):
    print("=== Displaying events")

    for i, event in enumerate(response_events):

        # Get and draw event name
        event_name = event["summary"] 
        print("=====", "Event Description:", event_name)
        # in case of very long event names, truncate & add ellipsis. 
        if (len(event_name) > TRUNCATE_EVENTNAME_LENGTH ):          
            event_name = event_name[:(TRUNCATE_EVENTNAME_LENGTH - 3)] + "..."
        
        # Get and draw event start time
        event_start_isotime = event["start"]["dateTime"]
        print("===== Event Time:", format_datetime(event_start_isotime))

        # Draw the event time in the UI
        pyportal.set_text(
            format_datetime(event_start_isotime),
            event_labels[i][0]
            )
        # Draw the event name in the UI
        pyportal.set_text(
            event_name,
            event_labels[i][1]
        )
    


    # If an event is coming up soon, draw it inside of a box that grabs attention
    # rect_top = Rect(0, 0, 480, 64, fill=0x161616)
    # pyportal.splash.append(rect_top)
    
    # Clear labels from length of response to max # of events.
    print( len(response_events) )
    for event_idx in range(len(response_events), MAX_EVENTS):
        pyportal.set_text("", event_labels[event_idx][0])
        pyportal.set_text("", event_labels[event_idx][1])

# Formats ISO-formatted datetime returned by Google Calendar API into a struct_time.
def format_datetime(datetime, pretty_date=False):
    times = datetime.split("T")
    the_date = times[0]
    the_time = times[1]
    year, month, mday = [int(x) for x in the_date.split("-")]
    the_time = the_time.split("-")[0]
    if "Z" in the_time:
        the_time = the_time.split("Z")[0]
    print(the_time) # 01:46:27
    hours, minutes, _ = the_time.split(":", 2)
    if(TWELVE_HOUR_CLOCK_FORMAT):
        am_pm = "am"
        if int(hours) >= 12:
            am_pm = "pm"
            # convert to 12hr time
            hours = int(hours) - 12
        # via https://github.com/micropython/micropython/issues/3087
        formatted_time = "{:01d}:{:02d}{:s}".format(int(hours), int(minutes), am_pm)
    else:
        formatted_time = "{:01d}:{:02d}".format(int(hours), int(minutes))
    if pretty_date:  # return a nice date for header label
        formatted_date = "{} {}.{:02d}, {:04d} ".format(
            WEEKDAYS[r.datetime[6]], MONTHS[month], mday, year
        )
        return formatted_date
    # Event occurs today, return the time only
    return formatted_time

###### MAIN PROGRAM ###############################################################################

# Create an esp object that's passed to the pyportal object. 
# Pyportal would create one automatically, but doesn't give you the ability to controle the ESP mnaually.
# You must manually reset the esp to recover from errors that occur frequently.
esp = adafruit_esp32spi.ESP_SPIcontrol(SPI, ESP32_CS, ESP32_READY, ESP32_RESET )
esp._debug = ESP_DEBUG
print( "Nina/ESP32 Firmware version:", esp.firmware_version )

pyportal = PyPortal(esp=esp, external_spi=SPI, debug=PYPORTAL_DEBUG)
pyportal.peripherals.set_backlight(BACKLIGHT_INTENSITY)
pyportal.set_background(BACKGROUND_COLOR)
pyportal.set_background(GCAL_ICON, position=(16, 16))

# Date title/label
label_date_header = pyportal.add_text(
    text = "Getting current time...",
    text_font=FONT_TITLE,
    text_position=(INDENT_DATE, 32),
    text_color=TITLE_COLOR,
)

# Array of labels to display calendar events
event_labels = []                               
create_event_labels()

r = rtc.RTC()
pyportal.network.connect()

# Initialize an OAuth2 object with GCal API scope
google_auth = OAuth2(
    pyportal.network.requests,
    secrets["google_client_id"],
    secrets["google_client_secret"],
    SCOPES,
    secrets["google_access_token"],
    secrets["google_refresh_token"],
)

if not google_auth.refresh_access_token():
    raise RuntimeError("Unable to refresh access token - has the token been revoked?")
access_token_obtained = int(time.monotonic())

calendar_events = []

while True:
    now = get_iso_time()
    pyportal.set_text( format_datetime(now, pretty_date=True), label_date_header)

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

    calendar_events = get_calendar_events(now)
    if (calendar_events):
        display_calendar_events(calendar_events)

    print("=== Sleeping for %d seconds" % REFRESH_TIME)
    time.sleep(REFRESH_TIME)
