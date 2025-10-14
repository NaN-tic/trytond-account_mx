# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.model import Workflow, ModelView
from trytond.exceptions import UserError
from trytond.i18n import gettext

class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'

    @classmethod
    @Workflow.transition('paid')
    def paid(cls, invoices):
        pool = Pool()
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        Configuration = pool.get('account.configuration')

        super().paid(invoices)

        config = Configuration(1)
        account_client_tax_paid = config.account_client_tax_paid
        account_supplier_tax_paid = config.account_supplier_tax_paid
        account_move_tax_journal = config.account_move_tax_journal

        if not (account_client_tax_paid and account_supplier_tax_paid and
                account_move_tax_journal):
            raise UserError(
                gettext('account_mx.msg_missing_account_move_tax_configuration'))
        to_save_moves = []
        for invoice in invoices:
            tax_acconts = set([tax.account for tax in invoice.taxes])
            account_paid = None
            if invoice.type == 'in':
                account_paid = account_supplier_tax_paid
            elif invoice.type == 'out':
                account_paid = account_client_tax_paid

            move = Move()
            move.origin = invoice
            move.journal = account_move_tax_journal
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
            to_save_moves.append(move)

        if to_save_moves:
            Move.save(to_save_moves)
            Move.post(to_save_moves)


class InvoiceAccountESDepends(metaclass=PoolMeta):
    __name__ = 'account.invoice'

    @classmethod
    @ModelView.button
    @Workflow.transition('posted')
    def unpay(cls, invoices):
        pool = Pool()
        Move = pool.get('account.move')
        Configuration = pool.get('account.configuration')

        super().unpay(invoices)

        config = Configuration(1)
        account_client_tax_paid = config.account_client_tax_paid
        account_supplier_tax_paid = config.account_supplier_tax_paid

        if not (account_client_tax_paid and account_supplier_tax_paid):
            raise UserError(
                gettext('account_mx.msg_missing_account_move_tax_configuration'))

        moves = Move.search([('origin', 'in', invoices)])
        to_delete_moves = []
        for move in moves:
            if move.origin.type == 'in':
                account_paid = account_supplier_tax_paid
            elif move.origin.type == 'out':
                account_paid = account_client_tax_paid
            for line in move.lines:
                if line.account == account_paid:
                    to_delete_moves.append(move)
                    break
        if moves:
            Move.draft(moves)
            Move.delete(moves)
