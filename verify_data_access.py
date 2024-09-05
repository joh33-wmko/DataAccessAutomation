#! /usr/local/anaconda/bin/python

import argparse
import json
import requests
import smtplib
from email.mime.text import MIMEText
import datetime as dt
import urllib3
urllib3.disable_warnings()
import pdb                             # remove when done

import pprint
import pdb

# config file modules
from os.path import dirname, isfile
import yaml

dirname = dirname(__file__)
configFile = "config.live.ini"
filename = f'{dirname}/{configFile}'
assert isfile(filename), f"ERROR: {filename} file missing"
with open(filename) as f: config = yaml.safe_load(f)

# parse command line arguments
parser = argparse.ArgumentParser(description="Verify Data Access")
parser.add_argument("--date", \
                    type=str, \
                    default=dt.datetime.now().strftime("%Y-%m-%d"), \
                    help="HST Run Date Format is yyyy-mm-dd", \
                    required=False)
parser.add_argument("--numdays", \
                    type=int, \
                    default=1, \
                    help="Integer from 1 to 180", \
                    required=False)
parser.add_argument("--email", \
                    dest="email", \
                    default=None, \
                    help="Email to send output to")
parser.add_argument("--sendData", \
                    default=False, \
                    action="store_true", \
                    help="Send data to NExScI")
parser.add_argument("--piOnly", \
                    default=False, \
                    action="store_true", \
                    help="Only check PIs")
args = parser.parse_args()

startDate = args.date
numdays   = args.numdays
email     = args.email
sendData  = args.sendData
piOnly    = args.piOnly

if numdays <= 0 or numdays > 35:
    numdays = 1

try:
    test = dt.datetime.strptime(startDate, "%Y-%m-%d")
except:
    print("Invalid date")
    exit()

message = f"Verifying data access starting {startDate} for {numdays} days\n\n"

api     = config["API"]["KECK_API"]
ipacapi = config["API"]["IPAC_URL"]

skip = ["keck@hawaii.edu", "coversheet@keck.hawaii.edu"]

# Get the telescope schedule entries
params = {}
params["date"]    = startDate
params["numdays"] = numdays
url = f"{api}/schedule/getSchedule"
schedData = requests.get(url, params=params, verify=False)
schedData = schedData.json()

# Get SA list
params = {}
params["role"] = "SA"
url = f"{api}/employee/getEmployee"
saData = requests.get(url, params=params, verify=False)
saData = saData.json()
saKeckId = {}
url = f"{api}/schedule/getObserverInfo"
for sa in saData:
    params = {}
    saemail  = f"{sa['Alias']}@keck.hawaii.edu"
    params["email"] = saemail
    obsData   = requests.get(url, params=params, verify=False)
    obsData   = obsData.json()[0]
    saKeckId[saemail] = obsData["Id"]

# For sending to NExScI
apiData = []

# Loop through the programs
done = []
for entry in schedData:
    if entry["Instrument"] == "PCS":
        continue

    semid = f"{entry['Semester']}_{entry['ProjCode']}"
    if semid in done:
        continue
    done.append(semid)
    pi = entry["PiEmail"]

    # Get KoaAccess for this program
    params         = {}
    params["ktn"]  = semid
    url = f"{api}/proposals/getKoaAccess"
    koa = requests.get(url, params=params, verify=False)
    koa = koa.json()
    try:
        koaAccess = koa["KoaAccess"]
    except:
        koaAccess = 0

    # Get KpfAccess for this program
    try:
        kpfAccess = koa["KpfAccess"]
    except:
        kpfAccess = 0

    # Get observers
    params = {}
    params["schedid"] = entry["SchedId"]
    url = f"{api}/schedule/getObservers"
    observers = requests.get(url, params=params, verify=False)
    observers = observers.json()

    # Get COIs
    params = {}
    params["ktn"] = semid
    url = f"{api}/proposals/getCOIs"
    cois = requests.get(url, params=params, verify=False)
    cois = cois.json()

    # Get access list for this program
    params = {}
    params["semid"] = semid
    url = f"{api}/koa/checkAccess"
    accessList = requests.get(url, params=params, verify=False)
    accessList = accessList.json()

    # Form the master list of who should have access
    masterList = []
    keckidList = saKeckId #{}
    if entry["PiEmail"] not in skip:
        masterList.append(entry["PiEmail"])
        keckidList[entry["PiEmail"]] = entry["PiId"]
    if not piOnly:
        masterList = masterList + [f"{i['Alias']}@keck.hawaii.edu" for i in saData]
        if koaAccess == 1:
            for obs in observers[0]["data"]:
                masterList.append(obs["Email"])
                keckidList[obs["Email"]] = obs["ObsId"]
            for coi in cois["data"]["COIs"]:
                masterList.append(coi["Email"])
                keckidList[coi["Email"]] = coi["ObsId"]
    masterList = set(masterList)

    print(entry["Date"], semid, koaAccess, kpfAccess)

    # Verify access
    try: # incase semid returned nothing for access
        for ipac in accessList["access"]:
            if ipac["email"] in masterList:
                masterList.remove(ipac["email"])
                print(f"{entry['Date']} {semid} koaAccess={koaAccess} {ipac['email']} OK")
    except:
        print()
        continue

    for user in masterList:
        isPI = 1 if user == pi else 0

        lastname = firstname = ""
        keckid = 0

        # Check if user has a KOA account
        params = {}
        params["user"] = user
        params["test"]  = test
        url = f"{api}/koa/checkUserAccess"
        access = requests.get(url, params=params, verify=False)
        access = access.json()
        accessType = None
        koaUser = None
        check = True
        try:
            koaUser = access["koaid"]
            accessType = "GRANT_ACCESS"
            try:
                koaKeckId = access["access"][0]["keckid"]
                if not koaKeckId:
                    accessType = "ADD_KECKID_AND_GRANT_ACCESS"
            except:
                pass
        except:
            params["user"] = keckidList[user]
            access = requests.get(url, params=params, verify=False)
            access = access.json()
            try:
                koaUser = access["koaid"]
                if koaUser == "":
                    raise Exception()
                accessType = "GRANT_ACCESS"
            except:
                params = {}
                params["email"] = user
                url = f"{api}/schedule/getObserverInfo"
                obsData   = requests.get(url, params=params, verify=False)
                # This catches possible mismatch in email between CS and OBS
                if len(obsData.json()) == 0:
                    print('ERROR:', params)
                    continue
                obsData   = obsData.json()[0]
                lastname  = obsData["LastName"]
                firstname = obsData["FirstName"]
                keckid    = keckidList[user]
                koaUser = "NONE"
                accessType = "CREATE_ACCOUNT_AND_GRANT_ACCESS"
                check = False

        # Verify access
        found = False
        if check:
            for ipac in accessList["access"]:
                if not found and ipac["userid"] == koaUser:
                    print(f"{entry['Date']} {semid} koaAccess={koaAccess} {user} isPI={isPI} OK")
                    found = True

        if found:
            continue

        # PHASE 1 - only create accounts for PI
        if accessType == "CREATE_ACCOUNT_AND_GRANT_ACCESS":
            continue
        if accessType == "CREATE_ACCOUNT_AND_GRANT_ACCESS" and isPI == 0:
            continue

        print(f"{entry['Date']} {semid} koaAccess={koaAccess} {user} KOAID={koaUser} PI={isPI} {accessType}")

        keckid  = keckidList[user]

        tmp = {}
        tmp["action"]    = accessType
        tmp["ispi"]      = isPI
        tmp["semid"]     = semid

        if accessType == "GRANT_ACCESS":
            tmp["koaid"]     = koaUser
        elif accessType == "ADD_KECKID_AND_GRANT_ACCESS":
            tmp["keckid"]    = keckid
            tmp["koaid"]     = koaUser
        elif accessType == "CREATE_ACCOUNT_AND_GRANT_ACCESS":
            tmp["email"]     = user
            tmp["keckid"]    = keckid
            tmp["lastname"]  = lastname
            tmp["firstname"] = firstname

        apiData.append(tmp)

    print()

message = f"{message}{json.dumps(apiData, indent=2)}"
print(message)

if len(apiData) > 0:
    if email:
        msg = MIMEText(message)
        msg['Subject'] = "KOA Data Access Verification"
        msg['To'] = email
        msg['From'] = config["REPORT"]["ADMIN_EMAIL"]
        s = smtplib.SMTP('localhost')
        s.send_message(msg)
        s.quit()
        print(f"Email sent to {email}")


    if sendData:

        #username = config["ipac"]["user"]
        #password = config["ipac"]["pwd"]

        username = config["ipac1"]["user"]
        password = config["ipac1"]["pwd"]

        #cmd = "request=PROCESS_PROGRAMS&PI=koaadmin"
        cmd = "request=PROCESS_PROGRAMS"
        api_call = ipacapi + cmd
        print(f'\napi_call: {api_call}')

        user_json = json.dumps(apiData)
        print(f'\nuser_json: {user_json}\n')

        try:
            r = requests.post( api_call, auth = ( username, password ), data=user_json)
        except Exception as e:
            print( "%s" % e )
            #exit()

        if r.status_code != 200:
            print( r.reason )
            #exit()

        else:
            ret_dict = r.json()

        #pprint.pprint( ret_dict )
        print(json.dumps(ret_dict, indent=4))
        print()


# original code - response object appears blank
#
#        params = {}
#        params["request"] = "PROCESS_PROGRAMS"
#        params["PI"]      = "koaadmin"
#        params["data"]    = json.dumps(apiData)
#        data_resp = requests.post(ipacapi, params=params, auth=(username, password))
#
#        #ret_dict = json.loads(data_resp.text)
#        #print(f'rect_dict: {rect_dict}')
#
#        print(f"Response URL: {data_resp.url}")
#        print(f'Text: {data_resp.text}')
#        print(f'Content: {data_resp.content}')
#
#        data_resp.close()
#        print()
