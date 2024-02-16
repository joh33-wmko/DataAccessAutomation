#! /usr/local/anaconda/bin/python

# ... something got cut off, please restore it ...

# -      Verifies if new observers
# - Check next month
# -      $ python3 ./verify_data_access.py --date 2024-02-01 --numdays 29
# -      Verifies PI, Observers, cps, etc.
# - Send report via email(s)
# -      $ python3 ./verify_data_access.py --date 2024-02-01 --numdays 29 --email jmader@keck.hawaii.edu
# - Run with kpython3 for logger functionality (uncomment "# toggle for logger" lines)

# ToDos:
# - X Remove PI from Observers list
# - X Remove COI from Observers list
# - X KoaAccess - report observers and COIs 
# - X            unique name, use ObsId = keckid, instead of alias or last name
# - X KpfAccess - report cpsadmin user
# - remove koa_access and kpf_access from PI output
# - make defs for "new" assignments
# - make defs for access granted/required 
# - restore logger witout requirement for kpython3

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
             # import pdb; pdb.set_trace() inline
             # breakpoint()   # can activate/deactivate all

# prepare config file
from os.path import dirname
import yaml

dirname = dirname(__file__)
configFile = "config.live.ini"
filename = f'{dirname}/{configFile}'
assert os.path.isfile(filename), f"ERROR: {filename} file missing"
with open(filename) as f: config = yaml.safe_load(f)

# ----- APIs ----- move to def calls
# admin_url = config["API"]["ADMIN_URL"]   # for user info
emp_url   = config['API']['EMP_URL']     # for SAs
sched_url = config['API']['SCHED_URL']   # for SEMIDs
obs_url   = config['API']['OBS_URL']     # for Observers' info
coi_url  = config['API']['COI_URL']      # for for coversheet COIs
koa_url  = config['API']['KOA_URL']      # for for coversheet KoaAccess
kpf_url  = config['API']['KPF_URL']      # for for coversheet KpfAccess
ipac_url  = config['API']['IPAC_URL']    # for IPAC GET_USERS_WITH_ACCESS

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

# pi, only, so far... extend use for other objects - nicety
def generate_output(type, in_obj, ktn, ipac_users_obj):

    out_obj = {}

    if type == 'pi':
        rec    = in_obj[ktn]
        userid = rec['userid']
        fname  = rec['firstname']
        lname  = rec['lastname']
        email  = rec['email']
        keckid = rec['keckid']
    
        new = {}
        new["semid"] = ktn
        new["usertype"] = type
        new["firstname"] = fname
        new["lastname"] = lname
        new["email"] = email
        new["userid"] = userid
        new["keckid"] = keckid
        new["access"] = "granted" if keckid in ipac_keckids[prog_code] or userid in ipac_userids[prog_code] or email in ipac_emails[prog_code] else "required"
        new["koa_access"] = koa_access   # remove after testing
        new["kpf_access"] = kpf_access   # remove after testing
        return new

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
parser.add_argument("--date", type=valid_date, default=dt.today(), help="HST Run Date Format is yyyy-mm-dd", required=False)   # do we need UTC?
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


# ----- create WMKO SA objects from employee API -----
# API request for list of current SAs - will only change for new and departing SAs

emp_params          = {}
emp_params["role"]  = "SA"

wmko_emp_resp = requests.get(emp_url, params=emp_params, verify=False)
if not wmko_emp_resp:
    print('NO DATA RESPONSE')
    message = ''.join((message, 'NO DATA RESPONSE'))
    sys.exit()
else:
    wmko_emp_data = wmko_emp_resp.json()

sa_obj = {}
sa_list = []
for sa_item in wmko_emp_data:

    sa_userid = sa_item["Alias"]
    sa_firstname = sa_item["FirstName"]
    sa_lastname = sa_item["LastName"]
    sa_addr = f'{sa_item["Alias"]}@keck.hawaii.edu'
    sa_list.append(sa_userid)

    sa_info = {}
    sa_info["firstname"] = sa_firstname
    sa_info["lastname"] = sa_lastname
    sa_info["email"] = sa_addr
    sa_info["userid"] = sa_userid
    sa_info["keckid"] = 0 #sa_keckid

    # retrieve and populate SA's keckid
    obs_params = {}
    obs_params["last"]   = sa_lastname
    obs_params["first"]  = sa_firstname
    wmko_obs_resp = requests.get(obs_url, params=obs_params, verify=False)
    wmko_obs_data = wmko_obs_resp.json()

    for obs in wmko_obs_data:
        sa_info["keckid"] = obs["Id"]

    sa_obj[sa_userid] = sa_info

# ----- create PI and Observer objects from schedule API -----
# Call APIs on the startDate and numdays

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
pi_list = {}
obs_list = {}

for entry in wmko_sched_data:
    #print(entry)

    # create prog_codes list
    prog_code = f"{entry['Semester']}_{entry['ProjCode']}"
    prog_codes.add(prog_code)

    # generate PI object per prog_code
    if entry['PiFirstName'] and entry['PiLastName']:
        pi_userid = (entry['PiFirstName'][0] + entry['PiLastName']).lower()   # get from getObserverInfo
    else:
        pi_userid = ''

    pi_list[prog_code] = {}
    pi_list[prog_code]['userid'] = pi_userid
    pi_list[prog_code]['firstname'] = entry['PiFirstName']
    pi_list[prog_code]['lastname'] = entry['PiLastName']
    pi_list[prog_code]['email'] = entry['PiEmail']
    pi_list[prog_code]['keckid'] = entry['PiId']

    # generate Observers per prog_code
    if prog_code not in obs_list.keys() or not entry["Observers"]:
        obs_list[prog_code] = {}           # add new prog_code list
        
    if 'Observers' in entry.keys():
        if entry["Observers"] and entry["ObsId"]:
            #obs_list[prog_code] += entry["Observers"].split(",")   # duplicates obs_list

            obs_list[prog_code]['lastnames'] = []
            obs_list[prog_code]['obs_ids']   = []

            obs_list[prog_code]['lastnames'] = entry["Observers"].split(",")
            obs_list[prog_code]["lastnames"] = set(obs_list[prog_code]["lastnames"])

            obs_list[prog_code]['obs_ids'] = entry["ObsId"].split(",")
            obs_list[prog_code]['obs_ids'] = [int(val) for val in obs_list[prog_code]['obs_ids']]
            obs_list[prog_code]["obs_ids"] = set(obs_list[prog_code]["obs_ids"])

        #else:
            #obs_list[prog_code] = None 
            #obs_list[prog_code] = {} 
    else:
        print(f'MISSING Observers key')
        obs_list[prog_code] = None

print(f'\nGlobal OBS_LIST[PROG_CODE] set: {obs_list}')

prog_codes = list(prog_codes)
prog_codes.sort()

print(f'\nPROG_CODES: {prog_codes}')


# ***** GENERATE OUTPUT *****

output = {}

message = ''.join((message, f'{len(prog_codes)} SEMIDs found \n'))
##daalogger.info('KOA DAA: Processing {len(prog_codes)} SEMIDs found ')   # toggle for logger


admins = ['hireseng', 'koaadmin']
cpsadmin = ['cpsadmin']
all_admins = cpsadmin + admins
#ipac_users = {}
ipac_keckids = {}
ipac_userids = {}
ipac_emails = {}
output = {}

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

    ipac_keckids[prog_code] = []
    ipac_userids[prog_code] = []
    ipac_emails[prog_code] = []
    for ipac_obj in ipac_resp["response"]["detail"]:
        ipac_keckids[prog_code].append(ipac_obj["keckid"])
        ipac_userids[prog_code].append(ipac_obj["userid"])
        ipac_emails[prog_code].append(ipac_obj["email"])


    # ----- WMKO KoaAccess -----
    koa_access          = 0
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
        #koa_access = 1                                    # remove after testing
        koa_pair = f'"KoaAccess": {koa_access}'


    # ----- WMKO KpfAccess [2024B Aug 2024] -----
    kpf_access          = 0
    kpf_params          = {}
    kpf_params["ktn"]   = prog_code
    
    wmko_kpf_resp = requests.get(kpf_url, params=kpf_params, verify=False)
    if not wmko_kpf_resp:
        #print('NO DATA RESPONSE')
        #message = ''.join((message, 'NO DATA RESPONSE'))   # uncomment when kpf access becomes available
        kpf_access = None
        kpf_pair = f'"KpfAccess": None'
        #sys.exit()
    else:
        kpf_access = wmko_kpf_resp.json()['KpfAccess']
        kpf_access = 1                                    # remove after testing
        kpf_pair = f'"KpfAccess": {kpf_access}'
        if kpf_access:
            admins = all_admins


    # ----- 1. WMKO PIs Output -----
    output[prog_code].append(generate_output('pi', pi_list, prog_code, ipac_userids))


    # ----- 2. WMKO COIs and Observers Outputs -----
    # - Observers listed as PI or COI will not appear as Observers, but only as PIs or COIs, instead
    # - all observers and COIs require access if KoaAccess = 1

    if koa_access:

        # ----- 2a. WMKO COIs Output -----
        wmko_coi_data = {}
        coi_firstnames = []
        coi_lastnames = []
        coi_keckids = []

        coi_params          = {}
        coi_params["ktn"]   = prog_code
        
        wmko_coi_resp = requests.get(coi_url, params=coi_params, verify=False)
        if not wmko_coi_resp:
            print('NO DATA RESPONSE')
            message = ''.join((message, 'NO DATA RESPONSE'))
            sys.exit()
        else:
            wmko_coi_data = wmko_coi_resp.json()['data']['COIs']
        
        for coi_item in wmko_coi_data:
            coi_semid  = coi_item['KTN']
            coi_type   = coi_item['Type']
            coi_fname  = coi_item['FirstName']
            coi_lname  = coi_item['LastName']
            coi_email  = coi_item['Email']
            coi_userid  = coi_item['Email'].split('@')[0]
            coi_keckid = coi_item['ObsId']

            # for obs comparisons
            coi_firstnames.append(coi_fname)
            coi_lastnames.append(coi_lname)
            coi_keckids.append(coi_keckid)
        
            new = {}
            new["semid"] = prog_code
            #new["semid"] = coi_semid
            new["usertype"] = coi_type.lower()
            new["firstname"] = coi_fname
            new["lastname"] = coi_lname
            new["email"] = coi_email
            new["userid"] = coi_userid
            new["keckid"] = coi_keckid
            new["access"] = "granted" if coi_keckid in ipac_keckids[prog_code] or coi_userid in ipac_userids[prog_code] or coi_email in ipac_emails[prog_code] else "required"
            new["koa_access"] = koa_access
            output[prog_code].append(new)

        # ----- 2b. WMKO Observers Output -----
        #for obs_lname in obs_list[prog_code]:
        for obs_id in obs_list[prog_code]['obs_ids']:
            obs_params = {}
            obs_params["obsid"]  = obs_id
            wmko_obs_resp = requests.get(obs_url, params=obs_params, verify=False)
            wmko_obs_data = wmko_obs_resp.json()
    
            for item in wmko_obs_data:
                #print(f'item is {item}')

                obs_fname = item["FirstName"]
                obs_lname = item["LastName"]
                obs_email = item["Email"]
                obs_id    = item["Id"]
                obs_userid  = item["username"]

                # removes replicated PI observers
                pi_lname = pi_list[prog_code]["lastname"]
                pi_fname = pi_list[prog_code]["firstname"]
                pi_keckid = pi_list[prog_code]["keckid"]

                if pi_lname == obs_lname and pi_fname == obs_fname and pi_keckid == obs_id:
                    continue 

                # removes replicated COI observers
                if obs_lname in coi_lastnames and obs_fname in coi_firstnames and obs_id in coi_keckids:
                    continue

                new = {}
                new["semid"] = prog_code
                new["usertype"] = "observer"
                new["firstname"] = obs_fname
                new["lastname"] = obs_lname
                new["email"] = obs_email
                new["userid"] = obs_userid
                new["keckid"] = obs_id
                new["access"] = "granted" if obs_id in ipac_keckids[prog_code] or obs_userid in ipac_userids[prog_code] or obs_email in ipac_emails[prog_code] else "required"
                new["koa_access"] = koa_access
                output[prog_code].append(new)

    # ----- 3. WMKO SAs Output -----
    for sa in sa_list:
        #print(sa)
        sa_fname  = sa_obj[sa]['firstname']
        sa_lname  = sa_obj[sa]['lastname']
        sa_email   = sa_obj[sa]['email']
        sa_userid  = sa_obj[sa]['userid']
        sa_keckid = sa_obj[sa]['keckid']

        new = {}
        new["semid"] = prog_code
        new["usertype"] = "sa"
        new["firstname"] = sa_fname
        new["lastname"] = sa_lname
        new["email"] = sa_email
        new["userid"] = sa_userid
        new["keckid"] = sa_keckid
        new["access"] = "granted" if sa_keckid in ipac_keckids[prog_code] or sa_userid in ipac_userids[prog_code] or sa_email in ipac_emails[prog_code] else "required"
        output[prog_code].append(new)

    # ----- 4. WMKO Admins Output -----
    for adm in admins:
        new = {}
        new["semid"] = prog_code
        new["usertype"] = "admin"
        new["firstname"] = ""
        new["lastname"] = ""
        new["email"] = ""
        new["userid"] = adm
        new["keckid"] = 0
        new["access"] = "granted" if adm in ipac_userids[prog_code] else "required"
        new["kpf_access"] = kpf_access
        output[prog_code].append(new)

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

