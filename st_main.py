import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from shapely import wkt
from geopy.geocoders import ArcGIS 
import requests
import time
import re

# Configuração da página
st.set_page_config(page_title="Table2Geo", layout="wide")
st.title("📍 Table2Geo Web - Versão Streamlit")

geolocator = ArcGIS(user_agent="table2geo_app")

# BARRA LATERAL (CONFIGURAÇÕES)
with st.sidebar:
    st.header("Configurações")
    arquivo = st.file_uploader("1. Carregar Planilha", type=["xlsx", "csv"])
    
    if arquivo:
        # Lê o arquivo
        if arquivo.name.endswith('.csv'):
            df = pd.read_csv(arquivo)
        else:
            df = pd.read_excel(arquivo)
            
        colunas = ["Nenhuma"] + df.columns.tolist()
        
        # Selects
        col_desc = st.selectbox("Coluna de Descrição (Popup)", df.columns.tolist())
        modo = st.radio("Modo de Busca:", ["Usar WKT", "Usar Endereço"])
        
        if modo == "Usar WKT":
            col_geo = st.selectbox("Coluna de Geometria (WKT)", colunas)
        else:
            col_endereco = st.selectbox("Coluna de Endereço", colunas)
            
        tipo_geo = st.selectbox("Tipo de Geometria", ["Point", "LineString", "Polygon"])
        
        # Botão principal
        btn_gerar = st.button("Gerar Mapa", use_container_width=True)

# LÓGICA DE PROCESSAMENTO (Roda só ao clicar no botão gerar)
if arquivo and btn_gerar:
    inform = st.info("Processando dados e buscando coordenadas... Aguarde!")
    
    m = folium.Map(location=[0, 0], zoom_start=2)
    sucessos = 0
    erros = 0
    bounds = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, row in df.iterrows():
        try:
            desc = str(row[col_desc])
            if pd.isna(desc) or desc.lower() == 'nan': desc = f"Item {i}"
            
            # --- MODO 1: WKT ---
            if modo == "Usar WKT" and col_geo != "Nenhuma":
                val_wkt = str(row[col_geo])
                if pd.isna(val_wkt) or val_wkt.lower() in ['nan', 'none', '']: continue
                try:
                    geom = wkt.loads(val_wkt)
                    if geom.geom_type == 'Point':
                        folium.Marker(
                            [geom.y, geom.x], 
                            popup=desc,
                            icon=folium.Icon(color="blue", icon="info-sign") # Formato de pino clássico!
                        ).add_to(m)
                        bounds.append([geom.y, geom.x])
                    else:
                        folium.GeoJson(geom.__geo_interface__, tooltip=desc).add_to(m)
                        bounds.append([geom.centroid.y, geom.centroid.x])
                    sucessos += 1
                except Exception:
                    erros += 1
                    continue
            
            # --- MODO 2: ENDEREÇO ---
            elif modo == "Usar Endereço" and col_endereco != "Nenhuma":
                busca = str(row[col_endereco])
                if pd.isna(busca) or busca.lower() in ['nan', 'none', '']: continue
                
                if tipo_geo == "Point":
                    location = geolocator.geocode(busca)
                    if location:
                        folium.Marker(
                            [location.latitude, location.longitude], 
                            popup=desc,
                            icon=folium.Icon(color="blue", icon="info-sign") # Formato de pino clássico!
                        ).add_to(m)
                        bounds.append([location.latitude, location.longitude])
                        sucessos += 1
                        
                elif tipo_geo in ["LineString", "Polygon"]:
                    url_nom = f"https://nominatim.openstreetmap.org/search?q={busca}&format=json&polygon_geojson=1&limit=50"
                    headers = {'User-Agent': 'Table2Geo_App'}
                    
                    time.sleep(1.2)
                    resp = requests.get(url_nom, headers=headers).json()
                    
                    if resp and len(resp) > 0:
                        if tipo_geo == "LineString":
                            desenhou_linha = False
                            for resultado in resp:
                                if "geojson" in resultado and "Line" in resultado["geojson"].get("type", ""):
                                    folium.GeoJson(resultado["geojson"], tooltip=desc, style_function=lambda x: {'color': '#3388ff', 'weight': 5}).add_to(m)
                                    desenhou_linha = True
                                    bounds.append([float(resultado['lat']), float(resultado['lon'])])
                            
                            if desenhou_linha:
                                sucessos += 1
                            else:
                                lat, lon = float(resp[0]['lat']), float(resp[0]['lon'])
                                folium.Marker([lat, lon], popup=f"{desc} (Apenas ponto)", icon=folium.Icon(color="orange")).add_to(m)
                                bounds.append([lat, lon])
                                sucessos += 1
                                
                        elif tipo_geo == "Polygon":
                            geo = None
                            for resultado in resp:
                                if "geojson" in resultado and "Polygon" in resultado["geojson"].get("type", ""):
                                    geo = resultado["geojson"]
                                    break
                                        
                            if not geo and "geojson" in resp[0]:
                                geo = resp[0]["geojson"]
                                
                            if "Polygon" in geo.get("type", ""):
                                folium.GeoJson(geo, tooltip=desc, style_function=lambda x: {'fillColor': '#ff7800', 'color': 'black', 'weight': 2}).add_to(m)
                                bounds.append([float(resp[0]['lat']), float(resp[0]['lon'])])
                                sucessos += 1
                            else:
                                lat, lon = float(resp[0]['lat']), float(resp[0]['lon'])
                                folium.Circle(location=[lat, lon], radius=50, popup=f"{desc} (Sem polígono)", color='red', fill=True).add_to(m)
                                bounds.append([lat, lon])
                                sucessos += 1
        except Exception as e:
            erros += 1
            
        porcentagem = (i + 1) / len(df)
        progress_bar.progress(porcentagem)
        status = status_text.text(f"Processando linha {i+1} de {len(df)}...")
        
    if bounds:
        m.fit_bounds(bounds)
        
    # SALVA NA MEMÓRIA DA PÁGINA
    st.session_state['mapa_obj'] = m
    st.session_state['mapa_html'] = m.get_root().render()
    concluido = st.success(f"Processamento concluído! {sucessos} itens desenhados com sucesso.")

    # LIMPA STATUS
    time.sleep(2)
    inform.empty()
    progress_bar.empty()
    status.empty()
    concluido.empty()

# ÁREA DE RENDERIZAÇÃO (Sempre visível se o mapa existir na memória)
if 'mapa_obj' in st.session_state:
    # 1. Exibe o mapa (travado para não recarregar à toa)
    st_folium(st.session_state['mapa_obj'], width=1000, height=600, returned_objects=[])
    
    # 2. Exibe o botão de Download que não quebra o código
    st.download_button(
        label="📥 Baixar Mapa em HTML", 
        data=st.session_state['mapa_html'], 
        file_name="meu_mapa_interativo.html", 
        mime="text/html",
        use_container_width=True
    )
