# Price Monitor

Monitor de qualquer produto por nome e preço desejado. A cada execução, o sistema pesquisa
Mercado Livre, OLX, Amazon, Magalu, KaBuM e Carrefour, salva as ofertas e envia alertas pelo
Telegram quando o preço anunciado chega à meta.

## Como funciona

1. Cadastre `ThinkPad T14` com o preço máximo que deseja pagar.
2. O monitor busca o termo nas lojas configuradas.
3. Resultados sem todos os termos e acessórios não solicitados são descartados.
4. Cada oferta mantém histórico próprio de preço.
5. Todas as ofertas abaixo da meta são alertadas uma vez; uma oferta só gera novo alerta se
   ficar ainda mais barata.

Produtos novos, usados e recondicionados são aceitos. Frete não entra na comparação.

## Instalação local

Requer Python 3.11 ou superior.

```bash
cd "/home/ryans/Projects/price monitor"
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
python -m playwright install chromium
alembic upgrade head
```

O padrão de localização é Itajaí/SC. Para alterar:

```bash
price-monitor config location --city "Florianópolis" --state SC
```

## Cadastrar e verificar produtos

```bash
price-monitor add --name "ThinkPad T14" --target-price "3000,00"
price-monitor run
price-monitor offers 1
price-monitor list
```

Uma localização diferente pode ser definida apenas para um produto:

```bash
price-monitor add \
  --name "iPhone 15 128GB" \
  --target-price "3500,00" \
  --city "Florianópolis" \
  --state SC
```

O modo antigo por URL continua disponível:

```bash
price-monitor add \
  --name "Produto específico" \
  --url "https://loja.example/produto" \
  --target-price "500,00"
```

## Autenticação das lojas

### Mercado Livre

Crie uma aplicação no portal de desenvolvedores e configure no `.env`:

```dotenv
PRICE_MONITOR_MERCADO_LIVRE_CLIENT_ID=
PRICE_MONITOR_MERCADO_LIVRE_CLIENT_SECRET=
PRICE_MONITOR_MERCADO_LIVRE_REDIRECT_URI=http://127.0.0.1:8766/callback
```

Depois execute:

```bash
price-monitor auth setup mercado-livre
```

O navegador será aberto para autorização. Tokens e renovações são salvos em `data/auth`.

### OLX, Amazon, Magalu e KaBuM

Prepare uma sessão local quando uma loja solicitar login ou verificação:

```bash
price-monitor auth setup olx
price-monitor auth setup amazon
price-monitor auth setup magalu
price-monitor auth setup kabum
```

O comando abre um navegador visível. Conclua o login ou desafio e pressione Enter no terminal.
Nenhum CAPTCHA é contornado. Se uma loja bloquear a automação, as demais continuam funcionando.

## Telegram

Preencha no `.env`:

```dotenv
PRICE_MONITOR_TELEGRAM_BOT_TOKEN=token_do_bot
PRICE_MONITOR_TELEGRAM_CHAT_ID=id_do_chat
```

Cada alerta contém produto, loja, condição, preço, meta e link da oferta.

## API

```bash
uvicorn price_monitor.api:app --reload
```

- API: http://127.0.0.1:8000
- Swagger: http://127.0.0.1:8000/docs

Exemplo:

```bash
curl -X POST http://127.0.0.1:8000/products \
  -H 'Content-Type: application/json' \
  -d '{"name":"ThinkPad T14","target_price":"3000.00"}'

curl -X POST http://127.0.0.1:8000/products/1/check
curl http://127.0.0.1:8000/products/1/offers
curl http://127.0.0.1:8000/providers/status
```

## Docker local

```bash
docker compose up --build -d
```

O serviço `scheduler` executa a busca a cada 24 horas. Banco e credenciais ficam em `./data`,
montado em `/app/data` nos containers.

## VPS privada com Tailscale

1. Faça a autenticação das lojas em uma máquina com interface gráfica.
2. Copie `.env` e `data/auth` com `scp` para a VPS, mantendo permissões restritas.
3. Crie uma chave de autenticação no Tailscale e defina `TS_AUTHKEY` no `.env`.
4. Execute:

```bash
docker compose -f docker-compose.vps.yml up --build -d
```

A API fica disponível apenas no IP Tailscale do container, na porta `8000`. Não publique essa
porta diretamente na internet.

## Banco e testes

```bash
alembic upgrade head
pytest
ruff check .
ruff format --check .
python -m compileall price_monitor tests alembic
```
