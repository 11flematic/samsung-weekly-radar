import os
import json
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from google import genai

# Fuentes abiertas: medios especializados, comunidad Reddit y filtradores clave de X
FUENTES = [
    "https://www.sammobile.com/feed/",
    "https://9to5google.com/guides/samsung/feed/",
    "https://www.androidauthority.com/feed/",
    "https://news.google.com/rss/search?q=site:reddit.com/r/samsung+OR+site:reddit.com/r/GalaxyS24&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=site:x.com+UniverseIce+OR+tarunvats33+OR+MaxJmb+Samsung&hl=en-US&gl=US&ceid=US:en"
]


def obtener_titulares():
    recopilacion = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
    }

    for url in FUENTES:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=12) as resp:
                xml_data = resp.read()
                root = ET.fromstring(xml_data)
                items = root.findall('.//item')[:8] or root.findall('.//{http://www.w3.org/2005/Atom}entry')[:8]
                for item in items:
                    titulo = item.findtext('title') or item.findtext('{http://www.w3.org/2005/Atom}title')
                    link = item.findtext('link')
                    if link is None:
                        link_el = item.find('{http://www.w3.org/2005/Atom}link')
                        link = link_el.attrib.get('href', '') if link_el is not None else ''
                    if titulo:
                        recopilacion.append(f"- {titulo.strip()} ({link})")
        except Exception as e:
            print(f"Saltando fuente {url}: {e}")

    return "\n".join(recopilacion)


def obtener_candidatos_modelo(client):
    candidatos = []
    excluidos = ("2.5", "2.0", "1.5", "embedding", "imagen", "veo", "tts", "audio", "image", "aqa", "robotics", "computer-use")

    try:
        for m in client.models.list():
            nombre = m.name.replace("models/", "")
            if "gemini" in nombre.lower() and not any(x in nombre.lower() for x in excluidos):
                if nombre not in candidatos:
                    candidatos.append(nombre)
    except Exception as e:
        print(f"Error listando modelos: {e}")

    def prioridad(nombre):
        if nombre == "gemini-3.8-flash":
            return 0
        if "3.8" in nombre and "flash" in nombre:
            return 1
        if "flash-lite" in nombre:
            return 2
        if "flash" in nombre:
            return 3
        if "3" in nombre:
            return 4
        return 5

    candidatos.sort(key=prioridad)
    if "gemini-3.8-flash" not in candidatos:
        candidatos.insert(0, "gemini-3.8-flash")
    print(f"Modelos candidatos detectados: {candidatos}")
    return candidatos


def generar_resumen(texto_bruto):
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    prompt = f"""
    Eres un analista experto en el ecosistema Samsung. Analiza estos titulares, tuits y posts de esta semana y crea un resumen ejecutivo en español, directo, sin relleno y bien estructurado.
    
    Reglas:
- Elimina duplicados y rumores sin fundamento.
- Devuelve ÚNICAMENTE un objeto JSON válido con esta estructura exacta (sin bloques markdown ```json):
    {{
      "fecha_actualizacion": "{datetime.now().strftime('%d/%m/%Y %H:%M')}",
      "titular_semana": "Frase corta con lo más importante de la semana",
      "bloques": [
        {{
          "categoria": "One UI y Actualizaciones",
          "resumen": "Párrafo claro y directo con las novedades de software y parches.",
          "puntos_clave": ["Dato 1", "Dato 2"]
        }},
        {{
          "categoria": "Filtraciones y Hardware",
          "resumen": "Qué se ha filtrado de próximos Galaxy, relojes o accesorios.",
          "puntos_clave": ["Dato 1", "Dato 2"]
        }},
        {{
          "categoria": "Pulso de la Comunidad",
          "resumen": "Qué comentan los usuarios en Reddit/X (bugs, trucos o funciones destacadas).",
          "puntos_clave": ["Dato 1", "Dato 2"]
        }}
      ]
    }}

    Datos recopilados:
    {texto_bruto}
    """

    ultimo_error = None
    for modelo in obtener_candidatos_modelo(client):
        print(f"Probando modelo: {modelo}")
        for intento in range(3):
            try:
                response = client.models.generate_content(
                    model=modelo,
                    contents=prompt
                )
                limpio = response.text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                return json.loads(limpio)
            except Exception as e:
                ultimo_error = e
                error_str = str(e)
                if ("503" in error_str or "UNAVAILABLE" in error_str) and intento < 2:
                    espera = (intento + 1) * 15
                    print(f"Modelo saturado (503). Reintentando {modelo} en {espera}s...")
                    time.sleep(espera)
                    continue
                print(f"No disponible {modelo}: {e}")
                break

    raise RuntimeError(f"Ningún modelo pudo generar el resumen. Último error: {ultimo_error}")


if __name__ == "__main__":
    noticias = obtener_titulares()
    if noticias:
        resultado = generar_resumen(noticias)
        with open("datos.json", "w", encoding="utf-8") as f:
            json.dump(resultado, f, ensure_ascii=False, indent=2)
        print("Resumen generado con éxito.")
