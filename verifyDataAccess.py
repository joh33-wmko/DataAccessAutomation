# KOA Data Access Automation
# runs daily via cron

# Verification Types (vtype) to be processed
# - PI                : PI Verification
# - PI_OBS            : PI & Observer Verification
# - COI_OBS           : COI/Observer Verification
# - TDA (ToO or TWI)  : ToO/Twilight Program Verification
# - KPF               : KPF Program Verification (SEM 2024B Aug 1, 2024)

import argparse
import json
import requests
import datetime as dt
import sys
import urllib3
urllib3.disable_warnings()

# logger imports
from LoggerClient import Logger as dl
import os
import logging
from logging import StreamHandler, FileHandler
import pdb

def create_logger(subsystem, configLoc, author, progid, semid, fileName, loggername):
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    kwargs = {'subsystem':subsystem, 'author':author, 'progid':progid, 'semid':semid, 'loggername': loggername}
    zmq_log_handler = dl.ZMQHandler(configLoc, local=False, **kwargs)
    ch = StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logger = logging.getLogger()
    logger.addHandler(zmq_log_handler)
    logger.addHandler(ch)
    logger.setLevel(logging.INFO)
    return logger

tclogger = create_logger('Data Access Automation', None, 'JPH', None, None, None, 'koa')
tclogger.info('Running KOA Data Access Automation')


# APIs (move to config.live.ini)

# WMKO Employee API
emp_url = "https://www3build.keck.hawaii.edu/api/employee"

# WMKO Telescope Schedule API
sched_url = "https://www3build.keck.hawaii.edu/api/schedule"

# IPAC Access API (for GET_USERS_WITH_ACCESS and GET_SEMIDS_PER_USER)
ipac_url = "http://vmkoatest.ipac.caltech.edu:8001/cgi-bin/PIAccess/nph-PIAccess_Auth.py"

# parse command line arguments
parser = argparse.ArgumentParser(description="Verify Data Access")
parser.add_argument("vtype")
args = parser.parse_args()
vtype = args.vtype              # vtype = PI, PI_OBS, COI_OBS, TDA (ToO or TWI), or KPF
print(f'\nvtype: {vtype}\n')

sa         = set()                          # required current SAs
admin      = ['koaadmin', 'hireseng']       # required admins
required   = []                             # required all = sa + admin
test       = ['rtiguitest1', 'rtiuser02']   # optional test
other      = ['jomeara', 'rcampbell']       # optional other
ignore     = test + other                   # optional all = test + other

prog_codes = set()
pi         = {}     # always one per prog_code
observers  = {}

sa_info    = {}


# API request for list of current SAs
url = emp_url
params = {}
params["cmd"]     = "getEmployee"
params["role"]    = "SA"

print(f'emp PARAMS for SAs: {params}')

resp = requests.get(url, params=params, verify=False)
if not resp:
    print('NO DATA RESPONSE')
    sys.exit()
else:
    sa_data = resp.json()

sa_obj = {}
for sa_item in sa_data:
    sa_info = {}
    sa_alias = sa_item["Alias"]
    sa_email = f'{sa_item["Alias"]}@keck.hawaii.edu'
    sa_firstname = sa_item["FirstName"]
    sa_lastname = sa_item["LastName"]
    sa_eid = sa_item["EId"]
    sa.add(sa_alias)
    sa_info["firstname"] = sa_firstname
    sa_info["lastname"] = sa_lastname
    sa_info["email"] = sa_email
    sa_info["eid"] = sa_eid
    sa_obj[sa_alias] = sa_info

#for k,v in sa_obj.items():
#    print(k,v)

#for x in sa:
#    print(x, sa_obj[x])

#print(f'SA Obj: {sa_obj}')

print(f'SAs: {sa}\n')    

# ====================

required = admin + list(sa)

# Type: PI Verification - send report monthly
if vtype == 'PI':
    # process argument(s) - move to main()

    # prepare vars
    #startDate = dt.datetime.strptime(startDate, "%Y-%m-%d")
    #endDate   = dt.datetime.strptime(endDate, "%Y-%m-%d")
    #delta     = endDate - startDate
    #days      = delta.days + 1

    # test vars
    startDate = dt.datetime.strptime("2024-01-01", "%Y-%m-%d")
    endDate   = dt.datetime.strptime("2024-01-31", "%Y-%m-%d")
    #num_days = (endDate - startDate) + dt.timedelta(days=1)
    #num_days = 31
    num_days = 10

    print(f'startDate: {startDate}, endDate: {endDate}, numDays: {num_days}')

    # prepare report date Monday prior to the start of next month, at least 7 days
    # today = 
    # month = month + 1
    # last_dom =  # 28, 29, 30, or 31
    # report_date = last_dom - 7 days
    # report_date - 1 day until dat is Monday
    # startDate = reportDate
    # num_dim = ...
    # endDate = startDate + num_dim
 
    url = sched_url
    params = {}
    params["cmd"]     = "getSchedule"
    #startDate = "2024-01-03"
    params["date"]    = startDate.strftime("%Y-%m-%d")
    params["numdays"] = num_days

print(f'sched PARAMS (PIs for SEMIDs): {params}\n')

resp = requests.get(url, params=params, verify=False)
if not resp:
    print('NO DATA RESPONSE')
    sys.exit()
else:
    data = resp.json()

# process data for vtype

# Type: PI Verification
# - Grab all unique programs for the upcoming month using the telescope schedule API 

for entry in data:
    #print(entry)
    prog_code = f"{entry['Semester']}_{entry['ProjCode']}"
    prog_codes.add(prog_code)

    # generate PI and Observers lists per prog_code
    pi_alias = (entry['PiEmail'].split('@'))[0]
    pi[prog_code] = f"{entry['PiEmail']}, {entry['PiLastName']}, {entry['PiFirstName']}, {pi_alias}"

    # original - verify, may have been modified...
    #if entry["ProjCode"] not in observers.keys():         # causes replicated observers ???
        #observers[semid] = []
    #observers[prog_code] += entry["Observers"].split(",")

    if prog_code not in observers.keys():                 # fixes replicated observers ???
        observers[prog_code] = []
    if 'Observers' in entry.keys():
        #observers[prog_code] += entry["Observers"].split(",")
        observers[prog_code] = entry["Observers"].split(",")

print()
print(f'SEMIDS: {prog_codes}\n')      # list of prog_codes
print(f'PIs: {pi}\n')
print(f'OBSERVERS: {observers}\n')    # list of observers per prog_code

print("***** WMKO API: PI and Observers *****\n")

for prog_code in prog_codes:
    print(f'{prog_code}: {pi[prog_code]}, {observers[prog_code]}')   # wmko everything
print(f'{len(prog_codes)} prog_codes\n')

print(f'PIs: {pi}')
for k,v in pi.items():
    print(f'{k}: {v}')
print(f'{len(pi)} PIs\n')

print(f'OBSERVERS" {observers}')
for k,v in observers.items():
    print(f'{k}: {v}')
print(f'{len(observers)} observers\n')

# ============

# - For each program, query the NExScI data access API to retrieve all accounts that have access 
print('***** NExScI API *****\n')

url = ipac_url
params = {}
params["request"] = "GET_USERS_WITH_ACCESS"

for prog_code in prog_codes:
    print(prog_code)
    print(f" -- PI: {pi[prog_code]}")
    print(f" -- Observers: {observers[prog_code]}")
    print(f'PROG_CODE {prog_code}')
    params["semid"] = prog_code
    resp = requests.get(url, params=params, auth=("KOA","Humu3"))   # use config.live.ini
    resp = resp.json()

    #print(f' -- SAs:')
    #for user in resp["response"]["detail"]:
    if not resp["response"]["detail"]:
        # ERROR
        sys.exit()
    for user in resp["response"]["detail"]:
        #print(user["userid"], user["email"], user["keckid"], user["first"], user["last"])
        if user["userid"] in required:
            print(f'+       {user}')
        elif user["userid"] in ignore:
            print(f'o       {user}')
        else:
            print(f'-       {user}')


print()

# ============

# - Verify that the PI, koaadmin, hireseng, and all SAs have access to that program 
# - Send an email summary to the KOA helpdesk with information for those programs that need their access updated 


# construct email(s)


# send email(s)


# if necessary to make make a class
# ================ main entry point

# - logger?

# - accept arguments
# - set up for vtype
# - send API request

# - process vtype

# - generate report

# - send report

