import ee
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

def ee_check_init():
    try:
        asset_id = 'USDOS/LSIB_SIMPLE/2017'
        ee.data.getInfo(asset_id)
        return True
    except ee.ee_exception.EEException:
        return False

if __name__ == '__main__':
    main()
    
def tree_cover_loss(country, fromYear, toYear, scale, maxPixels):

    if not ee_check_init():
        print("Earth Engine is not initialized. Exiting the function.")
        sys.exit()

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

    lossByYear = lossAreaHa.addBands(lossYear).reduceRegion(
        reducer=ee.Reducer.sum().group(1),
        geometry=area_of_interest.geometry(),
        scale=scale,
        maxPixels=maxPixels
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
    plt.show()
    
if __name__ == '__main__':
    main()