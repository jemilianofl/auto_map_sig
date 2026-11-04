import os
import json
import io
import tempfile
import asyncio
import textwrap
from datetime import datetime
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

import geopandas as gpd
import pandas as pd
import pygmt
import fiona
from shapely import force_2d
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
from PIL import Image

# Habilitar soporte KML
fiona.drvsupport.supported_drivers['KML'] = 'rw'
fiona.drvsupport.supported_drivers['LIBKML'] = 'rw'

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def procesar_mapa_sync(kml_path, autor, config_simbologia):
    """Función síncrona que realiza el cálculo pesado aislada en un directorio temporal."""
    
    layers = fiona.listlayers(kml_path)
    gdfs = []
    for layer in layers:
        gdf = gpd.read_file(kml_path, driver='KML', layer=layer)
        gdf = gdf.dropna(subset=['geometry'])
        if not gdf.empty:
            gdf['geometry'] = gdf['geometry'].apply(force_2d)
            gdf = gdf[gdf.geometry.type.isin(['Polygon', 'MultiPolygon'])]
            gdfs.append(gdf)
            
    if not gdfs:
        raise ValueError("No se encontraron polígonos válidos en el KML.")
            
    full_gdf = gpd.GeoDataFrame(pd.concat(gdfs, ignore_index=True), crs="EPSG:4326")
    gdf_utm = full_gdf.to_crs(epsg=32614)
    
    # Extraer centroides para la escala y el mapa de ubicación
    centroide_geo = gdf_utm.geometry.centroid.to_crs(epsg=4326).iloc[0]
    lon_centro, lat_centro = centroide_geo.x, centroide_geo.y
    bounds_utm = gdf_utm.geometry.centroid.iloc[0]
    
    buffer_metros = 150
    from shapely.geometry import box
    bbox_gdf = gpd.GeoDataFrame({'geometry': [box(bounds_utm.x - buffer_metros, bounds_utm.y - buffer_metros, bounds_utm.x + buffer_metros, bounds_utm.y + buffer_metros)]}, crs="EPSG:32614")
    region = bbox_gdf.to_crs(epsg=4326).total_bounds
    region_fmt = [region[0], region[2], region[1], region[3]]

    with tempfile.TemporaryDirectory() as tmpdir:
        mapa_temp = os.path.join(tmpdir, "mapa_temp.png")
        inset_temp = os.path.join(tmpdir, "inset_temp.png")
        
        # 1. Mapa Base PyGMT
        fig_main = pygmt.Figure()
        fig_main.tilemap(region=region_fmt, projection="M15c", source="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", zoom=19)
        
        datos_extraidos = []
        for i, row in full_gdf.reset_index(drop=True).iterrows():
            nombre = str(row.get('Name')).strip()
            
            if nombre not in config_simbologia:
                continue
                
            color_hex = config_simbologia.get(nombre, "#FF0000")
            datos_extraidos.append((nombre, "", color_hex))
            
            gdf_single = gpd.GeoDataFrame([row], crs=full_gdf.crs)
            fig_main.plot(data=gdf_single, pen="1.5p,white", fill=f"{color_hex}@50")
            
        fig_main.basemap(frame=["a", "WSne"], rose="jTL+w1.5c+o0.3c/0.3c+f2")
        # Restaurado: Escala del mapa
        fig_main.basemap(map_scale=f"jBR+c{lat_centro}+w50e+o1.2c/1.2c+f+l", box="+gwhite@50+p0.5p,gray")
        fig_main.savefig(mapa_temp, dpi=300)
        
        # Restaurado: Generar Inset (Mapa de ubicación de México)
        fig_inset = pygmt.Figure()
        region_inset = [-100, -92, 14, 19]
        fig_inset.tilemap(region=region_inset, projection="M4c", source="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", zoom=6)
        fig_inset.coast(borders=["1/0.8p,white", "2/0.3p,white,dashed"])
        fig_inset.plot(x=[lon_centro], y=[lat_centro], style="c0.2c", fill="red", pen="white")
        fig_inset.savefig(inset_temp, transparent=True, crop=True, dpi=300)
        
        # 2. Ensamblar layout institucional
        fig = plt.figure(figsize=(15, 10.5), facecolor='white')
        gs = GridSpec(1, 2, width_ratios=[3.2, 1.2], wspace=0.03)
        
        ax_map = fig.add_subplot(gs[0])
        ax_map.imshow(Image.open(mapa_temp))
        ax_map.axis('off')
        
        ax_panel = fig.add_subplot(gs[1])
        ax_panel.axis('off')
        ax_panel.set_xlim(0, 1)
        ax_panel.set_ylim(0, 1)
        
        if os.path.exists("header.png"):
            ax_header = inset_axes(ax_panel, width="100%", height="11%", loc='upper center', borderpad=0)
            ax_header.imshow(Image.open("header.png"))
            ax_header.axis('off')
            
        if os.path.exists("footer.png"):
            ax_footer = inset_axes(ax_panel, width="100%", height="7%", loc='lower center', borderpad=0)
            ax_footer.imshow(Image.open("footer.png"))
            ax_footer.axis('off')

        ax_panel.text(0.5, 0.88, "PROCURADURÍA FEDERAL DE PROTECCIÓN\nAL AMBIENTE", weight='bold', ha='center', va='center', fontsize=10)
        ax_panel.text(0.5, 0.85, "Subprocuraduría de Recursos Naturales", ha='center', va='center', fontsize=9)

        def draw_box(y_top, height, title, bg_color='#A01F41'):
            ax_panel.add_patch(plt.Rectangle((0, y_top - 0.03), 1, 0.03, fill=True, color=bg_color))
            ax_panel.text(0.5, y_top - 0.015, title, color='white', weight='bold', ha='center', va='center', fontsize=10)
            ax_panel.add_patch(plt.Rectangle((0, y_top - height), 1, height - 0.03, fill=False, edgecolor='black', linewidth=1.2))

        # Restaurado: Localización geográfica
        draw_box(y_top=0.83, height=0.25, title="Localización geográfica")
        ax_panel.imshow(Image.open(inset_temp), extent=[0.05, 0.95, 0.65, 0.79], aspect='auto')
        ax_panel.text(0.5, 0.615, "Estado: Oaxaca\nMunicipio: Santa María Huatulco\nPolígono ZOFEMAT", ha='center', va='center', fontsize=9)

        # Simbología Centrada y con salto de línea
        altura_simbologia = 0.03 + (len(datos_extraidos) * 0.07)
        draw_box(y_top=0.56, height=altura_simbologia, title="Simbología")
        y_offset = 0.56 - 0.03 - 0.035
        
        for nombre, desc, color in datos_extraidos:
            ax_panel.add_patch(plt.Rectangle((0.15, y_offset - 0.0125), 0.08, 0.025, fill=True, facecolor=color, alpha=0.5, edgecolor='black', linewidth=1))
            nombre_wrap = "\n".join(textwrap.wrap(nombre, width=35))
            ax_panel.text(0.26, y_offset + 0.012, nombre_wrap, ha='left', va='center', fontsize=8, weight='bold')
            y_offset -= 0.07 
        
        y_actual = 0.56 - altura_simbologia - 0.02

        # Sistema de Referencia
        draw_box(y_top=y_actual, height=0.08, title="Sistema de Referencia:", bg_color='#4C8C56')
        ax_panel.text(0.5, y_actual - 0.055, "DATUM WGS84 Zona 14 N\nProyección Transversal de Mercator", ha='center', va='center', fontsize=9)
        y_actual -= 0.10
        
        # Autor Dinámico (Opcional)
        if autor and autor.strip():
            draw_box(y_top=y_actual, height=0.08, title="Autor del Levantamiento:", bg_color='#A01F41')
            ax_panel.text(0.5, y_actual - 0.055, autor.strip(), ha='center', va='center', fontsize=9)
            y_actual -= 0.11

        # Fecha de elaboración
        meses = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
        fecha_str = f"{meses[datetime.now().month - 1]} de {datetime.now().year}"
        ax_panel.add_patch(plt.Rectangle((0, y_actual - 0.05), 1, 0.05, fill=False, edgecolor='black', linewidth=1.2))
        ax_panel.text(0.5, y_actual - 0.025, f"Fecha de elaboración: {fecha_str}", color='black', weight='bold', ha='center', va='center', fontsize=9)

        # Guardar en memoria
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=300, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        
        return buf

@app.post("/generar-mapa/")
async def generar_mapa(
    archivo: UploadFile = File(...),
    autor: str = Form(""), # <-- Cambiado para que sea opcional por defecto
    simbologia: str = Form(...) 
):
    config_simbologia = json.loads(simbologia)
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".kml") as temp_kml:
        temp_kml.write(await archivo.read())
        temp_kml_path = temp_kml.name

    try:
        image_buffer = await asyncio.to_thread(
            procesar_mapa_sync, 
            temp_kml_path, 
            autor, 
            config_simbologia
        )
        return StreamingResponse(image_buffer, media_type="image/png")
    
    finally:
        if os.path.exists(temp_kml_path):
            os.remove(temp_kml_path)