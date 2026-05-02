#Começar com materiais e métodos
#Descrever como foram feitos em python e JS
#Refazer site em leaflet

import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import folium
from shapely import wkt
from geopy.geocoders import ArcGIS 
import os
import requests
import time
import re

class Table2Geo:
    def __init__(self, root):
        self.root = root
        self.root.title("Table2Geo v1.0")
        self.root.geometry("600x550")
        
        self.df = None
        self.geolocator = ArcGIS(user_agent="table2geo_app")
        
        self.col_desc = tk.StringVar()
        self.col_geo = tk.StringVar()
        self.col_endereco = tk.StringVar()
        self.tipo_feicao = tk.StringVar(value="Point")

        self.create_widgets()

    def create_widgets(self):
        tk.Label(self.root, text="1. Carregar Dados", font=("Arial", 11, "bold")).pack(pady=10)
        tk.Button(self.root, text="Selecionar Planilha Excel", command=self.carregar_arquivo, bg="#4da6ff", fg="white").pack()
        self.lbl_status = tk.Label(self.root, text="Nenhum arquivo carregado", fg="red")
        self.lbl_status.pack(pady=5)

        self.frame_config = tk.LabelFrame(self.root, text=" 2. Configurações de Mapeamento ", padx=10, pady=10)
        self.frame_config.pack(padx=20, pady=10, fill="x")

        tk.Label(self.frame_config, text="Coluna para Popup:").grid(row=0, column=0, sticky="w")
        self.cb_desc = ttk.Combobox(self.frame_config, textvariable=self.col_desc, state="readonly", width=40)
        self.cb_desc.grid(row=0, column=1, pady=5)

        self.tabs = ttk.Notebook(self.frame_config)
        self.tabs.grid(row=1, column=0, columnspan=2, pady=10, sticky="ew")

        # Aba WKT
        self.tab_wkt = tk.Frame(self.tabs)
        self.tabs.add(self.tab_wkt, text="Usar Geometria (WKT)")
        tk.Label(self.tab_wkt, text="Coluna WKT:").pack(side="left", padx=5)
        self.cb_geo = ttk.Combobox(self.tab_wkt, textvariable=self.col_geo, state="readonly", width=35)
        self.cb_geo.pack(side="left", pady=10)

        # Aba Endereço
        self.tab_addr = tk.Frame(self.tabs)
        self.tabs.add(self.tab_addr, text="Usar Endereço (API)")
        tk.Label(self.tab_addr, text="Coluna Endereço:").pack(side="left", padx=5)
        self.cb_addr = ttk.Combobox(self.tab_addr, textvariable=self.col_endereco, state="readonly", width=35)
        self.cb_addr.pack(side="left", pady=10)

        tk.Label(self.root, text="3. Tipo de Geometria:", font=("Arial", 10, "bold")).pack()
        self.combo_tipo = ttk.Combobox(self.root, textvariable=self.tipo_feicao, 
                                       values=["Point", "LineString", "Polygon"], state="readonly")
        self.combo_tipo.pack(pady=5)

        tk.Button(self.root, text="GERAR E ABRIR MAPA", command=self.processar_mapa, 
                  bg="#25D366", fg="white", font=("Arial", 12, "bold"), height=2).pack(pady=20)

    def carregar_arquivo(self):
        caminho = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx"), ("CSV files", "*.csv")])
        if not caminho: return
        try:
            if caminho.endswith('.csv'):
                self.df = pd.read_csv(caminho)
            else:
                self.df = pd.read_excel(caminho)
                
            cols = list(self.df.columns)
            self.cb_desc['values'] = cols
            self.cb_geo['values'] = ["Nenhuma"] + cols
            self.cb_addr['values'] = ["Nenhuma"] + cols
            self.lbl_status.config(text=f"Carregado: {os.path.basename(caminho)}", fg="green")
        except Exception as e:
            messagebox.showerror("Erro", str(e))

    def processar_mapa(self):
        if self.df is None: return
        
        self.lbl_status.config(text="Buscando geometrias... Aguarde!", fg="blue")
        self.root.update()
        
        m = folium.Map(location=[-26.99, -48.63], zoom_start=13)
        aba_ativa = self.tabs.index(self.tabs.select())
        sucessos = 0

        for i, row in self.df.iterrows():
            try:
                desc = str(row[self.col_desc.get()])
                if pd.isna(desc) or desc.lower() == 'nan': desc = f"Item {i}"
                tipo = self.tipo_feicao.get()

                # ==========================================
                # MODO 1: WKT (Geometria do Banco)
                # ==========================================
                if aba_ativa == 0:
                    val_wkt = str(row[self.col_geo.get()])
                    if pd.isna(val_wkt) or val_wkt.lower() in ['nan', 'none', '']: continue
                    
                    try:
                        geom = wkt.loads(val_wkt)
                        if geom.geom_type == 'Point':
                            folium.Marker([geom.y, geom.x], popup=desc).add_to(m)
                        else:
                            folium.GeoJson(geom.__geo_interface__, tooltip=desc).add_to(m)
                        sucessos += 1
                    except Exception as e:
                        print(f"Erro ao ler WKT na linha {i}: O texto não é uma geometria válida.")
                        continue

                # ==========================================
                # MODO 2: ENDEREÇO (Busca via API Nominatim/ArcGIS)
                # ==========================================
                else:
                    endereco_bruto = str(row[self.col_endereco.get()])
                    if pd.isna(endereco_bruto) or endereco_bruto.lower() in ['nan', 'none', '']: continue
                    
                    # Limpeza inteligente para melhorar a busca
                    busca = endereco_bruto
                    if "SC" not in busca.upper() and "Santa Catarina" not in busca:
                        busca = f"{busca}, SC"
                    
                    # Remove a palavra "Bairro" que confunde a API
                    busca_limpa_poligono = busca.replace("Bairro ", "").replace("bairro ", "")

                    if tipo == "Point":
                        location = self.geolocator.geocode(f"{busca}, Brasil")
                        if location:
                            folium.Marker([location.latitude, location.longitude], popup=desc).add_to(m)
                            sucessos += 1

                    elif tipo in ["LineString", "Polygon"]:
                        if tipo == "LineString":
                            busca_api = re.sub(r'\b\d+\b', '', busca) # Tira números de porta
                            busca_api = busca_api.replace(', ,', ',').strip(' ,')
                            
                            # Tradutor rápido para ruas numeradas de BC
                            traducao_ruas = {
                                "3300": "Três Mil e Trezentos",
                                "1500": "Mil e Quinhentos",
                                "3100": "Três Mil e Cem",
                                # Você pode adicionar outras ruas importantes aqui!
                            }
                            for num, texto in traducao_ruas.items():
                                busca_api = busca_api.replace(num, texto)
                        else:
                            busca_api = busca_limpa_poligono

                        # Adicionei &limit=50 para a API trazer 50 resultados ao invés de só 10
                        url_nom = f"https://nominatim.openstreetmap.org/search?q={busca_api}&format=json&polygon_geojson=1&limit=50"
                        headers = {'User-Agent': 'Table2Geo_App_AllLines'}
                        
                        time.sleep(1.2) 
                        resp = requests.get(url_nom, headers=headers).json()
                        
                        if resp and len(resp) > 0:
                            
                            # ==========================================
                            # SE FOR LINHA: Pega TODOS os trechos
                            # ==========================================
                            if tipo == "LineString":
                                desenhou_linha = False
                                for resultado in resp:
                                    if "geojson" in resultado:
                                        if "Line" in resultado["geojson"].get("type", ""):
                                            # Aqui tiramos o 'break'! Ele vai pintar todos os trechos da rua
                                            folium.GeoJson(
                                                resultado["geojson"], 
                                                tooltip=desc, 
                                                style_function=lambda x: {'color': '#3388ff', 'weight': 5, 'opacity': 0.8}
                                            ).add_to(m)
                                            desenhou_linha = True
                                
                                if desenhou_linha:
                                    sucessos += 1
                                else:
                                    lat, lon = float(resp[0]['lat']), float(resp[0]['lon'])
                                    folium.Marker([lat, lon], popup=f"{desc} (Apenas ponto encontrado)").add_to(m)
                                    sucessos += 1

                            # ==========================================
                            # SE FOR POLÍGONO: Mantém a lógica do primeiro que achar
                            # ==========================================
                            elif tipo == "Polygon":
                                geo = None
                                tipo_geo = ""
                                for resultado in resp:
                                    if "geojson" in resultado:
                                        temp_tipo = resultado["geojson"].get("type", "")
                                        if "Polygon" in temp_tipo:
                                            geo = resultado["geojson"]
                                            tipo_geo = temp_tipo
                                            break # Para polígonos, queremos só 1 mesmo
                                
                                if not geo and "geojson" in resp[0]:
                                    geo = resp[0]["geojson"]
                                    tipo_geo = geo.get("type", "")

                                if "Polygon" in tipo_geo:
                                    folium.GeoJson(geo, tooltip=desc, style_function=lambda x: {'fillColor': '#ff7800', 'color': 'black', 'weight': 2}).add_to(m)
                                    sucessos += 1
                                else:
                                    lat, lon = float(resp[0]['lat']), float(resp[0]['lon'])
                                    folium.Circle(location=[lat, lon], radius=50, popup=f"{desc} (Sem polígono)", color='red', fill=True).add_to(m)
                                    sucessos += 1

            except Exception as e:
                print(f"Erro na linha {i} ({desc}): {e}")

        m.save("mapa_final.html")
        os.startfile("mapa_final.html")
        
        self.lbl_status.config(text=f"Processado: {sucessos} itens!", fg="green")
        messagebox.showinfo("Fim", f"Processamento concluído!\n{sucessos} itens desenhados no mapa.")

if __name__ == "__main__":
    root = tk.Tk()
    app = Table2Geo(root)
    root.mainloop()