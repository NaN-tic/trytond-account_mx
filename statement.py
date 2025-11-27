# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.exceptions import UserError
from trytond.i18n import gettext


class Origin(metaclass=PoolMeta):
    __name__ = 'account.statement.origin'

    @classmethod
    def cancel(cls, origins):
        pool = Pool()
        Configuration = pool.get('account.configuration')
        Move = pool.get('account.move')
        Reconciliation = pool.get('account.move.reconciliation')

        super().cancel(origins)

        config = Configuration(1)
        account_client_tax_paid = config.account_client_tax_paid
        account_supplier_tax_paid = config.account_supplier_tax_paid
        if not (account_client_tax_paid and account_supplier_tax_paid):
            raise UserError(
                gettext('account_mx.msg_missing_account_move_tax_configuration'))
        invoices = [l.invoice for s in origins for l in s.lines if l.invoice]

        to_delete_moves = []
        to_delete_reconciliations = []
        for invoice in invoices:
            if invoice.type == 'in':
                account_paid = account_supplier_tax_paid
            else: # out
                account_paid = account_client_tax_paid
            moves = Move.search([('origin', '=', invoice)])
            for move in moves:
                for line in move.lines:
                    if line.account == account_paid:
                        to_delete_moves.append(move)
                    if move in to_delete_moves and line.reconciliation:
                        to_delete_reconciliations.append(
                            line.reconciliation)
        print(to_delete_moves)
        print(to_delete_reconciliations)
        if to_delete_reconciliations:
            to_delete = list(tuple(to_delete_reconciliations))
            Reconciliation.delete(to_delete)
        if to_delete_moves:
            to_delete = list(tuple(to_delete_moves))
            Move.draft(to_delete)
            Move.delete(to_delete)
