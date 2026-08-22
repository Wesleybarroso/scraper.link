# 🚀 SCRAPER.LINK

API profissional para descoberta e extração de contatos comerciais a partir de perfis públicos de redes sociais e páginas web.

O SCRAPER.LINK foi desenvolvido para automatizar a identificação de informações públicas de contato, como:

* Telefones
* Links do WhatsApp
* Websites
* E-mails públicos
* Links sociais
* Biografias comerciais

A API utiliza uma combinação de:

* FastAPI
* BeautifulSoup
* Requests
* AI Fallback
* aiograpi
* Extração por HTML
* Análise de páginas Link-in-Bio

---

# 📌 Principais Recursos

✅ Extração de telefones públicos

✅ Extração de links do WhatsApp

✅ Extração de e-mails públicos

✅ Suporte para Instagram

✅ Suporte para Facebook

✅ Suporte para Linktree

✅ Suporte para Beacons

✅ Suporte para páginas personalizadas

✅ API REST

✅ Respostas em JSON

✅ Docker Ready

✅ Deploy em VPS

✅ Escalável para milhares de consultas

---

# 🏗 Arquitetura

```text
Cliente
   │
   ▼
FastAPI
   │
   ├── Instagram Scraper
   │
   ├── Facebook Scraper
   │
   ├── Link-In-Bio Parser
   │
   ├── Website Analyzer
   │
   └── AI Fallback Engine
            │
            ▼
      JSON Response
```

---

# ⚙ Tecnologias

| Tecnologia     | Finalidade       |
| -------------- | ---------------- |
| Python 3.11+   | Backend          |
| FastAPI        | API REST         |
| Uvicorn        | Servidor         |
| Requests       | Requisições HTTP |
| BeautifulSoup4 | Parsing HTML     |
| aiograpi       | Coleta Instagram |
| Pydantic       | Validação        |
| Docker         | Containerização  |
| Docker Compose | Orquestração     |

---

# 📂 Estrutura do Projeto

```text
scraper.link/

├── app/
│
├── main.py
│
├── services/
│   ├── instagram.py
│   ├── facebook.py
│   ├── parser.py
│   └── extractor.py
│
├── utils/
│   ├── regex.py
│   └── helpers.py
│
├── requirements.txt
│
├── Dockerfile
│
├── docker-compose.yml
│
└── README.md
```

---

# 🔧 Instalação Local

## Clone o projeto

```bash
git clone https://github.com/Wesleybarroso/scraper.link.git

cd scraper.link
```

---

## Crie ambiente virtual

Linux

```bash
python3 -m venv venv

source venv/bin/activate
```

Windows

```powershell
python -m venv venv

venv\Scripts\activate
```

---

## Instale dependências

```bash
pip install -r requirements.txt
```

---

## Execute

```bash
uvicorn main:app --reload
```

API disponível em:

```text
http://localhost:8000
```

---

# 📚 Documentação Automática

Swagger:

```text
http://localhost:8000/docs
```

Redoc:

```text
http://localhost:8000/redoc
```

---

# 🐳 Docker

Build

```bash
docker build -t scraper-link .
```

Run

```bash
docker run -p 8000:8000 scraper-link
```

---

# 🐳 Docker Compose

```yaml
version: "3.8"

services:
  scraper:
    build: .
    container_name: scraper-link

    restart: always

    ports:
      - "8000:8000"
```

Subir:

```bash
docker compose up -d
```

---

# 🔐 Variáveis de Ambiente

Crie um arquivo:

```bash
.env
```

Exemplo:

```env
APP_NAME=SCRAPER.LINK

APP_ENV=production

APP_DEBUG=false

PORT=8000

INSTAGRAM_USERNAME=

INSTAGRAM_PASSWORD=

OPENAI_API_KEY=
```

---

# 🚀 Endpoint Principal

## POST /scrape

Realiza a análise completa de um perfil ou URL.

### Request

```json
{
  "url": "https://instagram.com/empresa"
}
```

---

### Response

```json
{
  "success": true,
  "source": "instagram",
  "phone": "+55 91 99999-9999",
  "email": "contato@empresa.com",
  "website": "https://empresa.com",
  "whatsapp": "https://wa.me/5591999999999"
}
```

---

# 📱 Exemplo com cURL

```bash
curl -X POST \
"http://localhost:8000/scrape" \
-H "Content-Type: application/json" \
-d '{
  "url":"https://instagram.com/empresa"
}'
```

---

# 🐍 Exemplo Python

```python
import requests

response = requests.post(
    "http://localhost:8000/scrape",
    json={
        "url":"https://instagram.com/empresa"
    }
)

print(response.json())
```

---

# 🟨 Exemplo Node.js

```javascript
const axios = require("axios");

async function main() {

    const response = await axios.post(
        "http://localhost:8000/scrape",
        {
            url:
            "https://instagram.com/empresa"
        }
    );

    console.log(response.data);
}

main();
```

---

# 📊 Possíveis Retornos

## Sucesso

```json
{
  "success": true
}
```

## Perfil não encontrado

```json
{
  "success": false,
  "error": "profile_not_found"
}
```

## URL inválida

```json
{
  "success": false,
  "error": "invalid_url"
}
```

## Limite excedido

```json
{
  "success": false,
  "error": "rate_limit"
}
```

---

# 🔍 Fluxo de Extração

```text
URL recebida
      │
      ▼

Identificação da plataforma
      │
      ▼

Coleta HTML
      │
      ▼

Extração de:
- Telefones
- WhatsApp
- E-mails
- Links
- Bio
      │
      ▼

Fallback IA
      │
      ▼

Resposta JSON
```

---

# 📈 Casos de Uso

* Geração de Leads
* CRM
* Automação Comercial
* Enriquecimento de Dados
* Análise de Perfis
* Prospecção Comercial
* Integração com n8n
* Integração com Make
* Integração com Zapier
* Integração com Sistemas Próprios

---

# 🔒 Boas Práticas

* Respeite limites das plataformas.
* Utilize cache sempre que possível.
* Implemente rate limit em produção.
* Não utilize para coleta de dados privados.
* Utilize apenas informações publicamente disponíveis.

---

# 🛣 Roadmap

### v1

* [x] Instagram
* [x] Facebook
* [x] WhatsApp Links
* [x] Telefones

### v2

* [ ] Google Maps
* [ ] LinkedIn
* [ ] TikTok
* [ ] Threads

### v3

* [ ] Dashboard Web
* [ ] API Keys
* [ ] Sistema de Créditos
* [ ] Painel Administrativo

---

# 🤝 Contribuindo

1. Faça um Fork
2. Crie uma Branch

```bash
git checkout -b feature/minha-feature
```

3. Commit

```bash
git commit -m "Nova funcionalidade"
```

4. Push

```bash
git push origin feature/minha-feature
```

5. Abra um Pull Request

---

# 📄 Licença

Este projeto está licenciado sob a licença MIT.

Consulte:

```text
LICENSE
```

---

# 👨‍💻 Autor

**Wesley Barroso**

GitHub:

https://github.com/Wesleybarroso

---

# ⭐ Apoie o Projeto

Se este projeto foi útil para você:

⭐ Deixe uma estrela no repositório

🍴 Faça um Fork

🚀 Compartilhe com outros desenvolvedores

---

**SCRAPER.LINK**
Automatizando a descoberta de contatos públicos na web.
