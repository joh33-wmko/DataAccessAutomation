#! /usr/local/anaconda/bin/python

# WMKO KOA Data Access Automation (DAA)
# - Note: References to IPAC implies NExScI

# - Usage on vm-koartibuild:
# - Defaults (date=today and numofdays=1)
# -     $ python3 ./verify_data_access.py
# - Send report via email(s) with --email option
# -     $ python3 ./verify_data_access.py --email user0@keck.hawaii.edu[, user1@keck.hawaii.edu]
# - Check a specific date (num of days = 1)
# -     $ python3 ./verify_data_access.py --date 2024-02-01
# - Check a specific date and date range
# -     $ python3 ./verify_data_access.py --date 2024-14-01 --numdays 7
# - Check future (ex. if today is Jan 2024, next month is leap year month)
# -     $ python3 ./verify_data_access.py --date 2024-02-01 --numdays 29
# - Output options for testing
# -     $ python3 ./verify_data_access.py ... --force pi|coi|obs|koa|kpf|both koa and kpf (default is none)
#                                                     pi: pi only, 
#                                                     coi: pi and coi, 
#                                                     obs: pi, coi, and obs (supress SAs and admins)
#                                                     koa: koa_access = 1, kpf: kpf_access = a, 
#                                                     both: koa_access = 1 and kpf_access = 1
# - TBD Invoke with kpython3 for logger functionality (uncomment "# toggle for logger" lines)
# -     $ kpython3 ./verify_data_access.py --date 2024-02-01 --numdays 29 --email user@keck.hawaii.edu

# ToDos:
# - sa_obj must be changed from list of dicts keyed on lastname to dict of dicts keyed on semid
# - provide JSON obj as input to PROCESS_GRANTS API (formerly PROCESS_PROGRAMS)
#   - test when APIs fixed and available
# - F2F: IPAC API call to GET_USERS_WITH_ACCESS
#   - recode for use of full name as third option and userid (matches admins) as fourth
#   - test when APIs fixed and available
# x- F2F: Test: run for Mar 2024 and compare to Jeff's list in KOA slack (can do this on Ops?)
# x- F2F: Test: run for Apr 2024 and and verify
# x- finish implementing 
#   x- cmd line email
#   x- force pi only 
#   x- supress admin and sa
# - refactor and clean up
#   - make defs for "new" assignments
#   - move to main
# - restore logger without requirement for kpython3
# - additional:
#   - wmko keckid vs ipac koaid string mismatch report (???)

# daa modules
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
from pprint import pprint as pp
import pdb

# config file modules
from os.path import dirname
import yaml

dirname = dirname(__file__)
configFile = "config.live.ini"
filename = f'{dirname}/{configFile}'
assert os.path.isfile(filename), f"ERROR: {filename} file missing"
with open(filename) as f: config = yaml.safe_load(f)

# ===== APIs =====
# admin_url = config["API"]["ADMIN_URL"]   # for user info
emp_url   = config['API']['EMP_URL']      # for SAs
sched_url = config['API']['SCHED_URL']    # for SEMIDs
obs_url   = config['API']['OBS_URL']      # for Observers' info
coi_url   = config['API']['COI_URL']      # for for coversheet COIs
koa_url   = config['API']['KOA_URL']      # for for coversheet KoaAccess
kpf_url   = config['API']['KPF_URL']      # for for coversheet KpfAccess
ipac_url  = config['API']['IPAC_URL']     # for IPAC GET_USERS_WITH_ACCESS, PROCESS_PROGRAMS --> PROCESS_GRANTS

EMAIL_WMKO  = config["REPORT"]["WMKO_EMAIL"]
EMAIL_ADMIN = config["REPORT"]["ADMIN_EMAIL"]
EMAIL_IPAC  = config["REPORT"]["IPAC_EMAIL"]
#EMAIL_LIST = ','.join(EMAIL_WMKO, EMAIL_IPAC)

date_format = '%Y-%m-%d'
email = ''
error = ''
message = ''
message = ''.join((message, '\nKOA DATA ACCESS AUTOMATION (DAA) REPORT\n'))


def valid_date(date_str: str) -> dt:
    try:
        return dt.strptime(date_str, date_format)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a valid date: {date_str!r}")


# need ipac_fullnames object
# test order: keckid, email, full name, userid (needed for admins)

def get_access(prog_code_n, keckid_n, userid_n, email_n, ipac_keckids_n, ipac_userids_n, ipac_emails_n):
#def get_access(prog_code_n, keckid_n, keck_email_n, keck_fname, keck_lname, keck_userid_n, ipac_keckids_n, ipac_emails_n, ipac_fullnames_n, ipac_userids_n):
    access = ""
    #keck_fullname_n = f'{keck_fname} {keck_lname}'
    access = "granted" if keckid_n in ipac_keckids_n[prog_code_n] or \
                          email_n in ipac_emails_n[prog_code_n] or \
                          userid_n in ipac_userids_n[prog_code_n] \
                       else "required"
    #keck_fullname_n in ipac_fullnames_n[prog_code_n] or \
    return access


# only PI, so far... extend use for other objects - nicety
def generate_output(user_type, in_obj, ktn, ipac_keckids_lst, ipac_userids_lst, ipac_emails_lst):
#def generate_output(user_type, in_obj, ktn, ipac_keckids_lst, ipac_emails_lst, ipac_fullnames_lst, ipac_userids_lst):

    # special cases:
    #if user_type == 'pi':
    #if user_type == 'coi:
    #if user_type == 'obs':

    if user_type == 'sa':
        rec = in_obj
        #print(rec)
        sa_keckid = rec['keckid']
        sa_email  = rec['email']
        sa_fname  = rec['firstname']
        sa_lname  = rec['lastname']
        sa_userid = rec['userid']

        new = {}
        new["semid"] = ktn
        new["usertype"] = user_type
        new["keckid"] = sa_keckid
        new["email"] = sa_email
        new["firstname"] = sa_fname
        new["lastname"] = sa_lname
        new["userid"] = sa_userid
        new["access"] = get_access(ktn, sa_keckid, sa_userid, sa_email, ipac_keckids_lst, ipac_emails_lst, ipac_userids_lst)
        #new["access"] = get_access(prog_code, sa_keckid, sa_email, sa_fname, sa_lname, sa_userid, ipac_keckids_lst, ipac_emails_lst, ipac_fullnames_lst, ipac_userids_lst)
        #output[prog_code].append(new)
        #new_list[ktn].append(new)
        return new

    #if user_type == 'adm':

    #pdb.set_trace()

    rec    = in_obj[ktn]
    keckid = rec['keckid']
    email  = rec['email']
    fname  = rec['firstname']
    lname  = rec['lastname']
    userid = rec['userid']

    new = {}
    new["semid"] = ktn
    new["usertype"] = user_type
    new["keckid"] = keckid
    new["email"] = email
    new["firstname"] = fname
    new["lastname"] = lname
    new["userid"] = userid
    new["access"] = get_access(ktn, keckid, userid, email, ipac_keckids_lst, ipac_userids_lst, ipac_emails_lst)
    #new["access"] = get_access(ktn, keckid, email, fname, lname, userid, ipac_keckids_lst, ipac_emails_lst, ipace_fullnames_lst, ipac_userids_lst)
    
    if user_type == 'pi':
        new["koa_access"] = koa_access   # remove after testing
        new["kpf_access"] = kpf_access   # remove after testing

    return new


def send_email(email, message, error):
    errorMsg = 'ERROR: ' if error == 1 else ''
    msg = MIMEText(message)
    msg['Subject'] = f"{errorMsg} KOA Data Access Verification ({socket.gethostname()})"
    msg['To'] = email
    msg['From'] = EMAIL_ADMIN
    s = smtplib.SMTP('localhost')
    s.send_message(msg)
    s.quit()


#def main(argv):

# parse command line arguments
parser = argparse.ArgumentParser(description="Verify Data Access")
parser.add_argument("--date", type=valid_date, default=dt.today(), help="HST Run Date Format is yyyy-mm-dd", required=False)   # do we need UTC?
parser.add_argument("--numdays", type=int, default=1, help="Integer from 1 to 180", required=False)
#parser.add_argument("--email", default=False, action="store_true", help="Email addresses via config", required=False)
parser.add_argument("--email", type=str, default='none', help="Enter emails separated by commmas", required=False)
parser.add_argument("--force", type=str, default='none', help="pi = PI only, coi = pi and coi, obs = pi, coi, and obs, supress SAs and admins, koa = koa_access (show COIs and Observers), kpf = kpf_access (cpsadmin), both = koa_access and kpf_access", required=False)
args = parser.parse_args()

startDate = args.date
email = args.email
force = args.force
numdays = args.numdays

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
#sa_obj = []
#sa_list = []
for sa_item in wmko_emp_data:

    sa_addr = f'{sa_item["Alias"]}@keck.hawaii.edu'
    sa_firstname = sa_item["FirstName"]
    sa_lastname = sa_item["LastName"]
    sa_userid = sa_item["Alias"]
    #sa_list.append(sa_userid)

    sa_info = {}
    sa_info["keckid"] = 0         # n/a
    sa_info["email"] = sa_addr
    sa_info["firstname"] = sa_firstname
    sa_info["lastname"] = sa_lastname
    sa_info["userid"] = sa_userid

    # retrieve and populate SA's keckid
    obs_params = {}
    obs_params["first"]  = sa_firstname
    obs_params["last"]   = sa_lastname
    wmko_obs_resp = requests.get(obs_url, params=obs_params, verify=False)
    wmko_obs_data = wmko_obs_resp.json()

    sa_info["keckid"] = wmko_obs_data[0]["Id"]
    #sa_obj[sa_userid] = sa_info
    sa_obj[sa_userid] = sa_info
    #sa_obj.append(sa_info)
    #sa_obj.add(sa_info)

#print(f'*** SA_OBJ: {sa_obj} ***')
#for sobj in sa_obj:
    #print(f'*** SA_OBJ: {sobj} ***')

# ----- create PI and Observer objects from schedule API -----
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
    pi_list[prog_code]['keckid'] = entry['PiId']
    pi_list[prog_code]['email'] = entry['PiEmail']
    pi_list[prog_code]['firstname'] = entry['PiFirstName']
    pi_list[prog_code]['lastname'] = entry['PiLastName']
    pi_list[prog_code]['userid'] = pi_userid

    # generate Observers per prog_code
    if prog_code not in obs_list.keys():
        obs_list[prog_code] = {}           # add new prog_code list
        obs_list[prog_code]['lastnames'] = []
        obs_list[prog_code]['obs_ids']   = []
        
    if ('Observers' in entry.keys() and 'ObsId' in entry.keys()) and \
       (entry["Observers"] != 'none' and entry["ObsId"] != ''):

        obs_list[prog_code]['lastnames'] += entry["Observers"].split(",")
        obs_list[prog_code]["lastnames"] = list(dict.fromkeys(obs_list[prog_code]["lastnames"]))

        obs_list[prog_code]['obs_ids'] += entry["ObsId"].split(",")
        obs_list[prog_code]['obs_ids'] = [int(val) for val in obs_list[prog_code]['obs_ids']]
        obs_list[prog_code]["obs_ids"] = list(dict.fromkeys(obs_list[prog_code]["obs_ids"]))

#   else:
#       print(f'{prog_code} MISSING keys or values for Observers or ObsId')

prog_codes = list(prog_codes)
prog_codes.sort()

#print(f'\nPROG_CODES: {prog_codes}')
#print(f'\nGlobal OBS_LIST[PROG_CODE]:\n {obs_list}')


# ***** GENERATE OUTPUT *****

output = {}

message = ''.join((message, f'{len(prog_codes)} SEMIDs found \n'))
#daalogger.info('KOA DAA: Processing {len(prog_codes)} SEMIDs found ')   # toggle for logger

admins = ['hireseng', 'koaadmin']
cpsadmin = ['cpsadmin']
all_admins = cpsadmin + admins

#ipac_users = {}
ipac_keckids = {}
ipac_emails = {}
#ipac_fullnames = {}
ipac_userids = {}

for prog_code in prog_codes:
#    print(prog_code)
    output[prog_code] = []
    #daalogger.info('KOA DAA: Processing {prog_code}')   # split semid and progid and report for logger

    # ----- IPAC User Access List -----
    ipac_params = {}
    ipac_params["request"] = "GET_USERS_WITH_ACCESS"
    ipac_params["semid"] = prog_code
    #ipac_resp = requests.get(ipac_url, params=ipac_params, auth=(config['ipac1']['user'],config['ipac1']['pwd']))
    ipac_resp = requests.get(ipac_url, params=ipac_params, auth=(config['ipac1']['user'],config['ipac1']['pwd']), verify=False)
    ipac_resp = ipac_resp.json()

    ipac_keckids[prog_code] = []
    ipac_emails[prog_code] = []
    #ipac_fullnames[prog_code] = []
    ipac_userids[prog_code] = []
    for ipac_obj in ipac_resp["response"]["detail"]:
        #print(f'*** IPAC_OBJ: {ipac_obj} ***')
        ipac_keckids[prog_code].append(ipac_obj["keckid"])
        ipac_emails[prog_code].append(ipac_obj["email"])
        #ipac_fullnames[prog_code].append(ipac_obj["firstname"] + " " + ipac_obj["lastname"])
        ipac_userids[prog_code].append(ipac_obj["userid"])

    #pdb.set_trace()

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
        # force state for obs and coi
        if force in ('koa', 'both'):
            koa_access = 1
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
        # force state for cpsadmin
        if force in ('kpf', 'both'):
            kpf_access = 1
        kpf_pair = f'"KpfAccess": {kpf_access}'
        if kpf_access:
            admins = all_admins


    # ----- 1. WMKO PIs Output -----
    output[prog_code].append(generate_output('pi', pi_list, prog_code, ipac_keckids, ipac_userids, ipac_emails))
    #output[prog_code].append(generate_output('pi', pi_list, prog_code, ipac_keckids, ipac_emails, ipac_fullnames, ipac_userids))
    if force == 'pi':
        continue


    # ----- 2. WMKO COIs and Observers Outputs -----
    # - Observers listed as PI or COI will not appear as Observers, but only as PIs or COIs, instead
    # - all observers and COIs require access if KoaAccess = 1

    if koa_access:

        # for removal of replicated PI observers
        pi_keckid = pi_list[prog_code]["keckid"]
        pi_lname = pi_list[prog_code]["lastname"]
        pi_fname = pi_list[prog_code]["firstname"]
        pi_userid = pi_list[prog_code]["userid"]
    
        # ----- 2a. WMKO COIs Output -----
        wmko_coi_data = {}
        coi_keckids = []
        coi_firstnames = []
        coi_lastnames = []
        coi_userids = []

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
            coi_type   = coi_item['Type']
            coi_semid  = coi_item['KTN']
            coi_keckid = coi_item['ObsId']
            coi_email  = coi_item['Email']
            coi_fname  = coi_item['FirstName']
            coi_lname  = coi_item['LastName']
            coi_userid  = coi_item['Email'].split('@')[0]

            # for obs comparisons
            coi_keckids.append(coi_keckid)
            coi_firstnames.append(coi_fname)
            coi_lastnames.append(coi_lname)
            coi_userids.append(coi_userid)
        
            # removes coi if pi is also coi
            if pi_keckid == coi_keckid or (pi_lname == coi_lname and pi_fname == coi_fname) or pi_userid == coi_userid:
                continue 
    
            new = {}
            new["semid"] = prog_code
            #new["semid"] = coi_semid
            new["usertype"] = coi_type.lower()
            new["keckid"] = coi_keckid
            new["email"] = coi_email
            new["firstname"] = coi_fname
            new["lastname"] = coi_lname
            new["userid"] = coi_userid
            new["access"] = get_access(coi_semid, coi_keckid, coi_userid, coi_email, ipac_keckids, ipac_userids, ipac_emails)
            #new["access"] = get_access(coi_semid, coi_keckid, coi_email, coi_fname, coi_lname, coi_userid, ipac_keckids, ipac_emails, ipac_fullnames, ipac_userids)
            new["koa_access"] = koa_access
            output[prog_code].append(new)

        if force == 'coi':
            continue


        # ----- 2b. WMKO Observers Output -----
        if 'obs_ids' in obs_list[prog_code].keys() and obs_list[prog_code]["obs_ids"] != "":
            for obs_id in obs_list[prog_code]['obs_ids']:
                obs_params = {}
                obs_params["obsid"]  = obs_id
                wmko_obs_resp = requests.get(obs_url, params=obs_params, verify=False)
                wmko_obs_data = wmko_obs_resp.json()
        
                for item in wmko_obs_data:
                    #print(f'item is {item}')
    
                    obs_id    = item["Id"]
                    obs_email = item["Email"]
                    obs_fname = item["FirstName"]
                    obs_lname = item["LastName"]
                    obs_userid  = item["username"]
    
                    # removes replicated PI observers
                    #if pi_lname == obs_lname and pi_fname == obs_fname and pi_keckid == obs_id:
                    if pi_keckid == obs_id or (pi_lname == obs_lname and pi_fname == obs_fname) or pi_userid == obs_userid:
                        continue 
    
                    # removes replicated COI observers
                    #if obs_lname in coi_lastnames and obs_fname in coi_firstnames and obs_id in coi_keckids:
                    if obs_id in coi_keckids or (obs_lname in coi_lastnames and obs_fname in coi_firstnames) or obs_userid in coi_userids:
                        continue
    
                    new = {}
                    new["semid"] = prog_code
                    new["usertype"] = "observer"
                    new["keckid"] = obs_id
                    new["email"] = obs_email
                    new["firstname"] = obs_fname
                    new["lastname"] = obs_lname
                    new["userid"] = obs_userid
                    new["access"] = get_access(prog_code, obs_id, obs_userid, obs_email, ipac_keckids, ipac_userids, ipac_emails)
                    #new["access"] = get_access(prog_code, obs_id, obs_email, obs_fname, obs_lname, obs_userid, ipac_keckids, ipac_emails, ipac_fullnames, ipac_userids)
                    new["koa_access"] = koa_access
                    output[prog_code].append(new)


    if force not in ('pi', 'coi', 'obs'):

        # ----- 3. WMKO SAs Output -----
#        for sa in sa_obj:
#            #print(sa)
#            sa_keckid = sa['keckid']
#            sa_email   = sa['email']
#            sa_fname  = sa['firstname']
#            sa_lname  = sa['lastname']
#            sa_userid  = sa['userid']
#    
#            new = {}
#            new["semid"] = prog_code
#            new["usertype"] = "sa"
#            new["keckid"] = sa_keckid
#            new["email"] = sa_email
#            new["firstname"] = sa_fname
#            new["lastname"] = sa_lname
#            new["userid"] = sa_userid
#            new["access"] = get_access(prog_code, sa_keckid, sa_userid, sa_email, ipac_keckids, ipac_userids, ipac_emails)
#            #new["access"] = get_access(prog_code, sa_keckid, sa_email, sa_fname, sa_lname, sa_userid, ipac_keckids, ipac_emails, ipac_fullnames, ipac_userids)
#            output[prog_code].append(new)
    
        # loop or no loop???
        for sa in sa_obj:
            output[prog_code].append(generate_output('sa', sa_obj[sa], prog_code, ipac_keckids, ipac_userids, ipac_emails))
            #output[prog_code].append(generate_output('sa', sa_obj, prog_code, ipac_keckids, ipac_emails, ipac_fullnames, ipac_userids))

        #output[prog_code].append(generate_output('sa', sa_obj, prog_code, ipac_keckids, ipac_userids, ipac_emails))
        ##output[prog_code].append(generate_output('sa', sa_obj, prog_code, ipac_keckids, ipac_emails, ipac_fullnames, ipac_userids))

        # ----- 4. WMKO Admins Output -----
        for adm in admins:
            adm_semid = prog_code
            adm_usertype = "admin"
            #adm_keckid = 0
            if adm == 'koaadmin':
                adm_keckid = 9999
            elif adm == 'hireseng':
                adm_keckid = 5721
            elif adm == 'cpsadmin':
                adm_keckid = XXXX
            else:
                adm_keckid = 0
            adm_email = ""
            adm_firstname = ""
            adm_lastname = ""
            adm_userid = adm
    
            new = {}
            new["semid"] = adm_semid
            new["usertype"] = adm_usertype
            new["keckid"] = adm_keckid
            new["email"] = adm_email
            new["firstname"] = adm_firstname
            new["lastname"] = adm_lastname
            new["userid"] = adm_userid
            new["access"] = get_access(prog_code, adm_keckid, adm_userid, adm_email, ipac_keckids, ipac_userids, ipac_emails)
            #new["access"] = get_access(prog_code, adm_keckid, adm_email, adm_firstname, adm_lastname, adm_userid, ipac_keckids, ipac_emails, ipac_fullnames, ipac_userids)
            new["kpf_access"] = kpf_access
            output[prog_code].append(new)


json_output = json.dumps(output, indent=2)
#print(json_output)

# ***** Process Programs at IPAC *****

#pp_params = {}
##pp_params["request"] = "PROCESS_PROGRAMS"
#pp_params["request"] = "PROCESS_GRANTS"
#pp_params["PI"] = "koaadmin"
#
#try:
#    resp = requests.post(ipac_url, params=pp_params, auth=(config['ipac']['user'],config['ipac']['pwd']), data=json_output, verify=False)     # PROCESS_PROGRAMS
#    #resp = requests.post(ipac_url, params=pp_params, auth=(config['ipac1']['user'],config['ipac1']['pwd']), data=json_output, verify=False)   # PROCESS_GRANTS
#
#except Exception as e:
#    print( "%s" % e )
#    exit()
#
#if resp.status_code != 200:
#    print( resp.reason )
#    exit()
#
#else:
#    pp_string = resp.content.decode('utf-8')
#    pp_data = json.loads(pp_string)
#    pp_resp = json.dumps(pp_data)
#    #print(pp_resp)
#    pp(pp_resp, compact=False)
#    print()

# ----- send report via email -----
message = ''.join((message, "\n"))
#final_output = ''.join((message, json_output, "\n", pp_resp))
final_output = ''.join((message, json_output, "\n"))
    
if email != 'none':
    send_email(email, final_output, error)
else:
    print(final_output, error)


#if __name__ == "__main__":
   #main(sys.argv)
