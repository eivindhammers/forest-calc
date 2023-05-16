import ee

# Initialize Earth Engine
ee.Initialize()

# Load the vector data representing the area of interest
world = ee.FeatureCollection('USDOS/LSIB_SIMPLE/2017')

# Define the regions of interest
countries = ['Brazil', 'Dem Rep of the Congo', 'Indonesia']

# Filter the area_of_interest feature collection
area_of_interest = world.filter(ee.Filter.inList('country_na', countries))

# Get the list of ADM0 names for the area_of_interest
adm0_names = area_of_interest.aggregate_array('country_na').distinct().getInfo()

for name in sorted(adm0_names):
    print(name)

# Get the loss image.
# This dataset is updated yearly, so we get the latest version.
gfc2021 = ee.Image('UMD/hansen/global_forest_change_2021_v1_9')
lossImage = gfc2021.select(['loss'])
lossAreaImage = lossImage.multiply(ee.Image.pixelArea())

lossYear = gfc2021.select(['lossyear'])
lossByYear = lossAreaImage.addBands(lossYear).reduceRegion(
    reducer=ee.Reducer.sum().group(1),
    geometry=area_of_interest.geometry(),
    scale=300,
    maxPixels=1e9
)

# Print the loss by year statistics
print(lossByYear.getInfo())

# Convert the lossByYear dictionary to a FeatureCollection
groups = ee.List(lossByYear.get('groups'))
features = groups.map(lambda group: ee.Feature(None, group))

# Create an ee.FeatureCollection from the list of features
featureCollection = ee.FeatureCollection(features)

# Set the export parameters
export_params = {
    'collection': featureCollection,
    'description': 'loss_by_year_export',
    'fileFormat': 'CSV'
}

# Start the export task asynchronously
task = ee.batch.Export.table.toDrive(**export_params)
task.start()

print('Export task has started. You can check the progress in the Earth Engine Code Editor or Earth Engine Apps.')

# Get the task ID of the last Earth Engine request
task_id = lossByYear.get('task_id')

# Get the status of the task and display progress
while True:
    task_status = ee.data.getTaskStatus(task_id)[0]
    if task_status['state'] == 'COMPLETED':
        print('Task completed.')
        break
    print(f"Progress: {task_status['progress'] * 100}%")