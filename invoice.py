# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.model import Workflow, ModelView
from trytond.exceptions import UserError
from trytond.i18n import gettext

class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'

    @classmethod
    def paid(cls, invoices):
        pool = Pool()
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        Configuration = pool.get('account.configuration')
        Date = pool.get('ir.date')

        super().paid(invoices)
        if not invoices:
            return

        date = Date.today()

        config = Configuration(1)
        account_client_tax_paid = config.account_client_tax_paid
        account_supplier_tax_paid = config.account_supplier_tax_paid
        account_move_tax_journal = config.account_move_tax_journal

        if not (account_client_tax_paid and account_supplier_tax_paid and
                account_move_tax_journal):
            raise UserError(
                gettext('account_mx.msg_missing_account_move_tax_configuration'))
        to_post = []
        to_reconcile = {}
        for invoice in invoices:
            if invoice.type == 'in':
                account_paid = account_supplier_tax_paid
            else: # out
                account_paid = account_client_tax_paid
            moves = Move.search([('origin', '=', invoice)])
            to_continue = False
            for move in moves:
                for line in move.lines:
                    if line.account == account_paid:
                        to_continue = True
                        break
            if to_continue:
                continue

            tax_acconts = set([tax.account for tax in invoice.taxes])
            account_paid = None
            if invoice.type == 'in':
                account_paid = account_supplier_tax_paid
            elif invoice.type == 'out':
                account_paid = account_client_tax_paid

            move = Move()
            move.origin = invoice
            move.journal = account_move_tax_journal
            move.description = invoice.rec_name
            move.date = invoice.reconciled or date
            move.on_change_date()
            move.save()
            to_post.append(move)
            paid_line = Line()
            paid_line.move = move
            paid_line.account = account_paid
            paid_line.debit = 0
            paid_line.credit = 0
            for line in invoice.move.lines:
                if line.account not in tax_acconts:
                    continue
                key = (invoice, line.account)
                if key not in to_reconcile:
                    to_reconcile[key] = [line]
                unpaid_line = Line()
                unpaid_line.move = move
                unpaid_line.account = line.account
                unpaid_line.debit = line.credit
                unpaid_line.credit = line.debit
                unpaid_line.save()
                to_reconcile[key].append(unpaid_line)
                paid_line.debit += line.debit
                paid_line.credit += line.credit
            paid_line.save()

        if to_post:
            Move.post(to_post)

        if to_reconcile:
            for lines in to_reconcile.values():
                lines = Line.browse([line.id for line in lines])
                Line.reconcile(lines)

    @classmethod
    @ModelView.button
    @Workflow.transition('posted')
    def undo_pay(cls, invoices):
        pool = Pool()
        Move = pool.get('account.move')
        Reconciliation = pool.get('account.move.reconciliation')
        Configuration = pool.get('account.configuration')

        super().undo_pay(invoices)

        config = Configuration(1)
        account_client_tax_paid = config.account_client_tax_paid
        account_supplier_tax_paid = config.account_supplier_tax_paid

        if not (account_client_tax_paid and account_supplier_tax_paid):
            raise UserError(gettext(
                    'account_mx.msg_missing_account_move_tax_configuration'))

        moves = Move.search([('origin', 'in', invoices)])
        to_delete_moves = []
        reconciliations = []
        for move in moves:
            if move.origin.type == 'in':
                account_paid = account_supplier_tax_paid
            elif move.origin.type == 'out':
                account_paid = account_client_tax_paid
            to_delete = False
            reconcile = []
            for line in move.lines:
                if line.account == account_paid:
                    to_delete_moves.append(move)
                    to_delete = True
                if line.reconciliation:
                    reconcile.append(line.reconciliation)
            if to_delete and reconcile:
                reconciliations.extend(reconcile)
        if reconciliations:
            Reconciliation.delete(reconciliations)
        if moves:
            moves = list(set(moves))
            Move.draft(moves)
            Move.delete(moves)
