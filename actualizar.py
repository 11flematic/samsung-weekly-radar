import os
import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from google import genai

# Fuentes abiertas: medios especializados, Reddit y publicaciones indexadas de filtradores en X
FUENTES = [
    "https://www.sammobile.com/feed/",
    "https://9to5google.com/guides/samsung/feed/",
    "https://www.androidauthority.com/feed/",
    "https://www.reddit.com/r/samsung/top/.rss?t=week",
    "https://www.reddit.com/r/GalaxyS24/top/.rss?t=week",
    "https://news.google.com/rss/search?q=site:x.com+UniverseIce+OR+tarunvats33+OR+MaxJmb+Samsung&hl=en-US&gl=US&ceid=US:en"
]

def obtener_titulares():
    recopilacion = []
    # Identificador personalizado para evitar bloqueos 429 en Reddit
    headers = {'User-Agent': 'python:samsung-weekly-radar:v1.0 (by /u/11flematic)'}
    
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
    
    response = client.models.generate_content(
        model='gemini-3.0-flash',
        contents=prompt
    )
    
    limpio = response.text.strip().removeprefix("```json").removesuffix("```").strip()
    return json.loads(limpio)

if __name__ == "__main__":
    noticias = obtener_titulares()
    if noticias:
        resultado = generar_resumen(noticias)
        with open("datos.json", "w", encoding="utf-8") as f:
            json.dump(resultado, f, ensure_ascii=False, indent=2)
        print("Resumen generado con éxito.")
