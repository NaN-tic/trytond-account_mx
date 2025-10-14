# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.model import Workflow, ModelView
from trytond.exceptions import UserError
from trytond.i18n import gettext


class Origin(metaclass=PoolMeta):
    __name__ = 'account.statement.origin'

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, statements):
        pool = Pool()
        Configuration = pool.get('account.configuration')
        Move = pool.get('account.move')
        super().cancel(statements)

        config = Configuration(1)
        account_client_tax_paid = config.account_client_tax_paid
        account_supplier_tax_paid = config.account_supplier_tax_paid
        if not (account_client_tax_paid and account_supplier_tax_paid):
            raise UserError(
                gettext('account_mx.msg_missing_account_move_tax_configuration'))
        invoices = [l.invoice for s in statements for l in s.lines if l.invoice]

        to_delete_moves = []
        for invoice in invoices:
            if invoice.type == 'in':
                account_paid = account_supplier_tax_paid
            elif invoice.type == 'out':
                account_paid = account_client_tax_paid
            moves = Move.search([('origin', '=', invoice)])
            for move in moves:
                for line in move.lines:
                    if line.account == account_paid:
                        to_delete_moves.append(move)
                        break
        if to_delete_moves:
            Move.draft(to_delete_moves)
            Move.delete(to_delete_moves)