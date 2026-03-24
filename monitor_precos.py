"""
Monitor de Preços com IA (Groq — gratuito)
==========================================
Requisitos:
    pip install requests beautifulsoup4 groq

Variáveis de ambiente necessárias:
    GROQ_API_KEY  — chave da API da Groq
                    Cadastro gratuito em: https://console.groq.com
                    Localmente: export GROQ_API_KEY="gsk_..."
                    No GitHub:  Settings > Secrets > New secret
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

PRODUTOS = [
    {
        "nome": "Ovos brancos tipo grande c/20 - Pague Menos",
        "url": "https://www.superpaguemenos.com.br/ovos-brancos-tipo-grande-com-20-unidades/p",
        "loja": "Pague Menos",
    },
    {
        "nome": "Ovos - Tauste",
        "url": "https://tauste.com.br/marilia/hortifruti/ovos.html",
        "loja": "Tauste",
    },
    # Adicione mais produtos aqui no mesmo formato
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


def extrair_texto_limpo(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "meta", "link"]):
        tag.decompose()
    texto = soup.get_text(separator="\n", strip=True)
    linhas = [l for l in texto.splitlines() if l.strip()]
    return "\n".join(linhas[:150])


def extrair_preco_com_ia(texto_pagina: str, nome_produto: str) -> dict:
    client = Groq(api_key=GROQ_API_KEY)

    prompt = f"""Você é um extrator de preços de páginas de supermercado.

Produto buscado: {nome_produto}

Texto extraído da página:
---
{texto_pagina}
---

Responda APENAS com um JSON válido, sem explicação, sem markdown:
{{
  "preco": 12.99,
  "unidade": "pacote 20 unidades",
  "confianca": "alta",
  "observacao": "preco encontrado na secao de destaque"
}}

Se não encontrar o preço, retorne:
{{
  "preco": null,
  "unidade": null,
  "confianca": "nenhuma",
  "observacao": "motivo pelo qual nao encontrou"
}}
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",  # Modelo gratuito e rápido
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0,  # Zero = respostas mais consistentes para extração
        )
        resposta = response.choices[0].message.content.strip()
        resposta = resposta.replace("```json", "").replace("```", "").strip()
        return json.loads(resposta)
    except (json.JSONDecodeError, Exception) as e:
        print(f"  Erro na IA: {e}")
        return {"preco": None, "unidade": None, "confianca": "erro", "observacao": str(e)}


def salvar_csv(linha: dict):
    cabecalho = ["data", "hora", "loja", "nome", "preco", "unidade", "confianca", "observacao", "url"]
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
    print(f"\nMonitor de Precos — {agora.strftime('%d/%m/%Y %H:%M')}")
    print("=" * 50)

    for produto in PRODUTOS:
        print(f"\nProduto: {produto['nome']}")
        print(f"URL: {produto['url']}")

        html = buscar_html(produto["url"])
        if not html:
            continue

        texto = extrair_texto_limpo(html)

        print("Enviando para a IA...")
        resultado = extrair_preco_com_ia(texto, produto["nome"])

        if resultado["preco"]:
            print(f"Preco: R$ {resultado['preco']:.2f} ({resultado['unidade']})")
            print(f"Confianca: {resultado['confianca']}")
        else:
            print(f"Nao encontrado: {resultado['observacao']}")

        salvar_csv({
            "data": agora.strftime("%d/%m/%Y"),
            "hora": agora.strftime("%H:%M"),
            "loja": produto["loja"],
            "nome": produto["nome"],
            "preco": resultado.get("preco", ""),
            "unidade": resultado.get("unidade", ""),
            "confianca": resultado.get("confianca", ""),
            "observacao": resultado.get("observacao", ""),
            "url": produto["url"],
        })

    print(f"\nConcluido! Dados salvos em: {CSV_SAIDA}\n")


if __name__ == "__main__":
    main()
