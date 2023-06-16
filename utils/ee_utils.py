import ee
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import folium
#import matplotlib.cm as cm
#import contextily as ctx
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

  # Get primary humid tropical forest
  trop = ee.ImageCollection('UMD/GLAD/PRIMARY_HUMID_TROPICAL_FORESTS/v1')
  primaryForestMask = trop.select('Primary_HT_forests').mosaic().selfMask().unmask(0)
  
  # Get the loss image.
  # This dataset is updated yearly, so we get the latest version.
  gfc = ee.Image('UMD/hansen/global_forest_change_2022_v1_10').updateMask(primaryForestMask)
  
  # Forest loss in any year (from 2001)
  lossImage = gfc.select('loss')
  
  # Get the area of cumulative forest loss
  lossAreaImage = lossImage.multiply(ee.Image.pixelArea())
 
  # Convert from square meters to hectares and then to million hectares
  lossAreaHa = lossAreaImage.divide(1e4).divide(1e3)  

  # Year of forest loss in given pixel
  lossYear = gfc.select('lossyear')
  
  # Construct grid and intersect with country polygon
  # Get the first feature from 'selected'
  aoi_first = ee.Feature(area_of_interest.first())

  # Define a Python function to intersect the features in the grid collection with the country polygon
  def intersect_feature(feature):
    feature = ee.Feature(feature)
    intersection = aoi_first.intersection(feature, 0.1)  # 0.1 is the allowed error margin
    return intersection

  grid = area_of_interest.geometry().coveringGrid(area_of_interest.geometry().projection())
  gridClipped = grid.map(intersect_feature)
  
  # Should scale parameter be explicitly set, or left determined by bestEffort?
  def calcLoss(feature):
    loss = lossAreaHa.addBands(lossYear).reduceRegion(
      reducer=ee.Reducer.sum().group(1),
      geometry=feature.geometry(),
      maxPixels=maxPixels,
      bestEffort=bestEffort
    )
    return feature.set('loss', loss)
  
  lossByYear = gridClipped.map(calcLoss)

  # Get the data into a dataframe 
  dfs = []

  # Iterate over each feature in the lossByYear feature collection
  for feature in lossByYear.getInfo()['features']:
    properties = feature['properties']
    loss_data = properties['loss']
    # Check if 'loss' data exists for the current feature
    if loss_data:
        loss_year = [entry['group'] for entry in loss_data['groups']]
        loss_sum = [entry['sum'] for entry in loss_data['groups']]
        temp_df = pd.DataFrame({'year': loss_year, 'loss': loss_sum})
        dfs.append(temp_df)

  df = pd.concat(dfs, ignore_index=True)

  # Convert year to integer and make it YYYY format
  df['year'] = df['year'].astype('int') + 2000
    
  # Summarize loss within year, over all cells
  df = df.groupby('year')['loss'].sum().reset_index()
  
  scale_used = "Best Effort"
    
  # Create the table
  table = pd.DataFrame({'Year': df['year'], 'Tree cover loss (Kha)': df['loss'].round(2)})
  display(table)
  
  fig, ax = plt.subplots(figsize=(10, 6))

  df.plot('year', 'loss', kind='bar', legend=None, ax=ax)
  plt.xlabel('Year')
  plt.ylabel('Tree cover loss (Kha)')
  plt.title('Tree cover loss in ' + country)

  # Add data labels
  for i, v in enumerate(df['loss']):
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

  # Get primary humid tropical forest
  trop = ee.ImageCollection('UMD/GLAD/PRIMARY_HUMID_TROPICAL_FORESTS/v1')
  primaryForestMask = trop.select('Primary_HT_forests').mosaic().clip(area_of_interest).selfMask().unmask(0)
  
  # Get the loss image.
  # This dataset is updated yearly, so we get the latest version.
  gfc = ee.Image('UMD/hansen/global_forest_change_2022_v1_10').clip(area_of_interest).updateMask(primaryForestMask)

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

  # Construct grid and intersect with country polygon
  buffer = area_of_interest.geometry().buffer(200000)
  bufferClipped = buffer.difference(area_of_interest)
  grid = area_of_interest.geometry().coveringGrid(area_of_interest.geometry().projection())
  gridCountry = ee.FeatureCollection(grid.geometry().difference(bufferClipped, 1))
    
  return combinedImage, area_of_interest, gridCountry

# Generate interactive map of intact forest and forest loss
def forest_map(country, year):

  if not ee_check_init():
    print("Earth Engine is not initialized. Exiting the function.")
    return
  
  combinedImage, area_of_interest, gridCountry = forest_images(country, year)

  # Create a map centered around the area of interest
  map_center = area_of_interest.geometry().centroid().coordinates().reverse().getInfo()
  forest_map = folium.Map(location=map_center, zoom_start=6, tiles='CartoDB Positron', name='CartoDB Positron')

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

  # Add the gridCountry as a tile layer to the Folium map
  #gridCountryMapId = gridCountry.getMapId()
  #folium.TileLayer(
  #    tiles=gridCountryMapId['tile_fetcher'].url_format,
  #    attr='Google Earth Engine',
  #    overlay=True,
  #).add_to(forest_map)
  
  # Add a layer control panel to the map
  folium.LayerControl().add_to(forest_map)

  # Display or save the map
  display(forest_map)

