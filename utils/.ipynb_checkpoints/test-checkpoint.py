import ee
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import folium
import matplotlib.colors as mcolors
import base64
from io import BytesIO

def mpl_to_html(fig):
  # Save the matplotlib figure as bytes
  buf = BytesIO()
  fig.savefig(buf, format='png', bbox_inches='tight', dpi=300)
  buf.seek(0)

  # Convert the bytes to base64 encoding
  data = base64.b64encode(buf.getvalue()).decode()

  # Create the HTML string with the base64 encoded image
  html = '<img src="data:image/png;base64,{}">'.format(data)
  return html
  
def ee_check_init():
  try:
    asset_id = 'USDOS/LSIB_SIMPLE/2017'
    ee.data.getInfo(asset_id)
    return True
  except ee.ee_exception.EEException:
    return False

def tree_cover_loss(country, fromYear, toYear, maxPixels, scale=30, bestEffort=False):

  if not ee_check_init():
    print("Earth Engine is not initialized. Exiting the function.")
    return

  # Load the vector data representing the area of interest
  world = ee.FeatureCollection('USDOS/LSIB_SIMPLE/2017')

  # Filter the area_of_interest feature collection
  area_of_interest = world.filter(ee.Filter.eq('country_na', country))

  # Get the loss image.
  # This dataset is updated yearly, so we get the latest version.
  gfc = ee.Image('UMD/hansen/global_forest_change_2022_v1_10')
  lossImage = gfc.select(['loss'])
  lossAreaImage = lossImage.multiply(ee.Image.pixelArea())

  lossYear = gfc.select(['lossyear'])
  lossAreaHa = lossAreaImage.divide(10000).divide(1e3)  # Convert from square meters to hectares and then to million hectares

  # Should scale parameter be explicitly set, or left determined by bestEffort?
  if bestEffort:
    lossByYear = lossAreaHa.addBands(lossYear).reduceRegion(
      reducer=ee.Reducer.sum().group(1),
      geometry=area_of_interest.geometry(),
      maxPixels=maxPixels,
      bestEffort=bestEffort
    )
  else:
    lossByYear = lossAreaHa.addBands(lossYear).reduceRegion(
      reducer=ee.Reducer.sum().group(1),
      geometry=area_of_interest.geometry(),
      scale=scale,
      maxPixels=maxPixels,
      bestEffort=bestEffort
    )

  lossDict = lossByYear.getInfo()
  data = sorted(lossDict.items())
  df = pd.DataFrame(data[0][1])
  df['year'] = df['group'].replace(range(1, len(df) + 1), range(fromYear, toYear + 1))

  fig, ax = plt.subplots(figsize=(10, 6))

  df.plot('year', 'sum', kind='bar', legend=None, ax=ax)
  plt.xlabel('Year')
  plt.ylabel('Tree cover loss (Kha)')
  plt.title('Tree cover loss in ' + country)

  # Add data labels
  for i, v in enumerate(df['sum']):
    ax.text(i, v, str(round(v, 1)), ha='center', va='bottom')

  xticks = np.arange(0, len(df), 5)
  ax.set_xticks(xticks)
  ax.set_xticklabels(df['year'][::5], rotation=0)

  plt.tight_layout()

  # Create a folium map centered on the area of interest
  folium_map = folium.Map(location=[0, 0], zoom_start=3)

  # Adjust the scale parameter to keep pixel grid dimensions within the limit
  scale_factor = max(lossImage.projection().nominalScale().getInfo() / 32768, 1)
  scaled_scale = scale * scale_factor

  # Reduce the loss image resolution and adjust the maxPixels value
  reduced_loss = lossImage.reduceResolution(
    reducer=ee.Reducer.mean(),
    maxPixels=65536
  ).reproject(crs=lossImage.projection(), scale=scaled_scale)

  # Convert the reduced loss image to a format compatible with folium
  map_id_dict = reduced_loss.getMapId({'min': 0, 'max': 1, 'palette': ['black', 'red']})
  tiles = map_id_dict['tile_fetcher'].url_format
  folium.TileLayer(
    overlay=True,
    name='Forest Loss',
    tiles=tiles,
    attr='Map Data &copy; <a href="https://developers.google.com/earth-engine/datasets/catalog/UMD_hansen_global_forest_change_2022_v1_10">Hansen Global Forest Change</a>'
  ).add_to(folium_map)

  # Create a linear color map for the legend
  color_map = mcolors.LinearSegmentedColormap.from_list(
    'ForestLoss',
    ['black', 'red'],
    N=256
  )

  # Add a color scale legend to the map
  color_map_legend = plt.cm.ScalarMappable(cmap=color_map)
  color_map_legend.set_array([0, 1])
  color_map_legend.set_clim(0, 1)
  plt.colorbar(color_map_legend, ax=ax, label='Forest Loss')

  # Save the matplotlib figure as bytes
  buf = BytesIO()
  fig.savefig(buf, format='png', bbox_inches='tight', dpi=300)
  buf.seek(0)

  # Convert the bytes to base64 encoding
  data = base64.b64encode(buf.getvalue()).decode()

  # Create the HTML string with the base64 encoded image
  html = '<img src="data:image/png;base64,{}">'.format(data)

  # Add the HTML image to the folium map
  folium_map.get_root().html.add_child(folium.Element(html))

  # Save the folium map as HTML
  folium_map.save('forest_loss_map.html')

if __name__ == '__main__':
  main()