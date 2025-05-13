#!/usr/bin/env python
# python generate_accounts_xml.py file.xlsx
import sys
from openpyxl import load_workbook
account_file = sys.argv[1]

account_parent_0 = 'pc_0'

wb = load_workbook(filename=account_file, read_only=True)
ws = wb['full preparat']

first_row = True


#parent_accounts = {}

main_parent_accounts_to_print = [] # Ex account 105
sub_main_parent_accounts_to_print = [] # Ex account 105-00
parent_accounts_to_print = [] # 105-00-00
child_accounts_to_print = []
sub_child_accounts_to_print = []
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
        # Compte "pare principal"
        account_code = 'pg_' + code[:3]
        parent = account_parent_0
        main_parent_accounts_to_print.append(
            f'<record model="account.account.template" id="{account_code}">'
            f'\n    <field name="name">{name}</field>'
            f'\n    <field name="parent" ref="{parent}"/>'
            f'\n    <field name="code">{code[:3]}</field>'
            f'\n    <field name="party_required" eval="False"/>'
            '\n</record>')

        # Compte "pare subprincipal"
        parent = account_code
        account_code = 'pg_' + code[:6].replace('-', '_')
        sub_main_parent_accounts_to_print.append(
            f'<record model="account.account.template" id="{account_code}">'
            f'\n    <field name="name">{name}</field>'
            f'\n    <field name="parent" ref="{parent}"/>'
            f'\n    <field name="code">{code[:6]}</field>'
            f'\n    <field name="party_required" eval="False"/>'
            '\n</record>')

        # Compte "pare fill"
        parent = account_code
        account_code = 'pg_' + code.replace('-', '_')
        #parent_accounts[code[:6]] = account_code
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
        parent_code = 'pg_' + code[:3]
        child_accounts_to_print.append(
            f'<record model="account.account.template" id="{account_code}">'
            f'\n    <field name="name">{name}</field>'
            f'\n    <field name="parent" ref="{parent_code}"/>'
            f'\n    <field name="code">{code[:6]}</field>'
            f'\n    <field name="party_required" eval="False"/>'
            '\n</record>')

        # Compte "fill fill"
        parent_code = account_code
        account_code = 'pg_' + code.replace('-', '_')
        sub_child_accounts_to_print.append(
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


#for main_parent_account in main_parent_accounts_to_print:
#    print(main_parent_account)

#for sub_main_parent_account in sub_main_parent_accounts_to_print:
#    print(sub_main_parent_account)

#for parent_account in parent_accounts_to_print:
#    print(parent_account)

#for child_account in child_accounts_to_print:
#    print(child_account)

#for sub_child_account in sub_child_accounts_to_print:
#    print(sub_child_account)

#for child_child_account in child_child_accounts_to_print:
#    print(child_child_account)
