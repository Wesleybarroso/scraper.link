"""
SCRAPER DE CONTATOS - Extrator de Telefones/WhatsApp
=====================================================
Este é um web scraper automatizado que busca números de telefone e links de WhatsApp
em perfis de redes sociais (Instagram, Facebook) e páginas de link-in-bio (Linktree, Beacons, etc.).

Funcionalidades principais:
- Extrai telefones usando padrão regex para números brasileiros
- Resolve URLs de encurtadores (bit.ly, linktr.ee, etc.) para encontrar WhatsApp
- Funciona com redirecionamentos HTTP e JavaScript
- Fallback via API privada do Instagram (aiograpi) para perfis comerciais
- Fallback final via IA (Groq/OpenAI/OpenRouter/Google) quando nada mais funciona
- Acessa a API via FastAPI com dois endpoints:
  * POST /extrair-telefone: extrai telefone/WhatsApp de uma fonte
  * GET /health: verifica se a API está online
"""

# Importações de bibliotecas padrão para processamento de dados e logging
import re
import logging
import time
import os
import asyncio
from typing import Optional, List
from urllib.parse import urlparse, parse_qs

# Importações para requisições HTTP, API web e scraping
import httpx
from fastapi import FastAPI
from pydantic import BaseModel
from scrapling.fetchers import StealthyFetcher
from dotenv import load_dotenv
from aiograpi import Client as InstagramClient

# Carregar variáveis de ambiente do arquivo .env (se existir)
load_dotenv()

# Configuração de logs para rastrear execução e erros
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scraper-leads")

# Criação da aplicação FastAPI com título
app = FastAPI(title="Scraper de telefone - Leads")

# Padrão regex para encontrar números de telefone brasileiros (com ou sem +55)
# Aceita formatos como: (11) 99999-9999, 11 9 9999-9999, +55 11 99999-9999, etc.
PHONE_REGEX = re.compile(r"(?:\+?55\s?)?\(?\d{2}\)?\s?9?\d{4}-?\d{4}")

# Domínios que já SÃO o link final do WhatsApp (contém o número embutido).
# "whatsapp.com" pega qualquer subdomínio: web., api., chat., click., etc.
WHATSAPP_DIRECT_DOMAINS = ("wa.me", "whatsapp.com")

# Palavras-chave usadas pra reconhecer um BOTÃO de WhatsApp em link-in-bio
# (linktree, beacons, bio.link, etc.), mesmo quando ele passa por um encurtador
# de terceiro (tintim.link, sh.linktr.ee, bit.ly, etc.) antes de chegar no wa.me
WHATSAPP_HINT_KEYWORDS = ("whatsapp", "whats", "zap",
                          "fale conosco", "fale com")

# Headers do navegador para fazer requisições que pareçam vir de um usuário real
# Isso evita que sites bloqueiem as requisições automatizadas
HEADERS_NAVEGADOR = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )
}

# ========== CONFIGURAÇÃO DE APIS DE IA (Fallback) ==========
# Carrega configurações de IA de variáveis de ambiente
IA_PROVIDER = os.getenv("IA_PROVIDER", "groq").lower()
USE_IA_FALLBACK = os.getenv("USE_IA_FALLBACK", "true").lower() == "true"

# Chaves de API para diferentes provedores
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4-mini")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-2-70b-chat")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_MODEL = os.getenv("GOOGLE_MODEL", "gemini-1.5-flash")

# Inicializar clientes de IA
GROQ_CLIENT = None
OPENAI_CLIENT = None

# Inicializar Groq
if GROQ_API_KEY:
    try:
        from groq import Groq
        GROQ_CLIENT = Groq(api_key=GROQ_API_KEY)
        logger.info("✅ Groq API configurada com sucesso")
    except Exception as e:
        logger.warning(f"⚠️ Falha ao configurar Groq: {e}")

# Inicializar OpenAI
if OPENAI_API_KEY:
    try:
        from openai import OpenAI
        OPENAI_CLIENT = OpenAI(api_key=OPENAI_API_KEY)
        logger.info("✅ OpenAI API configurada com sucesso")
    except Exception as e:
        logger.warning(f"⚠️ Falha ao configurar OpenAI: {e}")

# Log do provedor IA selecionado
if USE_IA_FALLBACK:
    logger.info(f"🤖 Provedor de IA selecionado: {IA_PROVIDER.upper()}")
else:
    logger.info("🔇 Fallback com IA desativado")

# ========== CONFIGURAÇÃO DO AIOGRAPI (Fallback via API privada do Instagram) ==========
# Usa a mesma API que o app oficial do Instagram usa, através de uma conta logada.
# Só retorna telefone se o perfil-alvo for conta comercial com contato público configurado.
USE_AIOGRAPI_FALLBACK = os.getenv("USE_AIOGRAPI_FALLBACK", "true").lower() == "true"
IG_USERNAME = os.getenv("IG_USERNAME", "")
IG_PASSWORD = os.getenv("IG_PASSWORD", "")
SESSAO_INSTAGRAM_PATH = "/app/ig_session.json"

if USE_AIOGRAPI_FALLBACK and IG_USERNAME and IG_PASSWORD:
    logger.info("📷 Fallback aiograpi configurado")
else:
    USE_AIOGRAPI_FALLBACK = False
    logger.info("🔇 Fallback aiograpi desativado (sem credenciais ou desligado)")

# Modelos de dados usando Pydantic para validação de requisições e respostas


class ScrapeRequest(BaseModel):
    """Modelo para receber requisição de scraping com URLs de redes sociais"""
    instagram: Optional[str] = None
    facebook: Optional[str] = None
    link_bio: Optional[str] = None  # linktree, beacons.ai, bio.link, etc.


class ScrapeResponse(BaseModel):
    """Modelo para retornar o telefone encontrado e sua fonte"""
    telefone_encontrado: Optional[str] = None
    fonte: Optional[str] = None


def somenteNumeros(valor) -> str:
    """Remove tudo que não for dígito de um valor (mesma lógica usada
    no node 'Code preparar leads' do n8n, mantida consistente aqui)."""
    if valor is None:
        return ""
    return "".join(c for c in str(valor) if c.isdigit())


def extrair_telefone_de_texto(texto: str) -> Optional[str]:
    """Extrai o primeiro número de telefone encontrado no texto usando regex"""
    if not texto:
        return None
    match = PHONE_REGEX.search(texto)
    return match.group(0) if match else None


def extrair_numero_de_url_whatsapp(url: str) -> Optional[str]:
    """Extrai o número de dentro de uma URL wa.me ou api.whatsapp.com."""
    parsed = urlparse(url)
    if "wa.me" in parsed.netloc:
        numero = parsed.path.strip("/")
        return numero if numero.isdigit() else None
    if "whatsapp.com" in parsed.netloc:
        query = parse_qs(parsed.query)
        numero = query.get("phone", [None])[0]
        if numero:
            return re.sub(r"\D", "", numero)
    return None


def eh_link_whatsapp_direto(url: str) -> bool:
    """Verifica se a URL é um link direto do WhatsApp (wa.me ou whatsapp.com)"""
    return any(dominio in url for dominio in WHATSAPP_DIRECT_DOMAINS)


def parece_botao_whatsapp(href: str, texto_do_link: str) -> bool:
    """Verifica se o link e seu texto contêm palavras-chave de WhatsApp"""
    alvo = f"{href} {texto_do_link}".lower()
    return any(kw in alvo for kw in WHATSAPP_HINT_KEYWORDS)


def extrair_com_ia(conteudo: str, origem: str = "página") -> Optional[str]:
    """Fallback: usa IA para extrair WhatsApp quando método tradicional falha.
    Suporta múltiplos provedores: Groq, OpenAI, OpenRouter, Google.

    Args:
        conteudo: Texto/HTML da página a analisar
        origem: Origem (Instagram, Facebook, etc.)

    Returns:
        Número de WhatsApp encontrado ou None
    """
    if not USE_IA_FALLBACK:
        return None

    if not conteudo or len(conteudo) < 10:
        return None

    # Preparar conteúdo (limitar tamanho)
    conteudo_limitado = conteudo[:2000]

    prompt = f"""Você é um extrator de dados especializado em extrair números de WhatsApp.

Analise o seguinte conteúdo de um perfil {origem} e extraia APENAS o número de WhatsApp no formato brasileiro.

Conteúdo:
{conteudo_limitado}

Instruções:
1. Procure por números de WhatsApp em qualquer formato
2. Retorne APENAS o número (ex: 5511999999999 ou +5511999999999)
3. Se não encontrar WhatsApp, retorne: NENHUM
4. Não inclua explicações, retorne apenas o número ou NENHUM"""

    # Tentar com provedor selecionado
    if IA_PROVIDER == "groq" and GROQ_CLIENT:
        return _extrair_com_groq(prompt)
    elif IA_PROVIDER == "openai" and OPENAI_CLIENT:
        return _extrair_com_openai(prompt)
    elif IA_PROVIDER == "openrouter" and OPENROUTER_API_KEY:
        return _extrair_com_openrouter(prompt)
    elif IA_PROVIDER == "google" and GOOGLE_API_KEY:
        return _extrair_com_google(prompt)

    # Fallback: tentar qualquer uma disponível
    logger.warning(
        f"⚠️ Provedor {IA_PROVIDER} não configurado, tentando alternativas...")

    if GROQ_CLIENT:
        return _extrair_com_groq(prompt)
    elif OPENAI_CLIENT:
        return _extrair_com_openai(prompt)
    elif OPENROUTER_API_KEY:
        return _extrair_com_openrouter(prompt)
    elif GOOGLE_API_KEY:
        return _extrair_com_google(prompt)

    return None


def _extrair_com_groq(prompt: str) -> Optional[str]:
    """Extrai usando Groq API."""
    try:
        response = GROQ_CLIENT.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=20,
        )
        resultado = response.choices[0].message.content.strip()

        if resultado == "NENHUM" or not resultado:
            return None

        match = PHONE_REGEX.search(resultado)
        if match:
            numero = match.group(0)
            logger.info(f"✅ IA Groq extraiu WhatsApp: {numero}")
            return numero
    except Exception as e:
        logger.warning(f"⚠️ Falha ao usar Groq: {e}")

    return None


def _extrair_com_openai(prompt: str) -> Optional[str]:
    """Extrai usando OpenAI API."""
    try:
        response = OPENAI_CLIENT.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=20,
        )
        resultado = response.choices[0].message.content.strip()

        if resultado == "NENHUM" or not resultado:
            return None

        match = PHONE_REGEX.search(resultado)
        if match:
            numero = match.group(0)
            logger.info(f"✅ IA OpenAI extraiu WhatsApp: {numero}")
            return numero
    except Exception as e:
        logger.warning(f"⚠️ Falha ao usar OpenAI: {e}")

    return None


def _extrair_com_openrouter(prompt: str) -> Optional[str]:
    """Extrai usando OpenRouter API."""
    try:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://scraper.link",
            "X-Title": "Scraper de Telefones",
        }

        payload = {
            "model": OPENROUTER_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 20,
        }

        response = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30,
        )

        if response.status_code != 200:
            logger.warning(
                f"⚠️ OpenRouter retornou erro {response.status_code}")
            return None

        data = response.json()
        resultado = data["choices"][0]["message"]["content"].strip()

        if resultado == "NENHUM" or not resultado:
            return None

        match = PHONE_REGEX.search(resultado)
        if match:
            numero = match.group(0)
            logger.info(f"✅ IA OpenRouter extraiu WhatsApp: {numero}")
            return numero
    except Exception as e:
        logger.warning(f"⚠️ Falha ao usar OpenRouter: {e}")

    return None


def _extrair_com_google(prompt: str) -> Optional[str]:
    """Extrai usando Google Gemini API."""
    try:
        import google.generativeai as genai

        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel(GOOGLE_MODEL)

        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                max_output_tokens=20,
            )
        )

        resultado = response.text.strip()

        if resultado == "NENHUM" or not resultado:
            return None

        match = PHONE_REGEX.search(resultado)
        if match:
            numero = match.group(0)
            logger.info(f"✅ IA Google Gemini extraiu WhatsApp: {numero}")
            return numero
    except Exception as e:
        logger.warning(f"⚠️ Falha ao usar Google Gemini: {e}")

    return None


async def _buscar_telefone_via_aiograpi_async(username: str) -> Optional[str]:
    """Loga (ou reusa sessão salva) na API privada do Instagram e busca
    o telefone público configurado no perfil comercial informado."""
    cliente = InstagramClient()

    if os.path.exists(SESSAO_INSTAGRAM_PATH):
        cliente.load_settings(SESSAO_INSTAGRAM_PATH)

    await cliente.login(IG_USERNAME, IG_PASSWORD)
    cliente.dump_settings(SESSAO_INSTAGRAM_PATH)

    info = await cliente.user_info_by_username(username)

    telefone = (
        getattr(info, "public_phone_number", None)
        or getattr(info, "contact_phone_number", None)
    )
    return somenteNumeros(str(telefone)) if telefone else None


def buscar_telefone_via_aiograpi(username: str) -> Optional[str]:
    """Fallback via API privada do Instagram (aiograpi) — só roda
    se USE_AIOGRAPI_FALLBACK estiver ligado e tiver credenciais.
    Mais confiável que a IA porque vem de um campo estruturado real,
    não de texto interpretado."""
    if not USE_AIOGRAPI_FALLBACK:
        return None
    try:
        numero = asyncio.run(_buscar_telefone_via_aiograpi_async(username))
        if numero:
            logger.info(f"✅ aiograpi extraiu telefone: {numero}")
        return numero
    except Exception as e:
        logger.warning(f"⚠️ Falha ao usar aiograpi para @{username}: {e}")
        return None


def seguir_redirecionamentos(url: str) -> Optional[str]:
    """Segue redirects HTTP (302/301) server-side com um client rápido,
    sem abrir browser. Funciona para a maioria dos encurtadores.
    Tenta múltiplas vezes com retry automático."""
    max_retries = 3
    for tentativa in range(max_retries):
        try:
            with httpx.Client(headers=HEADERS_NAVEGADOR, follow_redirects=True, timeout=15) as client:
                resp = client.get(url)
                return str(resp.url)
        except Exception as e:
            if tentativa < max_retries - 1:
                # Backoff exponencial: 1s, 2s, 3s
                time.sleep(1 * (tentativa + 1))
                logger.info(f"Retry {tentativa + 1}/{max_retries} para {url}")
            else:
                logger.warning(
                    f"Falha final ao seguir redirect HTTP de {url}: {e}")
    return None


def seguir_redirecionamento_via_browser(url: str) -> Optional[str]:
    """Fallback para encurtadores que redirecionam via JavaScript
    (window.location) em vez de um redirect HTTP de verdade."""
    try:
        page = StealthyFetcher.fetch(url, headless=True, network_idle=True)
        return page.url if hasattr(page, "url") else None
    except Exception as e:
        logger.warning(f"Falha ao seguir redirect via browser de {url}: {e}")
        return None


def resolver_link_ate_whatsapp(url_inicial: str) -> Optional[str]:
    """Pega um link (direto ou de encurtador) e resolve até achar
    o número de WhatsApp, se existir na cadeia de redirecionamentos."""
    if eh_link_whatsapp_direto(url_inicial):
        return extrair_numero_de_url_whatsapp(url_inicial)

    url_final = seguir_redirecionamentos(url_inicial)
    if url_final and eh_link_whatsapp_direto(url_final):
        return extrair_numero_de_url_whatsapp(url_final)

    # Encurtador não redirecionou por HTTP puro -> provavelmente é JS-based
    url_final_browser = seguir_redirecionamento_via_browser(url_inicial)
    if url_final_browser and eh_link_whatsapp_direto(url_final_browser):
        return extrair_numero_de_url_whatsapp(url_final_browser)

    return None


# Domínios que NUNCA valem a pena tentar resolver no fallback genérico
# (redes sociais, navegação do próprio site, etc. — perda de tempo e requests)
DOMINIOS_IGNORAR_NO_FALLBACK = (
    "instagram.com", "facebook.com", "tiktok.com", "twitter.com", "x.com",
    "youtube.com", "linkedin.com", "spotify.com", "apple.com",
)

MAX_LINKS_FALLBACK = 15  # Aumentado para verificar mais links


def extrair_numero_de_tel(href: str) -> Optional[str]:
    """Extrai o número de um link com protocolo tel: (exemplo: tel:+5511999999999)"""
    if not href.lower().startswith("tel:"):
        return None
    numero = re.sub(r"\D", "", href)
    return numero if numero else None


def buscar_whatsapp_em_link_bio(url: str) -> Optional[str]:
    """Abre uma página tipo Linktree/Beacons/Bio.link, acha o botão
    de WhatsApp (mesmo atrás de um encurtador) e extrai o número."""
    try:
        page = StealthyFetcher.fetch(url, headless=True, network_idle=True)

        links = page.css("a::attr(href)").getall() or []
        textos = page.css("a::text").getall() or []
        textos += [""] * (len(links) - len(textos))

        # 1) tel: direto — não precisa nem seguir redirect
        for href in links:
            numero = extrair_numero_de_tel(href)
            if numero:
                return numero

        # 2) candidatos com palavra-chave de WhatsApp no link/texto (prioridade)
        candidatos_com_pista = [
            href for href, texto in zip(links, textos)
            if parece_botao_whatsapp(href, texto)
        ]
        candidatos_com_pista.sort(
            key=lambda h: 0 if eh_link_whatsapp_direto(h) else 1)

        for href in candidatos_com_pista:
            numero = resolver_link_ate_whatsapp(href)
            if numero:
                return numero

        # 3) fallback: sem pista textual (botão só com ícone) — tenta resolver
        #    os demais links externos, um a um, até achar algum que caia no WhatsApp.
        #    Cobre qualquer encurtador (Bitly, TinyURL, Cuttly, T.LY, Rebrandly...)
        #    sem precisar conhecer cada um deles.
        outros_links = [
            href for href in links
            if href.startswith("http")
            and href not in candidatos_com_pista
            and not any(dominio in href for dominio in DOMINIOS_IGNORAR_NO_FALLBACK)
        ][:MAX_LINKS_FALLBACK]

        for href in outros_links:
            numero = resolver_link_ate_whatsapp(href)
            if numero:
                return numero

        return None
    except Exception as e:
        logger.warning(f"Falha ao buscar WhatsApp em link-in-bio ({url}): {e}")
        return None


def buscar_telefone_instagram(link: str) -> Optional[str]:
    """Busca telefone/WhatsApp no perfil do Instagram com múltiplas estratégias:
    1) Verifica metadados (og:description e description)
    2) Procura links diretos de WhatsApp (wa.me, whatsapp.com)
    3) Procura link-in-bio (Linktree, Beacons, Bio.link, etc.)
    4) Procura por palavras-chave de contato
    5) Busca em todo o texto visível da página
    6) Fallback via API privada do Instagram (aiograpi)
    7) Último recurso: usa IA para extrair"""
    try:
        username = link.rstrip(
            "/").split("/")[-1].lstrip("@") if "instagram.com" in link else link.lstrip("@")
        url = f"https://www.instagram.com/{username}/"

        # Fetch com timeout maior para Instagram
        page = StealthyFetcher.fetch(
            url, headless=True, network_idle=True, timeout=30)

        # 1) Tenta extrair de metadados (og:description + description)
        descricao = page.css(
            "meta[property='og:description']::attr(content)").get() or ""
        descricao += " " + (page.css(
            "meta[name='description']::attr(content)").get() or "")

        telefone = extrair_telefone_de_texto(descricao)
        if telefone:
            return telefone

        # 2) Procura links diretos de WhatsApp (wa.me, whatsapp.com)
        links_whatsapp = page.css(
            "a[href*='wa.me']::attr(href), a[href*='whatsapp.com']::attr(href)").getall() or []
        for href in links_whatsapp:
            numero = extrair_numero_de_url_whatsapp(href)
            if numero:
                return numero

        # 3) Procura link-in-bio (Linktree, Beacons, Bio.link, etc.)
        bio_links = page.css(
            "a[href*='linktr.ee']::attr(href), "
            "a[href*='beacons.ai']::attr(href), "
            "a[href*='bio.link']::attr(href), "
            "a[href*='linkin.bio']::attr(href)").getall() or []

        for bio_link in bio_links:
            numero = buscar_whatsapp_em_link_bio(bio_link)
            if numero:
                return numero

        # 4) Procura por links com palavras-chave de contato/WhatsApp
        todos_os_links = page.css("a::attr(href)").getall() or []
        textos = page.css("a::text").getall() or []
        textos += [""] * (len(todos_os_links) - len(textos))

        candidatos = [
            href for href, texto in zip(todos_os_links, textos)
            if parece_botao_whatsapp(href, texto) or "contato" in texto.lower() or "message" in texto.lower()
        ]

        for href in candidatos:
            if href.startswith("http"):
                numero = resolver_link_ate_whatsapp(href)
                if numero:
                    return numero
            elif href.startswith("tel:"):
                numero = extrair_numero_de_tel(href)
                if numero:
                    return numero

        # 5) Fallback: busca em todo o texto da página com filtro
        texto_completo = page.get_all_text() if hasattr(
            page, "get_all_text") else str(page)

        # Procura por padrões de WhatsApp no texto
        if any(kw in texto_completo.lower() for kw in ["whatsapp", "zap", "wa.me", "msg"]):
            telefone = extrair_telefone_de_texto(texto_completo)
            if telefone:
                return telefone

        # 6) Fallback via API privada do Instagram (aiograpi) — mais confiável
        #    que a IA, porque vem direto do campo estruturado do Instagram
        numero_aiograpi = buscar_telefone_via_aiograpi(username)
        if numero_aiograpi:
            return numero_aiograpi

        # 7) Último recurso: usar IA para extrair se disponível
        numero_ia = extrair_com_ia(texto_completo, "Instagram")
        if numero_ia:
            return numero_ia

        return None
    except Exception as e:
        logger.warning(f"Falha ao buscar telefone no Instagram ({link}): {e}")
        return None


def buscar_telefone_facebook(link: str) -> Optional[str]:
    """Busca telefone/WhatsApp no perfil do Facebook:
    1) Verifica a og:description (metadados para compartilhamento)
    2) Procura em todo o texto visível da página
    3) Usa IA como fallback se disponível"""
    try:
        page = StealthyFetcher.fetch(link, headless=True, network_idle=True)
        # Tenta extrair da metadescription (Open Graph para compartilhamento)
        descricao = page.css(
            "meta[property='og:description']::attr(content)").get() or ""
        telefone = extrair_telefone_de_texto(descricao)
        if telefone:
            return telefone

        texto_completo = page.get_all_text() if hasattr(
            page, "get_all_text") else str(page)

        # Tenta com regex primeiro
        numero = extrair_telefone_de_texto(texto_completo)
        if numero:
            return numero

        # Fallback: usar IA se disponível
        numero_ia = extrair_com_ia(texto_completo, "Facebook")
        if numero_ia:
            return numero_ia

        return None
    except Exception as e:
        logger.warning(f"Falha ao buscar telefone no Facebook ({link}): {e}")
        return None


@app.post("/extrair-telefone", response_model=ScrapeResponse)
def extrair_telefone(req: ScrapeRequest):
    """Endpoint principal para extrair telefone/WhatsApp.
    Procura em link-in-bio, Instagram e Facebook (nessa ordem de prioridade).
    Retorna o telefone encontrado e a fonte de onde foi extraído."""
    # Primeiro tenta extrair do link-in-bio (Linktree, Beacons, etc.)
    if req.link_bio:
        numero = buscar_whatsapp_em_link_bio(req.link_bio)
        if numero:
            return ScrapeResponse(telefone_encontrado=numero, fonte="link_bio")

    # Se não encontrou, tenta no Instagram
    if req.instagram:
        telefone = buscar_telefone_instagram(req.instagram)
        if telefone:
            return ScrapeResponse(telefone_encontrado=telefone, fonte="instagram")

    # Se ainda não encontrou, tenta no Facebook
    if req.facebook:
        telefone = buscar_telefone_facebook(req.facebook)
        if telefone:
            return ScrapeResponse(telefone_encontrado=telefone, fonte="facebook")

    # Se nenhuma fonte tinha telefone, retorna vazio
    return ScrapeResponse(telefone_encontrado=None, fonte=None)


@app.get("/health")
def health():
    """Endpoint de health check para verificar se a API está rodando"""
    return {"status": "ok"}