import os


def achar_ca():
    """Acha o certificado CA: DB_SSL_CA (relativo ao projeto) > certs/ca.pem > certifi > certificado do sistema."""
    base = os.path.dirname(os.path.abspath(__file__))
    candidatos = []
    env = os.environ.get("DB_SSL_CA")
    if env:
        candidatos.append(env if os.path.isabs(env) else os.path.join(base, env))
    candidatos.append(os.path.join(base, "certs", "ca.pem"))
    try:
        import certifi
        candidatos.append(certifi.where())
    except ImportError:
        pass
    candidatos.append("/etc/ssl/certs/ca-certificates.crt")
    for c in candidatos:
        if os.path.isfile(c):
            return c
    raise FileNotFoundError(
        "Certificado CA nao encontrado. Rode: python -m pip install certifi"
    )
