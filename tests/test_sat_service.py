# This file is part account_mx module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
import base64
import unittest
from datetime import datetime, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from lxml import etree

from trytond.modules.account_mx.sat_service import (
    SATMassDownloadService, SATXMLSigner, authorization_header,
    build_auth_envelope, build_download_request_node, soap_envelope)


class Certificate:
    def __init__(self):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, 'MX'),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'HELSA TEST'),
            x509.NameAttribute(NameOID.COMMON_NAME, 'HELSA TEST'),
            x509.NameAttribute(NameOID.X500_UNIQUE_IDENTIFIER,
                'HEM010101AAA'),
        ])
        now = datetime.now(timezone.utc)
        certificate = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now.replace(year=now.year + 1))
            .sign(key, hashes.SHA256()))
        self.key = key
        self.certificate = certificate

    def load_pem_key(self):
        return self.key

    def load_pem_certificate(self):
        return self.certificate


class SATServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.signer = SATXMLSigner(Certificate())

    def test_authorization_header(self):
        self.assertEqual(
            authorization_header('abc.def'),
            'WRAP access_token="abc.def"')

    def test_auth_envelope_signs_timestamp_with_binary_token(self):
        xml = build_auth_envelope(
            self.signer,
            datetime(2026, 5, 6, 10, 0, tzinfo=timezone.utc))
        root = etree.fromstring(xml)
        self.assertEqual(root.tag.rsplit('}', 1)[1], 'Envelope')
        self.assertTrue(root.xpath(
            '//*[local-name()="BinarySecurityToken"]/text()'))
        self.assertEqual(
            root.xpath('string(//*[local-name()="Reference"]/@URI)'),
            '#_0')
        self.assertEqual(
            root.xpath('string(//*[local-name()="SignatureMethod"]/@Algorithm)'),
            'http://www.w3.org/2000/09/xmldsig#rsa-sha1')
        self.assertTrue(root.xpath('//*[local-name()="Autentica"]'))

    def test_received_request_attribute_order_and_signature(self):
        operation, node = build_download_request_node(self.signer, 'received', {
            'complemento': None,
            'estado_comprobante': 'Vigente',
            'date_from': datetime(2026, 1, 1, 0, 0),
            'date_to': datetime(2026, 1, 2, 0, 0),
            'rfc_emisor': None,
            'rfc_solicitante': 'HEM010101AAA',
            'tipo_comprobante': 'I',
            'download_type': 'CFDI',
            'rfc_receptor': 'HEM010101AAA',
            'rfc_a_cuenta_terceros': None,
        })
        self.assertEqual(
            list(node.attrib),
            ['EstadoComprobante', 'FechaInicial', 'FechaFinal',
             'RfcSolicitante', 'TipoComprobante', 'TipoSolicitud',
             'RfcReceptor'])
        self.assertEqual(operation.tag.rsplit('}', 1)[1],
            'SolicitaDescargaRecibidos')
        self.assertTrue(node.xpath('./*[local-name()="Signature"]'))

    def test_download_response_decodes_package(self):
        service = SATMassDownloadService(
            Certificate(), 'auth', 'request', 'verify', 'download')
        payload = base64.b64encode(b'zip-data').decode('ascii')
        response = service._parse_download_response((
            '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
            '<s:Header><h:respuesta '
            'xmlns:h="http://DescargaMasivaTerceros.sat.gob.mx" '
            'CodEstatus="5000" Mensaje="Solicitud Aceptada"/></s:Header>'
            '<s:Body><RespuestaDescargaMasivaTercerosSalida '
            'xmlns="http://DescargaMasivaTerceros.sat.gob.mx">'
            '<Paquete>%s</Paquete>'
            '</RespuestaDescargaMasivaTercerosSalida></s:Body></s:Envelope>'
        ) % payload)
        self.assertEqual(response.code, '5000')
        self.assertEqual(response.package, b'zip-data')

    def test_soap_envelope_uses_soap_11_body(self):
        operation, _ = build_download_request_node(self.signer, 'folio', {
            'folio': '22dac9d9-7a29-460d-a0a7-7d9e0be450d2',
            'rfc_solicitante': 'HEM010101AAA',
        })
        envelope = etree.fromstring(soap_envelope(operation))
        self.assertEqual(
            envelope.xpath('local-name(/*/*[local-name()="Body"]/*[1])'),
            'SolicitaDescargaFolio')


if __name__ == '__main__':
    unittest.main()
