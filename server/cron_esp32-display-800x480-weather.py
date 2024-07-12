#!/root/Scripts/py_venv_scripts/bin/python3
##!/usr/bin/python3

# Local Weather now from Netatmo over ioBroker
# Forecast Weather now from WUnderground non public API

# cd ~/Scripts
# python3 -m venv py_venv_scripts
# source py_venv_scripts/bin/activate
# pip3 install ...


##############
# Bibliotheken
import logging
import datetime
import locale
import codecs
import urllib.request
import json
import MySQLdb
import pytz
import cairosvg

from PIL import Image
import numpy as np
import xml.etree.ElementTree as ET



###########
# Variablen

WEATHER_URL_NEW = "https://api.weather.com"
WEATHER_KEY_NEW = "abcdefghuijklmnopqrstuvwxyz1234567890"
CITY = "Münchberg, Bayern, DE"
LATITUDE = "50.192900"
LONGTITUDE = "11.8035702"

PATH = "/root/Scripts"
LOG = "log/cron_esp32-display-800x480-weather.log"
OUTPUT = "/var/www/html/esp32-display-800x480-weather/weatherdata.png"
SVG_FILE = "%s/cron_esp32-display-800x480-weather_preprocess.svg" % PATH
SVG_OUTPUT = "%s/cron_esp32-display-800x480-weather_output.svg" % PATH

ROOMS = ["Bad", "Wohnzimmer"]

SQLHOST = "localhost"
SQLUSER = "iobroker_db_user"
SQLPW = "iobroker_db_pw"
SQLDB = "iobroker"
SQLTAB = "ts_number"

IOBROKER_API_URL = "http://192.168.1.10:8087/states?pattern=alias.0*&prettyPrint"

locale.setlocale(locale.LC_TIME, "de_DE.UTF-8") # Deutsches Zeitformat
TIME_NEXTHOUR = datetime.datetime.timestamp(datetime.datetime.now().replace(minute=0, second=0, microsecond=0)+datetime.timedelta(hours=1))



#################
# Protokollierung

logging.basicConfig(
	 filename=PATH + '/' + LOG,
	 level=logging.INFO,
	 #level=logging.WARNING,
	 format= '[%(asctime)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s',
	 #datefmt='%H:%M:%S'
)
console = logging.StreamHandler()
console.setLevel(logging.ERROR)
logging.getLogger('').addHandler(console)
logger = logging.getLogger(__name__)
logging.info("SCRIPT START")



############
# Funktionen

def asInteger(output, id, data, addi):
	output = output.replace(id, str('%.0f%s' % (float(data), addi)))
	return(output)

def asIntegerTenOrMinusTen(output, id, data, addi):
	if float(data) <= -10 or float(data) >= 10:
		output = output.replace(id, str('%.0f%s' % (float(data), addi)))
	else:
		#output = output.replace(id, str('%s%s' % (data, addi)))
		output = output.replace(id, str('%.1f%s' % (data, addi)))
	return(output)

def replace_daily(output, id, dataday, dataicon, datalow, datahigh, datawind, datarain, datarainint):
	output = output.replace("$D_DAYN" + id, str(dataday + "."))
	output = output.replace("$D_ICON" + id, str(dataicon))
	#output = output.replace("$D_TEM_HIG" + id, str('%.0f%s' % (float(datahigh), "°")))
	#output = output.replace("$D_TEM_LOW" + id, str('%.0f%s' % (float(datalow), "°")))
	output = output.replace("$D_TEM_HIG" + id, str('%.0f%s' % (float(datahigh), "")))
	output = output.replace("$D_TEM_LOW" + id, str('%.0f%s' % (float(datalow), "")))
	output = output.replace("$D_WIND" + id, str('%.0f' % (float(datawind))))
	#output = output.replace("$D_RAI_PER" + id, str('%.2d' % (float(datarain))))
	output = output.replace("$D_RAI_PER" + id, str('%.0f' % (float(datarain))))
	#output = output.replace("$D_RAI_MM" + id, str('%.1f' % (float(datarainint))))
	output = asIntegerTenOrMinusTen(output, "$D_RAI_MM" + id, datarainint, "")
	return(output)

def replace_hourly(output, id, datatime, dataicon, datarain, datarainint, datatemp, datawind):
	#output = output.replace("$H_TIM" + id, str(datatime))
	output = output.replace("$H_TIM" + id, str(int(datatime)))  # Uhrzeit ohne führende Nullen
	output = output.replace("$H_ICO" + id, str(dataicon))
	output = output.replace("$H_TMP" + id, str('%.0f%s' % (float(datatemp), "°")))
	output = output.replace("$H_WSP" + id, str(datawind) + " km/h")
	if datarain >= 30 or dataicon == "rain":
		output = output.replace("$H_RAI" + id, str('%.0f%s | %.1f%s' % (float(datarain), "%", float(datarainint), "")))
		output = remove_element_by_id(output, f"notRainy{id}")
	else:
		output = output.replace("$H_RAI" + id, str(""))
		output = remove_element_by_id(output, f"rainy{id}")
	return(output)

def remove_element_by_id(output, element_id):
    root = ET.fromstring(output)
    element_to_remove = root.find(f".//*[@id='{element_id}']")
    if element_to_remove is not None:
        root.remove(element_to_remove)
    return ET.tostring(root, encoding='unicode')

def icon_mapping(iconcode):
	# http://pwsdashboard.weather-template.com/documentation/wu_icons.pdf
	if iconcode in [32,34,36]: 						iconname = "clear-day"
	if iconcode in [31,33]: 						iconname = "clear-night"
	if iconcode in [28,30]: 						iconname = "partly-cloudy-day"
	if iconcode in [27,29]: 						iconname = "partly-cloudy-night"
	if iconcode in [26]: 							iconname = "cloudy"
	if iconcode in [8,9,11,12,17,35,39,40,45]: 		iconname = "rain"
	if iconcode in [3,4,37,38,47]: 					iconname = "thunder"
	if iconcode in [20]: 							iconname = "fog"
	if iconcode in [15,22,23,24]: 					iconname = "wind"
	if iconcode in [5,10,13,14,16,25,41,42,43,46]: 	iconname = "snow"
	if iconcode in [6,7,18]: 						iconname = "sleet"
	if iconcode in [0,1,2]: 						iconname = "hurricane"
	if iconcode in [19]: 							iconname = "dust"
	if iconcode in [21]: 							iconname = "haze"
	if iconcode in [44]: 							iconname = "n/e"
	return(iconname)

def moonicon_mapping(moonphase):
	if float(moonphase) < 3 or float(moonphase) > 97: 		moonicon = "moon-0"
	if float(moonphase) > 3 and float(moonphase) <= 17: 	moonicon = "moon-waxing-25"
	if float(moonphase) > 17 and float(moonphase) <= 32: 	moonicon = "moon-waxing-50"
	if float(moonphase) > 32 and float(moonphase) <= 46: 	moonicon = "moon-waxing-75"
	if float(moonphase) > 46 and float(moonphase) <= 53: 	moonicon = "moon-100"
	if float(moonphase) > 53 and float(moonphase) <= 67: 	moonicon = "moon-waning-75"
	if float(moonphase) > 67 and float(moonphase) <= 82: 	moonicon = "moon-waning-50"
	if float(moonphase) > 82 and float(moonphase) <= 97: 	moonicon = "moon-waning-25"
	return(moonicon)

def winddirection(windangle):
	if 0 <= float(windangle) <= 22.4: 			winddirection = "N"
	elif 22.5 <= float(windangle) <= 67.4:		winddirection = "NO"
	elif 67.5 <= float(windangle) <= 112.4:		winddirection = "O"
	elif 112.5 <= float(windangle) <= 157.4:	winddirection = "SO"
	elif 157.5 <= float(windangle) <= 202.4:	winddirection = "S"
	elif 202.5 <= float(windangle) <= 247.4:	winddirection = "SW"
	elif 247.5 <= float(windangle) <= 292.4:	winddirection = "W"
	elif 292.5 <= float(windangle) <= 337.4:	winddirection = "NW"
	elif 337.5 <= float(windangle) <= 360:		winddirection = "N"
	elif float(windangle) == -1:				winddirection = "*"
	return(winddirection)

def convert_image_to_4g(input_image_path):
    # Open an image file
    with Image.open(input_image_path) as img:
        # Ensure image has an alpha channel
        if img.mode in ('RGBA', 'LA'):
            # Create a white background image
            background = Image.new('RGBA', img.size, (255, 255, 255))
            img = Image.alpha_composite(background, img)        

        # Resize the image to 800x480 if it's not the right size
        img = img.resize((800, 480), Image.LANCZOS)
        
        # Convert the image to grayscale (8-bit)
        img = img.convert('L')
        
        # Map grayscale values to 4-level grayscale
        def to_4g(val):
            if val < 64:
                return 0  # Black
            elif val < 128:
                return 1  # Dark gray
            elif val < 192:
                return 2  # Light gray
            else:
                return 3  # White

        img_np = np.array(img)
        img_4g = np.vectorize(to_4g)(img_np)
        return img_4g

def save_as_bin(img_4g, output_path):
    with open(output_path, 'wb') as f:
        for row in img_4g:
            packed_row = []
            for i in range(0, len(row), 4):
                packed_byte = (row[i] << 6) | (row[i+1] << 4) | (row[i+2] << 2) | row[i+3]
                packed_row.append(packed_byte)
            f.write(bytearray(packed_row))



###############################################################
# Local Weather from ioBroker "Simple-API" über Netatmo-Adapter
## http://192.168.1.10:8087/states?pattern=alias.0*&prettyPrint
tries = 0
max_tries = 5
while tries < max_tries:
	try:
		iobroker_apidata = urllib.request.urlopen(
			"%s" %
			(IOBROKER_API_URL))
		json_iobroker_apidata = iobroker_apidata.read().decode('utf-8')
		parsed_iobroker_apidata = json.loads(json_iobroker_apidata)
		logging.info("OK | iobroker api quest successfully")

		#print(parsed_iobroker_apidata)


		###########
		### Outdoor
		weatherdata_now_temp = parsed_iobroker_apidata['alias.0.Garten.Sensorik.Klimasensor_01.Temperature']['val']
		weatherdata_now_humi = parsed_iobroker_apidata['alias.0.Garten.Sensorik.Klimasensor_01.Humidity']['val']
		
		weatherdata_now_windangle = parsed_iobroker_apidata['alias.0.Garten.Sensorik.Windmesser_01.WindAngle']['val']
		weatherdata_now_windspeed = parsed_iobroker_apidata['alias.0.Garten.Sensorik.Windmesser_01.WindStrength']['val']
		weatherdata_now_windgust = parsed_iobroker_apidata['alias.0.Garten.Sensorik.Windmesser_01.GustStrength']['val']
		weatherdata_now_winddirection = winddirection(weatherdata_now_windangle)
		
		weatherdata_now_temp_min = parsed_iobroker_apidata['alias.0.Garten.Sensorik.Klimasensor_01.TemperatureMin']['val']
		weatherdata_now_temp_max = parsed_iobroker_apidata['alias.0.Garten.Sensorik.Klimasensor_01.TemperatureMax']['val']
		
		weatherdata_now_rain = parsed_iobroker_apidata['alias.0.Garten.Sensorik.Niederschlagsmesser_01.Rain24h']['val']
		
		logging.info("- weatherdata_now | garden temperature: %s" % (weatherdata_now_temp))
		logging.info("- weatherdata_now | garden temperature min: %s" % (weatherdata_now_temp_min))
		logging.info("- weatherdata_now | garden temperature max: %s" % (weatherdata_now_temp_max))
		logging.info("- weatherdata_now | garden humidity: %s" % (weatherdata_now_humi))
		logging.info("- weatherdata_now | garden rain: %s" % (weatherdata_now_rain))
		logging.info("- weatherdata_now | garden windspeed: %s" % (weatherdata_now_windspeed))
		logging.info("- weatherdata_now | garden windgust: %s" % (weatherdata_now_windgust))
		logging.info("- weatherdata_now | garden winddirection: %s" % (weatherdata_now_winddirection))


		##########
		### Indoor
		weatherdata_now_livingr_temp = parsed_iobroker_apidata['alias.0.Haus.EG-Wohnzimmer.Sensorik.Klimasensor_01.Temperature']['val']
		weatherdata_now_livingr_humi = parsed_iobroker_apidata['alias.0.Haus.EG-Wohnzimmer.Sensorik.Klimasensor_01.Humidity']['val']
		weatherdata_now_livingr_co2 = parsed_iobroker_apidata['alias.0.Haus.EG-Wohnzimmer.Sensorik.Klimasensor_01.CO2']['val']
		weatherdata_now_livingr_noise = parsed_iobroker_apidata['alias.0.Haus.EG-Wohnzimmer.Sensorik.Klimasensor_01.Noise']['val']
		weatherdata_now_livingr_temp_min = parsed_iobroker_apidata['alias.0.Haus.EG-Wohnzimmer.Sensorik.Klimasensor_01.TemperatureMin']['val']
		weatherdata_now_livingr_temp_max = parsed_iobroker_apidata['alias.0.Haus.EG-Wohnzimmer.Sensorik.Klimasensor_01.TemperatureMax']['val']

		weatherdata_now_bathr_temp = parsed_iobroker_apidata['alias.0.Haus.OG-Bad.Sensorik.Klimasensor_01.Temperature']['val']
		weatherdata_now_bathr_humi = parsed_iobroker_apidata['alias.0.Haus.OG-Bad.Sensorik.Klimasensor_01.Humidity']['val']

		logging.info("- weatherdata_now | livingroom temperature: %s" % (weatherdata_now_livingr_temp))
		logging.info("- weatherdata_now | livingroom temperature min: %s" % (weatherdata_now_livingr_temp_min))
		logging.info("- weatherdata_now | livingroom temperature max: %s" % (weatherdata_now_livingr_temp_max))
		logging.info("- weatherdata_now | livingroom humidity: %s" % (weatherdata_now_livingr_humi))
		logging.info("- weatherdata_now | livingroom co2: %s" % (weatherdata_now_livingr_co2))

		logging.info("- weatherdata_now | bathroom temperature: %s" % (weatherdata_now_bathr_temp))
		logging.info("- weatherdata_now | bathroom humidity: %s" % (weatherdata_now_bathr_humi))


	except urllib.error.HTTPError as e:
		tries = tries + 1
		logging.WARNING("WARN | iobroker api quest not successfully - error <%s> on trial no %s" % (e.code, tries))
		time.sleep(10)
		continue

	else:
		break
else:
	logging.error("FAIL | iobroker api quest failed")



###############################################################
# Local Weather from ioBroker SQL-Instanz über Netatmo-Adapter
## SELECT MIN(val) FROM ts_number WHERE id = (SELECT id FROM datapoints WHERE name = 'alias.0.Haus.OG-Bad.Sensorik.Klimasensor_01.Humidity') AND ts >= UNIX_TIMESTAMP(CURRENT_DATE)*1000
mysqldb = MySQLdb.connect(SQLHOST, SQLUSER, SQLPW, SQLDB)
mysqlcursor = mysqldb.cursor()

mysqlcursor.execute(
	"SELECT MIN(val), MAX(val) FROM %s WHERE id = (SELECT id FROM datapoints WHERE name = '%s') AND ts >= UNIX_TIMESTAMP(CURRENT_DATE)*1000" %
		(SQLTAB, 'alias.0.Garten.Sensorik.Klimasensor_01.Humidity'))
for select in mysqlcursor.fetchall():
	try:
		weatherdata_now_humi_min = '%.0f' % float(select[0])
		weatherdata_now_humi_max = '%.0f' % float(select[1])
	except:
		weatherdata_now_humi_min = "-"
		weatherdata_now_humi_max = "-"


mysqlcursor.execute(
	"SELECT MIN(val), MAX(val) FROM %s WHERE id = (SELECT id FROM datapoints WHERE name = '%s') AND ts >= UNIX_TIMESTAMP(CURRENT_DATE)*1000" %
		(SQLTAB, 'alias.0.Haus.EG-Wohnzimmer.Sensorik.Klimasensor_01.Humidity'))
for select in mysqlcursor.fetchall():
	try:
		weatherdata_now_livingr_humi_min = '%.0f' % float(select[0])
		weatherdata_now_livingr_humi_max = '%.0f' % float(select[1])
	except:
		weatherdata_now_livingr_humi_min = "-"
		weatherdata_now_livingr_humi_max = "-"


mysqlcursor.execute(
	"SELECT MIN(val), MAX(val) FROM %s WHERE id = (SELECT id FROM datapoints WHERE name = '%s') AND ts >= UNIX_TIMESTAMP(CURRENT_DATE)*1000" %
		(SQLTAB, 'alias.0.Haus.EG-Wohnzimmer.Sensorik.Klimasensor_01.CO2'))
for select in mysqlcursor.fetchall():
	try:
		weatherdata_now_livingr_co2_today_min = '%.0f' % float(select[0])
		weatherdata_now_livingr_co2_today_max = '%.0f' % float(select[1])
	except:
		weatherdata_now_livingr_co2_today_min = "-"
		weatherdata_now_livingr_co2_today_max = "-"

mysqlcursor.execute(
	"SELECT MIN(val), MAX(val) FROM %s WHERE id = (SELECT id FROM datapoints WHERE name = '%s') AND ts >= UNIX_TIMESTAMP(CURRENT_DATE)*1000" %
		(SQLTAB, 'alias.0.Haus.OG-Bad.Sensorik.Klimasensor_01.Temperature'))
for select in mysqlcursor.fetchall():
	try:
		weatherdata_now_bathr_temp_min = '%.1f' % float(select[0])
		weatherdata_now_bathr_temp_max = '%.1f' % float(select[1])
	except:
		weatherdata_now_bathr_temp_min = "-"
		weatherdata_now_bathr_temp_max = "-"

mysqlcursor.execute(
	"SELECT MIN(val), MAX(val) FROM %s WHERE id = (SELECT id FROM datapoints WHERE name = '%s') AND ts >= UNIX_TIMESTAMP(CURRENT_DATE)*1000" %
		(SQLTAB, 'alias.0.Haus.OG-Bad.Sensorik.Klimasensor_01.Humidity'))
for select in mysqlcursor.fetchall():
	try:
		weatherdata_now_bathr_humi_min = '%.0f' % float(select[0])
		weatherdata_now_bathr_humi_max = '%.0f' % float(select[1])
	except:
		weatherdata_now_bathr_humi_min = "-"
		weatherdata_now_bathr_humi_max = "-"

mysqlcursor.execute(
	"SELECT MIN(val), MAX(val) FROM %s WHERE id = (SELECT id FROM datapoints WHERE name = '%s') AND ts >= UNIX_TIMESTAMP(CURRENT_DATE)*1000" %
		(SQLTAB, 'alias.0.Haus.EG-Wohnzimmer.Sensorik.Klimasensor_01.Noise'))
for select in mysqlcursor.fetchall():
	try:
		weatherdata_now_livingr_noise_min = '%.0f' % float(select[0])
		weatherdata_now_livingr_noise_max = '%.0f' % float(select[1])
	except:
		weatherdata_now_livingr_noise_min = "-"
		weatherdata_now_livingr_noise_max = "-"


logging.info("- weatherdata_now | garden humidity min: %s" % (weatherdata_now_humi_min))
logging.info("- weatherdata_now | garden humidity max: %s" % (weatherdata_now_humi_max))

logging.info("- weatherdata_now | livingroom humidity min: %s" % (weatherdata_now_livingr_humi_min))
logging.info("- weatherdata_now | livingroom humidity max: %s" % (weatherdata_now_livingr_humi_max))
logging.info("- weatherdata_now | livingroom co2 min: %s" % (weatherdata_now_livingr_co2_today_min))
logging.info("- weatherdata_now | livingroom co2 max: %s" % (weatherdata_now_livingr_co2_today_max))

logging.info("- weatherdata_now | bathroom temperature min: %s" % (weatherdata_now_bathr_temp_min))
logging.info("- weatherdata_now | bathroom temperature max: %s" % (weatherdata_now_bathr_temp_max))
logging.info("- weatherdata_now | bathroom humidity min: %s" % (weatherdata_now_bathr_humi_min))
logging.info("- weatherdata_now | bathroom humidity max: %s" % (weatherdata_now_bathr_humi_max))



#####################
# API-Abfrage WUNDERGROUND
## https://api.weather.com/v1/geocode/50.19/11.78/observations/current.json?apiKey=abcdefghuijklmnopqrstuvwxyz1234567890&units=m&language=de-DE
tries = 0
max_tries = 5
while tries < max_tries:
	try:
		apidata_current = urllib.request.urlopen(
			"%s/v1/geocode/%s/%s/observations/current.json?apiKey=%s&units=m&language=de-DE" %
			(WEATHER_URL_NEW, LATITUDE, LONGTITUDE, WEATHER_KEY_NEW))
		json_apidata_current = apidata_current.read().decode('utf-8')
		parsed_apidata_current = json.loads(json_apidata_current)
		logging.info("OK | wunderground api current quest successfully")

		# Now
		weatherdata_now_text = parsed_apidata_current['observation']['phrase_32char'][:20] + (parsed_apidata_current['observation']['phrase_32char'][20:] and '...')
		weatherdata_now_iconcode = parsed_apidata_current['observation']['icon_code']
		weatherdata_now_icon = icon_mapping(weatherdata_now_iconcode)

		logging.info("- weatherdata_now | summary: %s" % (weatherdata_now_text))
		logging.info("- weatherdata_now | iconcode: %s" % (weatherdata_now_iconcode))
		logging.info("- weatherdata_now | icon: %s" % (weatherdata_now_icon))

	except urllib.error.HTTPError as e:
		tries = tries + 1
		logging.WARNING("WARN | wunderground api current quest not successfully - error <%s> on trial no %s" % (e.code, tries))
		time.sleep(10)
		continue

	else:
		break
else:
	logging.error("FAIL | wunderground api current quest failed")


## https://api.weather.com/v2/astro?apiKey=abcdefghuijklmnopqrstuvwxyz1234567890&geocode=50.19,11.78&days=1&date=20190815&format=json
tries = 0
max_tries = 5
while tries < max_tries:
	try:
		apidata_astro = urllib.request.urlopen(
			"%s/v2/astro?apiKey=%s&geocode=%s,%s&days=1&date=%s&format=json" %
			(WEATHER_URL_NEW, WEATHER_KEY_NEW, LATITUDE, LONGTITUDE, datetime.datetime.now().strftime("%Y%m%d") ))
		json_apidata_astro = apidata_astro.read().decode('utf-8')
		parsed_apidata_astro = json.loads(json_apidata_astro)
		logging.info("OK | wunderground api astro quest successfully")

		astronomy_today_sunrise_json_utc = parsed_apidata_astro['astroData'][0]['sun']['riseSet']['riseUTC']
		astronomy_today_sunset_json_utc = parsed_apidata_astro['astroData'][0]['sun']['riseSet']['setUTC']
		astronomy_today_sunrise = pytz.utc.localize(datetime.datetime.strptime(astronomy_today_sunrise_json_utc, '%Y-%m-%dT%H:%M:%S.%fZ')).astimezone(pytz.timezone('Europe/Berlin')).strftime("%H:%M")
		astronomy_today_sunset = pytz.utc.localize(datetime.datetime.strptime(astronomy_today_sunset_json_utc, '%Y-%m-%dT%H:%M:%S.%fZ')).astimezone(pytz.timezone('Europe/Berlin')).strftime("%H:%M")

		astronomy_today_moonillu = parsed_apidata_astro['astroData'][0]['moon']['riseSet']['percentIlluminated']
		astronomy_today_moonage = parsed_apidata_astro['astroData'][0]['moon']['riseSet']['moonage']
		astronomy_today_moonphase = astronomy_today_moonage / 29.5 * 100

		astronomy_today_moonphase_icon = moonicon_mapping(astronomy_today_moonphase)

		logging.info("- astronomy_today | sunrise: %s, sunset %s" % (astronomy_today_sunrise, astronomy_today_sunset))
		logging.info("- astronomy_today | moonphase_icon: %s, moonphase: %.0f%%, moonage: %.1f days, moonilluminated %s%%" % (astronomy_today_moonphase_icon, astronomy_today_moonphase, astronomy_today_moonage, astronomy_today_moonillu))

	except urllib.error.HTTPError as e:
		tries = tries + 1
		logging.WARNING("WARN | wunderground api astro quest not successfully - error <%s> on trial no %s" % (e.code, tries))
		time.sleep(10)
		continue

	else:
		break
else:
	logging.error("FAIL | wunderground api astro quest failed")


## https://api.weather.com/v1/geocode/50.19/11.78/forecast/hourly/48hour.json?apiKey=abcdefghuijklmnopqrstuvwxyz1234567890&units=m&language=de-DE
## https://api.weather.com/v3/wx/forecast/hourly/2day?apiKey=abcdefghuijklmnopqrstuvwxyz1234567890&geocode=50.19%2C11.78&language=de-DE&units=m&format=json
tries = 0
max_tries = 5
while tries < max_tries:
	try:
		apidata_hourly = urllib.request.urlopen(
			"%s/v1/geocode/%s/%s/forecast/hourly/48hour.json?apiKey=%s&units=m&language=de-DE" %
			(WEATHER_URL_NEW, LATITUDE, LONGTITUDE, WEATHER_KEY_NEW))
		json_apidata_hourly = apidata_hourly.read().decode('utf-8')
		parsed_apidata_hourly = json.loads(json_apidata_hourly)
		logging.info("OK | wunderground api hourly quest successfully")

		# Forecast Hourly
		weatherdata_hourly_time = []
		weatherdata_hourly_iconcode = []
		weatherdata_hourly_icon = []
		weatherdata_hourly_temp = []
		weatherdata_hourly_wind = []
		weatherdata_hourly_rain = []
		weatherdata_hourly_rainint = []
		weatherdata_hourly_rainint_snow = []

		## array 0 not ever forcast for the next hour
		RBEG = 0
		REND = 24
		for bi in parsed_apidata_hourly['forecasts']:
			if bi['fcst_valid'] == TIME_NEXTHOUR:
				RBEG = parsed_apidata_hourly['forecasts'].index(bi)
				REND = RBEG + 24

		ai = 0
		for i in range(RBEG, REND):
			weatherdata_hourly_time.append(datetime.datetime.fromtimestamp(int(parsed_apidata_hourly['forecasts'][i]['fcst_valid'])).strftime("%H"))
			weatherdata_hourly_iconcode.append(parsed_apidata_hourly['forecasts'][i]['icon_code'])
			weatherdata_hourly_icon.append(icon_mapping(weatherdata_hourly_iconcode[ai]))
			weatherdata_hourly_temp.append(parsed_apidata_hourly['forecasts'][i]['temp'])
			weatherdata_hourly_wind.append(parsed_apidata_hourly['forecasts'][i]['wspd'])
			weatherdata_hourly_rain.append(parsed_apidata_hourly['forecasts'][i]['pop'])
			weatherdata_hourly_rainint.append(parsed_apidata_hourly['forecasts'][i]['qpf'])
			weatherdata_hourly_rainint_snow.append(parsed_apidata_hourly['forecasts'][i]['snow_qpf'])

			logging.info("- weatherdata_hourly | hour: %s, iconcode: %s, icon: %s, temp: %s, wind: %s km/h, pop: %s%%, rain: %s mm" % (weatherdata_hourly_time[ai], weatherdata_hourly_iconcode[ai], weatherdata_hourly_icon[ai], weatherdata_hourly_temp[ai], weatherdata_hourly_wind[ai], weatherdata_hourly_rain[ai], weatherdata_hourly_rainint[ai]+weatherdata_hourly_rainint_snow[ai]))

			ai = ai + 1

	except urllib.error.HTTPError as e:
		tries = tries + 1
		logging.WARNING("WARN | wunderground api hourly quest not successfully - error <%s> on trial no %s" % (e.code, tries))
		time.sleep(10)
		continue

	else:
		break
else:
	logging.error("FAIL | wunderground api hourly quest failed")


## https://api.weather.com/v1/geocode/50.19/11.78/forecast/daily/5day.json?apiKey=abcdefghuijklmnopqrstuvwxyz1234567890&language=de-DE&units=m
## https://api.weather.com/v3/wx/forecast/daily/5day?apiKey=abcdefghuijklmnopqrstuvwxyz1234567890&geocode=50.19%2C11.78&language=de-DE&units=m&format=json
tries = 0
max_tries = 5
while tries < max_tries:
	try:
		apidata_daily = urllib.request.urlopen(
			"%s/v1/geocode/%s/%s/forecast/daily/5day.json?apiKey=%s&units=m&language=de-DE" %
			(WEATHER_URL_NEW, LATITUDE, LONGTITUDE, WEATHER_KEY_NEW))
		json_apidata_daily = apidata_daily.read().decode('utf-8')
		parsed_apidata_daily= json.loads(json_apidata_daily)
		logging.info("OK | wunderground api daily quest successfully")

		# Forecast Daily
		weatherdata_forecast_date = []
		weatherdata_forecast_weekday = []
		weatherdata_forecast_iconD = []
		weatherdata_forecast_iconN = []
		weatherdata_forecast_iconcodeD = []
		weatherdata_forecast_iconcodeN = []
		weatherdata_forecast_tempD = []
		weatherdata_forecast_tempN = []
		weatherdata_forecast_windD = []
		weatherdata_forecast_windN = []
		weatherdata_forecast_rainD = []
		weatherdata_forecast_rainN = []
		weatherdata_forecast_rainintD = []
		weatherdata_forecast_rainintN = []
		weatherdata_forecast_rainint_snowD = []
		weatherdata_forecast_rainint_snowN = []
		##
		weatherdata_forecast_icon = []
		weatherdata_forecast_rain = []
		weatherdata_forecast_templow = []
		weatherdata_forecast_temphigh = []
		weatherdata_forecast_wind = []
		weatherdata_forecast_rain = []
		weatherdata_forecast_rainint = []

		## ab 15:00 bis 3:10, am nächsten morgen, kein "day" mehr im JSON-Output
		RBEG = 0
		REND = 3
		if 'day' not in parsed_apidata_daily['forecasts'][0]:
			RBEG = 1
			REND = 4

		ai = 0
		for i in range(RBEG, REND):
			weatherdata_forecast_date.append(datetime.datetime.fromtimestamp(int(parsed_apidata_daily['forecasts'][i]['fcst_valid'])).strftime("%d.%m."))
			weatherdata_forecast_weekday.append(datetime.datetime.fromtimestamp(int(parsed_apidata_daily['forecasts'][i]['fcst_valid'])).strftime("%a"))
			weatherdata_forecast_iconcodeD.append(parsed_apidata_daily['forecasts'][i]['day']['icon_code'])
			weatherdata_forecast_iconcodeN.append(parsed_apidata_daily['forecasts'][i]['night']['icon_code'])
			weatherdata_forecast_iconD.append(icon_mapping(weatherdata_forecast_iconcodeD[ai]))
			weatherdata_forecast_iconN.append(icon_mapping(weatherdata_forecast_iconcodeN[ai]))
			weatherdata_forecast_tempD.append(parsed_apidata_daily['forecasts'][i]['day']['temp'])
			weatherdata_forecast_tempN.append(parsed_apidata_daily['forecasts'][i]['night']['temp'])
			weatherdata_forecast_windD.append(parsed_apidata_daily['forecasts'][i]['day']['wspd'])
			weatherdata_forecast_windN.append(parsed_apidata_daily['forecasts'][i]['night']['wspd'])
			weatherdata_forecast_rainD.append(parsed_apidata_daily['forecasts'][i]['day']['pop'])
			weatherdata_forecast_rainN.append(parsed_apidata_daily['forecasts'][i]['night']['pop'])
			weatherdata_forecast_rainintD.append(parsed_apidata_daily['forecasts'][i]['day']['qpf'])
			weatherdata_forecast_rainintN.append(parsed_apidata_daily['forecasts'][i]['night']['qpf'])
			weatherdata_forecast_rainint_snowD.append(parsed_apidata_daily['forecasts'][i]['day']['snow_qpf'])
			weatherdata_forecast_rainint_snowN.append(parsed_apidata_daily['forecasts'][i]['night']['snow_qpf'])
			logging.info("- forecast_daily | day: %s, %s, icon: %s, temp: %s, wind: %s km/h, pop: %s%%, rain: %s mm" % (weatherdata_forecast_weekday[ai], weatherdata_forecast_date[ai], weatherdata_forecast_iconD[ai], weatherdata_forecast_tempD[ai], weatherdata_forecast_windD[ai], weatherdata_forecast_rainD[ai], weatherdata_forecast_rainintD[ai]+weatherdata_forecast_rainint_snowD[ai]))
			logging.info("- forecast_daily | night: %s, %s, icon: %s, temp: %s, wind: %s km/h, pop: %s%%, rain: %s mm" % (weatherdata_forecast_weekday[ai], weatherdata_forecast_date[ai], weatherdata_forecast_iconN[ai], weatherdata_forecast_tempN[ai], weatherdata_forecast_windN[ai], weatherdata_forecast_rainN[ai], weatherdata_forecast_rainintN[ai]+weatherdata_forecast_rainint_snowN[ai]))
			# summary
			weatherdata_forecast_icon.append(weatherdata_forecast_iconD[ai])
			weatherdata_forecast_templow.append(weatherdata_forecast_tempN[ai])
			weatherdata_forecast_temphigh.append(weatherdata_forecast_tempD[ai])
			weatherdata_forecast_wind.append( max(weatherdata_forecast_windD[ai], weatherdata_forecast_windN[ai]) )
			weatherdata_forecast_rain.append( max(weatherdata_forecast_rainD[ai], weatherdata_forecast_rainN[ai]) )
			weatherdata_forecast_rainint.append( weatherdata_forecast_rainintD[ai]+weatherdata_forecast_rainint_snowD[ai]+weatherdata_forecast_rainintN[ai]+weatherdata_forecast_rainint_snowN[ai] )
			logging.info("- forecast_daily | summary: %s, %s, icon: %s, temp+: %s, temp-: %s, wind: %s km/h, pop: %s%%, rain: %s mm" % (weatherdata_forecast_weekday[ai], weatherdata_forecast_date[ai], weatherdata_forecast_icon[ai], weatherdata_forecast_temphigh[ai], weatherdata_forecast_templow[ai], weatherdata_forecast_wind[ai], weatherdata_forecast_rain[ai], weatherdata_forecast_rainint[ai]))
			ai = ai + 1

		today = datetime.datetime.now().strftime("%a")
		day_in_first_array = weatherdata_forecast_weekday[0]

		if today == day_in_first_array:
			DAYTXT = "Heute"
		else:
			DAYTXT = "Morgen"

	except urllib.error.HTTPError as e:
		tries = tries + 1
		logging.WARNING("WARN | wunderground api daily quest not successfully - error <%s> on trial no %s" % (e.code, tries))
		time.sleep(10)
		continue

	else:
		break
else:
	logging.error("FAIL | wunderground api daily quest failed")



############################################################
# SVG einlesen, Output zusammensuchen und SVG/PNG generieren
### http://www.svgminify.com > then copy/paste "defs"

for ROOM in ROOMS:

	#OUTPUT = "/var/www/html/esp32-display-800x480-weather/weatherdata-%s" % (ROOM.lower())
	output_base = "/var/www/html/esp32-display-800x480-weather/weatherdata-%s" % (ROOM.lower())
	#ROOM1 = "Innen (%s)" % (ROOM)
	ROOM1 = "%s" % (ROOM)

	output = codecs.open(SVG_FILE, "r", encoding="utf-8").read()

	output = output.replace("$TEXT", str(weatherdata_now_text))
	output = output.replace("$C_ICON", str(weatherdata_now_icon))
	output = asInteger(output, "$C_TEMP", weatherdata_now_temp, "°")
	#output = output.replace("$C_TEM_MAX", str('%.1f°' % (float(weatherdata_now_temp_max))))
	#output = output.replace("$C_TEM_MIN", str('%.1f°' % (float(weatherdata_now_temp_min))))
	output = output.replace("$C_TEM_MAX", str('%.1f' % (float(weatherdata_now_temp_max))))
	output = output.replace("$C_TEM_MIN", str('%.1f' % (float(weatherdata_now_temp_min))))
	output = asInteger(output, "$C_HUMI", weatherdata_now_humi, "")
	output = output.replace("$C_HUM_MAX", str(weatherdata_now_humi_max))
	output = output.replace("$C_HUM_MIN", str(weatherdata_now_humi_min))
	output = asInteger(output, "$C_WIND", weatherdata_now_windspeed, "")
	output = output.replace("$C_WIN_DIR", str(weatherdata_now_winddirection))
	output = asInteger(output, "$C_WIN_MAX", weatherdata_now_windgust, "")
	#output = output.replace("$C_RAIN", str('%.1f' % (float(weatherdata_now_rain))))
	output = asIntegerTenOrMinusTen(output, "$C_RAIN", weatherdata_now_rain, "")
	output = output.replace("$C_SUNRISE", str(astronomy_today_sunrise))
	output = output.replace("$C_SUNSET", str(astronomy_today_sunset))
	output = output.replace("$C_MOON", str('%.2d' % (float(astronomy_today_moonphase))))
	output = output.replace("$C_MOO_ICO", str(astronomy_today_moonphase_icon))

	zeitstempel = datetime.datetime.now().strftime("%d. %B %Y um %H:%M")
	output = output.replace("$TIME", f"Wetterdaten aktualisiert am {zeitstempel}")
	output = output.replace("$LOC", str(CITY))

	output = output.replace("$DAYTXT", str(DAYTXT))
	for i in range(0, 3):
		output = replace_daily(output, str(i+1), weatherdata_forecast_weekday[i], weatherdata_forecast_icon[i], weatherdata_forecast_templow[i], weatherdata_forecast_temphigh[i], weatherdata_forecast_wind[i], weatherdata_forecast_rain[i], weatherdata_forecast_rainint[i])

	for i in range(0, 24):
		output = replace_hourly(output, str(i+1).zfill(2), weatherdata_hourly_time[i], weatherdata_hourly_icon[i], weatherdata_hourly_rain[i], weatherdata_hourly_rainint[i]+weatherdata_hourly_rainint_snow[i], weatherdata_hourly_temp[i], weatherdata_hourly_wind[i])

	if ROOM == "Bad":
		ROOM2 = "Wohnzimmer"
		output = output.replace("$ROOM1", str(ROOM1))
		output = output.replace("$ROOM2", str(ROOM2))
		output = output.replace("$I_TEMP", str('%.1f°' % (float(weatherdata_now_bathr_temp))))
		output = output.replace("$I_TEM_MIN", str(weatherdata_now_bathr_temp_min))
		output = output.replace("$I_TEM_MAX", str(weatherdata_now_bathr_temp_max))
		output = output.replace("$I_HUMI", str('%.0f' % (float(weatherdata_now_bathr_humi))))
		output = output.replace("$I_HUM_MIN", str(weatherdata_now_bathr_humi_max))
		output = output.replace("$I_HUM_MAX", str(weatherdata_now_bathr_humi_min))
		output = output.replace("$I_AIRQ", str(weatherdata_now_livingr_co2))
		output = output.replace("$I_AIR_MIN", str(weatherdata_now_livingr_co2_today_min))
		output = output.replace("$I_AIR_MAX", str(weatherdata_now_livingr_co2_today_max))
		output = output.replace("$I_NOIS", str(weatherdata_now_livingr_noise))
		output = output.replace("$I_NOI_MIN", str(weatherdata_now_livingr_noise_min))
		output = output.replace("$I_NOI_MAX", str(weatherdata_now_livingr_noise_max))
		

	if ROOM == "Wohnzimmer":
		ROOM2 = ""
		output = output.replace("$ROOM1", str(ROOM1))
		output = output.replace("$ROOM2", str(ROOM2))
		output = output.replace("$I_TEMP", str('%.1f' % (float(weatherdata_now_livingr_temp))))
		output = output.replace("$I_TEM_MIN", str(weatherdata_now_livingr_temp_min))
		output = output.replace("$I_TEM_MAX", str(weatherdata_now_livingr_temp_max))
		output = output.replace("$I_HUMI", str('%.0f' % (float(weatherdata_now_livingr_humi))))
		output = output.replace("$I_HUM_MIN", str(weatherdata_now_livingr_humi_min))
		output = output.replace("$I_HUM_MAX", str(weatherdata_now_livingr_humi_max))
		output = output.replace("$I_AIRQ", str(weatherdata_now_livingr_co2))
		output = output.replace("$I_AIR_MIN", str(weatherdata_now_livingr_co2_today_min))
		output = output.replace("$I_AIR_MAX", str(weatherdata_now_livingr_co2_today_max))
		output = output.replace("$I_NOIS", str(weatherdata_now_livingr_noise))
		output = output.replace("$I_NOI_MIN", str(weatherdata_now_livingr_noise_min))
		output = output.replace("$I_NOI_MAX", str(weatherdata_now_livingr_noise_max))
		

	# SVG speichern
	with open(SVG_OUTPUT, "w") as file:
	    file.write(output)
	print("SVG: Erfolgreich mit Wetterdaten befühlt.")

	# PNG (SVG in PNG konvertieren)
	png_output = f"{output_base}.png"
	cairosvg.svg2png(url=SVG_OUTPUT, write_to=png_output)
	print("- PNG: SVG-Code erfolgreich in PNG umgewandelt.")

	# JPEG (PNG öffnen, weißem Hintergrund hinzufügen und als JPEG speichern)
	png_image = Image.open(png_output)
	background = Image.new("RGB", png_image.size, (255, 255, 255))
	background.paste(png_image, (0, 0), png_image)
	jpeg_output = f"{output_base}.jpg"
	background.save(jpeg_output, "JPEG")
	print("- JPEG: PNG erfolgreich in JPEG umgewandelt und mit einem weißen Hintergrund versehen.")

	# BIN (PNG öffnen, in 4 Graustufen umwandeln und BIN speichern)
	img_4g = convert_image_to_4g(png_output)
	bin_output = f"{output_base}.bin"
	save_as_bin(img_4g, bin_output)
	print("- BIN: PNG in 4-Graustufen-Bild umwandeln und als Binärdatei für ESP32 speichern.")

	logging.info("SCRIPT END\n")
