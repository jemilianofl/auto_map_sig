import os
import re
import uuid
import json
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import FileResponse
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
from datetime import datetime

# Habilitar soporte KML[cite: 1]
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

def procesar_mapa(kml_path, autor, config_simbologia, session_id):
    # Adaptación de obtener_centroide_y_region[cite: 1]
    layers = fiona.listlayers(kml_path)
    gdfs = []
    for layer in layers:
        gdf = gpd.read_file(kml_path, driver='KML', layer=layer)
        gdf = gdf.dropna(subset=['geometry'])
        if not gdf.empty:
            gdf['geometry'] = gdf['geometry'].apply(force_2d)
            gdf = gdf[gdf.geometry.type.isin(['Polygon', 'MultiPolygon'])]
            gdfs.append(gdf)
            
    full_gdf = gpd.GeoDataFrame(pd.concat(gdfs, ignore_index=True), crs="EPSG:4326")
    gdf_utm = full_gdf.to_crs(epsg=32614)
    centroide_geo = gdf_utm.geometry.centroid.to_crs(epsg=4326).iloc[0]
    
    bounds = gdf_utm.geometry.centroid.iloc[0]
    buffer_metros = 150
    from shapely.geometry import box
    bbox_gdf = gpd.GeoDataFrame({'geometry': [box(bounds.x - buffer_metros, bounds.y - buffer_metros, bounds.x + buffer_metros, bounds.y + buffer_metros)]}, crs="EPSG:32614")
    region = bbox_gdf.to_crs(epsg=4326).total_bounds
    region_fmt = [region[0], region[2], region[1], region[3]]

    # Generar mapas base con PyGMT[cite: 1]
    fig_main = pygmt.Figure()
    fig_main.tilemap(region=region_fmt, projection="M15c", source="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", zoom=19)
    
    datos_extraidos = []
    for i, row in full_gdf.reset_index(drop=True).iterrows():
        nombre = str(row.get('Name')).strip()
        color_hex = config_simbologia.get(nombre, "#FF0000") # Color dinámico
        datos_extraidos.append((nombre, "", color_hex))
        
        gdf_single = gpd.GeoDataFrame([row], crs=full_gdf.crs)
        fig_main.plot(data=gdf_single, pen="1.5p,white", fill=f"{color_hex}@50")
        
    fig_main.basemap(frame=["a", "WSne"], rose="jTL+w1.5c+o0.3c/0.3c+f2")
    mapa_temp = f"mapa_temp_{session_id}.png"
    fig_main.savefig(mapa_temp, dpi=300)
    
    # Ensamblar layout institucional con matplotlib[cite: 1]
    fig = plt.figure(figsize=(15, 10.5), facecolor='white')
    gs = GridSpec(1, 2, width_ratios=[3.2, 1.2], wspace=0.03)
    
    ax_map = fig.add_subplot(gs[0])
    ax_map.imshow(Image.open(mapa_temp))
    ax_map.axis('off')
    
    ax_panel = fig.add_subplot(gs[1])
    ax_panel.axis('off')
    ax_panel.set_xlim(0, 1)
    ax_panel.set_ylim(0, 1)
    
    def draw_box(y_top, height, title, bg_color='#A01F41'):
        ax_panel.add_patch(plt.Rectangle((0, y_top - 0.03), 1, 0.03, fill=True, color=bg_color))
        ax_panel.text(0.5, y_top - 0.015, title, color='white', weight='bold', ha='center', va='center', fontsize=10)
        ax_panel.add_patch(plt.Rectangle((0, y_top - height), 1, height - 0.03, fill=False, edgecolor='black', linewidth=1.2))

    # Simbología[cite: 1]
    altura_simbologia = 0.03 + (len(datos_extraidos) * 0.07)
    draw_box(y_top=0.56, height=altura_simbologia, title="Simbología")
    y_offset = 0.56 - 0.065
    for nombre, desc, color in datos_extraidos:
        ax_panel.add_patch(plt.Rectangle((0.15, y_offset - 0.0125), 0.08, 0.025, fill=True, facecolor=color, alpha=0.5, edgecolor='black', linewidth=1))
        ax_panel.text(0.26, y_offset + 0.012, nombre, ha='left', va='center', fontsize=8, weight='bold')
        y_offset -= 0.07 
    
    # Autor dinámico
    y_actual = 0.56 - altura_simbologia - 0.12
    draw_box(y_top=y_actual, height=0.08, title="Autor del Levantamiento:", bg_color='#A01F41')
    ax_panel.text(0.5, y_actual - 0.055, autor, ha='center', va='center', fontsize=9)
    
    output = f"mapa_final_{session_id}.png"
    plt.savefig(output, dpi=300, bbox_inches='tight')
    
    os.remove(mapa_temp)
    return output

@app.post("/generar-mapa/")
async def generar_mapa(
    archivo: UploadFile = File(...),
    autor: str = Form(...),
    simbologia: str = Form(...) # JSON string con mapeo de colores
):
    session_id = str(uuid.uuid4())
    kml_path = f"temp_{session_id}.kml"
    
    with open(kml_path, "wb") as f:
        f.write(await archivo.read())
        
    config_simbologia = json.loads(simbologia)
    output_img = procesar_mapa(kml_path, autor, config_simbologia, session_id)
    
    os.remove(kml_path)
    return FileResponse(output_img, media_type="image/png")