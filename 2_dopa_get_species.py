import requests
import pandas as pd
from io import StringIO
import yaml
import os

# open configuration files
with open('config.yaml', 'r') as file:
    config = yaml.safe_load(file)

# access list of species IDs to iterate over from the config file
species_ids = config['species_ids']

# access CSV (or XLSX) file with the list of species names - TODO - to replace list of species with the file
# input_species = config['input_species']

# paths from the config file
input_dir = config['input_dir']
output_dir = config['output_dir']

# input file from the config file - TODO - to replace list of species with the file
# input = config['input_species']
# input = os.path.join(input_dir, input_species)

# output file from the config file
output_csv = config['iucn_csv']
output_csv = os.path.join(output_dir, output_csv)
output_csv = os.path.normpath(output_csv)

def dopa_fetch_iucn(species_ids):
    """
    Fetches IUCN species data from the DOPA REST service for a list of species IDs.

    Parameters:
    - species_ids: A list of species IDs to fetch data for.

    Returns:
    - df_list: A list of dataframes, each containing data for one species ID.
    """
    url = "https://dopa-services.jrc.ec.europa.eu/services/d6dopa/dopa_42/get_dopa_species"
    params_template = {
        "format": "csv",
        "includemetadata": "true",
        "fields": "id_no,class,order_,family,genus,binomial,category,threatened,country_n,endemic,ecosystems,"
                  "habitat_code,habitat_name,country_code,country_name,stress_code,stress_name,threat_code,"
                  "threat_name,research_needed_code,research_needed_name,conservation_needed_code,"
                  "conservation_needed_name,usetrade_code,usetrade_name",
        "dplimit": 2
    }
    
    # list to append dataframes
    df_list = []

    for species_id in species_ids:
        params = params_template.copy()
        params["a_id_no"] = species_id # extract unique ID of species to use later on

        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            # read the CSV using '|' as the delimiter
            csv_data = StringIO(response.text)
            df = pd.read_csv(csv_data, delimiter='|') # A
            
            # append the dataframe to the list
            df_list.append(df)

            # Debug: print the shape of the fetched DataFrame
            print(f"Debugging statement: fetched DataFrame for species ID {species_id} has shape: {df.shape}")
        else:
            print(f"Debugging statement: error fetching data for species ID {species_id}: {response.status_code} - {response.text}")
    
    return df_list

# fetch the data and get a list of datafranes
df_list = dopa_fetch_iucn(species_ids)

# combine all dataframes into one
combined_df = pd.concat(df_list, ignore_index=True, sort=False)

"""
# Debug: print the combined DataFrame
print("Combined DataFrame:")
print(combined_df)
"""

"""
# get unique values for id_no and select one row for columns where values are repeated
unique_columns = ['class', 'order_', 'family', 'genus', 'binomial', 'category', 
                  'threatened', 'country_n', 'endemic', 'ecosystems']


df_unique = combined_df.groupby('id_no').first().reset_index()[['id_no'] + unique_columns]

# group the dataframe by 'id_no'
grouped_df = combined_df.groupby('id_no')

# for each group (i.e., each unique 'id_no'), take the first row
first_row_df = grouped_df.first()

# reset the index so that 'id_no' becomes a regular column again
reset_df = first_row_df.reset_index()

# select only the 'id_no' and the columns of interest
df_unique = reset_df[['id_no'] + unique_columns]
"""

# group the dataframe by 'id_no'
grouped_df = combined_df.groupby('id_no')

# concatenate values for the rest of the columns
concat_columns = combined_df.drop(columns = ['id_no']).columns.tolist() # create a list of all columns, excluding ID

# select only the columns that need to be concatenated
df_columns_to_concat = grouped_df[concat_columns]

# define a function to concatenate non-null, unique values with '|'
def concatenate_unique_values(column):
    return '|'.join(column.dropna().astype(str).unique()) # remove null values, convert to string, choose only unique values and concatenate with '|' separator
# apply the concatenation function to each column in the group
concatenated_df = df_columns_to_concat.agg(concatenate_unique_values)

# reset the index so that 'id_no' becomes a regular column again
df_final = concatenated_df.reset_index()

# save the final dataframe to a new CSV file
df_final.to_csv(output_csv, index=False, sep='|')
print (f"Data from IUCN has been fetched and concatenated for the following species IDs: {species_ids}")