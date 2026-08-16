# Scraper de Telefones/WhatsApp 📱

Um web scraper automatizado que extrai números de telefone e links de WhatsApp a partir de perfis de redes sociais (Instagram, Facebook) e páginas de link-in-bio (Linktree, Beacons, Bio.link, etc.).

## 🎯 Funcionalidades

- ✅ Extrai telefones usando padrão regex para números brasileiros
- ✅ Resolve URLs de encurtadores (bit.ly, linktr.ee, tinyurl, etc.)
- ✅ Suporta redirecionamentos HTTP e JavaScript
- ✅ Busca em múltiplas fontes: Instagram, Facebook e Link-in-bio
- ✅ API REST com FastAPI
- ✅ Detecção inteligente de botões WhatsApp
- ✅ User-Agent real para evitar bloqueios

## 📋 Requisitos

- Python 3.8+
- pip (gerenciador de pacotes Python)

## 🚀 Instalação

### 1. Clonar o repositório

```bash
git clone https://github.com/Wesleybarroso/scraper.link.git
cd scraper.link
```

### 2. Criar ambiente virtual (opcional, mas recomendado)

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar dependências

```bash
pip install -r requeriments.txt
```

**Dependências incluídas:**
- `fastapi==0.115.0` - Framework web
- `uvicorn[standard]==0.30.6` - Servidor ASGI
- `pydantic==2.9.2` - Validação de dados
- `scrapling[fetchers]` - Scraping com suporte a JavaScript
- `httpx==0.27.2` - Cliente HTTP

## 💻 Como Usar

### Iniciar o servidor

```bash
# Windows
uvicorn main:app --reload

# Linux/Mac
python -m uvicorn main:app --reload
```

O servidor estará disponível em: **http://localhost:8000**

### Acessar a documentação interativa

Uma vez que o servidor está rodando, acesse:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Endpoints da API

#### 1. **Extrair Telefone** `POST /extrair-telefone`

Extrai telefone/WhatsApp de uma ou mais fontes.

**Requisição:**
```json
{
  "instagram": "https://instagram.com/seuuser/",
  "facebook": "https://facebook.com/seuperfil/",
  "link_bio": "https://linktr.ee/seulink"
}
```

**Resposta de sucesso (200):**
```json
{
  "telefone_encontrado": "+5511999999999",
  "fonte": "instagram"
}
```

**Resposta sem resultado:**
```json
{
  "telefone_encontrado": null,
  "fonte": null
}
```

**Parâmetros:**
- `instagram` (opcional): URL do perfil do Instagram
- `facebook` (opcional): URL do perfil do Facebook
- `link_bio` (opcional): URL da página de link-in-bio (Linktree, Beacons, Bio.link, etc.)

**Prioridade de busca:**
1. Link-in-bio (se fornecido)
2. Instagram (se fornecido)
3. Facebook (se fornecido)

#### 2. **Health Check** `GET /health`

Verifica se a API está online.

**Resposta:**
```json
{
  "status": "ok"
}
```

## 📚 Exemplos de Uso

### Usando cURL

```bash
# Buscar no Instagram
curl -X POST "http://localhost:8000/extrair-telefone" \
  -H "Content-Type: application/json" \
  -d '{"instagram": "https://instagram.com/seu_usuario/"}'

# Buscar no Linktree
curl -X POST "http://localhost:8000/extrair-telefone" \
  -H "Content-Type: application/json" \
  -d '{"link_bio": "https://linktr.ee/seu_link"}'

# Buscar em múltiplas fontes
curl -X POST "http://localhost:8000/extrair-telefone" \
  -H "Content-Type: application/json" \
  -d '{
    "instagram": "https://instagram.com/seu_usuario/",
    "facebook": "https://facebook.com/seu_perfil/",
    "link_bio": "https://linktr.ee/seu_link"
  }'

# Health check
curl "http://localhost:8000/health"
```

### Usando Python

```python
import requests

url = "http://localhost:8000/extrair-telefone"

# Buscar no Instagram
dados = {
    "instagram": "https://instagram.com/seu_usuario/"
}

resposta = requests.post(url, json=dados)
print(resposta.json())

# Output:
# {
#   "telefone_encontrado": "+5511999999999",
#   "fonte": "instagram"
# }
```

### Usando JavaScript/Node.js

```javascript
const fetch = require('node-fetch');

const url = "http://localhost:8000/extrair-telefone";
const dados = {
  "link_bio": "https://linktr.ee/seu_link"
};

fetch(url, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify(dados)
})
  .then(res => res.json())
  .then(data => console.log(data));
```

## 🏗️ Estrutura do Projeto

```
scraper.link/
│
├── main.py                # Código principal do scraper
├── requeriments.txt        # Dependências do projeto
├── README.md              # Este arquivo
└── .git/                  # Repositório git
```

## 🔍 Como Funciona

### Estratégia de Extração

O scraper utiliza uma abordagem de múltiplas camadas para encontrar telefones:

1. **Extração de padrão regex**: Busca números de telefone usando expressão regular
2. **Links diretos**: Identifica links wa.me e whatsapp.com
3. **Palavras-chave**: Detecta botões WhatsApp por palavras-chave ("whatsapp", "zap", "fale conosco", etc.)
4. **Resolução de encurtadores**: Segue redirecionamentos HTTP e JavaScript
5. **Fallback genérico**: Tenta resolver links desconhecidos

### Formatos de Telefone Suportados

O regex suporta números brasileiros nos seguintes formatos:

- `(11) 99999-9999`
- `11 99999-9999`
- `11 9 9999-9999`
- `+55 11 99999-9999`
- `+5511999999999`
- E variações similares

## ⚠️ Notas Importantes

### Limitações

- ⏱️ **Timeout**: Requisições têm timeout de 10 segundos
- 🔗 **Links**: Máximo de 8 links são processados por página (fallback)
- 🌐 **Domínios ignorados**: Alguns domínios são ignorados para evitar requisições desnecessárias:
  - Redes sociais: instagram.com, facebook.com, tiktok.com, twitter.com, youtube.com, etc.
  - Outros: spotify.com, apple.com
- 🤖 **User-Agent**: Usa User-Agent de navegador real para evitar bloqueios

### Rate Limiting

Se você receber muitos erros de conexão, é recomendado:

1. Aguardar alguns segundos entre requisições
2. Verificar se o site não está bloqueando bots
3. Usar proxies em produção

### Performance

Para melhor performance:

- Use URLs válidas e bem formadas
- Evite solicitar páginas muito grandes
- Considere usar um pool de requisições em produção

## 🐛 Troubleshooting

### Erro: "scrapling.fetchers could not be resolved"

**Solução:**
```bash
pip install scrapling[fetchers]
```

### Erro: "Connection refused"

**Solução:** Certifique-se que o servidor está rodando:
```bash
uvicorn scraper:app --reload
```

### Telefone não está sendo encontrado

**Possíveis causas:**
- O site está bloqueando bots
- O telefone está em um formato não reconhecido
- O conteúdo é carregado dinamicamente (JavaScript)

## 📝 Logging

O scraper registra avisos e erros em tempo real. Para ver os logs:

```bash
# Aumentar verbosidade
# Modificar logging.basicConfig(level=logging.INFO) 
# para logging.basicConfig(level=logging.DEBUG) em scraper.py
```

## 🚢 Deploy em Produção

### Opção 1: EasyPanel (Recomendado) ⭐

**EasyPanel** é a forma mais fácil de fazer deploy! Ele gerencia tudo automaticamente.

#### Passo a Passo:

1. **Acesse o EasyPanel** (http://seu-dominio/easypanel)
2. **Clique em "Add Service" → "Application"**
3. **Preencha os dados:**
   - **Nome**: `scraper-leads`
   - **Repository URL**: `https://github.com/Wesleybarroso/scraper.link.git`
   - **Branch**: `main`
   - **Port**: `8000`
   - **Container Port**: `8000`

4. **Clique em "Deploy"**
5. **Aguarde a conclusão** (cerca de 2-3 minutos)
6. **Acesse via**: `https://seu-dominio.com` ou conforme configurado

#### Vantagens do EasyPanel:
- ✅ Deploy automático ao fazer push no GitHub
- ✅ SSL/HTTPS automático
- ✅ Gerenciamento de banco de dados
- ✅ Monitoramento de saúde (Health Check)
- ✅ Backups automáticos
- ✅ Escalabilidade fácil

#### Variáveis de Ambiente (opcional no EasyPanel):

Se precisar de configurações customizadas:

```
LOG_LEVEL=INFO
WORKERS=4
```

---

### Opção 2: Usando Gunicorn (Produção Local)

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 main:app
```

**Parâmetros:**
- `-w 4`: 4 workers (ajuste conforme CPU)
- `-b 0.0.0.0:8000`: Bind em todas as interfaces, porta 8000

---

### Opção 3: Usando Docker Localmente

#### Build e Run Simples:

```bash
docker build -t scraper-leads .
docker run -p 8000:8000 scraper-leads
```

#### Com Docker Compose:

Crie `docker-compose.yml`:

```yaml
version: '3.8'

services:
  scraper:
    build: .
    ports:
      - "8000:8000"
    environment:
      - LOG_LEVEL=INFO
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

Execute:

```bash
docker-compose up -d
```

---

### Opção 4: Nginx + Uvicorn (Servidor Dedicado)

Para máxima performance e segurança:

**1. Instale dependências:**

```bash
sudo apt-get update
sudo apt-get install -y nginx supervisor python3-venv
```

**2. Crie usuário para a aplicação:**

```bash
sudo useradd -m scraper
sudo su - scraper
```

**3. Clone e configure:**

```bash
git clone https://github.com/Wesleybarroso/scraper.link.git
cd scraper.link
python3 -m venv venv
source venv/bin/activate
pip install -r requeriments.txt
```

**4. Configure Supervisor** (`/etc/supervisor/conf.d/scraper.conf`):

```ini
[program:scraper-leads]
directory=/home/scraper/scraper.link
command=/home/scraper/scraper.link/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --workers 4
user=scraper
autostart=true
autorestart=true
stderr_logfile=/var/log/scraper-leads.err.log
stdout_logfile=/var/log/scraper-leads.out.log
```

**5. Configure Nginx** (`/etc/nginx/sites-available/scraper`):

```nginx
upstream scraper {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name seu-dominio.com;

    location / {
        proxy_pass http://scraper;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**6. Ative e inicie:**

```bash
sudo a2ensite scraper
sudo systemctl restart nginx
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start scraper-leads
```

---

### Opção 5: Railway, Render ou Heroku

Estes serviços suportam deploy direto do GitHub:

#### Railway:
```bash
railway login
railway init
railway link <project-id>
railway up
```

#### Render:
1. Acesse [render.com](https://render.com)
2. Connect seu GitHub
3. Selecione o repositório
4. Render detecta o Dockerfile automaticamente

#### Heroku:
```bash
heroku create seu-app-name
git push heroku main
```

---

### Comparação de Opções

| Opção | Facilidade | Custo | Performance | Escalabilidade | Recomendado para |
|-------|-----------|-------|-------------|-----------------|------------------|
| **EasyPanel** ⭐ | ⭐⭐⭐⭐⭐ | Médio | Excelente | Excelente | Produção, iniciantes |
| **Docker Local** | ⭐⭐⭐ | Baixo | Muito Bom | Bom | Desenvolvimento, testes |
| **Gunicorn** | ⭐⭐ | Baixo | Bom | Médio | Servidor dedicado |
| **Nginx + Uvicorn** | ⭐⭐ | Baixo | Excelente | Excelente | Produção High Performance |
| **Railway/Render** | ⭐⭐⭐⭐ | Médio | Muito Bom | Muito Bom | Startup, prototipagem |
| **Heroku** | ⭐⭐⭐⭐ | Alto | Bom | Bom | Prototipagem rápida |

### 🎯 Recomendação

**Para EasyPanel:** Use a Opção 1, é a mais fácil e você terá tudo pronto em minutos!

**Para desenvolvimento local:** Use Docker Compose (Opção 3)

**Para máxima performance:** Use Nginx + Uvicorn (Opção 4)

---

## 📄 Licença

Este projeto é fornecido como está para fins educacionais e comerciais.

## 👤 Autor

**Wesley Barroso**  
GitHub: [@Wesleybarroso](https://github.com/Wesleybarroso)

## 🤝 Contribuições

Contribuições são bem-vindas! Sinta-se à vontade para fazer fork, melhorar e enviar pull requests.

## 📞 Suporte

Para dúvidas ou problemas:
1. Verifique a documentação da API em `/docs`
2. Revise os logs do servidor
3. Abra uma issue no GitHub

---

**Última atualização**: Agosto de 2026
