import board
import busio
from digitalio import DigitalInOut
import adafruit_esp32spi.adafruit_esp32spi_socket as socket
from adafruit_esp32spi import adafruit_esp32spi
import adafruit_requests as requests
from adafruit_oauth2 import OAuth2

import rtc
import time
from adafruit_datetime import datetime, timedelta

print("\n==== CALENDAR APP")

try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise

CALENDAR_ID = secrets["google_email"]
MAX_EVENTS = 8
REFRESH_TIME = 300   # in seconds

BACKGROUND_COLOR = 0x000000
BACKGROUND_ERROR_COLOR = 0xFF0000
TITLE_COLOR = 0x33cc33
TIME_COLOR = 0xFFFFFF
EVENT_COLOR = 0xFFFFFF
FONT_EVENTS = "fonts/Arial-14.pcf"
FONT_TITLE = "fonts/Arial-18.pcf"

ESP_DEBUG = False
SHOW_SSIDS = False

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
GOOGLE_AUTH = OAuth2(requests,
    secrets["google_client_id"],
    secrets["google_client_secret"],
    SCOPES,
    secrets["google_access_token"],
    secrets["google_refresh_token"],
)

_elapsed_time_since_token_auth = 0

############### WIFI, HARDWARE SETUP, GET CURRENT TIME ###############

spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
esp32_cs = DigitalInOut(board.ESP_CS)
esp32_ready = DigitalInOut(board.ESP_BUSY)
esp32_reset = DigitalInOut(board.ESP_RESET)

esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)
esp._debug = ESP_DEBUG
print( "Nina/ESP32 Firmware version:", esp.firmware_version )

requests.set_socket(socket, esp)

if esp.status == adafruit_esp32spi.WL_IDLE_STATUS:
    print("ESP32 found and in idle mode")

if (SHOW_SSIDS):
    print("SSIDs found:")
    for ap in esp.scan_networks():
        print("\t%s\t\tRSSI: %d" % (str(ap["ssid"], "utf-8"), ap["rssi"]))

print("Connecting to " + secrets["ssid"])
while not esp.is_connected:
    try:
        esp.connect_AP(secrets["ssid"], secrets["password"])
    except OSError as e:
        print("Could not connect to AP, retrying: ", e)
        continue
print(
    "Connected to", str(esp.ssid, "utf-8"), 
    "\nRSSI:", esp.rssi, 
    "\nMy IP address is", esp.pretty_ip(esp.ip_address) 
)

time_response = requests.get( "http://worldtimeapi.org/api/timezone/America/Los_Angeles" )
r = rtc.RTC()
r.datetime = time.localtime(time_response.json()['unixtime'])

############### GOOGLE OAUTH ###############

# print("Refreshing OAuth access token...")
# GOOGLE_AUTH.refresh_access_token()
# print("Access token status:", GOOGLE_AUTH.refresh_access_token())
# print("Access token expires in: ", GOOGLE_AUTH.access_token_expiration, "seconds")

# if not GOOGLE_AUTH.refresh_access_token():
#     raise RuntimeError("ERROR: Unable to refresh access token - has the token been revoked?")
# access_token_time_obtained = datetime.now()

############## DISPLAY EVENTS ##################
def display_calendar_events(resp_events):
    print("--- DISPLAYING EVENTS")
    
    for event_idx in range(len(resp_events)):
        event = resp_events[event_idx]
        event_name = event["summary"]
        #  if "error" in response_json:
        # event_start = event["start"]["dateTime"]
        # event_start = event["start"]["date"]                    #this is how to handle all-day events                  
        
        print( "------ EVENT DESCRIPTION: ", event_name )
        # print( "------ EVENT TIME: ", event_start)

############## GET CALENDAR DATA ###############
def get_calendar_events():      #Returns a list of events ordered by their start date/time in ascending order.

    time_current_iso =  datetime.now().isoformat()
    time_current_max =  (datetime.now() + timedelta(seconds=60000)).isoformat()

    print("--- FETCHING CALENDAR EVENTS FROM {0} to {1}".format(time_current_iso, time_current_max))

    headers = {
        "Authorization": "Bearer " + GOOGLE_AUTH.access_token,
        "Accept": "application/json",
        "Content-Length": "0",
    }

    url = (
        "https://www.googleapis.com/calendar/v3/calendars/" + CALENDAR_ID + 
        "/events?maxResults=" + str(MAX_EVENTS) +
        "&timeMin=" + time_current_iso + "Z" +
        "&timeMax=" + time_current_max + "Z" +
        "&orderBy=startTime&singleEvents=true"
    )

    # print("Request URL=\n" + url)

    while True:
        try:
            response = requests.get( url, headers=headers )
            break
        except (ValueError, RuntimeError, ConnectionError, OSError) as e:
            print("Failed to get data, retrying\n", e)
            esp.reset()
        
    response_json = response.json()
    # print("RESPONSE_JSON=", response_json)

    if "error" in response_json:
        raise RuntimeError("ERROR:", response_json)
    response.close()

    # Parse the 'items' array so we can iterate over it more easily
    items = []                          
    response_items = response_json["items"]
    # print("RESPONSE_ITEMS=", response_items)
    print("--- NUMBER OF EVENTS FOUND: " + str(len(response_items)))
    if not response_items:
        print("No events scheduled for today!")
    for event in range(0, len(response_items)):
        items.append(response_items[event])
    return items

############### MAIN LOOP ###############
while True:
    # if ( int_time < int(GOOGLE_AUTH.access_token_expiration) ):
    #     print("=== Access token expired, refreshing...")
    #     try:
    #         GOOGLE_AUTH.refresh_access_token()
    #         _elapsed_time_since_token_auth = 0
    #     except RuntimeError as e:
    #         raise RuntimeError( "ERROR: Unable to refresh access token. Has the token been revoked?" )

    GOOGLE_AUTH.refresh_access_token()
    access_token_time_obtained = datetime.now()

    events = get_calendar_events()
    display_calendar_events(events)

    print("=== SLEEPING FOR %d s" % REFRESH_TIME)
    time.sleep(REFRESH_TIME)