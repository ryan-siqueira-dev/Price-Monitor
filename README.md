# Price Monitor

Aplicação para monitorar o preço de qualquer produto por nome ou por URL. O programa pesquisa
ofertas em várias lojas, mantém o histórico de cada anúncio e pode enviar uma notificação pelo
Telegram quando uma oferta atinge o preço máximo definido pelo usuário.

O projeto oferece três formas de uso:

- CLI para cadastrar produtos, executar buscas e consultar ofertas;
- API REST com documentação Swagger;
- Docker Compose com API e agendador automático a cada 24 horas.

## Funcionalidades

- Cadastro de qualquer produto, como `ThinkPad T14`, `iPhone 15 128GB` ou `PlayStation 5`;
- preço desejado configurado individualmente para cada produto;
- pesquisa por nome em OLX, Amazon, KaBuM e Carrefour;
- monitoramento alternativo de uma URL específica;
- localização global configurável e substituição por produto;
- suporte a produtos novos, usados e recondicionados;
- filtro de acessórios não solicitados e de resultados sem todos os termos da busca;
- histórico de verificações do produto e de preços de cada oferta;
- ofertas identificadas por loja sem duplicação a cada execução;
- alerta para todas as ofertas iguais ou abaixo da meta;
- supressão de alertas repetidos: uma oferta só alerta novamente se ficar mais barata;
- falha isolada por loja: uma fonte bloqueada não interrompe as demais;
- API FastAPI, banco SQLite, migrações Alembic, testes e Docker.

Frete, cupons condicionais, cashback e impostos adicionais não entram na comparação. O preço
considerado é o valor anunciado que o parser conseguiu extrair.

## Como o monitor funciona

1. O usuário cadastra um nome, termo de busca e preço máximo.
2. O monitor consulta todas as fontes habilitadas.
3. Resultados que não contêm todos os termos são descartados.
4. Acessórios são descartados, exceto quando fazem parte do próprio termo pesquisado.
5. As ofertas válidas são salvas e ordenadas pelo menor preço.
6. Se uma oferta estiver dentro da meta, o Telegram é acionado.
7. O preço e o estado de cada oferta ficam registrados para consultas futuras.

Exemplo: para a busca `ThinkPad T14`, um `Teclado para ThinkPad T14` é descartado. Para a busca
`Teclado ThinkPad T14`, o mesmo tipo de resultado passa a ser válido.

## Fontes de busca

| Fonte | Implementação | Autenticação | Observações |
| --- | --- | --- | --- |
| OLX | Navegador e dados estruturados | Sessão opcional | Filtra os anúncios pela cidade e UF configuradas |
| Amazon | Navegador | Sessão opcional | Resultados nacionais |
| KaBuM | Navegador | Sessão opcional | Resultados nacionais, incluindo marketplace |
| Carrefour | Catálogo público | Não exige | Resultados nacionais |

Sites podem alterar HTML, seletores ou mecanismos de proteção sem aviso. Consulte o estado mais
recente de cada fonte em `GET /providers/status`.

## Requisitos

### Uso com Docker — recomendado

- Docker Engine;
- plugin Docker Compose;
- pelo menos 2 GB de espaço livre para a imagem e o Chromium.

### Uso local

- Python 3.11 ou superior;
- `venv` e `pip`;
- Chromium instalado pelo Playwright;
- interface gráfica somente para preparar sessões de navegador.

## Início rápido com Docker

Entre na pasta do projeto:

```bash
cd "/home/ryans/Projects/price monitor"
```

Crie o arquivo de configuração na primeira execução:

```bash
cp .env.example .env
```

Construa e inicie a API e o agendador:

```bash
docker compose up --build -d
```

Verifique os serviços:

```bash
docker compose ps
docker compose logs --tail=50 api scheduler
```

Acesse:

- API: http://127.0.0.1:8000
- Swagger: http://127.0.0.1:8000/docs
- verificação de saúde: http://127.0.0.1:8000/health

Cadastre um produto:

```bash
docker compose exec api price-monitor add \
  --name "ThinkPad T14" \
  --target-price "3000,00"
```

Execute todas as buscas imediatamente:

```bash
docker compose exec api price-monitor run
```

Consulte produtos e ofertas:

```bash
docker compose exec api price-monitor list
docker compose exec api price-monitor offers 1
```

O número `1` é o ID mostrado pelo comando `list`. O agendador também executa uma busca quando é
iniciado e depois repete a operação a cada 24 horas.

Para parar sem apagar o banco:

```bash
docker compose down
```

Para iniciar novamente:

```bash
docker compose up -d
```

## Instalação e execução local

```bash
cd "/home/ryans/Projects/price monitor"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
cp .env.example .env
python -m playwright install chromium
alembic upgrade head
```

No arquivo `.env`, habilite as fontes que usam navegador:

```dotenv
PRICE_MONITOR_USE_BROWSER=true
```

Teste a instalação:

```bash
price-monitor --help
price-monitor list
```

Para iniciar a API local:

```bash
uvicorn price_monitor.api:app --reload
```

Para sair do ambiente virtual:

```bash
deactivate
```

Ativar `.venv` não afeta comandos executados dentro do Docker. Escolha a execução local ou o
Docker para cada comando; não é necessário ativar o ambiente virtual para usar `docker compose`.

## Referência completa do CLI

Mostre os comandos disponíveis:

```bash
price-monitor --help
price-monitor add --help
```

No Docker, acrescente `docker compose exec api` antes de `price-monitor`. Exemplo:

```bash
docker compose exec api price-monitor list
```

### Cadastrar produto por nome

O nome também será usado como termo de busca:

```bash
price-monitor add \
  --name "ThinkPad T14" \
  --target-price "3000,00"
```

Formatos de preço aceitos incluem `3000`, `3000.00` e `3.000,00`.

### Usar um termo de busca diferente do nome

```bash
price-monitor add \
  --name "Notebook para trabalho" \
  --query "Lenovo ThinkPad T14 16GB" \
  --target-price "3500"
```

Use termos específicos, mas evite palavras desnecessárias. Todos os termos relevantes precisam
aparecer no título da oferta.

### Definir localização para um produto

```bash
price-monitor add \
  --name "iPhone 15 128GB" \
  --target-price "3500" \
  --city "Florianópolis" \
  --state SC
```

Essa localização substitui o padrão apenas nesse produto. Ela é especialmente importante para
classificados locais da OLX; lojas nacionais normalmente não filtram por cidade.

### Monitorar uma URL específica

```bash
price-monitor add \
  --name "Produto em uma página específica" \
  --url "https://loja.example/produto" \
  --target-price "500,00"
```

Nesse modo o monitor não pesquisa outras lojas. Ele acessa somente a URL informada e tenta obter
o preço por metadados estruturados ou seletores conhecidos.

### Listar produtos

```bash
price-monitor list
```

A saída mostra ID, nome, meta, último preço, origem, localização e estado ativo/inativo.

### Executar todos os produtos agora

```bash
price-monitor run
```

Exemplo de resultado:

```json
{"checked": 2, "successful": 2, "failed": 0, "alerts_sent": 1}
```

- `checked`: produtos ativos verificados;
- `successful`: produtos concluídos sem erro geral;
- `failed`: produtos cuja verificação falhou;
- `alerts_sent`: mensagens confirmadas pelo Telegram.

Uma loja individual pode falhar e o produto continuar contado como sucesso quando outras fontes
funcionarem.

### Verificar somente um produto

```bash
price-monitor check 1
```

### Consultar ofertas atuais

```bash
price-monitor offers 1
```

As ofertas são exibidas do menor para o maior preço, com loja, condição, título e URL.

### Alterar a localização global

O padrão inicial é Itajaí/SC:

```bash
price-monitor config location \
  --city "Itajaí" \
  --state SC
```

Produtos com cidade e UF próprias não são alterados.

### Executar continuamente sem Docker

```bash
price-monitor daemon --interval-hours 24
```

O daemon executa uma busca imediatamente e aguarda o intervalo antes da próxima. Interrompa com
`Ctrl+C`.

### Preparar autenticação

```bash
price-monitor auth setup olx
price-monitor auth setup amazon
price-monitor auth setup kabum
```

Os comandos que abrem navegador devem ser executados localmente em uma máquina com interface
gráfica, não em uma VPS sem tela.

## Configuração pelo `.env`

Copie `.env.example` para `.env` e altere somente o necessário. O `.env` não deve ser enviado ao
Git porque pode conter segredos.

| Variável | Padrão | Finalidade |
| --- | --- | --- |
| `PRICE_MONITOR_DATABASE_URL` | `sqlite:///data/price_monitor.db` | Endereço do banco |
| `PRICE_MONITOR_REQUEST_TIMEOUT_SECONDS` | `20` | Timeout de requisições HTTP |
| `PRICE_MONITOR_USE_BROWSER` | `false` | Habilita OLX, Amazon e KaBuM localmente |
| `PRICE_MONITOR_BROWSER_TIMEOUT_MS` | `30000` | Timeout do navegador em milissegundos |
| `PRICE_MONITOR_SEARCH_MAX_RESULTS_PER_STORE` | `20` | Limite por loja, entre 1 e 50 |
| `PRICE_MONITOR_DEFAULT_CITY` | `Itajaí` | Cidade inicial antes da configuração no banco |
| `PRICE_MONITOR_DEFAULT_STATE` | `SC` | UF inicial |
| `PRICE_MONITOR_AUTH_DIR` | `data/auth` | Diretório de tokens e perfis do navegador |
| `PRICE_MONITOR_BROWSER_HEADLESS` | `true` | Executa o navegador sem janela durante buscas |
| `PRICE_MONITOR_SCHEDULER_INTERVAL_HOURS` | `24` | Intervalo padrão do daemon local |
| `PRICE_MONITOR_TELEGRAM_BOT_TOKEN` | vazio | Token do bot do Telegram |
| `PRICE_MONITOR_TELEGRAM_CHAT_ID` | vazio | Destino das mensagens |
| `PRICE_MONITOR_LOG_LEVEL` | `INFO` | Nível dos logs |
| `TS_AUTHKEY` | vazio | Chave do Tailscale para a composição VPS |

O `docker-compose.yml` habilita `PRICE_MONITOR_USE_BROWSER=true` dentro dos containers,
independentemente do valor local do `.env`.

## Configurar notificações no Telegram

1. No Telegram, abra uma conversa com `@BotFather`.
2. Execute `/newbot` e conclua a criação.
3. Copie o token fornecido.
4. Envie qualquer mensagem para o bot criado.
5. Consulte `getUpdates` para localizar o ID do chat:

```bash
curl "https://api.telegram.org/botSEU_TOKEN/getUpdates"
```

6. No resultado JSON, procure `message.chat.id`.
7. Preencha o `.env`:

```dotenv
PRICE_MONITOR_TELEGRAM_BOT_TOKEN=seu_token
PRICE_MONITOR_TELEGRAM_CHAT_ID=seu_chat_id
```

Recrie os containers para recarregar o `.env`:

```bash
docker compose up -d --force-recreate
```

Execute uma busca:

```bash
docker compose exec api price-monitor run
```

Se o Telegram não estiver configurado ou rejeitar a mensagem, a oferta não é marcada como
alertada. Assim, ela poderá ser enviada em uma execução posterior depois da correção.

Cada alerta contém produto, loja, condição, preço encontrado, meta e link da oferta.

## Preparar sessões da OLX, Amazon e KaBuM

As buscas podem funcionar sem login, mas uma loja pode solicitar autenticação ou verificação.
Prepare a sessão localmente:

```bash
source .venv/bin/activate
price-monitor auth setup olx
price-monitor auth setup amazon
price-monitor auth setup kabum
```

Uma janela visível do Chromium será aberta. Faça login ou conclua a verificação manualmente e
pressione `Enter` no terminal. O projeto não tenta contornar CAPTCHA.

Os perfis ficam em `data/auth/browser`. Se uma loja continuar bloqueando a automação, o erro será
registrado e as demais fontes continuarão a busca.

## API REST

Com a API em execução, abra http://127.0.0.1:8000/docs para testar todos os endpoints pelo
navegador.

### Endpoints

| Método | Caminho | Função |
| --- | --- | --- |
| `GET` | `/health` | Saúde da API |
| `GET` | `/stores` | Fontes configuradas |
| `POST` | `/products` | Cadastra produto |
| `GET` | `/products` | Lista produtos; aceita `active=true/false` |
| `GET` | `/products/{id}` | Detalhes de um produto |
| `PATCH` | `/products/{id}` | Altera nome, busca, meta, localização ou estado |
| `DELETE` | `/products/{id}` | Exclui produto, ofertas e históricos |
| `POST` | `/products/{id}/check` | Verifica um produto agora |
| `GET` | `/products/{id}/history` | Histórico geral do produto |
| `GET` | `/products/{id}/offers` | Ofertas atuais ordenadas por preço |
| `GET` | `/products/{id}/offers/{offer_id}/history` | Histórico de uma oferta |
| `GET` | `/settings/location` | Localização global |
| `PATCH` | `/settings/location` | Altera localização global |
| `GET` | `/providers/status` | Último sucesso ou erro de cada fonte |
| `POST` | `/checks/run` | Verifica todos os produtos ativos |

### Cadastrar por nome

```bash
curl -X POST http://127.0.0.1:8000/products \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "ThinkPad T14",
    "search_query": "ThinkPad T14",
    "target_price": "3000.00"
  }'
```

`search_query` pode ser omitido; nesse caso, a API usa `name`.

### Cadastrar com localização própria

```bash
curl -X POST http://127.0.0.1:8000/products \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "iPhone 15 128GB",
    "target_price": "3500.00",
    "city": "Florianópolis",
    "state": "SC"
  }'
```

### Alterar meta ou desativar produto

```bash
curl -X PATCH http://127.0.0.1:8000/products/1 \
  -H 'Content-Type: application/json' \
  -d '{"target_price":"3200.00"}'

curl -X PATCH http://127.0.0.1:8000/products/1 \
  -H 'Content-Type: application/json' \
  -d '{"active":false}'
```

### Executar e consultar resultados

```bash
curl -X POST http://127.0.0.1:8000/checks/run
curl http://127.0.0.1:8000/products/1/offers
curl http://127.0.0.1:8000/products/1/history
curl http://127.0.0.1:8000/providers/status
```

### Alterar localização global

```bash
curl -X PATCH http://127.0.0.1:8000/settings/location \
  -H 'Content-Type: application/json' \
  -d '{"city":"Balneário Camboriú","state":"SC"}'
```

## Agendamento

O `docker-compose.yml` possui dois serviços:

- `api`: FastAPI na porta local `8000`;
- `scheduler`: executa o daemon com intervalo de 24 horas.

O agendador começa imediatamente quando o container inicia. Para alterar o intervalo no Docker,
edite `--interval-hours` no comando do serviço `scheduler` em `docker-compose.yml` e
`docker-compose.vps.yml`, depois recrie o serviço:

```bash
docker compose up -d --build --force-recreate scheduler
```

Logs do agendador:

```bash
docker compose logs -f scheduler
```

## Banco, dados e backup

Arquivos persistentes:

```text
data/
├── price_monitor.db
└── auth/
    └── browser/
```

O banco contém produtos, verificações, ofertas, históricos, configurações e estado dos
provedores. O diretório `data` está ignorado pelo Git e é montado em `/app/data` no Docker.

Faça backup com os containers parados para obter uma cópia consistente:

```bash
docker compose stop
cp -a data "data-backup-$(date +%Y%m%d-%H%M%S)"
docker compose start
```

Restaure substituindo `data` por uma cópia válida enquanto os containers estiverem parados.

As migrações são executadas automaticamente ao iniciar a API ou usar o CLI. Execução manual:

```bash
source .venv/bin/activate
alembic upgrade head
alembic check
```

## VPS privada com Tailscale

O arquivo `docker-compose.vps.yml` executa a API dentro da rede do container Tailscale e não
publica a porta `8000` diretamente na internet.

1. Instale Docker e Docker Compose na VPS.
2. Copie o projeto e o `.env` para a VPS.
3. Prepare as autenticações em uma máquina com interface gráfica.
4. Copie `data/auth` para a VPS preservando as permissões.
5. Crie uma chave de autenticação do Tailscale e defina no `.env`:

```dotenv
TS_AUTHKEY=tskey-auth-...
```

6. Inicie:

```bash
docker compose -f docker-compose.vps.yml up --build -d
```

7. Consulte o estado:

```bash
docker compose -f docker-compose.vps.yml ps
docker compose -f docker-compose.vps.yml logs -f api scheduler tailscale
```

A API ficará disponível no IP Tailscale do container `price-monitor`, na porta `8000`. Não
publique a API sem autenticação diretamente na internet.

## Testes e validação

```bash
source .venv/bin/activate
pytest
ruff check .
ruff format --check .
python -m compileall price_monitor tests alembic
pip check
alembic check
docker compose config --quiet
docker compose -f docker-compose.vps.yml config --quiet
```

Build e verificação da imagem:

```bash
docker compose build
docker compose up -d
docker compose ps
curl --fail http://127.0.0.1:8000/health
```

## Solução de problemas

### Permissão negada ao usar Docker

Se o usuário já foi adicionado ao grupo `docker`, encerre a sessão do sistema e entre novamente.
Como alternativa temporária, use `sudo`:

```bash
sudo docker compose ps
sudo docker compose exec api price-monitor run
```

### `ModuleNotFoundError: No module named 'price_monitor.cli'`

A imagem está desatualizada ou foi construída antes da instalação final do pacote. Reconstrua e
recrie os containers:

```bash
docker compose build
docker compose up -d --force-recreate
docker compose exec api price-monitor --help
```

Se o cache continuar preservando uma imagem inválida:

```bash
docker compose build --no-cache
docker compose up -d --force-recreate
```

### Telegram mostra `alerts_sent: 0`

Isso pode significar:

- nenhuma oferta atingiu a meta;
- token ou chat ID não configurado;
- Telegram rejeitou a mensagem;
- aquela oferta já foi alertada pelo mesmo preço.

Verifique o `.env` e os logs:

```bash
docker compose logs --tail=100 api scheduler
```

### Nenhuma oferta encontrada

- confira se o termo não está específico demais;
- confirme cidade e UF para anúncios da OLX;
- veja erros em `/providers/status`;
- habilite `PRICE_MONITOR_USE_BROWSER=true` no uso local;
- use `price-monitor check ID` para testar somente um produto;
- consulte os logs do navegador e do agendador.

### Chromium não encontrado no uso local

```bash
source .venv/bin/activate
python -m playwright install chromium
```

### Banco SQLite sem permissão de escrita

Confira o proprietário de `data`:

```bash
ls -ld data data/price_monitor.db
```

O usuário local e o usuário `1000` do container precisam conseguir escrever nesse diretório. Não
execute comandos de aplicação alternando desnecessariamente entre usuário normal e `root`.

### Porta 8000 já está em uso

```bash
docker compose ps
ss -ltnp | grep ':8000'
```

Pare o processo conflitante ou altere a porta publicada em `docker-compose.yml`.

## Segurança e limitações

- A API não possui login; mantenha o bind local ou use Tailscale.
- Nunca envie `.env`, tokens do Telegram ou `data/auth` para o Git.
- O projeto não contorna CAPTCHA nem mecanismos de proteção.
- Scraping por navegador pode quebrar quando uma loja altera a página.
- A classificação de acessórios é heurística e deve ser revisada para novos tipos de produto.
- Resultados de marketplace podem ser de vendedores terceiros.
- Compare condição, garantia, reputação, frete e descrição antes da compra.
- O monitor informa ofertas; ele não realiza compras automaticamente.

## Stack

- Python 3.11+
- FastAPI e Uvicorn
- SQLAlchemy e SQLite
- Alembic
- HTTPX
- BeautifulSoup
- Playwright e Chromium
- Telegram Bot API
- Pytest
- Ruff
- Docker e Docker Compose
- Tailscale no cenário VPS

## Estrutura principal

```text
price_monitor/
├── api.py                 # endpoints FastAPI
├── cli.py                 # comandos do terminal
├── config.py              # variáveis do .env
├── db.py                  # engine, sessões e migrações
├── models.py              # tabelas SQLAlchemy
├── notifications/         # Telegram
├── scrapers/              # monitoramento por URL
├── search/                # provedores, filtros e autenticação
└── services/              # monitor, alertas e configurações

alembic/                   # migrações do banco
tests/                     # testes automatizados
docker-compose.yml         # execução local
docker-compose.vps.yml     # execução privada com Tailscale
```
