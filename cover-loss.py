#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue May 16 13:32:38 2023

@author: eivindhammers
"""

import ee
ee.Initialize()

# Load the vector data representing the area of interest
area_of_interest = ee.FeatureCollection("FAO/GAUL_SIMPLIFIED_500m/2015/level0")
print(area_of_interest.getInfo())

# Define the regions of interest
regions = ['Brazil', 'Africa', 'Southeast Asia', 'Oceania']

# Filter the area_of_interest feature collection
filtered_area_of_interest = area_of_interest.filter(ee.Filter.inList('ADM0_NAME', regions))

# Print the information about the filtered feature collection
print(filtered_area_of_interest.getInfo())

# Load the Global Forest Change dataset
gfc_dataset = ee.Image('UMD/hansen/global_forest_change_2019_v1_8')
start_year = 2020
end_year = 2021

# Filter the dataset for the desired years
loss_image = gfc_dataset.select('loss').filter(ee.Filter.date(str(start_year), str(end_year))).sum()
gain_image = gfc_dataset.select('gain').filter(ee.Filter.date(str(start_year), str(end_year))).sum()

loss_image_clipped = loss_image.clip(area_of_interest)
gain_image_clipped = gain_image.clip(area_of_interest)

tree_cover_change = loss_image_clipped.subtract(gain_image_clipped)

# Set the export parameters
export_params = {
    'image': tree_cover_change,
    'description': 'tree_cover_change',
    'folder': 'output',
    'scale': 30,  # Adjust the scale according to your needs
    'region': area_of_interest.geometry().getInfo()
}

# Export the result as a GeoTIFF file
task = ee.batch.Export.image.toDrive(**export_params)
task.start()
