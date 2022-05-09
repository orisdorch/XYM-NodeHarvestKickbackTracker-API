"""
Created on Tue Apr 27 2021 using Python v3.7.6
@author: Oris Dorch

PURPOSE
This script is primarily intended to facilitate manual XYM Node Reward kickbacks by helping a node operator to identify harvested blocks, calculate reward amounts, and track payments.
It includes a prompt with additional functions that may be useful to node operators or other developers.

DESCRIPTION
A simple Python script that queries a Symbol(XYM) node via API for blocks harvested by the provided beneficiary address. Differentiates blocks harvester by the node operator and delegated harvesters using a provided list of node operator addresses.
Core function works by:
- Querying harvest transaction types using defined beneficiary address and last harvested block block height
- requerying for next page(s) if response length = pagesize limit
- Will calculate a node reward 'kickback' by percentage - to be manually sent & tracked as paid
- Tracks all harvested blocks in a text file output [NOTE: output is not a clean CSV]
- New sessions check for previous session's text file output and uses the last block harvested in the file to avoid duplicate entries.

Sample output line in file: height,123456,harvestAmount,134422724,nodeReward(satoshis),48008115,kickbackAmount,9.601623,Address,SAAA244WMCB2JXGNQTQHQOS45TGBFF4V2MJBVOQ,Date/Time: 2021-08-29 11:05:34.524000,Status,UNPAID,
Includes functions to: translate XYM Addresses between API-provided Hex and Base32 encodings, translate a public key to address, check current harvesters, return total # of blocks harvested on node .

SETUP
Define the variables in USER DEFINED VARIABLES section to: set your desired output file path, the API Node you want to query, your node's beneficiary address, the address you're harvesting on, and the kickback reward multiplier.

USE
Once the variables have been defined, run the script. It will check for an existing log file at the specified file path and read it if one exists, otherwise it will create a new log file. Next it queries the blockchain via the specified API Node. 
Once the script has completed its initial query, it will prompt you with a menu including several optional operations including a requery of the blockchain to check for newly harvested blocks. 
Blocks harvested on your node by addresses other than your own will be tracked in the log file with a default status of 'UNPAID'. Once you manually pay out the block reward, you can open the log file and change the status to 'PAID' to simplify tracking.
One of the options in the menu is to list all blocks in the log; this is useful when checking for unpaid blocks harvested. Note that at present, updates to the log file will not be reflected in Python until the script is re-run (the log file is re-read).

Distributed under  Mozilla Public Licence 2.0 
"""
import requests
import base64
import datetime
#import json - unused at present

### Global/Static Variables - do not change ###
blockList = {}    #list of blocks harvested by other harvesters
lastBlock = '0'   #last blocks harvested by another harvester
headers={'content-type':'application/json', 'Accept':'application/json'}  #parameters used in API calls
genesisBlockTime = datetime.datetime(2021, 3, 16, 0, 6, 25)   ## XYM Genesis block - against which all subsequent blocks are tracked.. Note: timezone is unclear at time of writing

### USER DEFINED VARIABLES - you will need to provide these! ###
APINodeURL = 'http://my.node.me:3000'   #Provide the node that should be queried and relevant port (can be your own node or any other API node)
HarvestedBlocksLocalFilePath = 'C:\\Users\\USER\\Desktop\\harvestedblocks.txt'   #Provide the location of the (headerless) csv file that will be used to track blocks harvested by others
myBeneficiaryAddress = 'SAAA244WMCB2JXGNQTQHQOS45TGBFF4V2MJBVOQ'   # Your node's beneficiary address (without hyphens) - this is where node rewards are sent, and is used to identify blocks harvested on your node. note: use hexToAddress() to convert a public key to an address
myHarvesterAddress = 'SAAA244WMCB2JXGNQTQHQOS45TGBFF4V2MJBVOQ'   # Additional harvesting address to be identified as yours (allnodes doesn't allow you to specify the node reward address, so use your primary harvesting address here. Otherwise this might be your node's delegation address - i.e. 'nodePublicKey' in http://my.node/node/info )
myOtherAddress = myHarvesterAddress   #Optional third address to identify as yours. Use myHarvesterAddress if a third address is not required.
kickbackMultiplier = 0.2   # percent to kickback to harvesters (i.e. 0.2 = 20%)

##### Define Core Processes #####

#### Functions used upon script launch - retrieving prior session details ####

### When first running the script, checks for previous output file: creates one if none exists, otherwise retrieve last block from existing file. ###
def firstRunFileCheck():
    fileExists = False
    try:                            #try to open the file at the specified path
        f = open(HarvestedBlocksLocalFilePath, "r")
        f.close()
        fileExists = True
        print("a previous output file has been found at the target location ...")
    except:
        print("no previous output file has been found at "+HarvestedBlocksLocalFilePath+", creating a new file...")
        f= open(HarvestedBlocksLocalFilePath,"w+")
        f.close() 
    if fileExists:
        print("retrieving last block from previous output file")
        getBlocksFromFile()
        updateBlocks()  
    else: 
        print("First time updating data from XYM blockchain; will subsequenty check blockchain for updates")
        updateBlocks()

### Retrieve the last harvested block indicated in the text file ###
def getBlocksFromFile():
    global lastBlock
    f = open(HarvestedBlocksLocalFilePath, "r")
    fileContents = f.readlines()
    f.close()
    if len(fileContents) == 0:
        print("Previous output file found, but it is empty")
    else: 
        lastBlock = fileContents[-1].split(",")[1]
        for i in fileContents:
            row = i.split(",")
            n=0
            stagedBlockList = []
            while n < len(row)-2:   # -2 because dict starts at , and line  ends with ',\n' for line break
                stagedBlockList.append((row[n],row[n+1]))
                n+=2
            blockList[row[1]]=dict(stagedBlockList)
        print("Previous output file found and last block identified as "+lastBlock+"\n")

#### Core functions ####

### Queries the specified API Node for newly harvested blocks (by beneficiary address), parses out blocks your address harvested, writes any new blocks to the output file, and updates 'last block' tracker ###
def updateBlocks():
    global blockList
    global lastBlock
    countOtherResults = 0
    countMyResults = 0
    apiEndpoint = '/statements/transaction?type=8515&artifactId=6BED913FA20223F8&targetAddress='+myBeneficiaryAddress+"&fromHeight="+str(int(lastBlock)+1)
    data = APICallPagination(APINodeURL,apiEndpoint)
    ### Review results and write target blocks to file before checking next page (if applicable) ###
    for i in data:
        lastBlock = i['statement']['height']
        hexKey = i['statement']['receipts'][0]['targetAddress']
        harvesterAddress = hexToAddress(hexKey)
        if i['statement']['receipts'][0]['targetAddress'] in myHarvestAddressesHex: #harvested by one of my addresses
            blockList[lastBlock] = {'height': lastBlock,'harvestAmount': i['statement']['receipts'][0]['amount'], 'nodeReward(satoshis)': i['statement']['receipts'][2]['amount'], 'kickbackAmount': 'N/A','Address': harvesterAddress,'Date/Time': str(getBlockTimestamp(APINodeURL,lastBlock)), 'Status': 'Harvested by me'}
            countMyResults+=1
        else:
            blockList[lastBlock] = {'height': lastBlock,'harvestAmount': i['statement']['receipts'][0]['amount'], 'nodeReward(satoshis)': i['statement']['receipts'][2]['amount'], 'kickbackAmount': str(int(i['statement']['receipts'][2]['amount'])*kickbackMultiplier/1000000),'Address': harvesterAddress,'Date/Time': str(getBlockTimestamp(APINodeURL,lastBlock)), 'Status': 'Unpaid'}
            countOtherResults+=1
        print(blockList[lastBlock])
        writeToFile(HarvestedBlocksLocalFilePath,blockList[lastBlock])
    print("\n"+str(countOtherResults)+" blocks harvested by others and "+str(countMyResults)+" by you since the last check")

### Write harvest block details to output file ###
def writeToFile(path,dictionary):
    with open(path, 'a' ) as f:
         for key in dictionary:
             f.write(key + ',' + dictionary[key] + ',')
         f.write('\n')
        
### Identify delegated harvesters currently harvesting on your node ###
def getHarvesters():
    otherHarvesters = []
    myHarvestingAddresses = []
    apiEndpoint = '/node/unlockedaccount'
    data = APICallNotPaged(APINodeURL,apiEndpoint,'unlockedAccount')          
    for i in data:   #loops through all public keys and translates to addresses
        address = nodeHarvesterkeytoAddress(APINodeURL,i)
        if address not in myHarvestAddresses:
            otherHarvesters.append(address)
        else:
            myHarvestingAddresses.append(address)
    print('\nOther harvesters presently delegated to your node:')
    for i in otherHarvesters:
        print(i)
    print('\nYour addresses harvesting on your node:')
    for i in myHarvestingAddresses:
        print(i)
   
    
### Prompt-loop that allows user to select a function from a list of options  ###
def runLoop():
    command = input("Enter: \n   1 to refresh data from blockchain \n   2 to show unpaid block kickbacks \n   3 to show details of all blocks harvested by others \n   4 to show details of all harvested blocks \n   5 for total # of harvested blocks on your node (including yours) \n   6 to see harvesters delegated to your node (incl. node beneficiary address) \n  x to exit \n ") 
    if command == "x":
        print("Exiting... Use runLoop() to continue checking...")
        return
    elif command == "1":
        updateBlocks()
    elif command == "2":
        blocks = []
        for block in blockList.keys():
            if blockList[block]['Status'] == 'Unpaid':
                         blocks.append(block)
        print(str(len(blocks))+" unpaid blocks on record: ")
        print(blocks)
        print("... to see additional block detail use the 'show details of blocks harvested by others' function or open "+HarvestedBlocksLocalFilePath)
    elif command == "3":        
        for block in blockList.keys():
            if blockList[block]['Status'] == 'Unpaid':
                print(blockList[block])
    elif command == "4":
        for block in blockList.keys():
            print(blockList[block])
    elif command == "5":
        for address in myHarvestAddresses:
            harvestedBlocksByAddress(APINodeURL,address)
    elif command == "6":
        getHarvesters()
    else:
        print("I did not understand the input, please try again.")
    input("\n<ENTER> to return to the menu...")
    runLoop()

        
##### REUSABLE functions (not script specific): Paged/unpaged API Queryies, address translations, and additional data collection #####

### API Calls ###
# For paged responses (record limit per query) - captures each 'page before querying the next, aggregating contents until the last page is found #
def APICallPagination(APINodeURL,endPoint):
    page = 1
    lastPage = False
    data = []
    while lastPage == False:
        requestURL = APINodeURL+endPoint+"&pageSize=100&pageNumber="+str(page)
        print('Collecting paged data from '+requestURL)
        r = requests.get(requestURL).json()
        data.extend(r.get('data'))
        # If the number of entries on the page is not equal to the page size limit, mark this as the last page
        if len(r.get('data')) != r['pagination']['pageSize'] :
            lastPage = True
            print("Page "+str(page)+" is the last page of results, analyzing results...")
        else:  
            lastPage = False
            print("Partial results retrieved - analyzing results for page "+str(page)+"...")
            page+=1
    return data

# For queries without responses (full contents are returned with a single query) #
def APICallNotPaged(APINodeURL,endPoint,dataKey):
    requestURL = APINodeURL+endPoint
    print('Collecting data from '+requestURL)
    r = requests.get(requestURL).json()
    data = r.get(dataKey)
    return data


### Translations between hexidecimal address (provided in API responses), Base32 (traditional address format), and private key to address translation. ###
def hexToAddress(hexKey):
    return base64.b32encode(bytes.fromhex(hexKey)).decode("utf-8").replace("=","")

# Translate a base32 XYM address to a hexidecimal equivelant #
def addresstoHex(address):
    address.replace("-","")
    address+="="
    return bytes.hex(base64.b32decode(address))

# determine the public address associated with a public key #
def publicKeytoAddress(APINodeURL,PublicKey):
    data = APICallNotPaged(APINodeURL,'/accounts/'+PublicKey,'account')
    if data == None:
        return 'Unused public key '+PublicKey+' has no address'
    else:
        address = hexToAddress(data['address'])
        return address

# Delegated-Key-to-Address translation specifically for delegated harvesters; identify the account linked to the delegated harvesting public key#
def nodeHarvesterkeytoAddress(APINodeURL,harvesterPublicKey):
    apiEndpoint = '/accounts/'+harvesterPublicKey
    data = APICallNotPaged(APINodeURL,apiEndpoint,'account')     
    primaryKey = data['supplementalPublicKeys']['linked']['publicKey']
    primaryAddress = publicKeytoAddress(APINodeURL,primaryKey)
    return primaryAddress

### Node harvester list and block timestamp functions ###
def harvestedBlocksByAddress(APINodeURL,address):
    data = APICallPagination(APINodeURL,'/blocks?beneficiaryAddress='+address)
    blocks = len(data)
    print("Your address "+address+" has harvested "+str(blocks)+" blocks")

# collects and translates a block's timestamp to a date and time #
def getBlockTimestamp(APINodeURL,height):
    blockTimeRaw = APICallNotPaged(APINodeURL,'/blocks/'+height,'block')
    secondsSinceGenesis = int(blockTimeRaw['timestamp'])/1000
    blockTime = genesisBlockTime + datetime.timedelta(0,secondsSinceGenesis)
    return blockTime



##### INITIATION #####
### Convert the address provided in user defined variables to a hex version so it matches the API response format ###
myHarvestAddressesHex = [addresstoHex(myHarvesterAddress.replace("=","")).upper(),addresstoHex(myBeneficiaryAddress.replace("=","")).upper(),addresstoHex(myOtherAddress.replace("=","")).upper()]
myHarvestAddresses = [myHarvesterAddress.replace("-", "").upper(), myBeneficiaryAddress.replace("-", "").upper(), myOtherAddress.replace("-", "").upper()]

### Once all functions are loaded, run firstRunFileCheck() to check for & load previous results file, then initiate the runLoop() user interface ###
firstRunFileCheck()
runLoop()
