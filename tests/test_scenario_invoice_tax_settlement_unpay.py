import datetime as dt
import unittest
from decimal import Decimal

from proteus import Model
from trytond.modules.account.tests.tools import (
    create_chart, create_fiscalyear, create_tax, get_accounts)
from trytond.modules.account_invoice.tests.tools import (
    set_fiscalyear_invoice_sequences)
from trytond.modules.company.tests.tools import create_company, get_company
from trytond.tests.test_tryton import drop_db
from trytond.tests.tools import activate_modules


class Test(unittest.TestCase):
    def setUp(self):
        drop_db()
        super().setUp()

    def tearDown(self):
        drop_db()
        super().tearDown()

    def test(self):

        today = dt.date.today()

        # Activate modules
        config = activate_modules(['account_mx'])

        # Create company
        _ = create_company()
        company = get_company()

        # Create fiscal year
        fiscalyear = set_fiscalyear_invoice_sequences(
            create_fiscalyear(company, today))
        fiscalyear.click('create_period')

        # Create chart of accounts
        _ = create_chart(company)
        accounts = get_accounts(company)
        revenue = accounts['revenue']
        expense = accounts['expense']
        account_tax = accounts['tax']
        account_cash = accounts['cash']

        # Create tax
        tax = create_tax(Decimal('.10'))
        tax.save()

        # Create accounts for configuration
        Account = Model.get('account.account')
        account_client_tax_paid = Account()
        account_client_tax_paid.name = 'Client Tax Paid'
        account_client_tax_paid.type = account_tax.type
        account_client_tax_paid.parent = account_tax.parent
        account_client_tax_paid.save()
        account_supplier_tax_paid = Account()
        account_supplier_tax_paid.name = 'Supplier Tax Paid'
        account_supplier_tax_paid.type = account_tax.type
        account_supplier_tax_paid.parent = account_tax.parent
        account_supplier_tax_paid.save()

        # Create journal for tax moves
        Journal = Model.get('account.journal')
        journal_tax_move = Journal()
        journal_tax_move.name = 'Tax Settlement'
        journal_tax_move.type = 'general'
        journal_tax_move.save()

        # Set configuration
        Configuration = Model.get('account.configuration')
        config = Configuration(1)
        config.account_client_tax_paid = account_client_tax_paid
        config.account_supplier_tax_paid = account_supplier_tax_paid
        config.account_move_tax_journal = journal_tax_move
        config.save()

        # Create party
        Party = Model.get('party.party')
        party = Party(name='Party')
        party.save()

        # Create account category
        ProductCategory = Model.get('product.category')
        account_category = ProductCategory(name='Account Category')
        account_category.accounting = True
        account_category.account_expense = expense
        account_category.account_revenue = revenue
        account_category.customer_taxes.append(tax)
        account_category.save()

        # Create product
        ProductUom = Model.get('product.uom')
        unit, = ProductUom.find([('name', '=', 'Unit')])
        ProductTemplate = Model.get('product.template')
        template = ProductTemplate()
        template.name = 'product'
        template.default_uom = unit
        template.type = 'service'
        template.list_price = Decimal('100')
        template.account_category = account_category
        template.save()
        product, = template.products

        # Create payment method
        PaymentMethod = Model.get('account.invoice.payment.method')
        journal_cash, = Journal.find([('type', '=', 'cash')])
        payment_method = PaymentMethod()
        payment_method.name = 'Cash'
        payment_method.journal = journal_cash
        payment_method.credit_account = account_cash
        payment_method.debit_account = account_cash
        payment_method.save()

        # Create invoice
        Invoice = Model.get('account.invoice')
        InvoiceLine = Model.get('account.invoice.line')
        invoice = Invoice()
        invoice.party = party
        line = InvoiceLine()
        invoice.lines.append(line)
        line.product = product
        line.quantity = 1
        line.unit_price = Decimal('100')
        invoice.save()
        self.assertEqual(invoice.untaxed_amount, Decimal('100.00'))
        self.assertEqual(invoice.tax_amount, Decimal('10.00'))
        self.assertEqual(invoice.total_amount, Decimal('110.00'))

        # Post invoice
        invoice.click('post')
        self.assertEqual(invoice.state, 'posted')

        # Pay invoice
        pay = invoice.click('pay')
        pay.form.amount = invoice.total_amount
        pay.form.payment_method = payment_method
        pay.execute('choice')
        self.assertEqual(pay.state, 'end')
        invoice.reload()
        self.assertEqual(invoice.state, 'paid')

        # Check tax settlement move
        Move = Model.get('account.move')
        tax_moves = Move.find([
            ('origin', '=', invoice),
            ('journal', '=', journal_tax_move),
        ])
        self.assertEqual(len(tax_moves), 1)
        tax_move = tax_moves[0]
        self.assertEqual(tax_move.state, 'posted')
        lines = tax_move.lines
        self.assertEqual(len(lines), 2)

        # Undo payment invoice
        invoice.click('undo_pay')
        invoice.reload()
        self.assertEqual(invoice.state, 'posted')
        tax_moves = Move.find([
            ('origin', '=', invoice),
            ('journal', '=', journal_tax_move),
        ])
        self.assertEqual(len(tax_moves), 0)
