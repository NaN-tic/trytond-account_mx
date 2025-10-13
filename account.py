# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.model import fields

class Configuration(metaclass=PoolMeta):
    __name__ = 'account.configuration'
    account_client_tax_unpaid = fields.Many2One(
        'account.account', "Client Tax Unpaid Account")
    account_supplier_tax_unpaid = fields.Many2One(
        'account.account', "Supplier Tax Unpaid Account")
    account_client_tax_paid = fields.Many2One(
        'account.account', "Client Tax Paid Account")
    account_supplier_tax_paid = fields.Many2One(
        'account.account', "Supplier Tax Paid Account")
