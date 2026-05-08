# This file is part account_mx module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.pool import Pool


class AccountMxTestCase(ModuleTestCase):
    'Test Account Mx module'
    module = 'account_mx'

    @with_transaction()
    def test_sat_views_open(self):
        pool = Pool()
        models = [
            'account.mx.sat.configuration',
            'account.mx.sat.download.request',
            'account.mx.sat.package',
        ]
        for model_name in models:
            Model = pool.get(model_name)
            form = Model.fields_view_get(view_type='form')
            tree = Model.fields_view_get(view_type='tree')
            self.assertTrue(form['arch'])
            self.assertTrue(tree['arch'])
            Model.default_get(Model._fields.keys(), with_rec_name=False)

del ModuleTestCase
