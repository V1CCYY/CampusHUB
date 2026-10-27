# Hospedar o CampusHub (Render + TiDB Cloud)

## 0) Segurança (faça primeiro)
Você mostrou a senha do TiDB em print e ela está no `.env` do zip.
No TiDB Cloud: Connect > **Reset Password** e use só a senha nova.
Nunca suba o `.env` nem a pasta `.venv` pro GitHub.

## 1) Substituir arquivos no projeto
Copie para a raiz do CampusHub (sobrescrevendo): `config.py`, `criar_tabelas.py`, `requirements.txt`, `.env.example`.
Apague `.venv/`, `__pycache__/` e `.env` antes de subir ao GitHub.
Confira o `.gitignore`: precisa ter `.venv/`, `.env`, `__pycache__/`.

## 2) Criar as tabelas no TiDB (uma vez, no seu PC)
Crie um `.env` local:
    DB_HOST=gateway01.us-east-1.prod.aws.tidbcloud.com
    DB_PORT=4000
    DB_USER=<seu usuario>.root
    DB_PASSWORD=<senha NOVA>
    DB_NAME=campushub
    DB_SSL=true
    DB_SSL_CA=<caminho do ca.pem baixado no painel do TiDB (Connect > CA cert)>
    SECRET_KEY=<chave aleatória>
Rode:  pip install -r requirements.txt  e depois  python criar_tabelas.py
(O script usa o database.sql, cria o banco `campushub` e ignora o trigger, que o TiDB não suporta. O limite de 4 usuários continua valendo pelo código.)
Login inicial: admin / adm123 (troque depois).

## 3) GitHub
Suba o projeto (sem .env/.venv).

## 4) Render (render.com) > New > Web Service
- Repositório: o seu
- Runtime: Python 3
- Build Command: pip install -r requirements.txt
- Start Command: gunicorn app:app
- Environment Variables: DB_HOST, DB_PORT=4000, DB_USER, DB_PASSWORD, DB_NAME=campushub, DB_SSL=true, SECRET_KEY
  (não precisa DB_SSL_CA: no Render usa o certificado do sistema)
Deploy > o Render te dá um link https://campushub.onrender.com.

Obs.: no plano grátis o site "dorme" após inatividade e a 1ª visita demora ~50s.
