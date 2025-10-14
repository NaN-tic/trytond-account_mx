# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import unittest

from trytond.modules.account_mx.tests.scenario_invoice_tax_settlement import ScenarioInvoiceTaxSettlement


def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite()
    suite.addTest(ScenarioInvoiceTaxSettlement('test_scenario'))
    return suite
