import ipaddress
from datetime import datetime, timedelta
from pathlib import Path

import environ
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from django.core.management.base import BaseCommand

env = environ.Env()


def generate_selfsigned_cert(
    hostname: str, ip_addresses: list[str] | None = None, key: rsa.RSAPrivateKey | None = None
):
    """Generates self signed certificate for a hostname, and optional IP addresses."""

    # Generate our key
    if key is None:
        key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend(),
        )

    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostname)])

    # best practice seem to be to include the hostname in the SAN,
    # which *SHOULD* mean COMMON_NAME is ignored.
    alt_names: list[x509.GeneralName] = [x509.DNSName(hostname)]

    # allow addressing by IP, for when you don't have real DNS (common in most testing scenarios
    if ip_addresses:
        for addr in ip_addresses:
            # openssl wants DNSnames for ips...
            alt_names.append(x509.DNSName(addr))
            # ... whereas golang's crypto/tls is stricter, and needs IPAddresses
            # note: older versions of cryptography do not understand ip_address objects
            alt_names.append(x509.IPAddress(ipaddress.ip_address(addr)))

    san = x509.SubjectAlternativeName(alt_names)

    # path_len=0 means this cert can only sign itself, not other certs.
    basic_contraints = x509.BasicConstraints(ca=True, path_length=0)
    now = datetime.utcnow()
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(1000)
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=10 * 365))
        .add_extension(basic_contraints, False)
        .add_extension(san, False)
        .sign(key, hashes.SHA256(), default_backend())
    )
    cert_pem = cert.public_bytes(encoding=serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )

    return cert_pem, key_pem


class Command(BaseCommand):
    help = "Generates a self signed SSL certificate."

    def handle(self, *args, **options):
        hostname = env.str("SSL_HOSTNAME")
        ip_addresses: list[str] | None = env.list("SSL_IP_ADDRESSES", default=[])  # type: ignore

        if not hostname:
            raise ValueError("SSL_HOSTNAME must be set.")

        (cert_pem, key_pem) = generate_selfsigned_cert(hostname, ip_addresses)

        do_generate = True

        cert_path = env("SSL_CERT_FILE")
        if Path(cert_path).is_file():
            do_generate = False
            print(f"Cert file {cert_path} already exists. Skipping.")

        key_path = env("SSL_KEY_FILE")
        if Path(key_path).is_file():
            do_generate = False
            print(f"Key file {key_path} already exists. Skipping.")

        if do_generate:
            with open(cert_path, "wb") as cert_file:
                cert_file.write(cert_pem)
                print(f"Generated cert file at {cert_path}.")

            with open(key_path, "wb") as key_file:
                key_file.write(key_pem)
                print(f"Generated key file at {key_path}.")
