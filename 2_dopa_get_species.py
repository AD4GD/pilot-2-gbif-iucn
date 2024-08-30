import requests
import pandas as pd
from io import StringIO
import yaml
import os
import time

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
input_path = config['input_species']
input_path = os.path.join(input_dir, input_path)

# output file from the config file
output_iucn_csv = config['iucn_csv']
output_iucn_csv = os.path.join(output_dir, output_iucn_csv )
output_iucn_csv = os.path.normpath(output_iucn_csv )

# function to access the DOPA REST function 42033. get_dopa_species_list
def process_species_4_IUCN(scientific_name):
    """
    Fetches and processes IUCN species data from the DOPA REST service.

    Parameters:
    - species_name: The scientific name of the species.

    Returns:
    - species_info: A dictionary containing species data or an empty dictionary if the data was not found.
    """
    url = "https://dopa-services.jrc.ec.europa.eu/services/d6dopa/dopa_42/get_dopa_species"
    params = {
        "format": "json", 
        "a_binomial": scientific_name, # use the scientific name to search as IUCN taxon ID might be tricky to map with GBIF taxon ID
        # works with species only, not subspecies!
        "fields": "id_no" # return only IUCN species ID
    }
    
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        species_info = response.json() # write the response to the variable
        return species_info if species_info else {}
    else:
        print(f"Error fetching data for {scientific_name}: {response.status_code}")
        return {}

# TODO - 2-step functions needed - fetch id_no by the scientific name and fetch all the attributes by the id_no (function 42032. get_dopa_species because this one provides the most wide list of attributes for species) 

def lookup_species_from_csv(file_path, output_path):
    """
    Reads species names from a CSV file, fetches and processes their data, and saves the results to a new CSV.

    Parameters:
    - file_path: Path to the input CSV file containing species names.
    - output_path: Path to save the output CSV file with species data.

    Returns:
    - None
    """
    try:
        # try reading the CSV with UTF-8 encoding
        df = pd.read_csv(file_path, encoding='utf-8')
    except UnicodeDecodeError:
        # if there is a Unicode error, try with a different encoding
        print("UTF-8 decoding failed. Trying ISO-8859-1 encoding...")
        df = pd.read_csv(file_path, encoding='ISO-8859-1')  # or 'Windows-1252'

    if df.empty:
        print("The CSV file is empty.")
        return
    
    # use the first column of input file without specifying its name
    first_column = df.iloc[:, 0]
    species_names = first_column.tolist()
    
    results = []  # list to store results
    
    for species_name in species_names:
        print(f"Fetching data for (sub)species: {species_name}")
        species_info = process_species_4_IUCN(species_name)
        
        if species_info:
            # assuming you have a function `fetch_gbif_id` to get GBIF IDs
            scientific_name = species_info.get('scientificName', '')
            gbif_key, gbif_species_key = process_species_4_IUCN(scientific_name)  # call the function to fetch GBIF Species ID for the fixed scientific name
            
            species_info['gbifKey'] = gbif_key
            species_info['gbifSpeciesKey'] = gbif_species_key
            results.append(species_info)

        # to avoid hitting API rate limits, wait for a short period between requests
        time.sleep(1)
    
    # save results to CSV
    results_df = pd.DataFrame(results)
    results_df.to_csv(output_path, index=False)
    print(f"Final results saved to {output_path}")

# Previous version of the DOPA REST function 42032. get_dopa_species (fetch info only by species IDs)

def dopa_fetch_iucn(species_ids):
    """
    Fetches IUCN species data from the DOPA REST service for a list of species IDs.

    Parameters:
    - species_ids: A path to the input CSV file with the scientific names of potential (sub)species of interest.

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

# TODO - raise a warning if shape of ID has 0 rows - no records found

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
df_final.to_csv(output_iucn_csv, index=False, sep='|')
print (f"Data from IUCN has been fetched and concatenated for the following species IDs: {species_ids}")