# This file is part account_mx module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import Pool
from . import account, invoice, statement

def register():
    Pool.register(
        account.Configuration,
        invoice.Invoice,
        module='account_mx', type_='model')
    Pool.register(
        module='account_mx', type_='wizard')
    Pool.register(
        module='account_mx', type_='report')
    Pool.register(
        statement.Origin,
        depends=['account_statement_enable_banking'],
        module='account_mx', type_='model')
