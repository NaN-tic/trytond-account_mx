#!/usr/bin/env python
# python generate_accounts_xml.py file.xlsx
import sys
from openpyxl import load_workbook
account_file = sys.argv[1]

account_parent_0 = 'pc_0'

wb = load_workbook(filename=account_file, read_only=True)
ws = wb['full preparat']

first_row = True


parent_accounts = {}

parent_accounts_to_print = []
child_accounts_to_print = []

for row in ws.rows:
    if first_row:
        first_row = False
        print('skiping first row...')
        continue
    #print(f'1: {row[0].value}')
    #print(f'2: {row[1].value}')
    #print(f'3: {row[2].value}')
    code = row[0].value
    name = row[1].value

    if code.endswith('-00-000'):
        # Compte "pare"
        account_code = 'pg_' + code[:6].replace('-', '_')
        parent_accounts[code[:6]] = account_code
        parent = account_parent_0
        parent_accounts_to_print.append(
            f'<record model="account.account.template" id="{account_code}">'
            f'\n    <field name="name">{name}</field>'
            f'\n    <field name="parent" ref="{parent}"/>'
            f'\n    <field name="code">{code}</field>'
            f'\n    <field name="party_required" eval="False"/>'
            '\n</record>')
    elif code.endswith('-000'):
        # Compte "fill"
        account_code = 'pg_' + code[:6].replace('-', '_')
        #print(f'CODE: {code} | ACCOUNT CODE: {account_code}')
        parent = None
        parent_code = 'pg_' + code[:3]+'_00'
        child_accounts_to_print.append(
            f'<record model="account.account.template" id="{account_code}">'
            f'\n    <field name="name">{name}</field>'
            f'\n    <field name="parent" ref="{parent_code}"/>'
            f'\n    <field name="code">{code}</field>'
            f'\n    <field name="party_required" eval="False"/>'
            '\n</record>')
    else:
        # Compte "personalitzat, saltar"
        continue

#for parent_account in parent_accounts_to_print:
#    print(parent_account)


for child_account in child_accounts_to_print:
    print(child_account)
