import ee
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import folium
import matplotlib.cm as cm
import contextily as ctx
from PIL import Image
import sys
import urllib.request

# Function to check if Earth Engine is initialized, and by extension, if it is authenticated.
def ee_check_init():
  try:
    asset_id = 'USDOS/LSIB_SIMPLE/2017'
    ee.data.getInfo(asset_id)
    return True
  except ee.ee_exception.EEException:
    return False

# Generate bar chart showing yearly forest loss 
def forest_loss(country, fromYear, toYear, maxPixels, scale=30, bestEffort=False):

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
    scale_used = "Best Effort" #lossByYear.getInfo()['scale']
  else:
    lossByYear = lossAreaHa.addBands(lossYear).reduceRegion(
      reducer=ee.Reducer.sum().group(1),
      geometry=area_of_interest.geometry(),
      scale=scale,
      maxPixels=maxPixels,
      bestEffort=bestEffort
    )
    scale_used = scale
    
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

   # Add scale_used as a figure note
  note = f"Scale used to calculate forest loss: {scale_used}. "
  plt.figtext(0.5, 0.01, note, wrap=True, horizontalalignment='center', fontsize=10)

  plt.tight_layout()
  plt.show()

# Generate and clip images of intact forest and forest loss    
def forest_images(country, year):
  
  if not ee_check_init():
    print("Earth Engine is not initialized. Exiting the function.")
    return
  
  # Load the vector data representing the area of interest
  world = ee.FeatureCollection('USDOS/LSIB_SIMPLE/2017')

  year2 = year - 2000
  
  # Filter the area_of_interest feature collection
  area_of_interest = world.filter(ee.Filter.eq('country_na', country))

  # Get the loss image
  gfc = ee.Image('UMD/hansen/global_forest_change_2022_v1_10').clip(area_of_interest)
  treecover2000 = gfc.select('treecover2000')
  lossYear = gfc.select('lossyear')

  # Generate the cumulative loss layer until year T-1
  cumulativeLoss = lossYear.lt(year2).selfMask().rename('cumulativeLoss')
    
  # Generate the forest loss layer for year T
  lossThisYear = lossYear.eq(year2).selfMask().rename('lossThisYear')
  
  # Generate the intact forest layer
  intactForestMask = lossYear.lt(year2).Or(lossYear.eq(year2)).unmask(0).eq(0)
  intactForest = treecover2000.updateMask(intactForestMask).rename('intactForest')

  combinedImage = cumulativeLoss.addBands(lossThisYear).addBands(intactForest)
    
  return combinedImage, area_of_interest

# Generate interactive map of intact forest and forest loss
def forest_map(country, year):

  if not ee_check_init():
    print("Earth Engine is not initialized. Exiting the function.")
    return
  
  combinedImage, area_of_interest = forest_images(country, year)

  # Create a map centered around the area of interest
  map_center = area_of_interest.geometry().centroid().coordinates().reverse().getInfo()
  forest_map = folium.Map(location=map_center, zoom_start=7, tiles='CartoDB Positron', name='CartoDB Positron')

  # Add a baselayer
  folium.TileLayer('CartoDB dark_matter', name = 'CartoDB Dark Matter').add_to(forest_map)
  folium.TileLayer('openstreetmap', name = 'OpenStreetMap').add_to(forest_map)

  attribution = ('Hansen, M. C., P. V. Potapov, R. Moore, M. Hancher, S. A. Turubanova, A. Tyukavina, D. Thau, '
                 'S. V. Stehman, S. J. Goetz, T. R. Loveland, A. Kommareddy, A. Egorov, L. Chini, C. O. Justice, '
                 'and J. R. G. Townshend. 2013. "High-Resolution Global Maps of 21st-Century Forest Cover Change." '
                 'Science 342 (15 November): 850–53. Data available from: earthenginepartners.appspot.com/science-2013-global-forest.')

  # Add the baselayer (intactForest band)
  baselayerParams = {'min': 0, 'max': 100, 'palette': ['000000', '00FF00']}
  baselayerTile = folium.TileLayer(
    tiles=combinedImage.select('intactForest').getMapId(baselayerParams)['tile_fetcher'].url_format,
    attr=attribution,
    overlay=True,
    name='Intact forest in ' + str(year)
  ).add_to(forest_map)

  # Add the cumulative loss band
  cumulativeLossParams = {'min': 0, 'max': 1, 'palette': ['000000', '6495ED']}
  cumulativeLossTile = folium.TileLayer(
    tiles=combinedImage.select('cumulativeLoss').getMapId(cumulativeLossParams)['tile_fetcher'].url_format,
    attr=attribution,
    overlay=True,
    name='Cumulative forest loss, 2001--' + str(year - 1)
  ).add_to(forest_map)

  # Add the loss this year band
  lossParams = {'min': 0, 'max': 1, 'palette': ['000000', 'FF0000']}
  lossTile = folium.TileLayer(
    tiles=combinedImage.select('lossThisYear').getMapId(lossParams)['tile_fetcher'].url_format,
    attr=attribution,
    overlay=True,
    name='Forest loss in ' + str(year)
  ).add_to(forest_map)

    # Add a layer control panel to the map
  folium.LayerControl().add_to(forest_map)

  # Display or save the map
  display(forest_map)

