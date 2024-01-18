# KOA Data Access Automation
# run via cron on desired date for next month
# runs daily via cron - TBD
# run with kpython3 for logger functionality

# Verification Types (vtype) to be processed
# - PI                : PI Verification
# - PI_OBS            : PI & Observer Verification
# - COI_OBS           : COI/Observer Verification
# - TDA (ToO or TWI)  : ToO/Twilight Program Verification
# - KPF               : KPF Program Verification (SEM 2024B Aug 1, 2024)

# ToDo:
# - Observers needs to be changed from a list to a set (can change per semid for multiday)

import pdb
#pdb.set_trace()

import argparse
import calendar as cal
from datetime import datetime as dt, timedelta
import json
import requests
import sys
import urllib3
urllib3.disable_warnings()

# logger imports
#from LoggerClient import Logger as dl
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

#tclogger = create_logger('Data Access Automation', None, 'JPH', None, None, None, 'koa')
#tclogger.info('Running KOA Data Access Automation')


# APIs (move to config.live.ini)

# WMKO Employee API
#emp_url = "https://www3build.keck.hawaii.edu/api/employee"
# https://vm-appserver.keck.hawaii.edu/api/employee/getEmployee?role=SA
emp_url = "https://vm-appserver.keck.hawaii.edu/api/employee"

# WMKO Telescope Schedule API
#sched_url = "https://www3build.keck.hawaii.edu/api/schedule"
# https://vm-appserver.keck.hawaii.edu/api/schedule/getSchedule?date=2024-01-17
sched_url = "https://vm-appserver.keck.hawaii.edu/api/schedule"

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
    sa_info["alias"] = sa_alias
    sa_info["eid"] = sa_eid
    sa_obj[sa_alias] = sa_info

#print(f'SAs: {sa}\n')    
#print(f'SA Object: {sa_obj}\n')    

# ====================

required = admin + list(sa)

# Type: PI Verification - send report monthly
#if vtype == 'PI':

#today = dt.now()
#next_month = today.month + 1
#this_year = today.year
#num_days = cal.monthrange(this_year, next_month)[1]
#startDate = f'{this_year}-{next_month}-1'
#startDate = dt.strptime(startDate, '%Y-%m-%d')
#endDate = startDate + timedelta(days=num_days-1)

#startDate = dt.strftime(startDate, '%Y-%m-%d')
#endDate   = dt.strftime(endDate, '%Y-%m-%d')

# TEST DATES
startDate = '2024-01-01'
endDate = '2024-01-31'
#num_days = 31
num_days = 5
# END TEST DATES

print(f'startDate: {startDate}, endDate: {endDate}, numDays: {num_days}')

url = sched_url
params = {}
params["cmd"]     = "getSchedule"
params["date"]    = startDate
params["numdays"] = num_days

print(f'sched PARAMS (PIs for SEMIDs): {params}\n')

resp = requests.get(url, params=params, verify=False)
if not resp:
    print('NO DATA RESPONSE')
    sys.exit()
else:
    data = resp.json()

# Type: PI Verification
# - Grab all unique programs for the upcoming month using the telescope schedule API 

for entry in data:
    #print(entry)
    prog_code = f"{entry['Semester']}_{entry['ProjCode']}"
    prog_codes.add(prog_code)

    # generate PIs per prog_code
    if entry['PiEmail']:
        pi_alias = (entry['PiEmail'].split('@'))[0]
    else:
        pi_alias = entry['PiEmail']

    pi[prog_code] = f"{entry['PiEmail']}, {entry['PiLastName']}, {entry['PiFirstName']}, {pi_alias}"

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

print()
#print(f'SEMIDS: {prog_codes}\n')      # list of prog_codes
#print(f'PIs: {pi}\n')
#print(f'SAs: {sa_obj}\n')    
#print(f'OBSERVERS: {observers}\n')    # list of observers per prog_code

print("***** WMKO API: PI and Observers *****\n")

for prog_code in prog_codes:
    print(f'{prog_code}: {pi[prog_code]}, {observers[prog_code]}')   # wmko everything
print(f'{len(prog_codes)} prog_codes\n')

#print(f'SAs: {sa_obj}')
print(f'SAs ({len(sa_obj)}):')
for k,v in sa_obj.items():
    print(f'{k}: {v}')
print()

#print(f'PIs: {pi}')
print(f'PIs ({len(pi)}):')
for k,v in pi.items():
    print(f'{k}: {v}')
print()

#print(f'OBSERVERS: {observers}')
print(f'Observers ({len(observers)}):')
for k,v in observers.items():
    print(f'{k}: {v}')
print()

# ============

# - For each program, query the NExScI data access API to retrieve all accounts that have access 
print('***** NExScI API *****\n')

url = ipac_url
params = {}
params["request"] = "GET_USERS_WITH_ACCESS"

for prog_code in prog_codes:
    print(f'SEMID: {prog_code}')
    #print(f" -- WMKO PI       : {pi[prog_code]}")
    #print(f" -- WMKO SAs      : {sa}")
    #print(f" -- WMKO Observers: {observers[prog_code]}")

    params["semid"] = prog_code
    resp = requests.get(url, params=params, auth=("KOA","Humu3"))   # use config.live.ini
    resp = resp.json()

    ipac_users = set()
    for user in resp["response"]["detail"]:
        #print(user["userid"], user["email"], user["keckid"], user["first"], user["last"])
        #ipac_users.add(user["userid"])  # additional check in case email address is changed
        ipac_users.add(user["email"].split("@")[0])

    print(f' -- IPAC Users    : {ipac_users}')

    print(f" -- WMKO PI       : {pi[prog_code]}")
    wmko_pi_alias = pi[prog_code].split(",")[-1].strip()

    #if wmko_pi_alias in ipac_users:
    if wmko_pi_alias not in ipac_users:
        print(f'    Access Required for PI: {pi[prog_code]}')

    print(f" -- WMKO SAs      : {sa}")
    for a_sa in sa:
        if a_sa not in ipac_users:
            print(f'    Access Required for SA: {sa_obj[a_sa]}')

#    print(f" -- WMKO Observers: {observers[prog_code]}")

#        # need to account for what is in WMKO and not in NExScI
#
#        # per SEMID (prog-code)
#        if vtype == 'PI':
#            # print if PI info not in NExScI info
#            #print(f'PI\'s Alias: {pi[prog_code].split(",")[-1]}')
#            print(f'USERID: {user["userid"]}')
#
#            if user['userid'] == pi[prog_code].split(",")[-1]:
#                print(f'PI Match {user}')
#            if user['userid'] in sa:
#                print(f'SA Match {user}')
#            
#        if vtype == 'PI_OPS':
#            # print if OPS info not in NExScI
#            if user['userid'] == pi[prog_code]:
#                print('PI Match {user}')
#            if user['userid'] == sa[prog_code]:
#                print('SA Match {user}')
#            if user['userid'] == sa[prog_code]:
#                print('OPS Match {user}')
#        if vtype == 'COI_OBS':
#            # process COI_OBS
#            pass
#        if vtype == 'TDA':
#            # process TDA - ToO or TWI
#            pass
#        if vtype == 'KPF':
#            # process KPF
#            pass
#
##        if user["userid"] in required:
##            print(f'+       {user}')
##        elif user["userid"] in ignore:
##            print(f'o       {user}')
##        else:
##            print(f'-       {user}')

print()

# ============

# - Verify that the PI, koaadmin, hireseng, and all SAs have access to that program 
# - Send an email summary to the KOA helpdesk with information for those programs that need their access updated 


# def construct email(s)


# def send email(s)


# if necessary to make make a class
# ================ main entry point

# - logger?

# - accept arguments
# - set up for vtype
# - send API request

# - process vtype

# - generate report

# - send report

