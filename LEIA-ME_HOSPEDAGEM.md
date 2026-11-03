# CampusHub – correção da hospedagem (Render + TiDB)

## O que eu encontrei
- A versão que está no GitHub (último commit `6ddcb06`) **renderiza Inventário, Requisições e Backup sem erro** quando testei com dados de exemplo. Ou seja: o código dessas telas não é o problema. O 500 vem do **banco / ambiente de hospedagem**.
- Causas mais prováveis: tabela ou coluna faltando no TiDB (ex.: `requisicoes.sala_id`), ou conexão velha do pool derrubada pelo TiDB. A lentidão vem de região diferente entre Render e TiDB, do worker padrão do gunicorn (atende 1 requisição por vez) e do plano grátis "dormindo".
- **Atenção:** a pasta que você me enviou está no meio de um `git merge` com conflito (marcadores `<<<<<<<` em `app.py`, `chatbot.py` e em quase todos os templates). **Não faça commit/push desse estado.** Rode `git merge --abort` para voltar ao que está funcionando.

## Passo 1 – Descobrir o erro exato (2 min, no seu PC)
Na pasta do projeto (com o `.env` preenchido):
```
python diagnostico.py
```
Ele mostra a latência até o TiDB, se faltam tabelas/colunas e o erro exato de cada tela (Inventário, Requisições, Backup). Se aparecer `[ERRO]`:
```
python diagnostico.py --corrigir
```
(só cria o que falta; não apaga nada). Rode de novo até tudo ficar `[ OK ]`.

## Passo 2 – Subir os arquivos novos
Copie para a **raiz** do projeto (ao lado do `app.py`), sobrescrevendo:
- `db.py` – descarta conexões velhas, repete a consulta se a conexão caiu, aquece o pool ao iniciar e registra consultas lentas no log.
- `gunicorn.conf.py` – 1 worker com 8 threads, timeout de 120s e logs com o erro real.
- `diagnostico.py` – o script do passo 1.
- `render.yaml` – opcional (só se quiser usar Blueprint).

Faça commit e push. No Render o **Start Command continua `gunicorn app:app`** (o resto vem do `gunicorn.conf.py`).

## Passo 3 – Deixar rápido
1. **Região do Render:** em *Settings > Region*, confira se é **Virginia (US East)**, a mesma do TiDB (`us-east-1`). Se estiver em Oregon ou outra, cada consulta ao banco fica bem mais lenta. A região de um serviço existente **não pode ser alterada**: crie um novo Web Service na região certa, com as mesmas variáveis de ambiente, e use o link novo.
2. **Plano grátis dorme** após ~15 min sem acesso e a primeira visita leva ~50 s. Para a apresentação: abra o site 2–3 minutos antes, ou crie um monitor grátis no UptimeRobot apontando para a página inicial a cada 5 min, ou use o plano Starter só no dia.
3. Opcional: `python criar_indices.py` (ou o `--corrigir` acima) cria os índices que aceleram as consultas.

## Se ainda aparecer "Internal Server Error"
Abra *Render > Logs*: o traceback com o erro real aparece lá. Se quiser ver na tela por pouco tempo, defina `DEBUG_ERROS=true` nas variáveis de ambiente (e remova depois).

## Segurança
O `.env` que veio no zip tem a senha real do TiDB. Faça *Reset Password* no TiDB Cloud, atualize no Render e não envie `.env` nem `.venv` para o GitHub/chat.
