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

NETWORK=["eth0", "wlan0", "br0", "tap_tap8"]
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

ADDR_BMP280 = 0x76
DIG_PARAM = []
def I2C_init():
    i2c = smbus.SMBus(1)
    global DIG_PARAM
    DIG_PARAM = i2c.read_i2c_block_data(ADDR_BMP280, 0x88, 26) # Compensation params
    #print(DIG_PARAM)
    return i2c

def get_temperature(i2c):
    i2c.write_byte_data(ADDR_BMP280, 0xF4, 0x25) # ctrl_meas 00100101
    time.sleep(0.1)
    data = i2c.read_i2c_block_data(ADDR_BMP280, 0xFA, 3) # Temperature data
    #print(data)
    T    = BMP280_compensate_temperature(data, DIG_PARAM)
    print(T / 100.0, "degC")
    return T / 100.0

def conv_s16(num):
    return (num + 2**15) % 2**16 - 2**15

def BMP280_compensate_temperature(data, dig):
    dig_T1 = dig[0] | dig[1] << 8 # unsigned short
    dig_T2 = conv_s16(dig[2] | dig[3] << 8) # signed short
    dig_T3 = conv_s16(dig[4] | dig[5] << 8) # signed short
    raw_data = (data[2] >> 4) | (data[1] << 4) | (data[0] << 12)
    # compensation calculation
    var1 = (((raw_data>>3) - (dig_T1<<1)) * dig_T2) >> 11
    var2 = (((((raw_data>>4) - dig_T1) * ((raw_data>>4) - dig_T1)) >> 12) * dig_T3) >> 14
    t_fine = var1 + var2
    T = (t_fine * 5 + 128) >> 8
    #print(raw_data)
    #print(dig_T1)
    #print(dig_T2)
    #print(dig_T3)
    #print(var1)
    #print(var2)
    #print(t_fine)
    #print(T)
    return T

def BMP280_compensate_pressure(data, dig):
    dig_P1 = dig[6] | dig[1] << 8 # unsigned short
    dig_P2 = conv_s16(dig[8]  | dig[9]  << 8)  # signed short
    dig_P3 = conv_s16(dig[10] | dig[11] << 8) # signed short
    dig_P4 = conv_s16(dig[12] | dig[13] << 8) # signed short
    dig_P5 = conv_s16(dig[14] | dig[15] << 8) # signed short
    dig_P6 = conv_s16(dig[16] | dig[17] << 8) # signed short
    dig_P7 = conv_s16(dig[18] | dig[19] << 8) # signed short
    dig_P8 = conv_s16(dig[20] | dig[21] << 8) # signed short
    dig_P9 = conv_s16(dig[22] | dig[23] << 8) # signed short
    raw_data = (data[2] >> 4) | (data[1] << 4) | (data[0] << 12)

i2c = I2C_init()
get_temperature(i2c)
exit(0)

if __name__=="__main__":
    #wp.wiringPiSetup() # For sequential pin numbering
    #wp.wiringPiSetupGpio() # For GPIO pin numbering
    #wp.pinMode(17, 0)
    switch           = digitalio.DigitalInOut(board.D17) # Physical 11th.
    switch.direction = digitalio.Direction.INPUT
    oled = OLED_init()
    OLED_clear_display(oled)
    wolflag   = False
    counter1  = 0
    counter2  = 0
    ipaddress = ""
    cpustat   = ""
    network_i = 0
    while True:
        #st17 = wp.digitalRead(17)
        #print("GPIO 17 ON/OFF: ", switch.value)
        if counter1 % 6 == 0: # update per 2 sec.
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
        if switch.value:
            if wolflag is False: # Detect Rising Edge
                subprocess.run(["wakeonlan " + MAC_ADDRESS], shell=True)
            OLED_show_text(oled, "Wake On LAN\n" + MAC_ADDRESS)
            wolflag = True
        else:
            now = datetime.datetime.now()
            OLED_show_text(oled, 
                    "Hello Pi!\n" 
                    + cpustat + "\n"
                    + ipaddress + "\n"
                    + str(now.strftime("%Y/%m/%d %H:%M:%S"))
                    )
            wolflag = False
        counter1 += 1
        counter2 += 1
        time.sleep(0.33333)
