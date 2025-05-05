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
child_child_accounts_to_print = []

# This dictionary handles the type accounts
type_dict = {
    'Activo': 'mx_01',
    'Pasivo': 'mx_02',
    'Capital': 'mx_03',
    'Ingresos': 'mx_04',
    'Costos': 'mx_05',
    'Gastos': 'mx_06',
    'Resultado': 'mx_07',
}


for row in ws.rows:
    if first_row:
        first_row = False
        print('skiping first row...')
        continue
    type = row[0].value
    code = row[1].value
    name = row[2].value

    if code.endswith('-00-000'):
        type_record = type_dict.get(type)
        if not type_record:
            print(f'-- ERROR: Type {type} not found for account: {code} - {name}')
            raise
        # Compte "pare"
        account_code = 'pg_' + code[:6].replace('-', '_')
        parent_accounts[code[:6]] = account_code
        parent = account_parent_0
        parent_accounts_to_print.append(
            f'<record model="account.account.template" id="{account_code}">'
            f'\n    <field name="name">{name}</field>'
            f'\n    <field name="type" ref="{type_record}"/>'
            f'\n    <field name="parent" ref="{parent}"/>'
            f'\n    <field name="code">{code}</field>'
            f'\n    <field name="party_required" eval="False"/>'
            '\n</record>')
    elif code.endswith('-000'):
        type_record = type_dict.get(type)
        if not type_record:
            print(f'-- ERROR: Type {type} not found for account: {code} - {name}')
            raise
        # Compte "fill"
        account_code = 'pg_' + code[:6].replace('-', '_')
        parent = None
        parent_code = 'pg_' + code[:3]+'_00'
        child_accounts_to_print.append(
            f'<record model="account.account.template" id="{account_code}">'
            f'\n    <field name="name">{name}</field>'
            f'\n    <field name="type" ref="{type_record}"/>'
            f'\n    <field name="parent" ref="{parent_code}"/>'
            f'\n    <field name="code">{code}</field>'
            f'\n    <field name="party_required" eval="False"/>'
            '\n</record>')
    else:
        type_record = type_dict.get(type)
        if not type_record:
            print(f'-- ERROR: Type {type} not found for account: {code} - {name}')
            raise
        # Compte "personalitzat"
        account_code = 'pg_' + code.replace('-', '_')
        parent = None
        parent_code = 'pg_' + code[:6].replace('-', '_')
        child_child_accounts_to_print.append(
            f'<record model="account.account.template" id="{account_code}">'
            f'\n    <field name="name">{name}</field>'
            f'\n    <field name="type" ref="{type_record}"/>'
            f'\n    <field name="parent" ref="{parent_code}"/>'
            f'\n    <field name="code">{code}</field>'
            f'\n    <field name="party_required" eval="False"/>'
            '\n</record>')

#for parent_account in parent_accounts_to_print:
#    print(parent_account)

#for child_account in child_accounts_to_print:
#    print(child_account)

for child_child_account in child_child_accounts_to_print:
    print(child_child_account)
