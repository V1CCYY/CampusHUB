import os
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", "3306")),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "database": os.environ.get("DB_NAME", "campushub"),
}

# TiDB Cloud exige TLS. Ative com DB_SSL=true.
if os.environ.get("DB_SSL", "false").lower() == "true":
    from ssl_util import achar_ca
    DB_CONFIG["ssl_ca"] = achar_ca()
    DB_CONFIG["ssl_verify_cert"] = True

SECRET_KEY = os.environ.get("SECRET_KEY", "troque-esta-chave-em-producao")
