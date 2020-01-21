import requests
import os
import time
import datetime
import re
import json
import serial
import smtplib
from bs4 import BeautifulSoup


arduino_serial = serial.Serial('/dev/ttyACM0', 9600)

##

def get_api_token():

    url = "http://192.168.254.254/api/webserver/SesTokInfo"

    r = requests.get(url)
    data = r.text
    soup = BeautifulSoup(data, 'html.parser')

    ses_info = str(soup.find ("sesinfo").contents)
    tok_info = str(soup.find ("tokinfo").contents)

    return ses_info, tok_info


def get_uptime():

    ses_info, tok_info = get_api_token()

    url = "http://192.168.254.254/api/monitoring/traffic-statistics"

    api_headers = {'__RequestVerificationToken': tok_info, 'Cookie': ses_info}
    
    r = requests.get(url, headers = api_headers)
    data = r.text
    soup = BeautifulSoup(data, 'html.parser')
    
    uptime = soup.find ("totalconnecttime").contents

    url = "http://192.168.254.254/api/device/signal"

    r = requests.get(url, headers = api_headers)
    data = r.text
    soup = BeautifulSoup(data, 'html.parser')

    uptime = round(float(uptime[0])/3600,2)

    return uptime


def power_outage_sequence():

    arduino_serial.write("<low,3,0>")       # DVR
    arduino_serial.write("<low,4,0>")       # CCTV PSU
    arduino_serial.write("<high,7,0>")      # Exhaust Fan - Normally Open
    arduino_serial.write("<high,8,0>")      # Intake Fan - Normally Open
    arduino_serial.write("<low,5,0">	    # UAP    

    print("Power outage sequence done.")
    append_history_log("Power Outage")


def power_resumption_sequence():
    
    arduino_serial.write("<high,3,0>")      # DVR
    arduino_serial.write("<high,4,0>")      # CCTV PSU
    
    print("Power resumption sequence done.")
    append_history_log("Power Resumption")


def power_outage_timer_append():

    with open ("/home/pi/Desktop/Apps/Power_Outage_Automation/logs/counters.json") as json_load:
        json_data = json.load(json_load)
        json_data["counters"]["power_outage_timer"] += 1

    with open ("/home/pi/Desktop/Apps/Power_Outage_Automation/logs/counters.json", "w") as json_save:
        json_save.write(json.dumps(json_data))
    

def power_outage_timer_reset():
        
    with open ("/home/pi/Desktop/Apps/Power_Outage_Automation/logs/counters.json") as json_load:
        json_data = json.load(json_load)
        json_data["counters"]["power_outage_timer"] = 0

    with open ("/home/pi/Desktop/Apps/Power_Outage_Automation/logs/counters.json", "w") as json_save:
        json_save.write(json.dumps(json_data))


def power_outage_timer_query():
        
    with open ("/home/pi/Desktop/Apps/Power_Outage_Automation/logs/counters.json") as json_load:
        json_data = json.load(json_load)
        power_outage_timer = json_data["counters"]["power_outage_timer"]
    
    return power_outage_timer


def previous_power_state_update(power_state):
        
    with open ("/home/pi/Desktop/Apps/Power_Outage_Automation/logs/counters.json") as json_load:
        json_data = json.load(json_load)
        json_data["counters"]["previous_power_state"] = power_state

    with open ("/home/pi/Desktop/Apps/Power_Outage_Automation/logs/counters.json", "w") as json_save:
        json_save.write(json.dumps(json_data))


def previous_power_state_query():
        
    with open ("/home/pi/Desktop/Apps/Power_Outage_Automation/logs/counters.json") as json_load:
        json_data = json.load(json_load)
        previous_power_state = json_data["counters"]["previous_power_state"]
    
    return previous_power_state


def append_history_log(sequence_type):

    current_timestamp = get_sytem_timestamp()

    log_input = ("\n" + current_timestamp + "\t-\t" + sequence_type)

    log_file = open("/home/pi/Desktop/Apps/Power_Outage_Automation/logs/history.log","a+")
    log_file.write(log_input)
    log_file.close()


def get_sytem_timestamp():

   # time.sleep(60)	
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    current_timestamp = str(now)

    return current_timestamp


def send_email_alert(msg_as_string):

    email = 'alerts@gmail.com'
    password = 'PASSWORD'
    mail_to = 'juan@gmail.com'

    try:
        try:
            smtp_obj = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        except:
            smtp_obj = smtplib.SMTP('smtp.gmail.com', 587)
            smtp_obj.ehlo()
            smtp_obj.starttls()
        
        smtp_obj.login(email, password)
        smtp_obj.sendmail(email, mail_to, msg_as_string)      # Send function
        smtp_obj.quit()
                    
    except Exception as err:
        try:
            print(err)
            smtp_obj.quit()
        except:
            print("SMTP process failed!")


def main():

    time.sleep(30)     # Sleep function to make sure datetime is loaded correctly
    append_history_log("Raspberry Pi Startup")

    current_timestamp = get_sytem_timestamp()
    send_email_alert("Subject: Sy-Baguio Pi Bootup - " + str(current_timestamp))

    while True:
        try:
            uptime = get_uptime()
           
        except Exception as err:
            #print (err)
            print("Append power outage timer")
            uptime = 0
            power_outage_timer_append()

        power_outage_timer = power_outage_timer_query()
        previous_power_state = previous_power_state_query()

        if uptime > 0.05 and power_outage_timer == 0 and previous_power_state == 1:
            print("Power status all good.")
         
        elif uptime == 0 and power_outage_timer <= 3 and previous_power_state == 1:
            print("Recent power outage, re-checking after 60 seconds.")

        elif uptime > 0 and power_outage_timer <= 3 and previous_power_state == 1:
            power_outage_timer_reset()
        
        elif uptime == 0 and power_outage_timer > 3 and previous_power_state == 1:
            print("Initiating power outage sequence.")
            power_outage_sequence()
            previous_power_state_update(0)
            
        elif uptime == 0 and power_outage_timer > 3 and previous_power_state == 0:
            print("Power have not yet resumed, re-checking after 60 seconds.")

        elif uptime > 0.05 and power_outage_timer > 3 and previous_power_state == 0:
            print("Initiating power resumption sequnce.")
            power_outage_timer = power_outage_timer_query()
            power_outage_timer = ("Power outage total time:\t" + str(power_outage_timer) + " minutes")
            power_outage_timer_reset()
            previous_power_state_update(1)
            power_resumption_sequence()
            append_history_log(power_outage_timer)
            send_email_alert("Subject: Sy-Baguio Power Outage - " + str(power_outage_timer))
            
        time.sleep(60)      # 1 minute cycle resolution
        os.system("clear")
			
			
if __name__ == "__main__":
    main()
