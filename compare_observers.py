#! /usr/local/anaconda/bin/python
# /usr/local/anaconda3-5.0.0.1/bin/python3

# run as koarti@vm-koartibuild

# examines wmko observers vs KOA accounts
# send results to IPAC

import os
import argparse
import requests
import urllib3
urllib3.disable_warnings()
import json
from datetime import datetime as dt, timedelta
#import pdb


def print_line(json_str):
    # deserialze string to list of dicts
    json_list = json.loads(json_str)
    num_usrs = len(json_list)

    count = 0
    if len(json_list) > 0:
        print('[')
    for line in json_list:
        count += 1
        print(f'  {line}', end='')
        if count != num_usrs:
            print(',')
        else:
            print()
    if len(json_list) > 0:
        print(']')


def print_results(acct_list, desc):
    acct_list_json = json.dumps(acct_list, indent=2)
    print(f'\n{desc} ({len(acct_list)} user(s))')
    print_line(acct_list_json)


# parse command line arguments
parser = argparse.ArgumentParser(description="Observer Acccounts")
parser.add_argument("sdate", type=str, default=dt.today(), help="HST Run Date Format is yyyy-mm-dd")
parser.add_argument("edate", type=str, default=dt.today(), help="HST Run Date Format is yyyy-mm-dd")
args = parser.parse_args()

date_format = '%Y-%m-%d'
startDate = args.sdate
endDate   = args.edate

# date objects
start_date = dt.strptime(startDate, date_format)
end_date   = dt.strptime(endDate, date_format)
numDays = (end_date - start_date + timedelta(days=1)).days
print(f'\nDate Range is {start_date.date()} to {end_date.date()} [{numDays} day(s)]')

# config file modules
from os.path import dirname
import yaml

dirname = dirname(__file__)
configFile = "config.live.ini"
filename = f'{dirname}/{configFile}'
assert os.path.isfile(filename), f"ERROR: {filename} file missing"
with open(filename) as f: config = yaml.safe_load(f)

# generate list of observers per specified date range

# WMKO ADMIN API (for observer list from schedule API)
# use the schedule API to get a list of all observers between a date range
# https://vm-appserver.keck.hawaii.edu/api/schedule/getUserInfo?startdate=2024-08-27&enddate=2025-02-01
obs_url = config["API"]["ADMIN_URL"]   # for observer info
obs_params = {}
obs_params["startdate"]   = startDate
obs_params["enddate"]     = endDate

obs_info_resp = requests.get(obs_url, params=obs_params, verify=False)
if not obs_info_resp:
    print('NO DATA RESPONSE')
    message = ''.join((message, 'NO DATA RESPONSE'))
    sys.exit()
else:
    obs_info_data = obs_info_resp.json()

print(f'{len(obs_info_data)} total observer accounts found at WMKO for this date range\n')


# IPAC USER_ACCESS API - get IPAC user info per observer info
# https://vm-appserver.keck.hawaii.edu/api/koa/checkUserAccess?user=ghez@astro.ucla.edu
usracc_url = config["API"]["USRACC_URL"]   # for user info
usracc_params = {}

#print(f'\n[USRACC_URL] USER INFO FROM IPAC User Access API Response:')

ipac_dne_accts       = []   # ipac accounts that do not exist (status=UNSUCCESSFUL)
wmko_ignore_accts    = []   # wmko accounts that exist (status=SUCCESSFUL) but should be ignored
ipac_noaccess_accts  = []   # ipac accounts that exist (status=SUCCESSFUL) - no program access
ipac_needs_attns     = []   # ipac accounts that exist (status=SUCCESSFUL) but should be examined
ipac_invalid_keckids = []   # ipac accounts that exist but keckid requires correction
ipac_valid_accts     = []   # ipac accounts that exist (status=SUCCESSFUL)

for obs in obs_info_data:
    status = ''
    user = obs["Email"]
    usracc_params["user"] = user
    usr_info_resp = requests.get(usracc_url, params=usracc_params, verify=False)
    if not usr_info_resp:
        print('NO DATA RESPONSE')
        message = ''.join((message, 'NO DATA RESPONSE'))
        continue
    else:
        usr_info_data = usr_info_resp.json()
        status = usr_info_data["status"]

    # account object keys mapped to IPAC format
    acct_info = { "email": "",
                  "keckid": "",
                  "userid": "",
                  "first": "",
                  "last": ""
                }

    acct_info["email"]   = obs["Email"]
    acct_info["keckid"]  = obs["Id"]
    #acct_info["userid"] = ''
    acct_info["first"]   = obs["FirstName"]
    acct_info["last"]    = obs["LastName"]

    # IPAC account missing or DNE
    if status == 'UNSUCCESSFUL':
        ipac_dne_accts.append(acct_info)
        continue

    # status = SUCCESS, but requires consideration

    # problematic accounts
    if isinstance(usr_info_data["access"], str):
        print(f'\nIPAC Account Needs Attention: {usr_info_data["access"]}')
        ipac_needs_attns.append(acct_info)
        continue

    # ignore segment exchange and engineering accounts
    ignores = [ 'keck@hawaii.edu']
    if obs["Email"] in ignores:
        wmko_ignore_accts.append(acct_info)
        continue

    try: 
        one_ipac_keckid = usr_info_data["access"][0]["keckid"]
    except IndexError:
        print(f'\nIndexError list index out of range:')
        print(f'usr_info_data: {usr_info_data}')
    except TypeError:
        print(f'\nTypeError not a list, string indices must be integers:', end="")
        print(type(usr_info_data["access"]))
        print(f'usr_info_data: {usr_info_data}')

    # user not assigned program/semid
    if len(usr_info_data["access"]) == 0:
        ipac_noaccess_accts.append(acct_info)
        continue

    # invalid keckid null or mismatch - send only these to IPAC
    if obs["Id"] != one_ipac_keckid:
        acct_info["userid"] = usr_info_data["access"][0]["userid"]
        ipac_invalid_keckids.append(acct_info)
        continue

    # successful accounts, do not send to IPAC
    ipac_valid_acct = usr_info_data["access"][0]
    ipac_valid_accts.append(ipac_valid_acct)


print_results(ipac_valid_accts, 'IPAC Valid User Accounts')
print_results(ipac_dne_accts, 'IPAC Accounts Do Not Exist')
print_results(ipac_invalid_keckids, 'IPAC Invalid KECKIDs')
print_results(ipac_noaccess_accts, 'IPAC Accounts Have No Program Access Yet')
print_results(wmko_ignore_accts, 'IPAC Ignore Accounts')
print_results(ipac_needs_attns, 'IPAC Account Needs Attention')
print()
