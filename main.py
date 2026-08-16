
"""
SCRAPER DE CONTATOS - Extrator de Telefones/WhatsApp
=====================================================
Este é um web scraper automatizado que busca números de telefone e links de WhatsApp
em perfis de redes sociais (Instagram, Facebook) e páginas de link-in-bio (Linktree, Beacons, etc.).

Funcionalidades principais:
- Extrai telefones usando padrão regex para números brasileiros
- Resolve URLs de encurtadores (bit.ly, linktr.ee, etc.) para encontrar WhatsApp
- Funciona com redirecionamentos HTTP e JavaScript
- Acessa a API via FastAPI com dois endpoints:
  * POST /extrair-telefone: extrai telefone/WhatsApp de uma fonte
  * GET /health: verifica se a API está online
"""

# Importações de bibliotecas padrão para processamento de dados e logging
import re
import logging
import time
from typing import Optional, List
from urllib.parse import urlparse, parse_qs

# Importações para requisições HTTP, API web e scraping
import httpx
from fastapi import FastAPI
from pydantic import BaseModel
from scrapling.fetchers import StealthyFetcher

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
                time.sleep(1 * (tentativa + 1))  # Backoff exponencial: 1s, 2s, 3s
                logger.info(f"Retry {tentativa + 1}/{max_retries} para {url}")
            else:
                logger.warning(f"Falha final ao seguir redirect HTTP de {url}: {e}")
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
    5) Resolve links de redirecionamento
    6) Busca em todo o texto visível da página"""
    try:
        username = link.rstrip(
            "/").split("/")[-1].lstrip("@") if "instagram.com" in link else link.lstrip("@")
        url = f"https://www.instagram.com/{username}/"
        
        # Fetch com timeout maior para Instagram
        page = StealthyFetcher.fetch(url, headless=True, network_idle=True, timeout=30)

        # 1) Tenta extrair de metadados (og:description + description)
        descricao = page.css(
            "meta[property='og:description']::attr(content)").get() or ""
        descricao += " " + (page.css(
            "meta[name='description']::attr(content)").get() or "")
        
        telefone = extrair_telefone_de_texto(descricao)
        if telefone:
            return telefone

        # 2) Procura links diretos de WhatsApp (wa.me, whatsapp.com)
        links_whatsapp = page.css("a[href*='wa.me']::attr(href), a[href*='whatsapp.com']::attr(href)").getall() or []
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

        return None
    except Exception as e:
        logger.warning(f"Falha ao buscar telefone no Instagram ({link}): {e}")
        return None


def buscar_telefone_facebook(link: str) -> Optional[str]:
    """Busca telefone/WhatsApp no perfil do Facebook:
    1) Verifica a og:description (metadados para compartilhamento)
    2) Procura em todo o texto visível da página"""
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
        return extrair_telefone_de_texto(texto_completo)
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
