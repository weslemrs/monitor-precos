"""
Monitor de Preços com IA (Groq — gratuito)
==========================================
Versão 2 — busca os dois produtos mais baratos numa página de resultados

Requisitos:
    pip install requests beautifulsoup4 groq

Variáveis de ambiente necessárias:
    GROQ_API_KEY  — chave da API da Groq
                    Cadastro gratuito em: https://console.groq.com
"""

import csv
import json
import os
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from groq import Groq

# ─────────────────────────────────────────────
# CONFIGURAÇÃO — edite aqui
# ─────────────────────────────────────────────

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise EnvironmentError(
        "Variável GROQ_API_KEY não encontrada.\n"
        "Localmente: export GROQ_API_KEY='gsk_...'\n"
        "No GitHub: Settings > Secrets and variables > Actions > New secret"
    )

# Cada entrada agora é uma página de BUSCA, não de produto único
# O script vai encontrar os dois mais baratos dentro dessa página
BUSCAS = [
    {
        "produto": "Ovos 20 unidades",
        "url": "https://www.superpaguemenos.com.br/ovos%20brancos%2020%20unidades/",
        "loja": "Pague Menos",
        "filtro_classe": "item product",  # classe CSS dos blocos de produto
    },
    # Adicione mais buscas aqui no mesmo formato
]

CSV_SAIDA = "historico_precos.csv"

# ─────────────────────────────────────────────
# FUNÇÕES
# ─────────────────────────────────────────────

def buscar_html(url: str) -> str | None:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "pt-BR,pt;q=0.9",
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"  Erro ao acessar {url}: {e}")
        return None


def extrair_blocos_produto(html: str, filtro_classe: str) -> str:
    """
    Em vez de pegar todo o texto da página:
    1. Encontra só os blocos com a classe CSS dos produtos
    2. Filtra os que mencionam "20" e "unidade" (para garantir que são ovos c/20)
    3. Retorna o texto limpo desses blocos
    """
    soup = BeautifulSoup(html, "html.parser")

    # Pega só os blocos de produto
    blocos = soup.find_all(class_=filtro_classe)

    blocos_filtrados = []
    for bloco in blocos:
        texto = bloco.get_text(separator=" ", strip=True)
        # Filtra só os blocos que mencionam 20 unidades
        if "20" in texto and ("unidade" in texto.lower() or "und" in texto.lower()):
            blocos_filtrados.append(texto)

    if not blocos_filtrados:
        # Se não encontrou com filtro, manda todos os blocos
        blocos_filtrados = [b.get_text(separator=" ", strip=True) for b in blocos]

    return "\n---\n".join(blocos_filtrados[:20])  # Limita a 20 blocos


def extrair_mais_baratos_com_ia(blocos_texto: str, nome_produto: str) -> dict:
    """
    Manda os blocos de produto pra IA e pede os dois mais baratos com marca.
    """
    client = Groq(api_key=GROQ_API_KEY)

    prompt = f"""Estou te enviando blocos de texto extraídos de uma página de supermercado.
Cada bloco separado por "---" representa um produto diferente.
Todos são relacionados a: {nome_produto}

Blocos:
---
{blocos_texto}
---

Encontre o preço e a marca de cada produto.
Retorne os dois produtos com menor preço.
Responda APENAS com JSON válido, sem explicação, sem markdown:

{{
  "produtos": [
    {{"marca": "Nome da marca", "preco": 0.00, "unidade": "20 unidades"}},
    {{"marca": "Nome da marca", "preco": 0.00, "unidade": "20 unidades"}}
  ]
}}

Se não encontrar dois produtos, retorne apenas os que encontrar.
Se não encontrar nenhum, retorne:
{{
  "produtos": [],
  "observacao": "motivo pelo qual não encontrou"
}}
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0,
        )
        resposta = response.choices[0].message.content.strip()
        resposta = resposta.replace("```json", "").replace("```", "").strip()
        return json.loads(resposta)
    except (json.JSONDecodeError, Exception) as e:
        print(f"  Erro na IA: {e}")
        return {"produtos": [], "observacao": str(e)}


def salvar_csv(linha: dict):
    cabecalho = ["data", "hora", "loja", "produto", "posicao", "marca", "preco", "unidade", "url"]
    arquivo_existe = os.path.exists(CSV_SAIDA)
    with open(CSV_SAIDA, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=cabecalho)
        if not arquivo_existe:
            writer.writeheader()
        writer.writerow(linha)


# ─────────────────────────────────────────────
# EXECUÇÃO PRINCIPAL
# ─────────────────────────────────────────────

def main():
    agora = datetime.now()
    print(f"\nMonitor de Precos v2 — {agora.strftime('%d/%m/%Y %H:%M')}")
    print("=" * 50)

    for busca in BUSCAS:
        print(f"\nProduto: {busca['produto']} — {busca['loja']}")
        print(f"URL: {busca['url']}")

        # Passo 1: Busca o HTML
        html = buscar_html(busca["url"])
        if not html:
            continue

        # Passo 2: Extrai só os blocos de produto relevantes
        blocos = extrair_blocos_produto(html, busca["filtro_classe"])
        print(f"  Blocos encontrados: {blocos.count('---') + 1}")

        # Passo 3: IA encontra os dois mais baratos
        print("  Enviando para a IA...")
        resultado = extrair_mais_baratos_com_ia(blocos, busca["produto"])

        produtos = resultado.get("produtos", [])

        if not produtos:
            print(f"  Nao encontrado: {resultado.get('observacao', 'sem detalhes')}")
            salvar_csv({
                "data": agora.strftime("%d/%m/%Y"),
                "hora": agora.strftime("%H:%M"),
                "loja": busca["loja"],
                "produto": busca["produto"],
                "posicao": "",
                "marca": "",
                "preco": "",
                "unidade": "",
                "url": busca["url"],
            })
            continue

        # Passo 4: Exibe e salva os dois mais baratos
        for i, p in enumerate(produtos, 1):
            print(f"  #{i} {p.get('marca','?')} — R$ {p.get('preco', 0):.2f} ({p.get('unidade','?')})")
            salvar_csv({
                "data": agora.strftime("%d/%m/%Y"),
                "hora": agora.strftime("%H:%M"),
                "loja": busca["loja"],
                "produto": busca["produto"],
                "posicao": i,
                "marca": p.get("marca", ""),
                "preco": p.get("preco", ""),
                "unidade": p.get("unidade", ""),
                "url": busca["url"],
            })

    print(f"\nConcluido! Dados salvos em: {CSV_SAIDA}\n")


if __name__ == "__main__":
    main()
