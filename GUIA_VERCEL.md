# CampusHub na Vercel (Flask + TiDB Cloud)

## 0) Segurança primeiro
O `.env` que veio no zip tem a senha real do TiDB. No TiDB Cloud: Connect > **Reset Password**.
Nunca suba `.env` nem `.venv` pro GitHub (o `.gitignore` e o `.vercelignore` já bloqueiam).

## 1) Criar os índices (uma vez, no seu PC, com o .env local)
    pip install -r requirements.txt
    python criar_indices.py
Pode rodar de novo sem problema (ele avisa "ja existe").

## 2) GitHub
Suba o projeto (sem `.env`, `.venv`). A pasta `Documentos/` é opcional.

## 3) Vercel
1. vercel.com > Add New > Project > importe o repositório (detecta Flask sozinho).
2. Environment Variables:
   DB_HOST, DB_PORT=4000, DB_USER, DB_PASSWORD, DB_NAME=campushub, DB_SSL=true, SECRET_KEY=<chave aleatória>
   (NÃO precisa de DB_SSL_CA)
3. Deploy.

Se aparecer "Internal Server Error": adicione DEBUG_ERROS=true, faça Redeploy e o erro real aparece na tela.
Depois remova a variável.

## Por que ficou mais rápido
- Região da função = `iad1` (Virgínia), a mesma do seu TiDB (`us-east-1`): consulta ao banco quase sem latência.
- Conexão com o banco reaproveitada entre requisições (antes abria TLS novo a cada clique).
- Visão Geral: 15 consultas -> 8. Backup: não baixa mais o banco inteiro só pra contar.
- Chatbot: o menu inicial abre sem ir ao servidor.
- Fundo de partículas bem mais leve e sem `backdrop-filter` (blur) sobre o canvas animado.

## Pontos de atenção
- Arquivos estáticos ficam em `public/static/` (a Vercel só serve estáticos dessa pasta; o Flask local usa a mesma).
- Restaurar backup: a Vercel limita o corpo da requisição a ~4,5 MB.
- Plano Hobby da Vercel é para uso pessoal/não comercial.
