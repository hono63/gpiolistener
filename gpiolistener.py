"""
Reference:
https://learn.adafruit.com/circuitpython-on-raspberrypi-linux/digital-i-o
https://learn.adafruit.com/monochrome-oled-breakouts/python-usage-2
"""

#import wiringpi as wp
import subprocess
import time
import datetime
import psutil

import board
import digitalio
from PIL import Image, ImageDraw, ImageFont
import adafruit_ssd1306
import smbus

# MAC Address of Desktop PC
MAC_ADDRESS = "04:d9:f5:fa:2c:78"

# OLED Display
WIDTH = 128
HEIGHT = 64 
BORDER = 2

def OLED_init():
    "initalize SPI I/F for OLED"
    # Use for SPI
    spi        = board.SPI()
    oled_reset = digitalio.DigitalInOut(board.D24) # Physical 18th.
    oled_cs    = digitalio.DigitalInOut(board.D8) # Physical 24th. (CE0)
    oled_dc    = digitalio.DigitalInOut(board.D23) # Physical 16th.
    oled       = adafruit_ssd1306.SSD1306_SPI(WIDTH, HEIGHT, spi, oled_dc, oled_reset, oled_cs)
    return oled

def OLED_clear_display(oled):
    "clear OLED display."
    oled.fill(0)
    oled.show()

def create_blank_image():
    "Create blank image for drawing."
    # Make sure to create image with mode '1' for 1-bit color.
    image = Image.new("1", (WIDTH, HEIGHT))
    # Get drawing object to draw on image.
    draw = ImageDraw.Draw(image)
    # Draw a white background
    draw.rectangle((0, 0, WIDTH, HEIGHT), outline=255, fill=255)
    # Draw a smaller inner rectangle
    draw.rectangle(
        (BORDER, BORDER, WIDTH - BORDER - 1, HEIGHT - BORDER - 1),
        outline=0,
        fill=0,
    )
    return image, draw

def OLED_show_text(oled, text="Hello World!"):
    "Show text on OLED."
    # Load default font.
    font = ImageFont.load_default()
    # Draw Some Text
    (font_width, font_height) = font.getsize(text)
    image, draw = create_blank_image()
    if "\n" in text:
        draw.text((BORDER+1,BORDER+1), text, font=font, fill=255)
    else:
        # draw at center
        draw.text(
            (oled.width // 2 - font_width // 2, oled.height // 2 - font_height // 2),
            text,
            font=font,
            fill=255,
        )
    # Display image
    oled.image(image)
    oled.show()

NETWORK=["eth0", "wlan0", "tailscale0", "br0", "tap_tap8"]
def get_addr_str(proc, network="eth0"):
    "Get inet address in ifconfig"
    ipaddress       = ""
    in_section = False
    for byte_line in proc.stdout:
        line = byte_line.decode()
        if line.strip() == "":
            in_section = False
        if in_section is True or network in line:
            in_section = True
            if "inet addr" in line:
                ipaddress = line.split()[1].split(":")[1]
                break
    return ipaddress

def get_cpu_stat(proc):
    "Get CPU statistics in vmstat"
    global a 
    cpustat   = "CPU"
    byte_line = b""
    for b in proc.stdout:
        byte_line = b
    stats     = byte_line.decode().split()
    #cpustat   += " us:" + stats[-5] + "% sy:" + stats[-4] + "%"
    cpustat   += ":" + str(100 - int(stats[-3]) + a) + "%" # stats[-3]:idle
    return cpustat

def I2C_init():
    i2c = smbus.SMBus(1)
    bmp280 = BMP280(i2c)
    si7021 = Si7021(i2c)
    ccs811 = None #CCS811(i2c)
    return i2c, bmp280, si7021, ccs811

def conv_s16(num):
    "convert positive integer to singed short"
    return (num + 2**15) % 2**16 - 2**15

class CCS811():
    "Control CCS811 the CO2 sensor via I2C."
    ADDR = 0x5A # when the ADDR is low.
    def __init__(self, i2c):
        self.i2c = i2c
        status = self.check_status()
        if status & 0b00000001:
            self.reset()
            self.get_ID()
            self.get_version()
            status = self.check_status()
        self.app_start(status)
        self.meas_mode = 0x00
        self.results = []

    def get_ID(self):
        self.ID = self.i2c.read_byte_data(CCS811.ADDR, 0x20)
        print("[CCS811] ID:", hex(self.ID))

    def get_version(self):
        self.hw_ver      = self.i2c.read_byte_data(CCS811.ADDR, 0x21)
        temp             = self.i2c.read_i2c_block_data(CCS811.ADDR, 0x23, 2)
        self.fw_boot_ver = str(temp[0] & 0xf0) + "." + str(temp[0] & 0x0f) + "." + str(temp[1])
        temp             = self.i2c.read_i2c_block_data(CCS811.ADDR, 0x24, 2)
        self.fw_app_ver  = str(temp[0] & 0xf0) + "." + str(temp[0] & 0x0f) + "." + str(temp[1])
        print("[CCS811] H/W ver:", hex(self.hw_ver), " FW Boot ver:", self.fw_boot_ver, " FW App ver:", self.fw_app_ver)

    def reset(self):
        self.i2c.write_i2c_block_data(CCS811.ADDR, 0xFF, [0x11, 0xE5, 0x72, 0x8A])
        print("[CCS811] Resetting...")
        time.sleep(0.1)
        self.check_error()
        time.sleep(0.01)

    def check_error(self, error=0x00):
        if error == 0:
            error = self.i2c.read_byte_data(CCS811.ADDR, 0xE0)
        #print("error:", bin(error))
        if error & 0b00000001:
            print("[CCS811] Error: WRITE_REG_INVALID")
        if error & 0b00000010:
            print("[CCS811] Error: READ_REG_INVALID")
        if error & 0b00000100:
            print("[CCS811] Error: MEASMODE_INVALID")
        if error & 0b00001000:
            print("[CCS811] Error: MAX_RESISTANCE")
        if error & 0b00010000:
            print("[CCS811] Error: HEATER_FAULT")
        if error & 0b00100000:
            print("[CCS811] Error: HEATER_SUPPLY")

    def check_status(self, status=0x00):
        if status == 0:
            status = self.i2c.read_byte_data(CCS811.ADDR, 0x00)
        print("status:", bin(status))
        if status & 0b00000001:
            print("[CCS811] Status: ERROR")
        if status & 0b00001000:
            print("[CCS811] Status: DATA_READY")
        if not (status & 0b00010000):
            print("[CCS811] Status: not APP_VALID")
        if not (status & 0b10000000):
            print("[CCS811] Status: FW_MODE in boot mode")
        return status

    def app_start(self, status):
        "If firmware is in boot mode and there is a valid application present, application will start."
        #status = self.check_status()
        if not (status & 0b10000000): # firmware is in boot mode
            # APP_VERIFY
            if not (status & 0b00010000): # app is not valid
                print("[CCS811] Verifying application...")
                self.i2c.write_byte(CCS811.ADDR, 0xF3)
                time.sleep(0.1) # must wait 70ms
                while(True):
                    status = self.i2c.read_byte_data(CCS811.ADDR, 0x00)
                    #print("status:", bin(status))
                    if status & 0x20:
                        #self.check_status()
                        #self.check_error()
                        break
                    time.sleep(0.1)
            # APP_START
            print("[CCS811] Starting application...")
            self.i2c.write_byte(CCS811.ADDR, 0xF4)
            #self.i2c.write_i2c_block_data(CCS811.ADDR, 0xF4, [])
        time.sleep(2.0)
        status = self.check_status()
        if status & 0b00000001:
            self.check_error()
            exit(0)

    def measure_start(self):
        "Mode1: Constant power mode, IAQ measurement every second."
        print("[CCS811] Starting mesurement Mode 1...")
        self.meas_mode = self.i2c.read_byte_data(CCS811.ADDR, 0x01)
        print("MEAS_MODE:", bin(self.meas_mode))
        self.meas_mode |= 0b00010000
        print("MEAS_MODE:", bin(self.meas_mode))
        time.sleep(0.01)
        self.i2c.write_byte_data(CCS811.ADDR, 0x01, self.meas_mode)
        time.sleep(0.01)
        self.check_status()
        self.check_error()
        time.sleep(0.01)

    def get_gas_data(self):
        "Get measurement results. eCO2 and TVOC (Total Volatile Organic Compound)."
        print("[CCS811] Getting gas data...")
        self.results = self.i2c.read_i2c_block_data(CCS811.ADDR, 0x02, 8)
        self.check_status(status=self.results[4])
        self.eCO2 = self.results[0] << 8 | self.results[1] # 400ppm ~ 8192ppm
        self.TVOC = self.results[2] << 8 | self.results[3] # 0ppb ~ 1187ppb
        self.check_error(error=self.results[5])
        return self.eCO2, self.TVOC

class BMP280():
    "Control BMP280 temperature & pressure sensor via I2C."
    ADDR = 0x76
    def __init__(self, i2c):
        self.i2c = i2c
        self.reset()
        self.dig_param = self.i2c.read_i2c_block_data(BMP280.ADDR, 0x88, 26) # Compensation params
        self.raw_pressure    = 0
        self.raw_temperature = 0
        self.t_fine = 0
        #print(self.dig_param)
        self.dig_T1 = self.dig_param[0] | self.dig_param[1] << 8 # unsigned short
        self.dig_T2 = conv_s16(self.dig_param[2] | self.dig_param[3] << 8) # signed short
        self.dig_T3 = conv_s16(self.dig_param[4] | self.dig_param[5] << 8) # signed short
        self.dig_P1 = self.dig_param[6] | (self.dig_param[7] << 8) # unsigned short
        self.dig_P2 = conv_s16(self.dig_param[8]  | (self.dig_param[9]  << 8))  # signed short
        self.dig_P3 = conv_s16(self.dig_param[10] | (self.dig_param[11] << 8)) # signed short
        self.dig_P4 = conv_s16(self.dig_param[12] | (self.dig_param[13] << 8)) # signed short
        self.dig_P5 = conv_s16(self.dig_param[14] | (self.dig_param[15] << 8)) # signed short
        self.dig_P6 = conv_s16(self.dig_param[16] | (self.dig_param[17] << 8)) # signed short
        self.dig_P7 = conv_s16(self.dig_param[18] | (self.dig_param[19] << 8)) # signed short
        self.dig_P8 = conv_s16(self.dig_param[20] | (self.dig_param[21] << 8)) # signed short
        self.dig_P9 = conv_s16(self.dig_param[22] | (self.dig_param[23] << 8)) # signed short

    def get_ID(self):
        self.ID = self.i2c.read_byte_data(BMP280.ADDR, 0xD0)
        print("[BMP280] ID:", hex(self.ID))

    def reset(self):
        self.i2c.write_byte_data(BMP280.ADDR, 0xE0, 0xB6)
        print("[BMP280] Resetting...")
        time.sleep(0.01)

    def measure_start(self):
        "Normal mode"
        self.i2c.write_byte_data(BMP280.ADDR, 0xF5, 0b01001000) #config t_standby(125ms):010|filter_coef(4):010|spi_en:00
        self.i2c.write_byte_data(BMP280.ADDR, 0xF4, 0b00101111) #ctrl_meas tempr(x1):001|press(x4):011|mode:11
        print("[BMP280] Starting mesurement...")
        #print(bin(self.i2c.read_byte_data(BMP280.ADDR, 0xF5)))
        time.sleep(0.1)

    def measure_once(self):
        "Forced mode"
        self.i2c.write_byte_data(BMP280.ADDR, 0xF4, 0b00100101) # ctrl_meas  tempr:001|press:001|mode:01
        print("[BMP280] Measuring once...")
        time.sleep(0.1)

    def get_temperature_and_pressure(self):
        data = self.i2c.read_i2c_block_data(BMP280.ADDR, 0xF7, 7) 
        self.raw_pressure    = (data[2] >> 4) | (data[1] << 4) | (data[0] << 12) # Pressure data
        self.raw_temperature = (data[5] >> 4) | (data[4] << 4) | (data[3] << 12) # Temperature data
        #print(data)
        T = self.compensate_temperature()
        #print(T / 100.0, "degC")
        P = self.compensate_pressure()
        #print(P / 25600.0, "hPa")
        return T / 100.0, P / 25600.0

    def compensate_temperature(self):
        """
        Returns temperature in DegC, resolution is 0.01 DegC. Output value of “5123” equals 51.23 DegC. 
        t_fine carries fine temperature as global value
        """
        # compensation calculation
        adc_T = self.raw_temperature
        var1 = (((adc_T >> 3) - (self.dig_T1 << 1)) * self.dig_T2) >> 11
        var2 = (((((adc_T >> 4) - self.dig_T1) * ((adc_T >> 4) - self.dig_T1)) >> 12) * self.dig_T3) >> 14
        self.t_fine = var1 + var2
        T = (self.t_fine * 5 + 128) >> 8
        return T

    def compensate_pressure(self):
        """
        Returns pressure in Pa as unsigned 32 bit integer in Q24.8 format (24 integer bits and 8 fractional bits). 
        Output value of “24674867” represents 24674867/256 = 96386.2 Pa = 963.862 hPa
        """
        # compensation calculation
        var1 = self.t_fine - 128000
        var2 = var1 * var1 * self.dig_P6
        var2 = var2 + ((var1 * self.dig_P5) << 17)
        var2 = var2 + (self.dig_P4 << 35)
        var1 = ((var1 * var1 * self.dig_P3) >> 8) + ((var1 * self.dig_P2) << 12) 
        var1 = (((1 << 47) + var1) * (self.dig_P1)) >> 33
        if var1 == 0:
            return 0 # avoid exception caused by division by zero
        p = 1048576 - self.raw_pressure
        p = (((p << 31) - var2) * 3125) // var1
        var1 = (self.dig_P9 * (p >> 13) * (p >> 13)) >> 25 
        var2 = (self.dig_P8 * p) >> 19
        p = ((p + var1 + var2) >> 8) + (self.dig_P7 << 4) 
        return p

class Si7021():
    "Control Si7021 temperature & humidity sensor via I2C."
    ADDR = 0x40
    def __init__(self, i2c):
        self.i2c = i2c
        self.reset()

    def reset(self):
        self.i2c.read_byte_data(Si7021.ADDR, 0xFE)
        print("[Si7021] Resetting...")
        time.sleep(0.01)

    def get_temperature(self):
        data = self.i2c.read_i2c_block_data(Si7021.ADDR, 0xE3, 2)
        print(data)
        time.sleep(0.01)

if __name__=="__main__":
    #wp.wiringPiSetup() # For sequential pin numbering
    #wp.wiringPiSetupGpio() # For GPIO pin numbering
    #wp.pinMode(17, 0)
    ### SPI Display ###
    switch           = digitalio.DigitalInOut(board.D17) # Physical 11th.
    switch.direction = digitalio.Direction.INPUT
    oled = OLED_init()
    OLED_clear_display(oled)
    ### I2C Sensors ###
    i2c, bmp280, si7021, ccs811 = I2C_init()
    #si7021.get_temperature() # remote I/O error
    #exit(0)
    #bmp280.measure_once()
    bmp280.measure_start()
    #ccs811.measure_start()
    ## variables ##
    wolflag   = False
    counter1  = 0
    counter2  = 0
    counter3  = 0
    ipaddress = ""
    cpustat   = ""
    sensordt  = ""
    network_i = 0
    while True:
        #st17 = wp.digitalRead(17)
        #print("GPIO 17 ON/OFF: ", switch.value)
        if counter1 % 4 == 0: # update per 1.3 sec.
            addrs_namedtuple = psutil.net_if_addrs()
            for j in range(len(NETWORK)):
                network_i = (network_i + 1) % len(NETWORK)
                addrs     = None
                addrs     = addrs_namedtuple.get(NETWORK[network_i])
                if addrs is not None:
                    ifname = NETWORK[network_i][max(0,len(NETWORK[network_i])-5):] # only show last 5 letters
                    if addrs[0].address.replace(".","").isnumeric():
                        ipaddress = ifname + ":" + str(addrs[0].address)
                    else:
                        ipaddress = ifname + ":---"
                    break
            counter1 = 0
        if counter2 % 3 == 0: # update per 1 sec.
            cpustat = "CPU:" + str(psutil.cpu_percent())
            cpustat += "% Mem:" + str(psutil.virtual_memory().percent) + "%"
            counter2 = 0
        if counter3 % 4 == 0: # update per 1.3 sec
            if counter3 == 4:
                tmpr, pres = bmp280.get_temperature_and_pressure()
                sensordt = "{:.1f}Cdeg {:.1f}hPa".format(tmpr, pres)
            #else:
                #co2, tvoc  = ccs811.get_gas_data()
                #sensordt = str(co2) + "ppm " + str(tvoc) + "ppb"
                #counter3 = 0
        if switch.value:
            if wolflag is False: # Detect Rising Edge
                subprocess.run(["wakeonlan " + MAC_ADDRESS], shell=True)
            OLED_show_text(oled, "Wake On LAN\n" + MAC_ADDRESS)
            wolflag = True
        else:
            now = datetime.datetime.now()
            OLED_show_text(oled, 
                    #"Hello Pi!\n" 
                    cpustat + "\n"
                    + ipaddress + "\n"
                    + sensordt + "\n"
                    + str(now.strftime("%Y/%m/%d %H:%M:%S"))
                    )
            wolflag = False
        counter1 += 1
        counter2 += 1
        counter3 += 1
        time.sleep(0.33333)
