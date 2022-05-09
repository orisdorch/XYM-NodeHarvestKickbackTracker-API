# XYM-NodeHarvestKickbackTracker-API
A simple Python script that queries the Symbol XYM blockchain via API for blocks harvested on your node (based on the beneficiary address) and by a harvester other than yourself (by omitting any blocks harvested by your address). 
- Queries for harvest transaction types using defined beneficiary address and last harvested block block height
    - requeries next page(s) if response length = pagesize limit
- Tracks harvested blocks in a text file output
- Will calculate a node reward 'kickback' by percentage - to be manually sent & tracked as paid
- New sessions check for previous session's text file output and uses the last block harvested in the file to avoid duplicate entries.
- Includes functions to translate XYM Addresses between API-provided Hex and Base32 encodings.

Perhaps neither optized nor elegant, but functional.

Define 5 variables to: set your desired output file path, the API Node you want to query, your node's beneficiary address, the address you're harvesting on, and the kickback reward multiplier.

Sample output line in file:
height,123456,harvestAmount,134422724,nodeReward(satoshis),48008115,kickbackAmount,9.601623,Address,ADDRESSGOPESHERE,Status,UNPAID,

Coded with Python v3.7.6
