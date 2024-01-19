#! /usr/local/anaconda/bin/pyton

# KOA Data Access Automation (DAA)
# - run via cron on desired date for next month
# - TBD - runs daily via cron
# - run with kpython3 for logger functionality

# Verification Types (vtype) to be processed
# - PI                : PI Verification
# - PI_OBS            : PI & Observer Verification
# - COI_OBS           : COI/Observer Verification
# - TDA (ToO or TWI)  : ToO/Twilight Program Verification
# - KPF               : KPF Program Verification (SEM 2024B Aug 1, 2024)

# ToDo's
# - [DONE] args PI vs PI_OBS
# - fix too many values for Observers output
# - sort SEMIDs for report
# - arg to override default (next month) with this month (or any month?) for PI
#   'jan' or '01' or '1'
# - [DONE] output {} in f-string expressions
# - case treatment of vtypes
# - alias/ipac koaid is first initial + last name
# - transfer API urls and account info to config.live.ini
# - defs for request params and object displays?
# - replace "set()" with None for output objects (ipac_users, etc.)
# - logger messages

# daa imports
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
import pdb   # pdb.set_trace() sets breakpoint

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
# emp_url = "https://www3build.keck.hawaii.edu/api/employee"
# https://vm-appserver.keck.hawaii.edu/api/employee/getEmployee?role=SA
emp_url = "https://vm-appserver.keck.hawaii.edu/api/employee"

# WMKO Telescope Schedule API
# sched_url = "https://www3build.keck.hawaii.edu/api/schedule"
# https://vm-appserver.keck.hawaii.edu/api/schedule/getSchedule?date=2024-01-17
sched_url = "https://vm-appserver.keck.hawaii.edu/api/schedule"

# IPAC Access API (for GET_USERS_WITH_ACCESS and GET_SEMIDS_PER_USER)
ipac_url = "http://vmkoatest.ipac.caltech.edu:8001/cgi-bin/PIAccess/nph-PIAccess_Auth.py"

print(f'\nKOA DATA ACCESS AUTOMATION (DAA) REPORT')

# parse command line arguments
parser = argparse.ArgumentParser(description="Verify Data Access")
parser.add_argument("vtype")
args = parser.parse_args()

vtype = args.vtype
if vtype.upper() == 'PI':
    vtype = 'PI'
    print(f'\nProcessing PI Verification for')
if vtype.upper() == 'PI_OBS':
    vtype = 'PI_OBS'
    print(f'\nProcessing PI & Observer Verification for')
#if vtype.upper() == 'COI_OBS':
#    vtype = 'COI_OBS'
#    print(f'\nProcessing COI & Observer Verification for')
#if vtype.upper() == 'TDA':   # ToO or TWI
#    vtype = 'TDA'
#    print(f'\nProcessing TDA (ToO or Twilight) Verification for')
#if vtype.upper() == 'KPF':
#    vtype = 'KPF'
#    print(f'\nProcessing KPF Verification for')

sa         = set()                          # required current SAs
admin      = ['koaadmin', 'hireseng']       # required admins
observers  = {}
pi         = {}     # always one per prog_code
#test       = ['rtiguitest1', 'rtiuser02']   # optional test
#other      = ['jomeara', 'rcampbell']       # optional other
#ignore     = test + other                   # optional all = test + other

prog_codes = set()
sa_info    = {}
admin_info = {}
#observer_info = {}
#pi_info        = {}

# API request for list of current SAs
url = emp_url
params = {}
params["cmd"]     = "getEmployee"
params["role"]    = "SA"

#print(f'emp PARAMS for SAs: {params}')

wmko_emp_resp = requests.get(url, params=params, verify=False)
if not wmko_emp_resp:
    print('NO DATA RESPONSE')
    sys.exit()
else:
    wmko_emp_data = wmko_emp_resp.json()

sa_obj = {}
for sa_item in wmko_emp_data:
    sa_info = {}
    sa_alias = sa_item["Alias"]
    sa_email = f'{sa_item["Alias"]}@keck.hawaii.edu'
    sa_firstname = sa_item["FirstName"]
    sa_lastname = sa_item["LastName"]
    sa_keckid = sa_item["EId"]
    sa.add(sa_alias)
    sa_info["firstname"] = sa_firstname
    sa_info["lastname"] = sa_lastname
    sa_info["email"] = sa_email
    sa_info["alias"] = sa_alias
    sa_info["keckid"] = sa_keckid
    sa_obj[sa_alias] = sa_info

# ====================

# calclates dates for next month
#today = dt.now()
#next_month = today.month + 1
#this_year = today.year
#num_days = cal.monthrange(this_year, next_month)[1]
#startDate = f'{this_year}-{next_month}-1'
#startDate = dt.strptime(startDate, '%Y-%m-%d')
#endDate = startDate + timedelta(days=num_days-1)
#
#startDate = dt.strftime(startDate, '%Y-%m-%d')
#endDate   = dt.strftime(endDate, '%Y-%m-%d')

# test dates
startDate = '2024-01-01'
endDate = '2024-01-31'
#num_days = 31
num_days = 5

print(f'{startDate} to {endDate} ({num_days} days)\n')

url = sched_url
params = {}
params["cmd"]     = "getSchedule"
params["date"]    = startDate
params["numdays"] = num_days

#print(f'sched PARAMS (PIs for SEMIDs): {params}\n')

wmko_sched_resp = requests.get(url, params=params, verify=False)
if not wmko_sched_resp:
    print('NO DATA RESPONSE')
    sys.exit()
else:
    wmko_sched_data = wmko_sched_resp.json()


# API request for list of current Observers
url = emp_url
params = {}
params["cmd"]       = "getEmployee"

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
            # convert last name to alias (username from email address)
            # params["lastname"]  = obs_lastname
            # request...
        else:
            observers[prog_code] = None 

for obs_item in observers:
    # search wmko API 
    pass

#print(f'\n***** WMKO API: {len(prog_codes)} PI and Observers *****\n')

#for prog_code in prog_codes:
#    print(f'{prog_code}: {pi[prog_code]}, {observers[prog_code]}')   # wmko everything

#print()

#print(f'Admins ({len(admin)}):')
#for adm in admin:
#    print(f'{adm}: ')   # get full info from IPAC?
#print()
#
#print(f'SAs ({len(sa_obj)}):')
#for k,v in sa_obj.items():
#    print(f'{k}: {v}')
#print()
#
#print(f'PIs ({len(pi)}):')
#for k,v in pi.items():
#    print(f'{k}: {v}')
#print()
#
#print(f'Observers ({len(observers)}):')
#print(f'Observers Object: {observers}')
#for k,v in observers.items():
#    print(f'{k}: {v}')

#print()

# ============

# - For each program, query the NExScI data access API to retrieve all accounts that have access 
#print(f'***** NExScI API: Evaluating {len(prog_codes)} SEMIDs *****')
print(f'Processing {len(prog_codes)} SEMIDs')
print('{semid, access, type, firstname, lastname, email, alias, keckid}')

url = ipac_url
params = {}
params["request"] = "GET_USERS_WITH_ACCESS"

for prog_code in prog_codes:
    print(f'\n{prog_code}')
    params["semid"] = prog_code
    ipac_resp = requests.get(url, params=params, auth=("KOA","Humu3"))   # use config.live.ini
    ipac_resp = ipac_resp.json()

    ipac_users = set()
    for ipac_obj in ipac_resp["response"]["detail"]:
        #print(ipac_obj["userid"], ipac_obj["email"], ipac_obj["keckid"], ipac_obj["first"], ipac_obj["last"])
        #ipac_users.add(ipac_obj["userid"])  # additional check in case email address is changed
        ipac_users.add(ipac_obj["email"].split("@")[0])

    #print(f'   IPAC Users    : {ipac_users}')

    #print(f"   WMKO PI       : {pi[prog_code]}")

    pi_rec    = pi[prog_code].split(",")
    pi_email  = pi_rec[0].strip()
    pi_lname  = pi_rec[1].strip()
    pi_fname  = pi_rec[2].strip()
    pi_alias  = pi_rec[3].strip()
    pi_keckid = pi_rec[4].strip()

    if pi_alias not in ipac_users:
        print(f"{{'{prog_code}', 'required', 'pi', '{pi_fname}', '{pi_lname}', '{pi_email}', '{pi_alias}', {pi_keckid}}}")
    else:
        print(f"{{'{prog_code}', 'ok', 'pi', '{pi_fname}', '{pi_lname}', '{pi_email}', '{pi_alias}', {pi_keckid}}}")

    # need additional admin info from IPAC database
    #print(f"   WMKO Admins   : {admin}")
    for adm in admin:
        if adm not in ipac_users:
            print(f"{{'{prog_code}', 'required', 'admin', None, None, None, '{adm}', None}}")
        else:
            print(f"{{'{prog_code}', 'ok', 'admin', None, None, None, '{adm}', None}}")

    #print(f"   WMKO SAs      : {sa}")
    for a_sa in sa:
        sa_fname  = sa_obj[a_sa]['firstname']
        sa_lname  = sa_obj[a_sa]['lastname']
        sa_addr   = sa_obj[a_sa]['email']
        sa_koaid  = sa_obj[a_sa]['alias']
        sa_keckid = sa_obj[a_sa]['keckid']

        if a_sa not in ipac_users:
            print(f"{{'{prog_code}', 'required', 'sa', '{sa_fname}', '{sa_lname}', '{sa_addr}', '{sa_koaid}', {sa_keckid}}}")
        else:
            print(f"{{'{prog_code}', 'ok', 'sa', '{sa_fname}', '{sa_lname}', '{sa_addr}', '{sa_koaid}', {sa_keckid}}}")

    # need additional observer info from IPAC database
    if vtype == 'PI_OBS':
        #print(f"   WMKO Observers: {observers[prog_code]}")
        for obs in observers[prog_code]:
            if obs not in ipac_users:
                print(f"{{'{prog_code}', 'required', 'observer', None, '{obs}', None, None, None}}")
            else:
                print(f"{{'{prog_code}', 'ok', 'observer', None, '{obs}', None, None, None}}")

print()

# def construct email(s)

# def send email(s)
# - Send an email summary to the KOA helpdesk with information for those programs that need their access updated 
