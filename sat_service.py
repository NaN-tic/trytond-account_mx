# This file is part account_mx module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
import base64
import gzip
import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError

import xmlsig
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import Encoding
from lxml import etree


SOAP_NS = 'http://schemas.xmlsoap.org/soap/envelope/'
SAT_AUTH_NS = 'http://DescargaMasivaTerceros.gob.mx'
SAT_DOWNLOAD_NS = 'http://DescargaMasivaTerceros.sat.gob.mx'
WSSE_NS = (
    'http://docs.oasis-open.org/wss/2004/01/'
    'oasis-200401-wss-wssecurity-secext-1.0.xsd')
WSU_NS = (
    'http://docs.oasis-open.org/wss/2004/01/'
    'oasis-200401-wss-wssecurity-utility-1.0.xsd')
X509_VALUE_TYPE = (
    'http://docs.oasis-open.org/wss/2004/01/'
    'oasis-200401-wss-x509-token-profile-1.0#X509v3')
BASE64_ENCODING_TYPE = (
    'http://docs.oasis-open.org/wss/2004/01/'
    'oasis-200401-wss-soap-message-security-1.0#Base64Binary')
DSIG_NS = xmlsig.constants.DSigNs

SOAP_ACTIONS = {
    'auth': (
        'http://DescargaMasivaTerceros.gob.mx/IAutenticacion/Autentica'),
    'emitted': (
        'http://DescargaMasivaTerceros.sat.gob.mx/'
        'ISolicitaDescargaService/SolicitaDescargaEmitidos'),
    'received': (
        'http://DescargaMasivaTerceros.sat.gob.mx/'
        'ISolicitaDescargaService/SolicitaDescargaRecibidos'),
    'folio': (
        'http://DescargaMasivaTerceros.sat.gob.mx/'
        'ISolicitaDescargaService/SolicitaDescargaFolio'),
    'verify': (
        'http://DescargaMasivaTerceros.sat.gob.mx/'
        'IVerificaSolicitudDescargaService/VerificaSolicitudDescarga'),
    'download': (
        'http://DescargaMasivaTerceros.sat.gob.mx/'
        'IDescargaMasivaTercerosService/Descargar'),
}

STATUS_MESSAGES = {
    '300': 'Usuario No Valido',
    '301': 'XML Mal Formado',
    '302': 'Sello Mal Formado',
    '303': 'Sello no corresponde con RFC',
    '304': 'Certificado Revocado o Caduco',
    '305': 'Certificado Invalido',
    '404': 'Error no controlado',
    '5000': 'Solicitud recibida con exito',
    '5001': 'Tercero no autorizado',
    '5002': 'Se han agotado las solicitudes de por vida',
    '5003': 'Tope maximo de elementos de la consulta',
    '5004': 'No se encontro la informacion',
    '5005': 'Ya se tiene una solicitud registrada',
    '5007': 'No existe el paquete solicitado',
    '5008': 'Maximo de descargas permitidas',
    '5011': 'Limite de descargas por folio por dia',
    '5012': 'No se permite la descarga de XML cancelados',
}


class SATServiceError(Exception):
    pass


@dataclass
class SATServiceResponse:
    code: str | None = None
    message: str | None = None
    request_id: str | None = None
    requester_rfc: str | None = None
    request_state: str | None = None
    request_state_code: str | None = None
    cfdi_count: int | None = None
    package_ids: tuple[str, ...] = ()
    package: bytes | None = None


def qname(namespace, name):
    return etree.QName(namespace, name)


def sat_datetime(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value.replace(microsecond=0).isoformat()
    return datetime.combine(value, datetime.min.time()).isoformat()


def authorization_header(token):
    return 'WRAP access_token="%s"' % token


def _text(node):
    return ''.join(node.itertext()).strip() if node is not None else None


def _first(root, local_name):
    result = root.xpath('//*[local-name()=$name]', name=local_name)
    return result[0] if result else None


def _remove_blank_text(xml):
    parser = etree.XMLParser(remove_blank_text=True)
    return etree.fromstring(xml, parser=parser)


class SATXMLSigner:
    def __init__(self, certificate):
        self.certificate = certificate
        self.private_key = certificate.load_pem_key()
        self.public_certificate = certificate.load_pem_certificate()

    @property
    def certificate_der_b64(self):
        der = self.public_certificate.public_bytes(Encoding.DER)
        return base64.b64encode(der).decode('ascii')

    @property
    def issuer_name(self):
        return xmlsig.utils.get_rdns_name(self.public_certificate.issuer.rdns)

    @property
    def serial_number(self):
        return str(self.public_certificate.serial_number)

    def _context(self):
        context = xmlsig.SignatureContext()
        context.private_key = self.private_key
        context.x509 = self.public_certificate
        context.public_key = self.public_certificate.public_key()
        return context

    def sign_request_node(self, node):
        digest = hashlib.sha1(etree.tostring(
            node, method='c14n', exclusive=False, with_comments=False))
        signature = etree.Element(qname(DSIG_NS, 'Signature'),
            nsmap={'ds': DSIG_NS})
        signed_info = etree.SubElement(signature, qname(DSIG_NS, 'SignedInfo'))
        etree.SubElement(signed_info, qname(DSIG_NS, 'CanonicalizationMethod'),
            Algorithm=xmlsig.constants.TransformInclC14N)
        etree.SubElement(signed_info, qname(DSIG_NS, 'SignatureMethod'),
            Algorithm=xmlsig.constants.TransformRsaSha1)
        reference = etree.SubElement(signed_info, qname(DSIG_NS, 'Reference'),
            URI='')
        transforms = etree.SubElement(reference, qname(DSIG_NS, 'Transforms'))
        etree.SubElement(transforms, qname(DSIG_NS, 'Transform'),
            Algorithm=xmlsig.constants.TransformEnveloped)
        etree.SubElement(reference, qname(DSIG_NS, 'DigestMethod'),
            Algorithm=xmlsig.constants.TransformSha1)
        etree.SubElement(reference, qname(DSIG_NS, 'DigestValue')).text = (
            base64.b64encode(digest.digest()).decode('ascii'))
        node.append(signature)

        signed_info_c14n = etree.tostring(
            signed_info, method='c14n', exclusive=False, with_comments=False)
        signature_value = self.private_key.sign(
            signed_info_c14n, padding.PKCS1v15(), hashes.SHA1())
        etree.SubElement(signature, qname(DSIG_NS, 'SignatureValue')).text = (
            base64.b64encode(signature_value).decode('ascii'))
        key_info = etree.SubElement(signature, qname(DSIG_NS, 'KeyInfo'))
        x509_data = etree.SubElement(key_info, qname(DSIG_NS, 'X509Data'))
        issuer_serial = etree.SubElement(
            x509_data, qname(DSIG_NS, 'X509IssuerSerial'))
        etree.SubElement(
            issuer_serial, qname(DSIG_NS, 'X509IssuerName')
        ).text = self.issuer_name
        etree.SubElement(
            issuer_serial, qname(DSIG_NS, 'X509SerialNumber')
        ).text = self.serial_number
        etree.SubElement(
            x509_data, qname(DSIG_NS, 'X509Certificate')
        ).text = self.certificate_der_b64
        return node

    def sign_auth_security(self, security, timestamp_id, token_id):
        signature = xmlsig.template.create(
            c14n_method=xmlsig.constants.TransformExclC14N,
            sign_method=xmlsig.constants.TransformRsaSha1)
        reference = xmlsig.template.add_reference(
            signature, xmlsig.constants.TransformSha1, uri='#' + timestamp_id)
        xmlsig.template.add_transform(
            reference, xmlsig.constants.TransformExclC14N)
        security.append(signature)
        self._context().sign(signature)

        key_info = etree.SubElement(signature, qname(DSIG_NS, 'KeyInfo'))
        token_reference = etree.SubElement(
            key_info, qname(WSSE_NS, 'SecurityTokenReference'))
        etree.SubElement(token_reference, qname(WSSE_NS, 'Reference'), {
            'URI': '#' + token_id,
            'ValueType': X509_VALUE_TYPE,
        })
        return security


class SATMassDownloadService:
    def __init__(self, certificate, auth_url, request_url, verify_url,
            download_url, timeout=60):
        self.signer = SATXMLSigner(certificate)
        self.auth_url = auth_url
        self.request_url = request_url
        self.verify_url = verify_url
        self.download_url = download_url
        self.timeout = timeout

    def authenticate(self):
        envelope = build_auth_envelope(self.signer)
        response = self._post(self.auth_url, SOAP_ACTIONS['auth'], envelope)
        root = _remove_blank_text(response)
        fault = _first(root, 'Fault')
        if fault is not None:
            raise SATServiceError(_text(fault) or 'SAT authentication fault')
        token_node = _first(root, 'AutenticaResult')
        token = _text(token_node)
        if not token:
            raise SATServiceError('SAT did not return an authentication token')
        return token

    def request_download(self, token, request_type, values):
        operation, node = build_download_request_node(
            self.signer, request_type, values)
        envelope = soap_envelope(operation)
        return self._parse_request_response(self._post(
            self.request_url, SOAP_ACTIONS[request_type], envelope,
            token=token))

    def verify_request(self, token, request_id, requester_rfc):
        operation = etree.Element(
            qname(SAT_DOWNLOAD_NS, 'VerificaSolicitudDescarga'),
            nsmap={'des': SAT_DOWNLOAD_NS})
        node = etree.SubElement(operation, qname(SAT_DOWNLOAD_NS, 'solicitud'))
        node.set('IdSolicitud', request_id)
        node.set('RfcSolicitante', requester_rfc)
        self.signer.sign_request_node(node)
        response = self._post(
            self.verify_url, SOAP_ACTIONS['verify'], soap_envelope(operation),
            token=token)
        return self._parse_verify_response(response)

    def download_package(self, token, package_id, requester_rfc):
        operation = etree.Element(
            qname(SAT_DOWNLOAD_NS, 'PeticionDescargaMasivaTercerosEntrada'),
            nsmap={'des': SAT_DOWNLOAD_NS})
        node = etree.SubElement(
            operation, qname(SAT_DOWNLOAD_NS, 'peticionDescarga'))
        node.set('IdPaquete', package_id)
        node.set('RfcSolicitante', requester_rfc)
        self.signer.sign_request_node(node)
        response = self._post(
            self.download_url, SOAP_ACTIONS['download'],
            soap_envelope(operation), token=token)
        return self._parse_download_response(response)

    def _post(self, url, soap_action, body, token=None):
        headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': '"%s"' % soap_action,
        }
        if token:
            headers['Authorization'] = authorization_header(token)
        request = urlrequest.Request(url, data=body, headers=headers)
        try:
            with urlrequest.urlopen(request, timeout=self.timeout) as response:
                data = response.read()
                if response.headers.get('Content-Encoding') == 'gzip':
                    data = gzip.decompress(data)
                return data
        except HTTPError as error:
            data = error.read()
            raise SATServiceError(
                'SAT HTTP error %s calling %s' % (error.code, soap_action))
        except URLError as error:
            raise SATServiceError('SAT connection error: %s' % error.reason)

    def _parse_request_response(self, xml):
        root = _remove_blank_text(xml)
        result = (
            _first(root, 'SolicitaDescargaEmitidosResult')
            or _first(root, 'SolicitaDescargaRecibidosResult')
            or _first(root, 'SolicitaDescargaFolioResult'))
        if result is None:
            raise SATServiceError('SAT request response has no result node')
        return SATServiceResponse(
            code=result.get('CodEstatus'),
            message=result.get('Mensaje'),
            request_id=result.get('IdSolicitud'),
            requester_rfc=result.get('RfcSolicitante'),
        )

    def _parse_verify_response(self, xml):
        root = _remove_blank_text(xml)
        result = _first(root, 'VerificaSolicitudDescargaResult')
        if result is None:
            raise SATServiceError('SAT verification response has no result node')
        count = result.get('NumeroCFDIs')
        return SATServiceResponse(
            code=result.get('CodEstatus'),
            message=result.get('Mensaje'),
            request_state=result.get('EstadoSolicitud'),
            request_state_code=result.get('CodigoEstadoSolicitud'),
            cfdi_count=int(count) if count and count.isdigit() else None,
            package_ids=tuple(
                _text(node) for node in root.xpath(
                    '//*[local-name()="IdsPaquetes"]') if _text(node)),
        )

    def _parse_download_response(self, xml):
        root = _remove_blank_text(xml)
        header = _first(root, 'respuesta')
        package = _first(root, 'Paquete')
        encoded = _text(package)
        return SATServiceResponse(
            code=header.get('CodEstatus') if header is not None else None,
            message=header.get('Mensaje') if header is not None else None,
            package=base64.b64decode(encoded) if encoded else None,
        )


def build_auth_envelope(signer, created=None):
    created = created or datetime.now(timezone.utc)
    expires = created + timedelta(minutes=5)
    timestamp_id = '_0'
    token_id = 'uuid-%s-1' % uuid.uuid4()

    envelope = etree.Element(
        qname(SOAP_NS, 'Envelope'),
        nsmap={'s': SOAP_NS, 'u': WSU_NS})
    header = etree.SubElement(envelope, qname(SOAP_NS, 'Header'))
    security = etree.SubElement(header, qname(WSSE_NS, 'Security'), {
        qname(SOAP_NS, 'mustUnderstand'): '1',
    }, nsmap={'o': WSSE_NS})
    timestamp = etree.SubElement(security, qname(WSU_NS, 'Timestamp'))
    timestamp.set(qname(WSU_NS, 'Id'), timestamp_id)
    etree.SubElement(timestamp, qname(WSU_NS, 'Created')).text = (
        created.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z')
    etree.SubElement(timestamp, qname(WSU_NS, 'Expires')).text = (
        expires.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z')
    token = etree.SubElement(security, qname(WSSE_NS, 'BinarySecurityToken'), {
        qname(WSU_NS, 'Id'): token_id,
        'ValueType': X509_VALUE_TYPE,
        'EncodingType': BASE64_ENCODING_TYPE,
    })
    token.text = signer.certificate_der_b64
    signer.sign_auth_security(security, timestamp_id, token_id)

    body = etree.SubElement(envelope, qname(SOAP_NS, 'Body'))
    etree.SubElement(body, qname(SAT_AUTH_NS, 'Autentica'))
    return etree.tostring(envelope, xml_declaration=False, encoding='UTF-8')


def soap_envelope(operation):
    envelope = etree.Element(
        qname(SOAP_NS, 'Envelope'),
        nsmap={'soapenv': SOAP_NS, 'des': SAT_DOWNLOAD_NS})
    etree.SubElement(envelope, qname(SOAP_NS, 'Header'))
    body = etree.SubElement(envelope, qname(SOAP_NS, 'Body'))
    body.append(operation)
    return etree.tostring(envelope, xml_declaration=False, encoding='UTF-8')


def build_download_request_node(signer, request_type, values):
    operations = {
        'emitted': 'SolicitaDescargaEmitidos',
        'received': 'SolicitaDescargaRecibidos',
        'folio': 'SolicitaDescargaFolio',
    }
    operation = etree.Element(
        qname(SAT_DOWNLOAD_NS, operations[request_type]),
        nsmap={'des': SAT_DOWNLOAD_NS})
    node = etree.SubElement(operation, qname(SAT_DOWNLOAD_NS, 'solicitud'))
    for name, value in _ordered_request_attributes(request_type, values):
        if value not in (None, ''):
            node.set(name, value)
    if request_type == 'emitted' and values.get('rfc_receptor'):
        receptores = etree.SubElement(
            node, qname(SAT_DOWNLOAD_NS, 'RfcReceptores'))
        for rfc in values['rfc_receptor'].split(',')[:5]:
            etree.SubElement(
                receptores, qname(SAT_DOWNLOAD_NS, 'RfcReceptor')
            ).text = rfc.strip()
    signer.sign_request_node(node)
    return operation, node


def _ordered_request_attributes(request_type, values):
    if request_type == 'folio':
        return (
            ('Folio', values.get('folio')),
            ('RfcSolicitante', values.get('rfc_solicitante')),
        )
    common = (
        ('Complemento', values.get('complemento')),
        ('EstadoComprobante', values.get('estado_comprobante')),
        ('FechaInicial', sat_datetime(values.get('date_from'))),
        ('FechaFinal', sat_datetime(values.get('date_to'))),
        ('RfcEmisor', values.get('rfc_emisor')),
        ('RfcSolicitante', values.get('rfc_solicitante')),
        ('TipoComprobante', values.get('tipo_comprobante')),
        ('TipoSolicitud', values.get('download_type')),
    )
    if request_type == 'received':
        return common + (
            ('RfcReceptor', values.get('rfc_receptor')),
            ('RfcACuentaTerceros', values.get('rfc_a_cuenta_terceros')),
        )
    return common + (
        ('RfcACuentaTerceros', values.get('rfc_a_cuenta_terceros')),
    )


def package_checksum(data):
    return hashlib.sha256(data).hexdigest()
