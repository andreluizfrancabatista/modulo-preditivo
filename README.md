# Módulo Preditivo — Climacta

Microserviço Django/DRF que estima o **VDS diário**, o **SRVDS acumulado** e emite **recomendações de pulverização** para os próximos 1 a 7 dias, por talhão, integrando a API Climacta com a API OpenWeatherMap.

---

## Sumário

- [Arquitetura](#arquitetura)
- [Pré-requisitos](#pré-requisitos)
- [Configuração](#configuração)
- [Subindo com Docker Compose](#subindo-com-docker-compose)
- [Endpoints](#endpoints)
- [Exemplos de resposta](#exemplos-de-resposta)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Integração com o projeto principal](#integração-com-o-projeto-principal)

---

## Arquitetura

```
Cliente
  │
  ├── GET /preditivo/api/v1/predicao/
  ├── GET /preditivo/api/v1/predicao/detalhada/
  └── GET /preditivo/exemplo/
        │
        ▼
  [Django + DRF] preditivo/views.py
        │
        ├── services/climacta.py  ──► API Climacta (talhões, VDS histórico, tabela, threshold)
        ├── services/owm.py       ──► OpenWeatherMap /forecast (PMF estimado por dia)
        ├── services/vds.py       ──► Cálculo VDS, SRVDS, AD, recomendação
        └── services/pipeline.py  ──► Orquestra tudo e retorna resultado
```

O módulo é **stateless** — não possui banco de dados próprio. Toda persistência fica na API Climacta existente.

---

## Pré-requisitos

- Docker e Docker Compose instalados
- Rede Docker `climacta_network` já existente (criada pelo projeto principal)
- Credenciais da API Climacta e chave OpenWeatherMap

---

## Configuração

Copie o arquivo de exemplo e preencha as variáveis:

```bash
cp .env.example .env
nano .env
```

| Variável        | Descrição                                                           |
|-----------------|---------------------------------------------------------------------|
| `BASE_URL`      | URL base da API Climacta (ex: `https://api.climacta.agr.br/api/v1`) |
| `LOGIN`         | Usuário de autenticação Climacta                                    |
| `SENHA`         | Senha de autenticação Climacta                                      |
| `APPID`         | Chave de API do OpenWeatherMap                                      |
| `SECRET_KEY`    | Chave secreta Django (gere uma segura em produção)                  |
| `DEBUG`         | `True` para desenvolvimento, `False` para produção                  |
| `ALLOWED_HOSTS` | Hosts permitidos (ex: `*` ou `api.climacta.agr.br`)                 |

> O `.env` está no `.gitignore` e nunca é sobrescrito pelo `git pull`.

---

## Subindo com Docker Compose

### Primeira vez

```bash
# 1. Garantir que a rede existe (pular se já criada pelo projeto principal)
docker network create climacta_network

# 2. Clonar e configurar
git clone https://github.com/seu-usuario/modulo-preditivo.git
cd modulo-preditivo
cp .env.example .env
nano .env   # preencher variáveis

# 3. Build e subida
docker compose up -d --build
```

### Atualizações

```bash
cd modulo-preditivo
git pull
docker compose up -d --build
```

### Outros comandos úteis

```bash
docker compose logs -f preditivo   # logs em tempo real
docker compose restart             # reiniciar sem rebuild
docker compose stop                # parar sem remover
docker compose down                # remover container
```

---

## Endpoints

### `GET /api/v1/predicao/`

Estimativa básica de VDS, SRVDS e recomendação de pulverização.

### `GET /api/v1/predicao/detalhada/`

Mesmas informações da rota básica com adição do array `methods` em cada entrada da série, contendo `method_a`, `method_b`, `method_c` e `method_d` no mesmo formato retornado por `/diseases/daily-records/`, acrescidos dos campos `ad` e `am`.

### `GET /exemplo/`

Dashboard HTML com tabela interativa de talhões × dias, bolinhas coloridas por recomendação e tooltip com detalhes ao clicar.

---

### Query params (compartilhados pelas rotas da API)

| Parâmetro | Tipo    | Padrão | Descrição                                          |
|-----------|---------|--------|----------------------------------------------------|
| `field`   | inteiro | —      | Filtra por id do talhão (ex: `?field=177`)         |
| `farm`    | inteiro | —      | Filtra por id da fazenda (ex: `?farm=52`)          |
| `days`    | inteiro | `7`    | Horizonte de previsão: 1 a 7 dias (ex: `?days=3`) |

Os parâmetros são combináveis: `?farm=52&field=177&days=5`

### Códigos de resposta

| Código | Situação                                       |
|--------|------------------------------------------------|
| `200`  | Sucesso                                        |
| `400`  | Parâmetro inválido (`days` fora de 1–7, etc.)  |
| `502`  | Erro HTTP ao chamar API externa                |
| `504`  | Timeout ao chamar API externa                  |
| `500`  | Erro interno inesperado                        |

---

## Exemplos de resposta

### `GET /api/v1/predicao/?field=177&days=3`

```json
{
  "count": 1,
  "days": 3,
  "filters": { "field": 177, "farm": null },
  "results": [
    {
      "id": 177,
      "talhao": "Marialva",
      "fazenda": 52,
      "cultivo": "milho",
      "serie": [
        {
          "date": "2026-04-07",
          "vds_estimado": 2,
          "pmf_horas": 12.0,
          "avg_temp": 22.4,
          "chuva_mm": 4.2,
          "dia_chuvoso": false,
          "pmf_periodos": [ ... ],
          "estimado": true,
          "srvds": 6,
          "chuva_last_7": { "dias_chuva": 1, "label": "< 4" },
          "recomendacao": {
            "codigo": 1,
            "texto": "Pulverizar a cada 7 dias",
            "srvds_label": "5 a 6",
            "chuva_label": "< 4"
          }
        }
      ]
    }
  ]
}
```

### `GET /api/v1/predicao/detalhada/?field=177&days=3`

Mesmo retorno acima, com `methods` adicionado em cada entrada da `serie`:

```json
"methods": {
  "method_a": {
    "up_dia": 7.5067,
    "vds_dia": 2,
    "srup": 42.1,
    "srvds": 6,
    "teve_aplicacao": false,
    "sob_protecao": false,
    "ad": 0,
    "am": null
  },
  "method_b": {
    "vds_dia": null,
    "svds": null,
    "teve_aplicacao": false,
    "sob_protecao": false,
    "ad": null,
    "am": null
  },
  "method_c": {
    "vds_dia": 2,
    "svds": 18.0,
    "srvds": 6,
    "teve_aplicacao": false,
    "sob_protecao": false,
    "ad": 0,
    "am": null
  },
  "method_d": {
    "df": null,
    "svds": null,
    "srdf": null,
    "vds_day": null,
    "accumulated_rain": null,
    "is_rainy_day": false,
    "rain_days_count": null,
    "hours_high_humidity": null,
    "hours_low_humidity": null,
    "teve_aplicacao": false,
    "sob_protecao": false,
    "ad": null,
    "am": null
  }
}
```

---

## Campos da `serie[]`

| Campo           | Presente em          | Descrição                                                         |
|-----------------|----------------------|-------------------------------------------------------------------|
| `date`          | histórico + estimado | Data do registro (YYYY-MM-DD)                                     |
| `vds_estimado`  | histórico + estimado | VDS do dia (0, 1, 2 ou 3)                                         |
| `pmf_horas`     | estimado             | Total de horas de molhamento foliar estimado                      |
| `avg_temp`      | estimado             | Temperatura média do dia (°C)                                     |
| `chuva_mm`      | histórico + estimado | Precipitação acumulada no dia (mm)                                |
| `dia_chuvoso`   | histórico + estimado | `true` se `chuva_mm > 30`                                         |
| `pmf_periodos`  | estimado             | Lista de períodos de molhamento (mesmo formato `/daily-records/`) |
| `estimado`      | ambos                | `false` = dado real da API · `true` = estimativa OWM              |
| `srvds`         | histórico + estimado | Soma acumulada do VDS nos últimos 7 dias                          |
| `chuva_last_7`  | histórico + estimado | Dias chuvosos e label da faixa nos últimos 7 dias                 |
| `recomendacao`  | histórico + estimado | `codigo`, `texto`, `srvds_label`, `chuva_label`                   |
| `methods`       | histórico + estimado | Apenas na rota `/detalhada/` — ver tabela abaixo                  |

---

## Campos de `methods` (rota `/detalhada/`)

### method_a

| Campo            | Tipo    | Descrição                                                                 |
|------------------|---------|---------------------------------------------------------------------------|
| `up_dia`         | float   | `0` se `vds_dia == 0`, senão `avg_temp / 2.984`                           |
| `vds_dia`        | int     | Mesmo que `vds_estimado`                                                  |
| `srup`           | float   | Soma acumulada de `up_dia` nos últimos 7 dias                             |
| `srvds`          | int     | Soma acumulada de `vds_dia` nos últimos 7 dias                            |
| `teve_aplicacao` | bool    | Sempre `false`                                                            |
| `sob_protecao`   | bool    | Sempre `false`                                                            |
| `ad`             | int     | Alerta de decisão: `-1`, `0` ou `1` (ver matriz AD abaixo)               |
| `am`             | null    | Sempre `null` (aguardando especificação)                                  |

### method_b

Sem modelo preditivo implementado. Todos os campos numéricos são `null`.

| Campo            | Tipo | Descrição      |
|------------------|------|----------------|
| `vds_dia`        | null | Sempre `null`  |
| `svds`           | null | Sempre `null`  |
| `teve_aplicacao` | bool | Sempre `false` |
| `sob_protecao`   | bool | Sempre `false` |
| `ad`             | null | Sempre `null`  |
| `am`             | null | Sempre `null`  |

### method_c

| Campo            | Tipo  | Descrição                                               |
|------------------|-------|---------------------------------------------------------|
| `vds_dia`        | int   | Mesmo que `vds_estimado`                                |
| `svds`           | float | Soma acumulada irrestrita de todos os `vds` disponíveis |
| `srvds`          | int   | Mesmo que `method_a.srvds`                              |
| `teve_aplicacao` | bool  | Sempre `false`                                          |
| `sob_protecao`   | bool  | Sempre `false`                                          |
| `ad`             | int   | Mesmo que `method_a.ad` (compartilha `srup` e `srvds`)  |
| `am`             | null  | Sempre `null` (aguardando especificação)                |

### method_d

Aguardando especificação. Todos os campos numéricos são `null`, booleanos são `false`.

---

## Matriz AD (Alerta de Decisão)

Usada por `method_a.ad` e `method_c.ad`.

|                  | SRUP ≤ 60 | SRUP 61–80 | SRUP > 80 |
|------------------|:---------:|:----------:|:---------:|
| **SRVDS < 9**    |    −1     |     0      |     1     |
| **SRVDS 9–15**   |     0     |     0      |     1     |
| **SRVDS > 15**   |     1     |     1      |     1     |

---

## Códigos de recomendação

| Código | Texto                    |
|--------|--------------------------|
| `−1`   | Não pulverizar           |
| `0`    | Alerta                   |
| `1`    | Pulverizar a cada 7 dias |
| `2`    | Pulverizar a cada 5 dias |

---

## Estrutura do projeto

```
modulo-preditivo/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── .gitignore
├── manage.py
├── README.md
├── core/
│   ├── settings.py        # Django sem banco de dados (stateless)
│   ├── urls.py
│   └── wsgi.py
└── preditivo/
    ├── urls.py            # 3 rotas: predicao/, predicao/detalhada/, exemplo/
    ├── views.py           # PredicaoView, PredicaoDetalhadaView, exemplo_view
    ├── templates/
    │   └── preditivo/
    │       └── exemplo.html   # dashboard interativo
    └── services/
        ├── climacta.py    # auth, talhões, histórico VDS, tabela, threshold
        ├── owm.py         # previsão OWM + estimativa PMF diária
        ├── vds.py         # calcular_vds, calcular_ad, calcular_serie, calcular_serie_detalhada
        └── pipeline.py    # executar() e executar_detalhado()
```

---

## Integração com o projeto principal

O serviço expõe a porta `8001` e está na rede `climacta_network`.

### Nginx (proxy reverso)

Adicione dentro do `server` block SSL existente:

```nginx
location /preditivo/ {
    proxy_pass         http://localhost:8001/;
    proxy_set_header   Host $host;
    proxy_set_header   X-Real-IP $remote_addr;
    proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header   X-Forwarded-Proto $scheme;
    proxy_read_timeout 60s;
}
```

Após editar:

```bash
nginx -t && systemctl reload nginx
```

### URLs públicas após configuração

```
https://seudominio.com/preditivo/api/v1/predicao/
https://seudominio.com/preditivo/api/v1/predicao/detalhada/
https://seudominio.com/preditivo/exemplo/
```

### Docker Compose do projeto principal

```yaml
services:
  preditivo:
    image: climacta_preditivo
    env_file: ./modulo-preditivo/.env
    networks:
      - climacta_network
```
