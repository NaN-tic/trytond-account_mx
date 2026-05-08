# This file is part account_mx module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from datetime import datetime, timezone

from trytond.exceptions import UserError
from trytond.i18n import gettext
from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import Pool

from .sat_service import (
    SATMassDownloadService, SATServiceError, STATUS_MESSAGES,
    package_checksum)


AUTH_URL = (
    'https://cfdidescargamasivasolicitud.clouda.sat.gob.mx/'
    'Autenticacion/Autenticacion.svc')
REQUEST_URL = (
    'https://cfdidescargamasivasolicitud.clouda.sat.gob.mx/'
    'SolicitaDescargaService.svc')
VERIFY_URL = (
    'https://cfdidescargamasivasolicitud.clouda.sat.gob.mx/'
    'VerificaSolicitudDescargaService.svc')
DOWNLOAD_URL = (
    'https://cfdidescargamasiva.clouda.sat.gob.mx/'
    'DescargaMasivaService.svc')


REQUEST_TYPES = [
    ('emitted', 'Emitted'),
    ('received', 'Received'),
    ('folio', 'Folio'),
]

DOWNLOAD_TYPES = [
    ('CFDI', 'CFDI'),
    ('Metadata', 'Metadata'),
]

REQUEST_STATES = [
    (None, ''),
    ('1', 'Accepted'),
    ('2', 'In Process'),
    ('3', 'Finished'),
    ('4', 'Error'),
    ('5', 'Rejected'),
    ('6', 'Expired'),
]

PACKAGE_STATES = [
    ('pending', 'Pending'),
    ('downloaded', 'Downloaded'),
    ('error', 'Error'),
]


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class SATConfiguration(ModelSQL, ModelView):
    'SAT Configuration'
    __name__ = 'account.mx.sat.configuration'

    company = fields.Many2One('company.company', 'Company', required=True)
    rfc = fields.Char('RFC', required=True, strip=True)
    certificate = fields.Many2One(
        'certificate', 'e.firma Certificate', required=True,
        help='Certificate Manager record containing the e.firma certificate '
        'and encrypted private key.')
    auth_url = fields.Char('Authentication URL', required=True)
    request_url = fields.Char('Request URL', required=True)
    verify_url = fields.Char('Verification URL', required=True)
    download_url = fields.Char('Download URL', required=True)
    active = fields.Boolean('Active')
    last_authentication = fields.DateTime('Last Authentication', readonly=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update({
            'test_authentication': {},
        })

    @classmethod
    def default_auth_url(cls):
        return AUTH_URL

    @classmethod
    def default_request_url(cls):
        return REQUEST_URL

    @classmethod
    def default_verify_url(cls):
        return VERIFY_URL

    @classmethod
    def default_download_url(cls):
        return DOWNLOAD_URL

    @classmethod
    def default_active(cls):
        return True

    @classmethod
    def for_company(cls, company):
        configs = cls.search([
            ('company', '=', company.id if hasattr(company, 'id') else company),
            ('active', '=', True),
        ], limit=1)
        if not configs:
            raise UserError(gettext(
                'account_mx.msg_sat_missing_configuration'))
        return configs[0]

    def get_client(self):
        return SATMassDownloadService(
            self.certificate, self.auth_url, self.request_url,
            self.verify_url, self.download_url)

    @classmethod
    @ModelView.button
    def test_authentication(cls, configurations):
        for configuration in configurations:
            try:
                configuration.get_client().authenticate()
            except SATServiceError as error:
                raise UserError(gettext(
                    'account_mx.msg_sat_service_error',
                    message=str(error)))
            cls.write([configuration], {
                'last_authentication': utcnow(),
            })


class SATDownloadRequest(ModelSQL, ModelView):
    'SAT Download Request'
    __name__ = 'account.mx.sat.download.request'

    company = fields.Many2One('company.company', 'Company', required=True)
    request_type = fields.Selection(REQUEST_TYPES, 'Request Type',
        required=True)
    download_type = fields.Selection(DOWNLOAD_TYPES, 'Download Type',
        required=True)
    date_from = fields.DateTime('From')
    date_to = fields.DateTime('To')
    rfc_emisor = fields.Char('Issuer RFC', strip=True)
    rfc_receptor = fields.Char('Receiver RFC', strip=True,
        help='For emitted requests, comma-separated values are accepted '
        'and only the first five RFCs are sent.')
    rfc_solicitante = fields.Char('Requester RFC', required=True, strip=True)
    rfc_a_cuenta_terceros = fields.Char('Third Party Account RFC', strip=True)
    tipo_comprobante = fields.Char('CFDI Type', strip=True)
    estado_comprobante = fields.Selection([
        (None, ''),
        ('Todos', 'All'),
        ('Cancelado', 'Cancelled'),
        ('Vigente', 'Current'),
    ], 'CFDI Status')
    complemento = fields.Char('Complement', strip=True)
    folio = fields.Char('Fiscal Folio', strip=True)
    sat_request_id = fields.Char('SAT Request ID', readonly=True)
    sat_status_code = fields.Char('SAT Status Code', readonly=True)
    sat_status_message = fields.Char('SAT Status Message', readonly=True)
    sat_request_state = fields.Selection(REQUEST_STATES, 'SAT Request State',
        readonly=True)
    sat_request_state_code = fields.Char('SAT Request State Code',
        readonly=True)
    num_cfdis = fields.Integer('CFDIs', readonly=True)
    created_at = fields.DateTime('Created At', readonly=True)
    last_check_at = fields.DateTime('Last Check At', readonly=True)
    packages = fields.One2Many(
        'account.mx.sat.package', 'request', 'Packages', readonly=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update({
            'send_to_sat': {},
            'verify_in_sat': {},
            'download_sat_packages': {},
        })

    @classmethod
    def default_request_type(cls):
        return 'received'

    @classmethod
    def default_download_type(cls):
        return 'CFDI'

    @classmethod
    def default_created_at(cls):
        return utcnow()

    def _request_values(self):
        return {
            'date_from': self.date_from,
            'date_to': self.date_to,
            'rfc_emisor': self.rfc_emisor,
            'rfc_receptor': self.rfc_receptor,
            'rfc_solicitante': self.rfc_solicitante,
            'rfc_a_cuenta_terceros': self.rfc_a_cuenta_terceros,
            'tipo_comprobante': self.tipo_comprobante,
            'estado_comprobante': self.estado_comprobante,
            'complemento': self.complemento,
            'download_type': self.download_type,
            'folio': self.folio,
        }

    def _client_and_token(self):
        configuration = SATConfiguration.for_company(self.company)
        client = configuration.get_client()
        try:
            token = client.authenticate()
        except SATServiceError as error:
            raise UserError(gettext(
                'account_mx.msg_sat_service_error', message=str(error)))
        return client, token

    @classmethod
    @ModelView.button
    def send_to_sat(cls, requests):
        for download_request in requests:
            client, token = download_request._client_and_token()
            try:
                response = client.request_download(
                    token, download_request.request_type,
                    download_request._request_values())
            except SATServiceError as error:
                raise UserError(gettext(
                    'account_mx.msg_sat_service_error', message=str(error)))
            cls.write([download_request], {
                'sat_request_id': response.request_id,
                'sat_status_code': response.code,
                'sat_status_message': (
                    response.message or STATUS_MESSAGES.get(response.code)),
            })

    @classmethod
    @ModelView.button
    def verify_in_sat(cls, requests):
        Package = Pool().get('account.mx.sat.package')
        for download_request in requests:
            if not download_request.sat_request_id:
                raise UserError(gettext(
                    'account_mx.msg_sat_missing_request_id'))
            client, token = download_request._client_and_token()
            try:
                response = client.verify_request(
                    token, download_request.sat_request_id,
                    download_request.rfc_solicitante)
            except SATServiceError as error:
                raise UserError(gettext(
                    'account_mx.msg_sat_service_error', message=str(error)))
            cls.write([download_request], {
                'sat_status_code': response.code,
                'sat_status_message': (
                    response.message or STATUS_MESSAGES.get(response.code)),
                'sat_request_state': response.request_state,
                'sat_request_state_code': response.request_state_code,
                'num_cfdis': response.cfdi_count,
                'last_check_at': utcnow(),
            })
            existing = {
                package.package_id for package in Package.search([
                    ('request', '=', download_request.id),
                ])
            }
            to_save = []
            for package_id in response.package_ids:
                if package_id in existing:
                    continue
                package = Package()
                package.request = download_request
                package.package_id = package_id
                package.status = 'pending'
                to_save.append(package)
            if to_save:
                Package.save(to_save)

    @classmethod
    @ModelView.button
    def download_sat_packages(cls, requests):
        Package = Pool().get('account.mx.sat.package')
        for download_request in requests:
            client, token = download_request._client_and_token()
            packages = Package.search([
                ('request', '=', download_request.id),
                ('status', '!=', 'downloaded'),
            ])
            for package in packages:
                try:
                    response = client.download_package(
                        token, package.package_id,
                        download_request.rfc_solicitante)
                except SATServiceError as error:
                    Package.write([package], {
                        'status': 'error',
                        'sat_status_message': str(error),
                    })
                    continue
                if response.package:
                    Package.write([package], {
                        'status': 'downloaded',
                        'downloaded_at': utcnow(),
                        'file': fields.Binary.cast(response.package),
                        'filename': '%s.zip' % package.package_id,
                        'checksum': package_checksum(response.package),
                        'sat_status_code': response.code,
                        'sat_status_message': (
                            response.message
                            or STATUS_MESSAGES.get(response.code)),
                    })
                else:
                    Package.write([package], {
                        'status': 'error',
                        'sat_status_code': response.code,
                        'sat_status_message': (
                            response.message
                            or STATUS_MESSAGES.get(response.code)),
                    })


class SATPackage(ModelSQL, ModelView):
    'SAT Package'
    __name__ = 'account.mx.sat.package'

    request = fields.Many2One(
        'account.mx.sat.download.request', 'Request', required=True,
        ondelete='CASCADE')
    company = fields.Function(
        fields.Many2One('company.company', 'Company'), 'on_change_with_company',
        searcher='search_company')
    package_id = fields.Char('Package ID', required=True, readonly=True)
    status = fields.Selection(PACKAGE_STATES, 'Status', required=True)
    downloaded_at = fields.DateTime('Downloaded At', readonly=True)
    file = fields.Binary('File', filename='filename', readonly=True)
    filename = fields.Char('Filename', readonly=True)
    checksum = fields.Char('Checksum', readonly=True)
    processed = fields.Boolean('Processed')
    sat_status_code = fields.Char('SAT Status Code', readonly=True)
    sat_status_message = fields.Char('SAT Status Message', readonly=True)

    @classmethod
    def default_status(cls):
        return 'pending'

    @fields.depends('request', '_parent_request.company')
    def on_change_with_company(self, name=None):
        return self.request.company if self.request else None

    @classmethod
    def search_company(cls, name, clause):
        return [('request.company',) + tuple(clause[1:])]
