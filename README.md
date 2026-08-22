# 🚀 SCRAPER.LINK v3

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Latest-green)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue)
![Redis](https://img.shields.io/badge/Redis-Latest-red)
![RabbitMQ](https://img.shields.io/badge/RabbitMQ-Latest-orange)
![Docker](https://img.shields.io/badge/Docker-Ready-blue)
![License](https://img.shields.io/badge/License-MIT-green)

**Plataforma profissional de mineração de leads e enriquecimento de dados comerciais**

Extraia telefones, WhatsApp, e-mails, websites e informações comerciais de Google Maps, Instagram, Facebook e sites utilizando IA, Playwright e processamento distribuído.

</div>

---

# 📌 Visão Geral

SCRAPER.LINK é uma plataforma SaaS desenvolvida para automatizar a descoberta e enriquecimento de contatos comerciais.

A solução permite:

* Gerar leads através do Google Maps
* Extrair telefones comerciais
* Encontrar WhatsApps
* Encontrar e-mails públicos
* Descobrir websites
* Enriquecer informações utilizando IA
* Exportar resultados para CSV e XLSX
* Integrar com n8n, Make e CRMs

---

# 🎯 Casos de Uso

* Agências de Marketing
* SDRs
* Inside Sales
* Empresas de Geração de Leads
* Automação Comercial
* CRM
* Prospecção B2B
* Inteligência Comercial
* Franquias
* Consultorias

---

# ⚡ Funcionalidades

## Google Maps

* Busca por segmento
* Busca por cidade
* Busca por CEP
* Busca por estado
* Extração de telefone
* Extração de website
* Extração de avaliações
* Extração de endereço

## Instagram

* Extração de telefone
* Extração de e-mail
* Extração de bio
* Extração de links
* Extração de WhatsApp

## Facebook

* Extração de telefone
* Extração de website
* Extração de e-mail

## Website Scanner

* Busca por telefone
* Busca por WhatsApp
* Busca por e-mail
* Busca por redes sociais

## IA

* Groq
* OpenAI
* Gemini

---

# 🏗 Arquitetura

```text
Cliente
   │
   ▼
Traefik
   │
   ▼
FastAPI
   │
   ├── Auth JWT
   │
   ├── API Keys
   │
   ├── Credits System
   │
   ├── Google Maps Engine
   │
   ├── Instagram Engine
   │
   ├── Facebook Engine
   │
   ├── Website Scanner
   │
   ├── AI Enrichment
   │
   └── Webhooks
   │
   ▼
RabbitMQ
   │
   ▼
Workers
   │
   ▼
PostgreSQL
   │
   ▼
Redis Cache
```

---

# 🧱 Stack Tecnológica

## Backend

* Python 3.11+
* FastAPI
* SQLAlchemy
* Alembic
* Pydantic

## Banco de Dados

* PostgreSQL

## Cache

* Redis

## Fila

* RabbitMQ

## Navegação

* Playwright

## IA

* Groq
* OpenAI
* Gemini

## Infraestrutura

* Docker
* Docker Compose
* Traefik
* Coolify

---

# 📂 Estrutura do Projeto

```text
scraper-link/

├── app/
│
├── api/
│   ├── routes/
│   │
│   ├── auth.py
│   ├── leads.py
│   ├── campaigns.py
│   └── webhooks.py
│
├── services/
│   ├── google_maps.py
│   ├── instagram.py
│   ├── facebook.py
│   ├── website.py
│   └── ai_enrichment.py
│
├── workers/
│   ├── lead_worker.py
│   └── enrichment_worker.py
│
├── core/
│   ├── config.py
│   ├── security.py
│   ├── database.py
│   └── cache.py
│
├── models/
│   ├── user.py
│   ├── lead.py
│   ├── campaign.py
│   ├── credit.py
│   └── api_key.py
│
├── schemas/
│
├── migrations/
│
├── tests/
│
├── Dockerfile
│
├── docker-compose.yml
│
├── requirements.txt
│
└── README.md
```

---

# 🔐 Autenticação

A API utiliza JWT e API Keys.

## Login

```http
POST /api/auth/login
```

### Request

```json
{
  "email": "usuario@email.com",
  "password": "123456"
}
```

### Response

```json
{
  "access_token": "jwt_token",
  "token_type": "bearer"
}
```

---

# 🔑 API Keys

Cada usuário possui uma chave exclusiva.

Exemplo:

```http
X-API-KEY: sk_live_xxxxxxxxx
```

---

# 💳 Sistema de Créditos

Cada operação consome créditos.

| Operação         | Créditos |
| ---------------- | -------- |
| Extrair telefone | 1        |
| Extrair e-mail   | 1        |
| Extrair WhatsApp | 1        |
| Website Scan     | 2        |
| Lead Google Maps | 5        |
| IA Enrichment    | 3        |

---

# 📊 Dashboard

O painel administrativo possui:

* Usuários
* Leads
* Campanhas
* Consumo
* Créditos
* API Keys
* Logs
* Webhooks

---

# 📦 Banco de Dados

## users

```sql
CREATE TABLE users (
 id UUID PRIMARY KEY,
 name VARCHAR(255),
 email VARCHAR(255),
 password_hash TEXT,
 created_at TIMESTAMP
);
```

## campaigns

```sql
CREATE TABLE campaigns (
 id UUID PRIMARY KEY,
 user_id UUID,
 name VARCHAR(255),
 status VARCHAR(50),
 created_at TIMESTAMP
);
```

## leads

```sql
CREATE TABLE leads (
 id UUID PRIMARY KEY,
 campaign_id UUID,
 company_name TEXT,
 phone TEXT,
 whatsapp TEXT,
 email TEXT,
 website TEXT,
 address TEXT,
 city TEXT,
 state TEXT
);
```

## api_keys

```sql
CREATE TABLE api_keys (
 id UUID PRIMARY KEY,
 user_id UUID,
 api_key TEXT,
 active BOOLEAN
);
```

---

# 🚀 Endpoints

## Health Check

```http
GET /health
```

---

## Extrair Telefone

```http
POST /api/extract/phone
```

### Request

```json
{
  "url": "https://instagram.com/empresa"
}
```

---

## Extrair Website

```http
POST /api/extract/website
```

---

## Extrair E-mail

```http
POST /api/extract/email
```

---

## Gerar Leads

```http
POST /api/leads/generate
```

### Request

```json
{
  "keyword": "dentista",
  "city": "São Paulo",
  "limit": 100
}
```

### Response

```json
{
  "campaign_id": "uuid",
  "status": "processing"
}
```

---

# 🔄 Filas

Todo processamento pesado é executado em background.

Fluxo:

```text
API
 │
 ▼
RabbitMQ
 │
 ▼
Worker
 │
 ▼
PostgreSQL
```

---

# 📤 Exportação

## CSV

```http
GET /api/export/csv/{campaign_id}
```

## XLSX

```http
GET /api/export/xlsx/{campaign_id}
```

---

# 🔔 Webhooks

Configure URLs para receber eventos.

Eventos:

```text
lead.created

campaign.finished

credits.low

export.finished
```

---

# 🔥 Integração n8n

Exemplo:

```http
POST https://seu-n8n/webhook/leads
```

Payload:

```json
{
  "lead_id": "uuid",
  "company_name": "Empresa X",
  "phone": "+55 11 99999-9999"
}
```

---

# 🐳 Docker

## Build

```bash
docker build -t scraper-link .
```

## Run

```bash
docker run -p 8000:8000 scraper-link
```

---

# 🐳 Docker Compose

```yaml
version: "3.9"

services:

  api:
    build: .
    container_name: scraper-link-api

  postgres:
    image: postgres:16

  redis:
    image: redis:latest

  rabbitmq:
    image: rabbitmq:management
```

---

# ⚙ Variáveis de Ambiente

```env
APP_NAME=SCRAPER.LINK

APP_ENV=production

SECRET_KEY=

JWT_SECRET=

POSTGRES_HOST=

POSTGRES_PORT=5432

POSTGRES_DB=scraperlink

POSTGRES_USER=

POSTGRES_PASSWORD=

REDIS_HOST=redis

RABBITMQ_HOST=rabbitmq

OPENAI_API_KEY=

GROQ_API_KEY=

GEMINI_API_KEY=

NOPECHA_KEY=
```

---

# 🛡 Segurança

* JWT Authentication
* API Keys
* Rate Limit
* CORS
* Request Validation
* Password Hashing
* Credit Control
* Audit Logs

---

# 📈 Roadmap

## v3

* [x] FastAPI
* [x] Playwright
* [x] Google Maps
* [x] IA

## v4

* [ ] Dashboard Web
* [ ] Sistema de Créditos
* [ ] Webhooks
* [ ] API Keys

## v5

* [ ] Multi-Tenant
* [ ] Billing
* [ ] PIX
* [ ] Stripe
* [ ] Asaas

---

# 🧪 Testes

```bash
pytest
```

---

# 🚀 Deploy

Compatível com:

* VPS
* Docker
* Docker Compose
* Coolify
* EasyPanel
* Portainer
* Kubernetes

---

# 🤝 Contribuição

```bash
git checkout -b feature/nova-feature

git commit -m "Nova funcionalidade"

git push origin feature/nova-feature
```

Abra um Pull Request.

---

# 📄 Licença

MIT License

---

# 👨‍💻 Autor

**Wesley Barroso**

GitHub: https://github.com/Wesleybarroso

---

# ⭐ Apoie o Projeto

Se este projeto foi útil:

* ⭐ Deixe uma estrela
* 🍴 Faça um Fork
* 🚀 Compartilhe

---

## SCRAPER.LINK

**A plataforma completa para geração de leads, enriquecimento de dados e automação comercial.**
