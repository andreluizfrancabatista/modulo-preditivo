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
  └── GET /api/v1/predicao/?field=177&days=7
        │
        ▼
  [Django + DRF] preditivo/views.py
        │
        ├── services/climacta.py  ──► API Climacta (talhões, VDS histórico, tabela, threshold)
        ├── services/owm.py       ──► OpenWeatherMap /forecast (PMF estimado)
        ├── services/vds.py       ──► Cálculo VDS, SRVDS, recomendação
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
```

| Variável     | Descrição                                          |
|--------------|----------------------------------------------------|
| `BASE_URL`   | URL base da API Climacta (ex: `https://api.climacta.agr.br/api/v1`) |
| `LOGIN`      | Usuário de autenticação Climacta                   |
| `SENHA`      | Senha de autenticação Climacta                     |
| `APPID`      | Chave de API do OpenWeatherMap                     |
| `SECRET_KEY` | Chave secreta Django (gere uma em produção)        |
| `DEBUG`      | `True` para desenvolvimento, `False` para produção |
| `ALLOWED_HOSTS` | Hosts permitidos (ex: `*` ou `api.climacta.agr.br`) |

---

## Subindo com Docker Compose

### 1. Garantir que a rede existe

```bash
docker network create climacta_network
```

> Se a rede já foi criada pelo projeto principal, pule este passo.

### 2. Build e subida

```bash
docker compose up -d --build
```

### 3. Verificar logs

```bash
docker compose logs -f preditivo
```

### 4. Testar

```bash
curl http://localhost:8001/api/v1/predicao/?field=177&days=3
```

---

## Endpoints

### `GET /api/v1/predicao/`

Retorna a estimativa preditiva de VDS, SRVDS e recomendação de pulverização.

#### Query params

| Parâmetro | Tipo    | Padrão | Descrição                                        |
|-----------|---------|--------|--------------------------------------------------|
| `field`   | inteiro | —      | Filtra por id do talhão (ex: `?field=177`)       |
| `farm`    | inteiro | —      | Filtra por id da fazenda (ex: `?farm=52`)        |
| `days`    | inteiro | `7`    | Horizonte de previsão: 1 a 7 dias (ex: `?days=3`) |

Os parâmetros são combináveis: `?farm=52&days=5`

#### Códigos de resposta

| Código | Situação                                      |
|--------|-----------------------------------------------|
| `200`  | Sucesso                                       |
| `400`  | Parâmetro inválido (`days` fora de 1–7, etc.) |
| `502`  | Erro HTTP ao chamar API externa               |
| `504`  | Timeout ao chamar API externa                 |
| `500`  | Erro interno inesperado                       |

---

## Exemplos de resposta

### Requisição

```
GET /api/v1/predicao/?field=177&days=3
```

### Resposta `200 OK`

```json
{
  "count": 1,
  "days": 3,
  "filters": {
    "field": 177,
    "farm": null
  },
  "results": [
    {
      "id": 177,
      "talhao": "Marialva",
      "fazenda": 52,
      "cultivo": "milho",
      "serie": [
        {
          "date": "2026-03-31",
          "vds_estimado": 3,
          "pmf_horas": null,
          "avg_temp": null,
          "chuva_mm": 18.4,
          "dia_chuvoso": false,
          "estimado": false,
          "srvds": 3,
          "chuva_last_7": {
            "dias_chuva": 0,
            "label": "< 4"
          },
          "recomendacao": {
            "codigo": 0,
            "texto": "Alerta",
            "srvds_label": "< 4",
            "chuva_label": "< 4"
          }
        },
        {
          "date": "2026-04-07",
          "vds_estimado": 1,
          "pmf_horas": 12.0,
          "avg_temp": 22.4,
          "chuva_mm": 4.2,
          "dia_chuvoso": false,
          "pmf_periodos": [
            {
              "period_number": 1,
              "start_time": "2026-04-07T03:00:00+00:00",
              "end_time": "2026-04-07T09:00:00+00:00",
              "duration_hours": 9.0,
              "avg_temperature": 21.5,
              "teve_ponto_orvalho": false,
              "estimado": true
            }
          ],
          "estimado": true,
          "srvds": 6,
          "chuva_last_7": {
            "dias_chuva": 0,
            "label": "< 4"
          },
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

### Campos da `serie[]`

| Campo           | Presente em          | Descrição                                                   |
|-----------------|----------------------|-------------------------------------------------------------|
| `date`          | histórico + estimado | Data do registro (YYYY-MM-DD)                               |
| `vds_estimado`  | histórico + estimado | VDS do dia (0, 1, 2 ou 3)                                   |
| `pmf_horas`     | estimado             | Total de horas de molhamento foliar estimado                |
| `avg_temp`      | estimado             | Temperatura média do dia (°C)                               |
| `chuva_mm`      | histórico + estimado | Precipitação acumulada no dia (mm)                          |
| `dia_chuvoso`   | histórico + estimado | `true` se chuva_mm > 30 mm                                  |
| `pmf_periodos`  | estimado             | Lista de períodos de molhamento (mesmo formato /daily-records/) |
| `estimado`      | ambos                | `false` = dado real da API; `true` = estimativa OWM         |
| `srvds`         | histórico + estimado | Soma acumulada do VDS nos últimos 7 dias                    |
| `chuva_last_7`  | histórico + estimado | Dias chuvosos e label da faixa nos últimos 7 dias           |
| `recomendacao`  | histórico + estimado | `codigo`, `texto`, `srvds_label`, `chuva_label`             |

### Códigos de recomendação

| Código | Texto                     |
|--------|---------------------------|
| `-1`   | Não pulverizar            |
| `0`    | Alerta                    |
| `1`    | Pulverizar a cada 7 dias  |
| `2`    | Pulverizar a cada 5 dias  |

---

## Estrutura do projeto

```
modulo-preditivo/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── manage.py
├── core/
│   ├── settings.py        # configurações Django (sem banco de dados)
│   ├── urls.py            # rota raiz → preditivo.urls
│   └── wsgi.py
└── preditivo/
    ├── urls.py            # GET /api/v1/predicao/
    ├── views.py           # PredicaoView — validação e resposta HTTP
    └── services/
        ├── climacta.py    # autenticação, talhões, histórico VDS, tabela, threshold
        ├── owm.py         # previsão OWM + estimativa PMF diária
        ├── vds.py         # cálculo VDS, SRVDS, recomendação
        └── pipeline.py    # orquestra todos os serviços
```

---

## Integração com o projeto principal

O serviço expõe a porta `8001` e está na rede `climacta_network`.  
O Nginx (ou o gateway do projeto principal) pode fazer proxy para ele:

```nginx
location /api/v1/predicao/ {
    proxy_pass http://climacta_preditivo:8001;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

Ou via `docker-compose.yml` do projeto principal, adicionando o serviço à mesma rede:

```yaml
services:
  preditivo:
    image: climacta_preditivo   # após o build local
    env_file: ./modulo-preditivo/.env
    networks:
      - climacta_network
```
