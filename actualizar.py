import os
import json
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
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; SamsungRadarBot/1.0)'}
    
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

def elegir_modelo_flash(client):
    try:
        disponibles = [
            m.name.replace("models/", "")
            for m in client.models.list()
            if "flash" in m.name.lower()
            and "lite" not in m.name.lower()
            and "image" not in m.name.lower()
            and "audio" not in m.name.lower()
        ]
        for preferido in ["gemini-3-flash", "gemini-3-flash-preview", "gemini-2.5-flash"]:
            if preferido in disponibles:
                return preferido
        if disponibles:
            return disponibles[0]
    except Exception:
        pass
    return "gemini-3-flash"

def generar_resumen(texto_bruto):
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    modelo = elegir_modelo_flash(client)
    print(f"Usando modelo: {modelo}")
    
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
        model=modelo,
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
