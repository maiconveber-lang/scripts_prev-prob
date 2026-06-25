# -*- coding: utf-8 -*-
import datetime
import pygrib
import numpy as np
import matplotlib.pyplot as plt
import cartopy.feature as cfeature
import cartopy.crs as ccrs
import geopandas as gpd
import pandas as pd
from cartopy.feature import ShapelyFeature
from cartopy.mpl.gridliner import LATITUDE_FORMATTER, LONGITUDE_FORMATTER
import matplotlib.offsetbox as offsetbox
import json
import os

data_atual_base = datetime.datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
base_path = "/oper/modelo/wrf/ams_07km/brutos/{}/{}/{}/{}/WRF_cpt_07KM_{}{}{}{}_"
fmt = data_atual_base.strftime
caminho_prefixo = base_path.format(fmt("%Y"), fmt("%m"), fmt("%d"), "00", fmt("%Y"), fmt("%m"), fmt("%d"), "00")

logo_path = '/home/maicon.veber/scripts_python/previsoes/inpe.png'
shape_path = "/home/maicon.veber/scripts_python/previsoes/shape_file/ne_10m_admin_0_countries.shp"

descricoes_niveis = ["Nivel 0", "Nivel 1", "Nivel 2", "Nivel 3", "Nivel 4"]
cores = [(0.6, 1.0, 0.6), 'yellow', 'orange', 'red', 'purple']
titulos_niveis = ['Tempestades', 'Baixo', 'Moderado', 'Alto', 'Muito Alto']

# --- Função para Plotagem e Salvamento ---
def salvar_previsao(resultados, d_ini, d_fim, lats, lons, sufixo):
    print(f"Gerando mapa para: {sufixo} ({d_ini.strftime('%d/%m')} - {d_fim.strftime('%d/%m')})")
    
    plt.figure(figsize=(12, 10))
    ax = plt.axes(projection=ccrs.PlateCarree())
    ax.set_extent([285, 327, -37, 7])

    # 1. Plotar Riscos
    for idx, res in enumerate(resultados):
        if res is not None and np.any(res > 0):
           ax.contourf(lons, lats, res, colors=[cores[idx]], levels=[0.5, 1.5], transform=ccrs.PlateCarree(), zorder=5)


    # 2. Base Geográfica
    gdf = gpd.read_file(shape_path)
    brasil = gdf[gdf['ADMIN'] == 'Brazil']
    sul_sem_br = gdf[(gdf['CONTINENT'] == 'South America') & (gdf['ADMIN'] != 'Brazil')]
    guiana = gdf[gdf['NAME'] == 'France']
    central = gdf[gdf['ADMIN'].isin(['Belize', 'Costa Rica', 'El Salvador', 'Guatemala', 'Honduras', 'Nicaragua', 'Panama'])]
    america_latina = pd.concat([sul_sem_br, guiana, central])

    ax.add_feature(cfeature.OCEAN.with_scale('10m'), facecolor='lightblue', zorder=6)
    ax.add_feature(ShapelyFeature(america_latina.geometry, ccrs.PlateCarree(), facecolor='whitesmoke', edgecolor='black', linewidth=0.4), zorder=7)
    ax.add_feature(ShapelyFeature(brasil.geometry, ccrs.PlateCarree(), facecolor='none', edgecolor='black', linewidth=1.0), zorder=6)
    ax.add_feature(cfeature.BORDERS.with_scale('10m'), edgecolor='k', linewidth=0.5, zorder=7)
    ax.add_feature(cfeature.STATES.with_scale('10m'), edgecolor='k', linewidth=0.5, zorder=7)

    # 3. Título e Grades
    ax.set_title(f'Risco para Eventos de Tempo Severo\nValidade: {d_ini.strftime("%Y-%m-%d 12:00 UTC")} a {d_fim.strftime("%Y-%m-%d 12:00 UTC")}', fontweight='bold')
    gl = ax.gridlines(draw_labels=True, linestyle='--', color='gray', linewidth=0.25, zorder=8)
    gl.top_labels = gl.right_labels = False

    # 4. Logo
    if os.path.exists(logo_path):
        logo_img = plt.imread(logo_path)
        ab = offsetbox.AnnotationBbox(offsetbox.OffsetImage(logo_img, zoom=0.15), (0.92, 0.072), frameon=False, xycoords='axes fraction', zorder=10)
        ax.add_artist(ab)

    # 5. Legenda
    legend_rect = plt.Rectangle((0.008, 0.008), 0.275, 0.23, transform=ax.transAxes, edgecolor='gray', facecolor='white', zorder=10)
    ax.add_patch(legend_rect)
    ax.text(0.023, 0.216, 'Categoria de Risco', transform=ax.transAxes, fontsize=10, fontweight='bold', zorder=11)
    for i, (titulo, cor) in enumerate(zip(titulos_niveis, cores)):
        ax.add_patch(plt.Rectangle((0.026, 0.17 - i * 0.035), 0.03, 0.03, transform=ax.transAxes, facecolor=cor, edgecolor='gray', zorder=11))
        ax.text(0.07, 0.185 - i * 0.035, titulo, transform=ax.transAxes, fontsize=9, fontweight='bold', zorder=11)

    # 6. Salvar Arquivos
    out_dir = f"/scripts/nowcasting/maicon.veber/figuras/produtos/previsoes/tempo_severo/{d_ini.strftime('%Y')}/{d_ini.strftime('%m')}"
    os.makedirs(out_dir, exist_ok=True)
    
    prefixo_nome = f"Tempo_severo_{d_ini.strftime('%Y%m%d12Z')}_{d_fim.strftime('%Y%m%d12Z')}_{sufixo}"
    
    plt.savefig(f"{out_dir}/{prefixo_nome}.png", dpi=300, bbox_inches='tight')
    plt.savefig(f"/scripts/nowcasting/maicon.veber/figuras/produtos/previsoes/tempo_severo_{sufixo}.png", dpi=300, bbox_inches='tight')

    dados_json = {
        "data_inicial": d_ini.strftime("%Y-%m-%d %H:00 UTC"),
        "data_final": d_fim.strftime("%Y-%m-%d %H:00 UTC"),
        "resultados": [res.tolist() for res in resultados if res is not None]
    }
    with open(f"{out_dir}/{prefixo_nome}.json", 'w') as f:
        json.dump(dados_json, f)

    plt.close()

resultados_acumulados = [None] * len(descricoes_niveis)
lats, lons = None, None

# fcast_hour 12 a 36 = Dia 1 | 37 a 60 = Dia 2
for fcast_hour in range(12, 61):
    dt_hora = data_atual_base + datetime.timedelta(hours=fcast_hour)
    arquivo = f"{caminho_prefixo}{dt_hora.strftime('%Y%m%d%H')}.grib2"
    
    try:
        grbs = pygrib.open(arquivo)
        print(f"Lendo: {dt_hora.strftime('%Y-%m-%d %H:00 UTC')} (F-Hour: {fcast_hour})")
        
        prc, lats, lons = grbs.select(name='Total Precipitation')[0].data(lat1=-50, lat2=7, lon1=285, lon2=330)
        lifted = grbs.select(name='Best (4-layer) lifted index')[0].data(lat1=-50, lat2=7, lon1=285, lon2=330)[0]
        mucape = grbs.select(name='Convective available potential energy')[3].data(lat1=-50, lat2=7, lon1=285, lon2=330)[0]
        u500 = grbs.select(name='U component of wind')[9].data(lat1=-50, lat2=7, lon1=285, lon2=330)[0]
        v500 = grbs.select(name='V component of wind')[9].data(lat1=-50, lat2=7, lon1=285, lon2=330)[0]
        u10 = grbs.select(name='10 metre U wind component')[0].data(lat1=-50, lat2=7, lon1=285, lon2=330)[0]
        v10 = grbs.select(name='10 metre V wind component')[0].data(lat1=-50, lat2=7, lon1=285, lon2=330)[0]
        grbs.close()

        bwd06 = np.sqrt((u500 - u10)**2 + (v500 - v10)**2)

        # Lógica de Níveis
        condicoes = [
            (lifted <= -1) & (mucape >= 250),
            (lifted <= -2) & (bwd06 >= 13) & (mucape >= 500) & (prc >= 0.5),
            (lifted <= -2) & (bwd06 >= 19) & (mucape >= 1000) & (prc >= 2),
            (lifted <= -4) & (bwd06 >= 23) & (mucape >= 1500) & (prc >= 4),
            (lifted <= -5) & (bwd06 >= 28) & (mucape >= 2000) & (prc >= 8)
        ]

        for i in range(len(resultados_acumulados)):
            mask = condicoes[i].astype(int)
            if resultados_acumulados[i] is None:
                resultados_acumulados[i] = mask
            else:
                resultados_acumulados[i] = np.maximum(resultados_acumulados[i], mask)

    except Exception as e:
        print(f"Erro ao processar {dt_hora}: {e}")

    # --- Dia 1 ---
    if fcast_hour == 36:
        d1_ini = data_atual_base + datetime.timedelta(hours=12)
        d1_fim = data_atual_base + datetime.timedelta(hours=36)
        salvar_previsao(resultados_acumulados, d1_ini, d1_fim, lats, lons, "dia_1")
        # Limpa o acumulador para o Dia 2
        resultados_acumulados = [None] * len(descricoes_niveis)

    # --- Dia 2 ---
    if fcast_hour == 60:
        d2_ini = data_atual_base + datetime.timedelta(hours=36)
        d2_fim = data_atual_base + datetime.timedelta(hours=60)
        salvar_previsao(resultados_acumulados, d2_ini, d2_fim, lats, lons, "dia_2")
