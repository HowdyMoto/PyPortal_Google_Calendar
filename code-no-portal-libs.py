import board
import busio
from digitalio import DigitalInOut
import adafruit_esp32spi.adafruit_esp32spi_socket as socket
from adafruit_esp32spi import adafruit_esp32spi
import adafruit_requests as requests
from adafruit_oauth2 import OAuth2
import displayio
from adafruit_bitmap_font import bitmap_font
from adafruit_display_text import label
import rtc
import time
from adafruit_datetime import datetime, timedelta
import audioio
import audiocore

print("\n==== GCAL APP")

try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise

CALENDAR_ID = secrets["google_email"]
MAX_EVENTS = 8
LOOKAHEAD_TIME = 90000
REFRESH_TIME_SECONDS = 60

WHITE = 0xFFFFFF
BLACK = 0x000000
GREEN = 0x00FF00
RED =   0xFF0000

BACKGROUND_COLOR = BLACK
BACKGROUND_ERROR_COLOR = RED
TITLE_COLOR = GREEN
TIME_COLOR = WHITE
EVENT_COLOR = WHITE
FONT_EVENTS = "fonts/Arial-14.pcf"
FONT_TITLE = "fonts/Arial-18.pcf"
INDENT_TIME = 24
INDENT_NAME = 160

EVENT_Y = 88
EVENT_Y_SPACING = 44

ESP_DEBUG = False

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
GOOGLE_AUTH = OAuth2(requests,
    secrets["google_client_id"],
    secrets["google_client_secret"],
    SCOPES,
    secrets["google_access_token"],
    secrets["google_refresh_token"],
)

GCAL_BMP = displayio.OnDiskBitmap("bitmaps/GCal_32.bmp")
FONT = bitmap_font.load_font("fonts/Arial-14.pcf")
TICK_SOUND = "wavs/tick.wav"

# Set up ESP32 wifi chip
spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
esp32_cs = DigitalInOut(board.ESP_CS)
esp32_ready = DigitalInOut(board.ESP_BUSY)
esp32_reset = DigitalInOut(board.ESP_RESET)
esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)
esp._debug = ESP_DEBUG
print( "Nina/ESP32 Firmware version:", esp.firmware_version )

# Set up display and UI
display = board.DISPLAY
loadscreen_group = displayio.Group()

tile_grid_gcal = displayio.TileGrid(GCAL_BMP, pixel_shader=GCAL_BMP.pixel_shader, x=INDENT_TIME, y=24)

datetime_label = label.Label(FONT, text="Google Calendar", scale=1, color=WHITE, x=72, y=40)
event1_time_label = label.Label(FONT, text="Time1", color=WHITE, x=INDENT_TIME, y=EVENT_Y)
event1_name_label = label.Label(FONT, text="Name1", color=WHITE, x=INDENT_NAME, y=EVENT_Y)
event2_time_label = label.Label(FONT, text="Time2", color=WHITE, x=INDENT_TIME, y=EVENT_Y + EVENT_Y_SPACING )
event2_name_label = label.Label(FONT, text="Name2", color=WHITE, x=INDENT_NAME, y=EVENT_Y + EVENT_Y_SPACING )
event3_time_label = label.Label(FONT, text="Time3", color=WHITE, x=INDENT_TIME, y=EVENT_Y + EVENT_Y_SPACING*2 )
event3_name_label = label.Label(FONT, text="Name3", color=WHITE, x=INDENT_NAME, y=EVENT_Y + EVENT_Y_SPACING*2 )
event4_time_label = label.Label(FONT, text="Time4", color=WHITE, x=INDENT_TIME, y=EVENT_Y + EVENT_Y_SPACING*3 )
event4_name_label = label.Label(FONT, text="Name4", color=WHITE, x=INDENT_NAME, y=EVENT_Y + EVENT_Y_SPACING*3 )
event5_time_label = label.Label(FONT, text="Time5", color=WHITE, x=INDENT_TIME, y=EVENT_Y + EVENT_Y_SPACING*4 )
event5_name_label = label.Label(FONT, text="Name5", color=WHITE, x=INDENT_NAME, y=EVENT_Y + EVENT_Y_SPACING*4 )

error_label = label.Label(FONT, text="", scale=1, color=RED, x=24, y=290)

loadscreen_group.append(datetime_label)
loadscreen_group.append(event1_time_label)
loadscreen_group.append(event1_name_label)
loadscreen_group.append(event2_time_label)
loadscreen_group.append(event2_name_label)
loadscreen_group.append(event3_time_label)
loadscreen_group.append(event3_name_label)
loadscreen_group.append(event4_time_label)
loadscreen_group.append(event4_name_label)
loadscreen_group.append(event5_time_label)
loadscreen_group.append(event5_name_label)
loadscreen_group.append(error_label)

loadscreen_group.append(tile_grid_gcal)

display.show(loadscreen_group)

# # Set up audio
# tick_wav = audiocore.WaveFile(TICK_SOUND)
# dac = audioio.AudioOut(board.SPEAKER)

# def playTickSound():
#     dac.play(tick_wav, loop=False)

############### WIFI, HARDWARE SETUP, GET CURRENT TIME ###############
def espWifiConnect():
    requests.set_socket(socket, esp)

    if esp.status == adafruit_esp32spi.WL_IDLE_STATUS:
        print("ESP32 found and in idle mode")

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

def getCurrentTime():
    time_response = requests.get( "http://worldtimeapi.org/api/timezone/America/Los_Angeles" )
    unixtime = time_response.json()['unixtime']
    print("worldtimeapi.org unixtime=", unixtime)
    time_offset = time_response.json()['utc_offset']
    
    r = rtc.RTC()
    r.datetime = time.localtime(unixtime)

    time_response.close()

############## GET CALENDAR DATA ###############
def get_calendar_events():      #Returns a list of events ordered by their start date/time in ascending order.

    time_current_iso =  datetime.now().isoformat()
    time_current_max =  (datetime.now() + timedelta(seconds=LOOKAHEAD_TIME)).isoformat()

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

    while True:
        try:
            response = requests.get( url, headers=headers )
            error_label.color = GREEN
            error_label.text = "Success: Get calendar"
            break
        except (ValueError, RuntimeError, ConnectionError, OSError) as e:
            print("Request for Calendar data failed, retrying\n", e)
            error_label.text = "Error: Get calendar"
            esp.reset()
            espWifiConnect() 
        
    response_json = response.json()
    if "error" in response_json:
        raise RuntimeError("ERROR:", response_json)
    response.close()

    items = []                          
    response_items = response_json["items"]
    print("--- NUMBER OF EVENTS FOUND: " + str(len(response_items)))
    if not response_items:
        print("No events today!")
    for event in range(0, len(response_items)):
        items.append(response_items[event])

    return items

############## DISPLAY EVENTS ##################
def display_calendar_events(eventsList):

    print("Events list=", eventsList)

    if not eventsList:
        event1_name_label.text = "No events today!"
    else:
        event1_time_label.text = eventsList[0]["start"]["date"]
        event1_name_label.text = eventsList[0]["summary"]

        event2_time_label.text = eventsList[1]["start"]["dateTime"]
        event2_name_label.text = eventsList[1]["summary"]

           
############### MAIN PROGRAM ###############

espWifiConnect()
getCurrentTime()
GOOGLE_AUTH.refresh_access_token()
lastTokenReceivedTime = time.monotonic()    # Time in integer format

while True:

    now = time.monotonic()    # Time in integer format
    timeDeltaSinceToken = (now - lastTokenReceivedTime)    # Time since last token, int
    print("Token expiration=", GOOGLE_AUTH.access_token_expiration) # Seconds until token expires
    print("Time since last token=", timeDeltaSinceToken)
    if timeDeltaSinceToken > GOOGLE_AUTH.refresh_access_token():
        try:
            GOOGLE_AUTH.refresh_access_token()
            lastTokenReceivedTime = time.monotonic()
            error_label.text = "Success: Get calendar"
            error_label.color = GREEN
        except:
            error_label.text = "Error: REFRESH TOKEN"
            error_label.color = RED

    eventsListRespose = get_calendar_events()
    display_calendar_events(eventsListRespose)

    datetime_label.text = str( datetime.now() )

    print("=== SLEEPING FOR %d s" % REFRESH_TIME_SECONDS)
    time.sleep(REFRESH_TIME_SECONDS)