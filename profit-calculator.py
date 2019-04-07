"""Profit calculator for Althea networks.

Usage:
  profit-calculator.py <eth-address> [--days=n>]
  profit-calculator.py (-h | --help)
  protit-calcualtor.py --version

Options:
  --days=n      Cover up until n days ago
  -h --help     Show this screen.
  --version     Show version.

"""
from docopt import docopt
import json
from web3 import Web3
import requests
import os


def get_transactions_by_address(address, startblock=0, endblock=99999999):
    apikey = os.environ['ETHERSCAN_API_KEY']
    url = "https://api.etherscan.io/api?module=account&action=txlist&address={}&startblock={}&endblock={}&sort=asc&apikey={}".format(
        address, startblock, endblock, apikey)
    r = requests.get(url)
    return r.json()['result']


def get_eth_price():
    url = "https://api.cryptonator.com/api/ticker/eth-usd"
    r = requests.get(url)
    return float(r.json()['ticker']['price'])

# current althea transactions target 5% fees so this is the best way to find them


def is_althea_transaction(tx):
    if int(tx['value']) == 0:
        return False

    val = (float(tx['gas']) * float(tx['gasPrice'])) / float(tx['value'])
    if val > 0.01 and val < 0.2:
        return True
    else:
        return False


def is_not_althea_transaction(tx):
    return not is_althea_transaction(tx)


def sum_tx_value(address, transactions):
    total = 0
    for tx in transactions:
        if int(tx['value']) == 0:
            continue
        if tx['to'] == address:
            total = total + int(tx['value'])
        elif tx['from'] == address:
            total = total - int(tx['value'])
        else:
            print("what? this is an error")
    return total


def gas_value(address, transactions):
    total = 0
    for tx in transactions:
        if tx['from'] == address:
            total = total + (int(tx['gasPrice']) * int(tx['gas']))
    return total


def wei_to_eth(num):
    return num / pow(10, 18)


def profit_stats(address, web3, startblock=0, endblock=99999999):
    address = address.lower()
    price = get_eth_price()
    web3address = Web3.toChecksumAddress(address)
    endblock = min(web3.eth.blockNumber, endblock)
    transactions = get_transactions_by_address(
        address, startblock=startblock, endblock=endblock)
    balance = wei_to_eth(web3.eth.getBalance(web3address))
    total_deposited = wei_to_eth(sum_tx_value(
        address, filter(is_not_althea_transaction, transactions)))
    total_deposited_usd = total_deposited * price
    althea_spent = wei_to_eth(sum_tx_value(
        address, filter(is_althea_transaction, transactions)))
    althea_spent_usd = althea_spent * price
    txfees_paid = wei_to_eth(gas_value(address, transactions))
    txfees_paid_usd = txfees_paid * price
    val = "Address {0} has a current balance of {1:.2f} Eth".format(
        address, balance)
    print(val)

    val = "Over the specified period {0:.2f} ETH / {1:.2f} USD has been deposited/withdrawn by the user".format(
        total_deposited, total_deposited_usd)
    print(val)
    val = "During that same time Althea has spent/earned a total of {0:.2f} ETH / {1:.2f} USD".format(
        althea_spent, althea_spent_usd)
    print(val)
    val = "Finally {0:.2f} ETH / {1:.2f} USD was spent on txfees from this address".format(
        txfees_paid, txfees_paid_usd)
    print(val)


def address_from_publickey(publickey):
    hash = Web3.sha3(hexstr=Web3.toHex(publickey))
    address = Web3.toHex(hash[-20:])
    return address


my_provider = Web3.HTTPProvider("https://eth.althea.org")
w3 = Web3(my_provider)

arguments = docopt(__doc__, version='parser 0.0.1')

starting_address = arguments['<eth-address>']
startblock = 0
if arguments['--days']:
    startblock = w3.eth.blockNumber - (int(arguments['--days']) * 5760)

profit_stats(starting_address, w3, startblock=startblock)
