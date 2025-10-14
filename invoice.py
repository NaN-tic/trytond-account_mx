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
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        Configuration = pool.get('account.configuration')
        config = Configuration(1)

        account_client_tax_paid = config.account_client_tax_paid
        account_supplier_tax_paid = config.account_supplier_tax_paid

        super().paid(invoices)

        to_save = []
        for invoice in invoices:
            tax_acconts = set([tax.account for tax in invoice.taxes])
            account_paid = None
            if invoice.type == 'in':
                account_paid = account_supplier_tax_paid
            elif invoice.type == 'out':
                account_paid = account_client_tax_paid

            move = Move()
            move.origin = invoice
            move.journal = invoice.journal
            paid_line = Line()
            paid_line.account = account_paid
            paid_line.debit = 0
            paid_line.credit = 0
            new_lines = []
            for line in invoice.move.lines:
                if line.account not in tax_acconts:
                    continue
                unpaid_line = Line()
                unpaid_line.account = line.account
                unpaid_line.debit = line.credit
                unpaid_line.credit = line.debit
                new_lines.append(unpaid_line)
                paid_line.debit += line.debit
                paid_line.credit += line.credit
            new_lines.append(paid_line)
            move.lines = new_lines
            to_save.append((invoice, move))

        if to_save:
            moves = [move for _, move in to_save]
            Move.save(moves)
            Move.post(moves)
            for invoice, move in to_save:
                invoice.additional_moves = list(invoice.additional_moves) + [move]
            cls.save([i for i, _ in to_save])

    @classmethod
    @Workflow.transition('posted')
    def post(cls, invoices):
        was_paid = [invoice for invoice in invoices if invoice.state == 'paid']
        super().post(invoices)
        if was_paid:
            pool = Pool()
            Move = pool.get('account.move')
            to_delete = []
            for invoice in was_paid:
                to_delete.extend(invoice.additional_moves)
            if to_delete:
                Move.delete(to_delete)
