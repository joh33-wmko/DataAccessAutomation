#! /usr/local/anaconda/bin/python

# KOA Data Access Automation (DAA)
# - Check tonight
# -      $ python3 ./verify_data_access.py
# -      Default date is today and default num days is 1
# - Check schedule changes (programs, observers, etc.)
# -      $ python3 ./verify_data_access.py --numdays 7
# -      Verifies if new observers
# - Check next month
# -      $ python3 ./verify_data_access.py --date 2024-02-01 --numdays 29
# -      Verifies PI, Observers, cps, etc.
# - Send report via email(s)
# -      $ python3 ./verify_data_access.py --date 2024-02-01 --numdays 29 --email jmader@keck.hawaii.edu
# - Run with kpython3 for logger functionality (uncomment "# toggle for logger" lines)

# ToDos:
# - KoaAccess
# - KpfAccess
# - make defs for "new" assignments

# daa imports
import argparse
import json
import os
import requests
import smtplib
import socket
from socket import gethostname
import sys
from email.mime.text import MIMEText
from datetime import datetime as dt, timedelta
import urllib3
urllib3.disable_warnings()

import pdb   # pdb.set_trace() sets breakpoint

# prepare config file
from os.path import dirname
import yaml

dirname = dirname(__file__)
configFile = "config.live.ini"
filename = f'{dirname}/{configFile}'
assert os.path.isfile(filename), f"ERROR: {filename} file missing"
with open(filename) as f: config = yaml.safe_load(f)

date_format = '%Y-%m-%d'

email = ''
error = ''
message = ''
#message = ''.join((message, id.zfill(4), '  '))

message = ''.join((message, '\nKOA DATA ACCESS AUTOMATION (DAA) REPORT\n'))

#EMAIL_LIST = config["REPORT"]["ADMIN_EMAIL"]
EMAIL_LIST = config["REPORT"]["WMKO_EMAIL"]
#EMAIL_LIST = config["REPORT"]["IPAC_EMAIL"]
#EMAIL_LIST = ','.join(config["REPORT"]["WMKO_EMAIL"], config["REPORT"]["IPAC_EMAIL"])

def send_email(message, error):
    errorMsg = 'ERROR: ' if error == 1 else ''
    #email = config["REPORT"]["EMAIL_LIST"]
    msg = MIMEText(message)
    msg['Subject'] = f"{errorMsg} KOA Data Access Verification ({socket.gethostname()})"
    msg['To'] = EMAIL_LIST
    msg['From'] = config["REPORT"]["ADMIN_EMAIL"]
    s = smtplib.SMTP('localhost')
    s.send_message(msg)
    s.quit()

def valid_date(date_str: str) -> dt:
    try:
        return dt.strptime(date_str, date_format)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a valid date: {date_str!r}")

# parse command line arguments
parser = argparse.ArgumentParser(description="Verify Data Access")
parser.add_argument("--date", type=valid_date, default=dt.today(), help="Run Date Format is yyyy-mm-dd", required=False)
parser.add_argument("--numdays", type=int, default=1, help="Integer from 1 to 180", required=False)
parser.add_argument("--email", default=False, action="store_true", help="Enter emails separated by commmas", required=False)
args = parser.parse_args()

startDate = args.date
numdays = args.numdays
email = args.email

if numdays <= 0:
    numdays = 1
if numdays >=180:
    numdays = 180

#startDate = dt.strptime(startDate, date_format)
endDate = startDate + timedelta(days=numdays-1)

startDate = dt.strftime(startDate, '%Y-%m-%d')
endDate   = dt.strftime(endDate, '%Y-%m-%d')

date_range = f'{startDate} to {endDate} ({numdays} day(s)) '
message = ''.join((message, date_range, "\n"))

# ----- APIs ----- move to def calls

emp_url   = config['API']['EMP_URL']     # for SAs
sched_url = config['API']['SCHED_URL']   # for SEMIDs
obs_url   = config['API']['OBS_URL']     # for Observers' info
#admin_url = config["API"]["ADMIN_URL"]   # for user info
coi_url  = config['API']['COI_URL']      # for for coversheet COIs
koa_url  = config['API']['KOA_URL']      # for for coversheet KoaAccess
kpf_url  = config['API']['KPF_URL']      # for for coversheet KpfAccess
ipac_url  = config['API']['IPAC_URL']    # for IPAC GET_USERS_WITH_ACCESS

# ----- create data objects: WMKO SAs -----
# Call APIs on the startDate and numdays
# API request for list of current SAs - will only change for new and departing SAs

#emp_url             = config['API']['EMP_URL']
emp_params          = {}
emp_params["role"]  = "SA"

wmko_emp_resp = requests.get(emp_url, params=emp_params, verify=False)
if not wmko_emp_resp:
    print('NO DATA RESPONSE')
    message = ''.join((message, 'NO DATA RESPONSE'))
    sys.exit()
else:
    wmko_emp_data = wmko_emp_resp.json()

#for sa_item in wmko_emp_data:
    #print(sa_item)

# API request for list of current Observers
#obs_url = config['API']['OBS_URL']
sa_obj = {}
sa_list = []
for sa_item in wmko_emp_data:
    sa_info = {}
    sa_alias = sa_item["Alias"]
    sa_firstname = sa_item["FirstName"]
    sa_lastname = sa_item["LastName"]
    sa_email = f'{sa_item["Alias"]}@keck.hawaii.edu'
    sa_keckid = sa_item["EId"]
    #sa.add(sa_alias)
    sa_list.append(sa_alias)
    sa_info["firstname"] = sa_firstname
    sa_info["lastname"] = sa_lastname
    sa_info["email"] = sa_email
    sa_info["alias"] = sa_alias
    sa_info["keckid"] = 0 #sa_keckid

    obs_params = {}
    obs_params["last"]   = sa_lastname
    obs_params["first"]  = sa_firstname
    wmko_obs_resp = requests.get(obs_url, params=obs_params, verify=False)
    wmko_obs_resp = wmko_obs_resp.json()

    for item in wmko_obs_resp:
        sa_info["keckid"] = item["Id"]

    sa_obj[sa_alias] = sa_info

# ----- create PI and OBS objects from schedule API -----

#sched_url = config['API']['SCHED_URL']
sched_params = {}
sched_params["date"]    = startDate
sched_params["numdays"] = numdays

wmko_sched_resp = requests.get(sched_url, params=sched_params, verify=False)
if not wmko_sched_resp:
    print('NO DATA RESPONSE')
    message = ''.join((message, 'NO DATA RESPONSE'))
    sys.exit()
else:
    wmko_sched_data = wmko_sched_resp.json()

prog_codes = set()
pi = {}
observers = {}

for entry in wmko_sched_data:
    #print(entry)
    prog_code = f"{entry['Semester']}_{entry['ProjCode']}"
    prog_codes.add(prog_code)

    # generate PIs per prog_code
    if entry['PiEmail']:
        pi_alias = (entry['PiEmail'].split('@'))[0]
    else:
        pi_alias = entry['PiEmail']

    pi[prog_code] = f"{entry['PiEmail']}, {entry['PiLastName']}, {entry['PiFirstName']}, {pi_alias}, {entry['PiId']}"

    # generate Observers per prog_code
    if prog_code not in observers.keys():
        observers[prog_code] = []           # add new prog_code list
    if 'Observers' in entry.keys():
        if entry["Observers"] != None:
            #observers[prog_code] += entry["Observers"].split(",")
            observers[prog_code] = entry["Observers"].split(",")   # fixes replicated observers
            observers[prog_code] = set(observers[prog_code])
        else:
            observers[prog_code] = None 

prog_codes = list(prog_codes)
prog_codes.sort()

output = {}

# ----- generate report -----

#print(f'{len(prog_codes)} SEMIDs found')
message = ''.join((message, f'{len(prog_codes)} SEMIDs found \n'))
##daalogger.info('KOA DAA: Processing {len(prog_codes)} SEMIDs found ')   # toggle for logger


admins = ['koaadmin', 'hireseng']
output = {}

#ipac_url = config['API']['IPAC_URL']

for prog_code in prog_codes:
#    print(prog_code)
    output[prog_code] = []
    ##daalogger.info('KOA DAA: Processing ', ..., {semid}, {progid})   # split semid and progid and report to logger; toggle for logger
    #daalogger.info('KOA DAA: Processing {prog_code}')   # split semid and progid and report to logger

    # ----- IPAC User Access List -----
    ipac_params = {}
    ipac_params["request"] = "GET_USERS_WITH_ACCESS"
    ipac_params["semid"] = prog_code
    ipac_resp = requests.get(ipac_url, params=ipac_params, auth=(config['ipac']['user'],config['ipac']['pwd']))
    ipac_resp = ipac_resp.json()

    ipac_users = set()
    for ipac_obj in ipac_resp["response"]["detail"]:
        #print(ipac_obj["userid"], ipac_obj["email"], ipac_obj["keckid"], ipac_obj["first"], ipac_obj["last"])
        #ipac_users.add(ipac_obj["userid"])  # additional check in case email address is changed
        ipac_users.add(ipac_obj["email"].split("@")[0])

    # ----- WMKO KoaAccess -----

    koa_params          = {}
    koa_params["ktn"]   = prog_code
    
    wmko_koa_resp = requests.get(koa_url, params=koa_params, verify=False)
    if not wmko_koa_resp:
        print('NO DATA RESPONSE')
        message = ''.join((message, 'NO DATA RESPONSE'))
        koa_access = None
        sys.exit()
    else:
        koa_access = wmko_koa_resp.json()['KoaAccess']
        koa_pair = f'"KoaAccess": {koa_access}'

    #print(f'*** {prog_code} WMKO KoaAccess Data: {koa_access} ***')
    #output[prog_code].append(koa_pair)


    # ----- WMKO KpfAccess [TBD 2024B Aug 2024] -----

    kpf_params          = {}
    kpf_params["ktn"]   = prog_code
    
    wmko_kpf_resp = requests.get(kpf_url, params=kpf_params, verify=False)
    #print(f'WMKO KpfAccess Data: {wmko_kpf_resp}')
    if not wmko_kpf_resp:
        #print('NO DATA RESPONSE')
        #message = ''.join((message, 'NO DATA RESPONSE'))   # uncomment when kpf access becomes available
        kpf_access = None
        kpf_pair = f'"KpfAccess": None'
        #sys.exit()
    else:
        kpf_access = wmko_kpf_resp.json()['KpfAccess']
        kpf_pair = f'"KpfAccess": {kpf_access}'

    #print(f'*** {prog_code} WMKO KpfAccess Data: {kpf_access} ***')
    #output[prog_code].append(kpf_pair)

    # ----- WMKO PIs -----
    pi_rec    = pi[prog_code].split(",")
    pi_email  = pi_rec[0].strip()
    pi_lname  = pi_rec[1].strip()
    pi_fname  = pi_rec[2].strip()
    pi_alias  = pi_rec[3].strip()
    pi_keckid = pi_rec[4].strip()

    new = {}
    new["semid"] = prog_code
    new["usertype"] = "pi"
    new["firstname"] = pi_fname
    new["lastname"] = pi_lname
    new["email"] = pi_email
    #new["alias"] = ""
    new["alias"] = pi_alias
    new["keckid"] = pi_keckid
    new["access"] = "required" if pi_alias not in ipac_users else "granted"
    new["koa_access"] = koa_access
    new["kpf_access"] = kpf_access
    output[prog_code].append(new)


    # ----- WMKO Admins -----
    # need additional admin info from IPAC database
    # API request for list of current admins
    # admin_url = config["API"]["IPAC_URL"]
    for adm in admins:
        #print(f'adm is {adm}')
#        admin_params = {}
#        admin_params["last"]  = adm
#        wmko_adm_resp = requests.get(admin_url, params=admin_params, verify=False)
#        wmko_adm_resp = wmko_adm_resp.json()

#        if wmko_adm_resp:
#            admin_lname = wmko_adm_resp["LastName"]
#            admin_fname = wmko_adm_resp["FirstName"]
#            admin_email = wmko_adm_resp["Email"]
#            admin_id    = wmko_adm_resp["Id"]
#            admin_user  = wmko_adm_resp["username"]

        new = {}
        new["semid"] = prog_code
        new["usertype"] = "admin"
        new["firstname"] = ""
        new["lastname"] = ""
        new["email"] = ""
        new["alias"] = adm
        new["keckid"] = 0
        new["access"] = "required" if adm not in ipac_users else "granted"
        output[prog_code].append(new)
    
    # ----- WMKO SAs -----
    for sa in sa_list:
        #print(sa)
        sa_fname  = sa_obj[sa]['firstname']
        sa_lname  = sa_obj[sa]['lastname']
        sa_addr   = sa_obj[sa]['email']
        sa_alias  = sa_obj[sa]['alias']
        sa_keckid = sa_obj[sa]['keckid']

        new = {}
        new["semid"] = prog_code
        new["usertype"] = "sa"
        new["firstname"] = sa_fname
        new["lastname"] = sa_lname
        new["email"] = sa_addr
        new["alias"] = sa_alias
        new["keckid"] = sa_keckid
        new["access"] = "required" if sa not in ipac_users else "granted"
        output[prog_code].append(new)

    # ----- WMKO Observers -----
    if koa_access:
        for obs_lname in observers[prog_code]:
            obs_params = {}
            obs_params["last"]  = obs_lname
            wmko_obs_resp = requests.get(obs_url, params=obs_params, verify=False)
            wmko_obs_resp = wmko_obs_resp.json()
    
            for item in wmko_obs_resp:
                #print(f'item is {item}')
                obs_fname = item["FirstName"]
                obs_lname = item["LastName"]
                obs_email = item["Email"]
                obs_id    = item["Id"]
                obs_user  = item["username"]
    
                new = {}
                new["semid"] = prog_code
                new["usertype"] = "observer"
                new["firstname"] = obs_fname
                new["lastname"] = obs_lname
                new["email"] = obs_email
                #new["alias"] = ""
                new["alias"] = obs_user
                #new["username"] = obs_user
                new["keckid"] = obs_id
                new["access"] = "required" if obs_user not in ipac_users else "granted"
                #new["koa_access"] = koa_access
                #new["kpf_access"] = kpf_access
                output[prog_code].append(new)


    # ----- WMKO COI -----
        coi_params          = {}
        coi_params["ktn"]   = prog_code
        
        wmko_coi_resp = requests.get(coi_url, params=coi_params, verify=False)
        if not wmko_coi_resp:
            print('NO DATA RESPONSE')
            message = ''.join((message, 'NO DATA RESPONSE'))
            sys.exit()
        else:
            wmko_coi_data = wmko_coi_resp.json()['data']['COIs']
        
        #print(f'WMKO COI DATA: {wmko_coi_data}')
        
        for coi_item in wmko_coi_data:
            coi_semid  = coi_item['KTN']
            coi_type   = coi_item['Type']
            coi_fname  = coi_item['FirstName']
            coi_lname  = coi_item['LastName']
            coi_email  = coi_item['Email']
            coi_alias  = coi_item['Email'].split('@')[0]
            coi_keckid = coi_item['ObsId']
        
            new = {}
            new["semid"] = prog_code
            #new["semid"] = coi_semid
            #new["usertype"] = "coi"   # if both observer and coi, do not replicate
            new["usertype"] = coi_type.lower()
            new["firstname"] = coi_fname
            new["lastname"] = coi_lname
            new["email"] = coi_email
            new["alias"] = coi_alias
            new["keckid"] = coi_keckid
            new["access"] = "required" if pi_alias not in ipac_users else "granted"
            #new["access"] = "required"   # combine with observers
            #new["koa_access"] = koa_access
            #new["kpf_access"] = kpf_access
            output[prog_code].append(new)

#    # ----- WMKO KoaAccess -----
#
#        koa_params          = {}
#        koa_params["ktn"]   = prog_code
#        
#        wmko_koa_resp = requests.get(koa_url, params=koa_params, verify=False)
#        if not wmko_koa_resp:
#            print('NO DATA RESPONSE')
#            message = ''.join((message, 'NO DATA RESPONSE'))
#            koa_access = None
#            sys.exit()
#        else:
#            koa_access = wmko_koa_resp.json()['KoaAccess']
#            koa_pair = f'"KoaAccess": {koa_access}'
#
#        print(f'*** {prog_code} WMKO KoaAccess Data: {koa_access} ***')
#        output[prog_code].append(koa_pair)
#    
#
#    # ----- WMKO KpfAccess [TBD 2024B Aug 2024] -----
#
#        kpf_params          = {}
#        kpf_params["ktn"]   = prog_code
#        
#        wmko_kpf_resp = requests.get(kpf_url, params=kpf_params, verify=False)
#        #print(f'WMKO KpfAccess Data: {wmko_kpf_resp}')
#        if not wmko_kpf_resp:
#            #print('NO DATA RESPONSE')
#            #message = ''.join((message, 'NO DATA RESPONSE'))   # uncomment when kpf access becomes available
#            kpf_access = None
#            kpf_pair = f'"KpfAccess": None'
#            #sys.exit()
#        else:
#            kpf_access = wmko_kpf_resp.json()['KpfAccess']
#            kpf_pair = f'"KpfAccess": {kpf_access}'
#
#        print(f'*** {prog_code} WMKO KpfAccess Data: {kpf_access} ***')
#        output[prog_code].append(kpf_pair)



json_output = json.dumps(output, indent=2)
#print(json_output)

# ----- send report via email -----
# send an email python object to the KOA helpdesk users (and respective info) which require access
# output report is a python object. to make json friendly, remove final commas from lists

message = ''.join((message, "\n"))

final_output = ''.join((message, json_output))

#sendReport = False
# if ...
sendReport = True
#...

if (sendReport and email):
    send_email(final_output, error)
else: print(final_output, error)
