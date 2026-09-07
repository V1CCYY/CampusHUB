# CampusHUB

Sistema de gerenciamento de ativos de TI para universidades (usuários, salas/labs,
inventário de peças, requisições, logs). Backend em Flask + MySQL.

## O que mudou nesta versão

O projeto original só tinha rotas Flask retornando HTML estático (sem formulário
funcionando, sem banco). Agora:

- Existe um banco de dados MySQL real (`database.sql`), pronto para importar no
  **MySQL Workbench**.
- O login é funcional, com senha criptografada (hash), sessão e logout.
- Existe um **administrador** e um **usuário comum** já cadastrados para você
  testar (ver credenciais abaixo).
- Um administrador pode cadastrar até **4 usuários** (login + senha próprios).
- **Somente o administrador** cadastra salas/labs, peças e aprova/recusa
  requisições. Usuários comuns visualizam e podem abrir requisições.
- Cada administrador (e a equipe de até 4 usuários que ele criou) só enxerga
  os próprios dados — salas, inventário, requisições e logs de outro
  administrador ficam isolados.

## Credenciais iniciais

| Login | Senha  | Tipo          |
|-------|--------|---------------|
| admin | adm123 | Administrador |
| user  | 123    | Usuário comum |

## 1) Criar o banco de dados (MySQL Workbench)

1. Abra o MySQL Workbench e conecte na sua instância do MySQL.
2. Vá em **File > Open SQL Script...** e selecione o arquivo `database.sql`
   deste projeto.
3. Execute o script inteiro (ícone do raio, ou `Ctrl+Shift+Enter`).
4. Isso cria o schema `campushub`, todas as tabelas, a trigger que impede
   mais de 4 usuários por administrador, e os 2 usuários iniciais (tabela
   acima).

## 2) Configurar a conexão do Flask com o banco (sem expor a senha no código)

Nunca deixe a senha do banco escrita direto dentro do `config.py` — principalmente
se você for subir esse projeto pro GitHub. Use um arquivo `.env`, que fica só na
sua máquina e nunca é versionado (já está no `.gitignore`).

1. Copie o arquivo `.env.example` e renomeie a cópia para `.env`.
2. Abra o `.env` e preencha com os seus dados reais:

```
DB_HOST=localhost
DB_PORT=3306
DB_USER=campushub_app
DB_PASSWORD=sua_senha_real_aqui
DB_NAME=campushub
SECRET_KEY=uma-string-aleatoria-bem-grande
```

3. O `config.py` já lê essas variáveis automaticamente (via `python-dotenv`) —
   você não precisa editar o `config.py` nunca mais.

## 3) Instalar dependências e rodar

```bash
pip install -r requirements.txt
python app.py
```

Acesse `http://127.0.0.1:5000/login` e entre com `admin` / `adm123`.

## Segurança — checklist rápido

- **Nunca** comite o `.env` no Git (ele já está no `.gitignore`). Só o
  `.env.example` (sem valores reais) deve ir pro repositório.
- Use um usuário de banco dedicado (`campushub_app`) com permissão só no
  schema `campushub` — nunca use o `root` na aplicação.
- Troque o `SECRET_KEY` padrão por uma string aleatória longa antes de
  colocar em produção (ex: `python -c "import secrets; print(secrets.token_hex(32))"`).
- Se uma senha ou chave for compartilhada sem querer (print, chat, commit),
  troque essa senha imediatamente — considere-a comprometida.
- Em produção, rode com `debug=False` (o `app.run(debug=True)` no final do
  `app.py` é só para desenvolvimento local).
- No servidor de hospedagem (PythonAnywhere, Railway etc.), defina as
  mesmas variáveis do `.env` na área de configuração deles (variáveis de
  ambiente / "Environment Variables"), nunca direto no código.

## Estrutura do banco

- **usuarios** — administradores e usuários comuns (`tipo`), com
  `criado_por` apontando para o administrador que cadastrou aquele usuário.
- **salas** — laboratórios/salas, sempre vinculadas ao admin que criou
  (`criado_por`).
- **pecas** — itens de inventário/estoque.
- **requisicoes** — pedidos de material feitos por qualquer usuário do time,
  aprovados/recusados pelo admin.
- **movimentacoes** — saídas/entradas de peças (alimenta a Visão Geral).
- **logs** — histórico de ações (login, logout, cadastros, aprovações etc.).

## Próximos passos sugeridos

- Trocar a senha padrão de `admin` e `user` após o primeiro acesso.
- Adicionar recuperação de senha (o link "Esqueceu a senha?" hoje só leva à
  tela de solicitação de acesso).
- Se quiser múltiplos administradores independentes, basta cadastrar outro
  usuário direto no banco com `tipo = 'admin'` e `criado_por = NULL`.
