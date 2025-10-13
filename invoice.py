# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.model import Workflow


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'

    @classmethod
    @Workflow.transition('paid')
    def paid(cls, invoices):
        pool = Pool()
        Line = pool.get('account.move.line')
        Configuration = pool.get('account.configuration')
        config = Configuration(1)

        account_client_tax_unpaid = config.account_client_tax_unpaid
        account_supplier_tax_unpaid = config.account_supplier_tax_unpaid
        account_client_tax_paid = config.account_client_tax_paid
        account_supplier_tax_paid = config.account_supplier_tax_paid

        super().paid(invoices)

        to_save_lines = []
        for invoice in invoices:
            if invoice.move:
                move = invoice.move
            if move and invoice.type == 'out':
                for line in move.lines:
                    if line.account == account_client_tax_unpaid:
                        paid_line = Line()
                        paid_line.account = account_client_tax_paid
                        paid_line.debit = line.credit
                        paid_line.move = move

                        line.debit = line.credit
                        line.credit = 0
                        to_save_lines.extend([line, paid_line])
                        break
            elif move and invoice.type == 'in':
                for line in move.lines:
                    if line.account == account_supplier_tax_unpaid:
                        paid_line = Line()
                        paid_line.account = account_supplier_tax_paid
                        paid_line.credit = line.debit
                        paid_line.move = move

                        line.credit = line.debit
                        line.debit = 0
                        to_save_lines.extend([line, paid_line])
                        break
        if to_save_lines:
            Line.save(to_save_lines)
