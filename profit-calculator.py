"""Profit calculator for Althea networks.

Usage:
  profit-calculator.py <eth-address> [--days=n>] [--follow-the-money]
  profit-calculator.py (-h | --help)
  protit-calcualtor.py --version

Options:
  --follow-the-money  Track all Althea spent funds to source and destination
  --days=n            Cover up until n days ago
  -h --help           Show this screen.
  --version           Show version.

"""
from docopt import docopt
import json
from web3 import Web3
import requests
import os
import pandas as pd
import holoviews as hv
from holoviews import opts, dim
from bokeh.sampledata.les_mis import data
from bokeh.sampledata.les_mis import data


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


def is_althea_transaction(tx):
    """"current althea transactions target 5% fees so this is the best way to find them"""
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


def get_full_network_transactions(address, network_data, startblock=0, endblock=99999999):
    """given one address get other althea addresses that have paid/been paid from that address
       return a dict containing all addresses to transaction lists"""
    print("Getting transactions for {}".format(address))
    transactions = get_transactions_by_address(
        address, startblock=startblock, endblock=endblock)
    network_data[address] = transactions
    for tx in transactions:
        if is_althea_transaction(tx) and tx['from'] not in network_data:
            # combines the dictionaries
            network_data = {**network_data, **get_full_network_transactions(
                tx['from'], network_data, startblock=startblock, endblock=endblock)}
        elif is_althea_transaction(tx) and tx['to'] not in network_data:
            network_data = {**network_data, **get_full_network_transactions(
                tx['to'], network_data, startblock=startblock, endblock=endblock)}
    return network_data


def address_from_publickey(publickey):
    hash = Web3.sha3(hexstr=Web3.toHex(publickey))
    address = Web3.toHex(hash[-20:])
    return address


def count_tx(address_a, address_b, transactions):
    num = 0
    for tx in transactions:
        if tx['from'] == address_a and tx['to'] == address_b:
            num = num + 1
    return num


def generate_links(all_transactions):
    """Generates the links array accepted by hv"""
    # first we assign numbers to the addresses
    order = {}
    num = 0
    for key in all_transactions.keys():
        order[key] = num
        num = num + 1

    result = []
    for a in all_transactions.keys():
        for b in all_transactions.keys():
            if a == b:
                continue
            else:
                print("adding entry for {} and {}".format(a, b))
                entry = {}
                entry['source'] = order[a]
                entry['target'] = order[b]
                entry['value'] = count_tx(a, b, all_transactions[a])
                result.append(entry)
    return result


def generate_nodes(all_transactions):
    """Generates the nodes aray accepted by hv"""
    nodes = []
    num = 0
    for n in all_transactions.keys():
        entry = {}
        entry['name'] = n
        entry['group'] = num
        num = num + 1
        nodes.append(entry)
    return nodes


def plot_network(all_transactions):
    hv.extension('bokeh')
    hv.output(size=500)
    links = pd.DataFrame(generate_links(all_transactions))
    print(links)
    hv.Chord(links)
    nodes = hv.Dataset(pd.DataFrame(generate_nodes(all_transactions)), 'index')
    nodes.data.head()
    chord = hv.Chord((links, nodes)).select(value=(1, None))
    chord.opts(
        opts.Chord(cmap='Category20', edge_cmap='Category20', edge_color=dim('source').str(),
                   labels='name', node_color=dim('index').str()))
    hv.save(chord, 'image.html')
    print("Network analysis complete, saved as image.html")


my_provider = Web3.HTTPProvider("https://eth.althea.org")
w3 = Web3(my_provider)

arguments = docopt(__doc__, version='parser 0.0.1')

starting_address = arguments['<eth-address>']
startblock = 0
if arguments['--days']:
    startblock = w3.eth.blockNumber - (int(arguments['--days']) * 5760)

if arguments['--follow-the-money']:
    print("Follow the money mode enabled, please wait while we collect data for the entire network")
    all_transactions = get_full_network_transactions(
        starting_address, {}, startblock=startblock)
    plot_network(all_transactions)
else:
    profit_stats(starting_address, w3, startblock=startblock)
