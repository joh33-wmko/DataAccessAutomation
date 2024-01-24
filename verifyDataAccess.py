#! /usr/local/anaconda/bin/pyton

# KOA Data Access Automation (DAA)
# - run via cron on desired date for next month (default)
# - run via command line with date $ python3 ./verifyDataAccess.py --date yyyy-m[m]
#   ex.  $ python3 ./verifyDataAccess.py --date 2024-3 will run for Mar 2024
# - TBD - runs daily via cron
# - run with kpython3 for logger functionality (uncomment "# toggle for logger" lines)

# Verification Types (vtype) to be processed
# - PI                : PI Verification
# - PI_OBS            : PI & Observer Verification
# - COI_OBS           : COI/Observer Verification
# - TDA (ToO or TWI)  : ToO/Twilight Program Verification
# - KPF               : KPF Program Verification (SEM 2024B Aug 1, 2024)

# ToDo's
# - logger messages without kpython3
# - readable vs minified version
# - email send output, and to koaadmin at IPAC: ______
# - replace "set()" with None for output objects (ipac_users, etc.)
# - clean up imports (PEP8)
# - defs for request params and object displays?
# - case treatment of vtypes
# - [DONE] args PI vs PI_OBS
# - [DONE] fix too many values for Observers output
# - [DONE] output {} in f-string expressions
# - [DONE] sort SEMIDs for report
# - [DONE] transfer API urls and account info to config.live.ini
# - [DONE] logger messages with kpython3
# - [DONE] arg to override default (next month) with this month (or any month?) for PI
#   - [DONE] 'jan' or '01' or '1'
#   - [DONE] calculate for next month is Jan, next year
# - [DONE] format output as one single large object
# - [DONE] results for observers now includes email addresses
# - [INFO] keck alias/ipac username is first initial + last name
# - [INFO] ipac calls keck id koaid

# daa imports
import argparse
import calendar as cal
from datetime import datetime as dt, timedelta
from dateutil.relativedelta import relativedelta

import json
import requests
import sys
import urllib3
urllib3.disable_warnings()

# logger imports - need kpython3 on command line (see Jeff's fix)
#from LoggerClient import Logger as dl   # toggle for logger
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

#daalogger = create_logger('Data Access Automation', None, 'JPH', None, None, None, 'koa')   # toggle for logger
#daalogger.info('Running KOA Data Access Automation')   # toggle for logger

# prepare config file
from os.path import dirname
import yaml

dirname = dirname(__file__)
configFile = "config.live.ini"
filename = f'{dirname}/{configFile}'
assert os.path.isfile(filename), f"ERROR: {filename} file missing"
with open(filename) as f: config = yaml.safe_load(f)

print(f'\nKOA DATA ACCESS AUTOMATION (DAA) REPORT')

# parse command line arguments
parser = argparse.ArgumentParser(description="Verify Data Access")
parser.add_argument("vtype")
parser.add_argument("--date", help="Run Date Format is YYYY-MM", required=False)
args = parser.parse_args()

vtype = args.vtype
if vtype.upper() == 'PI':
    vtype = 'PI'
    print(f'\nProcessing PI Verification for')
    #daalogger.info('Running PI Verification Report')   # toggle for logger
if vtype.upper() == 'PI_OBS':
    vtype = 'PI_OBS'
    print(f'\nProcessing PI & Observer Verification for')
    #daalogger.info('Running PI_OBS Verification Report')   # toggle for logger
#if vtype.upper() == 'COI_OBS':
#    vtype = 'COI_OBS'
#    daalogger.info('Running COI_OBS Verification Report')   # toggle for logger
#    print(f'\nProcessing COI & Observer Verification for')
#if vtype.upper() == 'TDA':   # ToO or TWI
#    vtype = 'TDA'
#    print(f'\nProcessing TDA (ToO or Twilight) Verification for')
#    daalogger.info('Running TDA (ToO/TWI) Verification Report')   # toggle for logger
#if vtype.upper() == 'KPF':
#    vtype = 'KPF'
#    print(f'\nProcessing KPF Verification for')
#    daalogger.info('Running KPF Verification Report')   # toggle for logger


if not args.date:
    next_month = dt.today() + relativedelta(day=1, months=1)
    run_year = next_month.year
    run_month = next_month.month
    num_days = cal.monthrange(run_year, run_month)[1]
    startDate = f'{run_year}-{run_month}-1'
    startDate = dt.strptime(startDate, '%Y-%m-%d')
    endDate = startDate + timedelta(days=num_days-1)
    startDate = dt.strftime(startDate, '%Y-%m-%d')
    endDate   = dt.strftime(endDate, '%Y-%m-%d')
else:
    run_date = args.date.split('-')
    run_year = int(run_date[0])
    run_month = int(run_date[1])
    run_day = 1
    num_days = cal.monthrange(run_year, run_month)[1]
    startDate = f'{run_year}-{run_month}-{run_day}'
    startDate = dt.strptime(startDate, '%Y-%m-%d')
    endDate = startDate + timedelta(days=num_days-1)
    startDate = dt.strftime(startDate, '%Y-%m-%d')
    endDate = dt.strftime(endDate, '%Y-%m=%d')

print(f'{startDate} to {endDate} ({num_days} days)\n')
#daalogger.info('Running KOA DAA for {startDate} to {endDate} ({num_days} days')   # toggle logger

# initializations
pi         = {}                              # required; always one per prog_code
#pi_info    = {}
sa         = set()                           # required current SAs
sa_info    = {}
admin      = ['koaadmin', 'hireseng']        # required admins
admin_info = {}
observers  = {}
#observer_info = {}
#test       = ['rtiguitest1', 'rtiuser02']   # optional test
#other      = ['jomeara', 'rcampbell']       # optional other
#ignore     = test + other                   # optional all = test + other
prog_codes = set()

# ----- create data objects -----

# API request for list of current SAs - will only change for new and departing SAs

url = config['API']['EMP_URL']
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

# ----- generate PI and OBS objects from schedule API -----

url = config['API']['SCHED_URL']
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

# ----- objects viewer -----

# ============
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

# ----- generate report -----

# for each program, query the NExScI data access API to retrieve all accounts that have access 
#print(f'***** NExScI API: Evaluating {len(prog_codes)} SEMIDs *****')

print(f'Processing {len(prog_codes)} SEMIDs')
#daalogger.info('KOA DAA: Processing {len(prog_codes)} SEMIDs')   # toggle for logger

print('{semid, access, type, firstname, lastname, email, alias, keckid}')   # legend for recipient

# API request for list of current Observers
#obs_url = config['API']['SCHED_URL']
obs_url = config['API']['OBS_URL']
obs_params = {}
obs_params["cmd"]       = "getObserverInfo"

ipac_url = config['API']['IPAC_URL']
ipac_params = {}
ipac_params["request"] = "GET_USERS_WITH_ACCESS"

print('\n{')
for prog_code in prog_codes:
    print(f'    \'{prog_code}\': {{')
    ##daalogger.info('KOA DAA: Processing ', ..., {semid}, {progid})   # split semid and progid and report to logger; toggle for logger
    #daalogger.info('KOA DAA: Processing {prog_code}')   # split semid and progid and report to logger

    ipac_params["semid"] = prog_code
    ipac_resp = requests.get(ipac_url, params=ipac_params, auth=(config['ipac']['user'],config['ipac']['pwd']))
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
        print(f"        {{'{prog_code}', 'required', 'pi', '{pi_fname}', '{pi_lname}', '{pi_email}', '{pi_alias}', {pi_keckid}}},")
    else:
        print(f"        {{'{prog_code}', 'ok', 'pi', '{pi_fname}', '{pi_lname}', '{pi_email}', '{pi_alias}', {pi_keckid}}},")

    # need additional admin info from IPAC database
    #print(f"   WMKO Admins   : {admin}")
    for adm in admin:
        if adm not in ipac_users:
            print(f"        {{'{prog_code}', 'required', 'admin', None, None, None, '{adm}', None}},")
        else:
            print(f"        {{'{prog_code}', 'ok', 'admin', None, None, None, '{adm}', None}},")

    #print(f"   WMKO SAs      : {sa}")
    for a_sa in sa:
        sa_fname  = sa_obj[a_sa]['firstname']
        sa_lname  = sa_obj[a_sa]['lastname']
        sa_addr   = sa_obj[a_sa]['email']
        sa_koaid  = sa_obj[a_sa]['alias']
        sa_keckid = sa_obj[a_sa]['keckid']

        if a_sa not in ipac_users:
            print(f"        {{'{prog_code}', 'required', 'sa', '{sa_fname}', '{sa_lname}', '{sa_addr}', '{sa_koaid}', {sa_keckid}}},")
        else:
            print(f"        {{'{prog_code}', 'ok', 'sa', '{sa_fname}', '{sa_lname}', '{sa_addr}', '{sa_koaid}', {sa_keckid}}},")

    # need additional observer info from IPAC database
    if vtype == 'PI_OBS':
        #print(f"   WMKO Observers: {observers[prog_code]}")

        for obs_lname in observers[prog_code]:
            obs_params["last"]  = obs_lname
            wmko_obs_resp = requests.get(obs_url, params=obs_params, verify=False)
            wmko_obs_resp = wmko_obs_resp.json()
            for item in wmko_obs_resp:
                #print(f'item is {item}')
                obs_lname = item["LastName"]
                obs_fname = item["FirstName"]
                obs_email = item["Email"]
                obs_id    = item["Id"]
                obs_user  = item["username"]

            if obs_user not in ipac_users:
                print(f"        {{'{prog_code}', 'required', 'observer', '{obs_fname}', '{obs_lname}', '{obs_email}', '{obs_user}', '{obs_id}'}},")
            else:
                print(f"        {{'{prog_code}', 'ok', 'observer', '{obs_fname}', '{obs_lname}', '{obs_email}', '{obs_user}', '{obs_id}'}},")
    print('    },')

print('}')
print()

# def construct email(s)

# def send email(s)
# - Send an email summary to the KOA helpdesk with information for those programs that need their access updated 


#daalogger.info('KOA Data Access Automation Finished')   # toggle for logger
