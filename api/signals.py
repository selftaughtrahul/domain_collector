"""
signals.py
==========

The PATTERN layer. This file holds *what* we look for.
`website_analyzer.py` holds *how* we look for it and *how* we decide.

Keeping them apart is the whole point: you should be able to improve
accuracy by editing only this file, without ever touching the engine.

--------------------------------------------------------------------
HOW TO ADD A PATTERN
--------------------------------------------------------------------

    S("adicionar ao carrinho", 12, "pt")
      |            |            |    |
      |            |            |    +-- language tag (documentation only,
      |            |            |        the engine matches every language)
      |            |            +------- weight: how much evidence this is
      |            +-------------------- the phrase, lowercase, no accents
      +--------------------------------- helper that builds a Signal

Then drop it into the right list below. That's it.

--------------------------------------------------------------------
WEIGHT SCALE  (be disciplined about this or scores stop meaning anything)
--------------------------------------------------------------------

    12  Decisive.   Only this kind of site says this.
                    "add to cart", "request a demo", "fale com vendas"
     8  Strong.     Very typical, occasionally borrowed by others.
                    "free shipping", "wholesale", "ultimas noticias"
     5  Supporting. Real evidence, but common across categories.
                    "partners", "loja", "magazine"
     3  Weak.       Only useful in aggregate. Never decides anything alone.
                    "teams", "delivery"

--------------------------------------------------------------------
MATCH KINDS
--------------------------------------------------------------------

    "word"       whole-word match (DEFAULT — use this)
                 "api" will NOT match "rapido", "capital", "terapia"
    "substring"  raw substring; only for things that live inside markup,
                 e.g. platform fingerprints like "woocommerce"

Accents are stripped before matching, so write patterns WITHOUT accents:
"noticias" matches "notícias", "promocao" matches "promoção".
"""

from dataclasses import dataclass


# ====================================================================
# SIGNAL TYPE
# ====================================================================


@dataclass(frozen=True)
class Signal:
    text: str
    weight: int
    lang: str = "en"
    kind: str = "word"  # "word" | "substring"


def S(text: str, weight: int, lang: str = "en", kind: str = "word") -> Signal:
    """Shorthand constructor so the tables below stay readable."""
    return Signal(text=text, weight=weight, lang=lang, kind=kind)


# ====================================================================
# TEXT SIGNALS
# ====================================================================
#
# Every group is scored independently. A page can score on several
# groups at once — that is intentional and the decision layer uses it.
# ====================================================================


B2B = [
    # ---------- English: sales-led motion ----------
    S("request a demo", 12),
    S("book a demo", 12),
    S("schedule a demo", 12),
    S("contact sales", 12),
    S("talk to sales", 12),
    S("get a quote", 10),
    S("request pricing", 10),
    S("custom pricing", 10),
    S("request a quote", 10),
    S("enterprise solution", 10),
    S("enterprise plan", 10),
    S("business solutions", 8),
    S("for businesses", 8),
    S("for enterprises", 8),
    S("business customers", 8),
    S("minimum order", 10),
    S("wholesale", 10),
    S("distributor", 9),
    S("reseller", 8),
    S("procurement", 8),
    S("partner program", 8),
    S("bulk order", 9),
    S("supplier", 6),
    S("enterprise", 6),
    S("saas", 5),
    S("for teams", 5),
    S("partners", 4),
    S("integrations", 3),
    S("organizations", 3),
    S("corporate", 4),
    S("api", 3),
    # ---------- Portuguese (BR) ----------
    S("fale com vendas", 12, "pt"),
    S("solicite um orcamento", 12, "pt"),
    S("peca um orcamento", 12, "pt"),
    S("agende uma demonstracao", 12, "pt"),
    S("solucoes empresariais", 10, "pt"),
    S("solucoes corporativas", 10, "pt"),
    S("para empresas", 9, "pt"),
    S("para sua empresa", 9, "pt"),
    S("venda no atacado", 10, "pt"),
    S("atacado", 8, "pt"),
    S("revendedor", 9, "pt"),
    S("distribuidor", 9, "pt"),
    S("seja um parceiro", 8, "pt"),
    S("plano empresarial", 9, "pt"),
    S("orcamento", 6, "pt"),
    S("consultoria", 5, "pt"),
    S("cnpj", 5, "pt"),
    S("tabela de precos", 8, "pt"),
    S("nossos clientes", 4, "pt"),
    # ---------- Italian ----------
    S("richiedi una demo", 12, "it"),
    S("contatta il commerciale", 12, "it"),
    S("soluzioni aziendali", 10, "it"),
    S("per le aziende", 9, "it"),
    S("preventivo", 7, "it"),
    S("rivenditore", 9, "it"),
    S("all ingrosso", 10, "it"),
    S("grossista", 9, "it"),
    # ---------- Dutch (BE/NL) ----------
    S("vraag een demo aan", 12, "nl"),
    S("neem contact op met sales", 12, "nl"),
    S("zakelijke oplossingen", 10, "nl"),
    S("voor bedrijven", 9, "nl"),
    S("offerte aanvragen", 10, "nl"),
    S("groothandel", 10, "nl"),
    S("wederverkoper", 9, "nl"),
    # ---------- Spanish ----------
    S("solicitar una demo", 12, "es"),
    S("hablar con ventas", 12, "es"),
    S("soluciones empresariales", 10, "es"),
    S("para empresas", 9, "es"),
    S("mayorista", 10, "es"),
    S("distribuidor", 9, "es"),
]


B2C = [
    # ---------- English: transactional ----------
    S("add to cart", 12),
    S("shopping cart", 12),
    S("proceed to checkout", 12),
    S("checkout", 10),
    S("buy now", 12),
    S("shop now", 10),
    S("track your order", 10),
    S("place order", 9),
    S("order now", 8),
    S("free shipping", 9),
    S("home delivery", 8),
    S("free returns", 9),
    S("size guide", 8),
    S("wishlist", 8),
    S("your cart", 9),
    S("customer reviews", 6),
    S("gift card", 7),
    S("subscribe now", 5),
    S("shop", 4),
    S("store", 3),
    S("coupon", 5),
    S("discount", 3),
    S("sale", 3),
    S("delivery", 3),
    S("consumer", 4),
    # ---------- Portuguese (BR) ----------
    S("adicionar ao carrinho", 12, "pt"),
    S("finalizar compra", 12, "pt"),
    S("meu carrinho", 12, "pt"),
    S("comprar agora", 12, "pt"),
    S("frete gratis", 10, "pt"),
    S("calcular frete", 10, "pt"),
    S("rastrear pedido", 10, "pt"),
    S("meus pedidos", 9, "pt"),
    S("forma de pagamento", 8, "pt"),
    S("parcelado", 8, "pt"),
    S("em ate 12x", 9, "pt"),
    S("lista de desejos", 8, "pt"),
    S("promocao", 5, "pt"),
    S("desconto", 4, "pt"),
    S("loja", 4, "pt"),
    S("carrinho", 6, "pt"),
    S("cupom", 5, "pt"),
    S("assine agora", 6, "pt"),
    S("cadastre se", 4, "pt"),
    # ---------- Italian ----------
    S("aggiungi al carrello", 12, "it"),
    S("il tuo carrello", 12, "it"),
    S("acquista ora", 12, "it"),
    S("spedizione gratuita", 10, "it"),
    S("carrello", 6, "it"),
    S("saldi", 5, "it"),
    S("negozio", 5, "it"),
    # ---------- Dutch ----------
    S("in winkelwagen", 12, "nl"),
    S("winkelwagen", 10, "nl"),
    S("nu kopen", 12, "nl"),
    S("gratis verzending", 10, "nl"),
    S("bestel nu", 9, "nl"),
    S("webshop", 8, "nl"),
    # ---------- Spanish ----------
    S("anadir al carrito", 12, "es"),
    S("comprar ahora", 12, "es"),
    S("envio gratis", 10, "es"),
    S("carrito", 6, "es"),
    S("tienda", 5, "es"),
]


# General-audience news / publishing. Audience = the public.
MEDIA = [
    S("breaking news", 12),
    S("latest news", 10),
    S("newsroom", 10),
    S("news portal", 10),
    S("online newspaper", 12),
    S("daily newspaper", 12),
    S("journalism", 10),
    S("journalist", 8),
    S("editorial team", 9),
    S("newspaper", 9),
    S("magazine", 7),
    S("editorial", 7),
    S("news", 6),
    S("press", 5),
    S("reporter", 7),
    S("columnist", 7),
    S("local news", 8),
    S("headlines", 7),
    S("subscribe to our newsletter", 4),
    S("ultimas noticias", 12, "pt"),
    S("noticias", 9, "pt"),
    S("plantao de noticias", 12, "pt"),
    S("jornal", 9, "pt"),
    S("reportagem", 9, "pt"),
    S("redacao", 9, "pt"),
    S("editoria", 9, "pt"),
    S("colunistas", 9, "pt"),
    S("manchete", 9, "pt"),
    S("materia", 4, "pt"),
    S("politica", 4, "pt"),
    S("economia", 4, "pt"),
    S("esporte", 4, "pt"),
    S("entretenimento", 4, "pt"),
    S("cotidiano", 6, "pt"),
    S("portal de noticias", 12, "pt"),
    S("blog", 3, "pt"),
    S("ultime notizie", 12, "it"),
    S("quotidiano", 10, "it"),
    S("giornale", 10, "it"),
    S("cronaca", 9, "it"),
    S("rivista", 8, "it"),
    S("notizie", 9, "it"),
    S("redazione", 9, "it"),
    S("laatste nieuws", 12, "nl"),
    S("nieuws", 9, "nl"),
    S("redactie", 9, "nl"),
    S("krant", 9, "nl"),
    S("artikel", 4, "nl"),
    S("reportage", 7, "nl"),
    S("nieuwsbrief", 4, "nl"),
    S("ultimas noticias", 12, "es"),
    S("periodico", 9, "es"),
    S("redaccion", 9, "es"),
]


# Trade press: media, but the audience is professionals -> reads as B2B.
TRADE_MEDIA = [
    S("trade magazine", 12),
    S("trade publication", 12),
    S("trade press", 10),
    S("industry publication", 12),
    S("industry magazine", 10),
    S("industry news", 10),
    S("b2b media", 12),
    S("professional publication", 10),
    S("business magazine", 8),
    S("industry insights", 7),
    S("market insights", 6),
    S("sector news", 8),
    S("for professionals", 7),
    S("industry report", 8),
    S("revista do setor", 12, "pt"),
    S("noticias do setor", 10, "pt"),
    S("portal do setor", 10, "pt"),
    S("para profissionais", 8, "pt"),
    S("mercado publicitario", 10, "pt"),
    S("veiculos de comunicacao", 8, "pt"),
    S("rivista di settore", 12, "it"),
    S("notizie di settore", 10, "it"),
    S("vakblad", 12, "nl"),
    S("vakmedia", 12, "nl"),
]


EDUCATION = [
    S("university", 12),
    S("college", 9),
    S("admissions", 12),
    S("faculty", 8),
    S("campus", 8),
    S("curriculum", 8),
    S("school", 8),
    S("academy", 7),
    S("degree", 8),
    S("scholarship", 9),
    S("courses", 6),
    S("training", 5),
    S("students", 5),
    S("enroll", 8),
    S("universidade", 12, "pt"),
    S("faculdade", 10, "pt"),
    S("vestibular", 12, "pt"),
    S("matricula", 9, "pt"),
    S("curso", 5, "pt"),
    S("cursos", 6, "pt"),
    S("aluno", 6, "pt"),
    S("bolsa de estudos", 10, "pt"),
    S("escola", 7, "pt"),
    S("universita", 12, "it"),
    S("iscrizioni", 9, "it"),
    S("corsi", 6, "it"),
    S("universiteit", 12, "nl"),
    S("opleiding", 8, "nl"),
]


GOVERNMENT = [
    S("government agency", 12),
    S("public administration", 12),
    S("ministry of", 12),
    S("municipality", 10),
    S("city council", 10),
    S("public services", 8),
    S("official website of", 8),
    S("prefeitura", 12, "pt"),
    S("governo do estado", 12, "pt"),
    S("ministerio", 12, "pt"),
    S("camara municipal", 12, "pt"),
    S("portal da transparencia", 12, "pt"),
    S("servicos publicos", 8, "pt"),
    S("diario oficial", 12, "pt"),
    S("pubblica amministrazione", 12, "it"),
    S("ministero", 12, "it"),
    S("comune di", 10, "it"),
    S("regione", 6, "it"),
    S("gemeente", 10, "nl"),
    S("overheid", 12, "nl"),
]


NONPROFIT = [
    S("non profit", 12),
    S("nonprofit", 12),
    S("charity", 12),
    S("ngo", 12),
    S("donate now", 10),
    S("our mission", 5),
    S("foundation", 7),
    S("volunteer", 8),
    S("fundraising", 9),
    S("organizacao sem fins lucrativos", 12, "pt"),
    S("doe agora", 10, "pt"),
    S("faca uma doacao", 12, "pt"),
    S("voluntario", 8, "pt"),
    S("instituto", 5, "pt"),
    S("ong", 12, "pt"),
    S("senza scopo di lucro", 12, "it"),
    S("beneficenza", 10, "it"),
    S("fondazione", 8, "it"),
    S("associazione", 6, "it"),
    S("goede doel", 10, "nl"),
    S("vzw", 10, "nl"),
]


# Advertising / monetization. NOT an audience signal — every news portal
# sells ad space, which is exactly why the first version of this rewrite
# mislabelled news portals as B2B. Kept as its own group so the decision
# layer can read it as "how the site makes money", never as "who it serves".
ADVERTISING = [
    S("advertise with us", 10),
    S("media kit", 10),
    S("advertising rates", 10),
    S("advertise", 6),
    S("sponsored content", 7),
    S("partner with us", 5),
    S("anuncie conosco", 10, "pt"),
    S("anuncie aqui", 10, "pt"),
    S("midia kit", 10, "pt"),
    S("publicidade", 6, "pt"),
    S("conteudo patrocinado", 8, "pt"),
    S("publieditorial", 8, "pt"),
    S("pubblicita", 6, "it"),
    S("adverteren", 8, "nl"),
]


TEXT_SIGNALS: dict[str, list[Signal]] = {
    "B2B": B2B,
    "B2C": B2C,
    "MEDIA": MEDIA,
    "TRADE_MEDIA": TRADE_MEDIA,
    "EDUCATION": EDUCATION,
    "GOVERNMENT": GOVERNMENT,
    "NONPROFIT": NONPROFIT,
    "ADVERTISING": ADVERTISING,
}


# ====================================================================
# URL / PATH SIGNALS
# ====================================================================
#
# Matched against internal link paths. A site's own navigation is far
# more honest than its marketing copy — /carrinho is not a coincidence.
# ====================================================================


URL_SIGNALS: dict[str, dict[str, int]] = {
    "B2B": {
        "/enterprise": 10,
        "/business": 7,
        "/solutions": 5,
        "/industries": 5,
        "/partners": 6,
        "/partner": 6,
        "/developers": 5,
        "/api": 5,
        "/request-demo": 12,
        "/demo": 9,
        "/contact-sales": 12,
        "/pricing": 5,
        "/wholesale": 12,
        "/resellers": 10,
        # pt / it / nl
        "/empresas": 9,
        "/para-empresas": 10,
        "/atacado": 12,
        "/revendedor": 10,
        "/orcamento": 8,
        "/aziende": 9,
        "/rivenditori": 10,
        "/zakelijk": 9,
    },
    "B2C": {
        "/cart": 12,
        "/checkout": 12,
        "/shop": 8,
        "/store": 6,
        "/products": 5,
        "/product": 5,
        "/wishlist": 8,
        "/collections": 6,
        "/sale": 5,
        "/orders": 6,
        "/my-account": 6,
        "/carrinho": 12,
        "/finalizar-compra": 12,
        "/loja": 8,
        "/produtos": 5,
        "/produto": 5,
        "/minha-conta": 6,
        "/meus-pedidos": 8,
        "/promocoes": 6,
        "/carrello": 12,
        "/negozio": 8,
        "/winkelwagen": 12,
        "/webshop": 8,
        "/carrito": 12,
        "/tienda": 8,
    },
    "MEDIA": {
        "/news": 10,
        "/newsroom": 10,
        "/press": 6,
        "/magazine": 8,
        "/editorial": 8,
        "/article": 6,
        "/articles": 6,
        "/opinion": 7,
        "/noticias": 10,
        "/ultimas-noticias": 12,
        "/cronaca": 10,
        "/politica": 6,
        "/economia": 6,
        "/esportes": 6,
        "/esporte": 6,
        "/entretenimento": 6,
        "/colunistas": 9,
        "/redacao": 9,
        "/editorias": 9,
        "/blog": 3,
        "/categoria": 4,
        "/tag": 3,
        "/notizie": 10,
        "/articoli": 7,
        "/redazione": 9,
        "/nieuws": 10,
        "/redactie": 9,
        "/artikel": 5,
    },
    "TRADE_MEDIA": {
        "/industry": 8,
        "/sectors": 8,
        "/trade": 8,
        "/market": 5,
        "/setor": 8,
        "/mercado": 6,
    },
    "EDUCATION": {
        "/education": 10,
        "/courses": 10,
        "/course": 8,
        "/training": 9,
        "/academy": 10,
        "/school": 10,
        "/university": 12,
        "/admissions": 12,
        "/cursos": 10,
        "/curso": 8,
        "/vestibular": 12,
        "/matricula": 10,
        "/alunos": 8,
        "/corsi": 10,
        "/opleidingen": 10,
    },
    "GOVERNMENT": {
        "/government": 12,
        "/ministry": 12,
        "/ministero": 12,
        "/comune": 10,
        "/regione": 8,
        "/servizi": 5,
        "/prefeitura": 12,
        "/transparencia": 10,
        "/licitacoes": 10,
        "/servicos": 5,
        "/gemeente": 10,
    },
    "ADVERTISING": {
        "/advertise": 10,
        "/media-kit": 10,
        "/advertising": 8,
        "/anuncie": 10,
        "/publicidade": 8,
        "/midia-kit": 10,
        "/adverteren": 10,
        "/pubblicita": 8,
    },
    "NONPROFIT": {
        "/donate": 12,
        "/donation": 12,
        "/volunteer": 9,
        "/mission": 4,
        "/doacao": 12,
        "/doe": 10,
        "/voluntario": 9,
        "/doneren": 12,
    },
}


# ====================================================================
# PLATFORM FINGERPRINTS  (matched as raw substrings in the HTML source)
# ====================================================================


ECOMMERCE_TECH: dict[str, int] = {
    "shopify": 12,
    "woocommerce": 12,
    "magento": 10,
    "prestashop": 10,
    "bigcommerce": 10,
    "opencart": 8,
    "vtex": 10,  # dominant in Brazil
    "nuvemshop": 10,  # dominant in Brazil
    "tray.com.br": 8,
    "loja integrada": 10,
}

# Publishing platforms — weak evidence of MEDIA, never of commerce.
PUBLISHING_TECH: dict[str, int] = {
    "wp-content": 2,
    "wordpress": 2,
    "googletagmanager": 0,
    "wp-json/wp/v2/posts": 4,
    "arc-publishing": 8,
    "eleicoes": 0,
}


# ====================================================================
# CRAWL HINTS
# ====================================================================
#
# On a deep run the engine fetches a few internal pages. Homepages of
# news portals are pure headlines and reveal almost nothing about the
# business model; /sobre, /anuncie, /contato do.
# ====================================================================


CRAWL_HINT_PATHS: list[str] = [
    "/about",
    "/about-us",
    "/contact",
    "/pricing",
    "/services",
    "/shop",
    "/products",
    "/advertise",
    "/media-kit",
    "/partners",
    "/solutions",
    "/sobre",
    "/sobre-nos",
    "/quem-somos",
    "/contato",
    "/anuncie",
    "/publicidade",
    "/midia-kit",
    "/expediente",
    "/institucional",
    "/servicos",
    "/produtos",
    "/planos",
    "/assine",
    "/chi-siamo",
    "/contatti",
    "/over-ons",
    "/contacteer",
    "/adverteren",
]


# ====================================================================
# NICHE
# ====================================================================


NICHE_KEYWORDS: dict[str, list[str]] = {
    "crypto": [
        "cryptocurrency",
        "bitcoin",
        "ethereum",
        "crypto",
        "blockchain",
        "web3",
        "defi",
        "nft",
        "criptomoeda",
        "criptomoedas",
        "cripto",
    ],
    "finance": [
        "banking",
        "loan",
        "mortgage",
        "investment",
        "fintech",
        "insurance",
        "banco",
        "emprestimo",
        "investimento",
        "financas",
        "seguros",
        "cartao de credito",
    ],
    "casino": [
        "casino",
        "slots",
        "betting",
        "sportsbook",
        "poker",
        "gambling",
        "apostas",
        "cassino",
        "aposta esportiva",
        "bet",
    ],
    "technology": [
        "software",
        "technology",
        "cloud",
        "saas",
        "developer",
        "platform",
        "tecnologia",
        "desenvolvimento",
        "programacao",
        "aplicativo",
        "inteligencia artificial",
    ],
    "gaming": [
        "gaming",
        "gamer",
        "videogame",
        "playstation",
        "xbox",
        "nintendo",
        "esports",
        "jogos",
        "jogo",
        "games",
        "steam",
    ],
    "sports": [
        "football",
        "soccer",
        "tennis",
        "basketball",
        "championship",
        "futebol",
        "campeonato",
        "time",
        "torcida",
        "tenis",
        "atleta",
        "placar",
        "rodada",
    ],
    "ecommerce": [
        "online store",
        "add to cart",
        "checkout",
        "shop now",
        "loja online",
        "comprar",
        "carrinho",
        "frete",
    ],
    "healthcare": [
        "healthcare",
        "hospital",
        "clinic",
        "medical",
        "pharmacy",
        "saude",
        "medico",
        "clinica",
        "farmacia",
        "tratamento",
    ],
    "education": [
        "education",
        "course",
        "training",
        "school",
        "university",
        "educacao",
        "curso",
        "escola",
        "universidade",
        "aprendizado",
    ],
    "marketing": [
        "marketing",
        "seo",
        "advertising",
        "digital marketing",
        "branding",
        "publicidade",
        "propaganda",
        "agencia",
        "midia",
        "campanha",
    ],
    "environment": [
        "sustainability",
        "environment",
        "climate",
        "renewable",
        "ecology",
        "sustentabilidade",
        "meio ambiente",
        "clima",
        "ecologia",
        "reciclagem",
        "natureza",
    ],
    "logistics": [
        "logistics",
        "shipping",
        "freight",
        "port",
        "supply chain",
        "logistica",
        "porto",
        "portos",
        "navegacao",
        "cabotagem",
        "carga",
    ],
    "news": [
        "breaking news",
        "newsroom",
        "noticias",
        "jornal",
        "reportagem",
        "manchete",
        "nieuws",
        "notizie",
    ],
}
