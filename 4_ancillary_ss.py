# "pip install openpyxl" to work with xslx through pandas
import pandas as pd
import argparse

# import own function to fix scientific names
from _1_gbif_lookup import fix_species_name
# TODO - implement fixing scientific names

"""
24/09/2024
Attempt to bring tabular data for the custom of list of species from ancillary sources (national and regional Red Lists) through a command line tool.

INPUT
- List of species with scientific names (CSV format)
Mandatory: yes

- Ancillary sources, for example national and regional Red Lists (CSV or XLSX format.)
Mandatory: at least one

OUTPUT
- Combined table with scientific names of species and columns from ancillary sources (CSV format).
Mandatory: yes

"""

# for compound arguments with subarguments: to parse pairs of key (subargument) and value (value of subargument)
class ValidateKeyValuePairs(argparse.Action):
    """
    argparse action to parse KEY=VALUE pairs and validate them dynamically based on the required keys.
    """
    def __init__(self, option_strings, dest, required_keys=None, **kwargs):
        self.required_keys = required_keys or set()  # set of required keys can be passed when adding the argument
        super(ValidateKeyValuePairs, self).__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        parsed_values = {}

        # split and parse key-value pairs
        for item in values:
            try:
                key, value = item.split('=', 1)  # split into key and value
                key = key.strip()
                value = value.strip()
                parsed_values[key] = value
                # debug: print(key, ' ', value)
            except ValueError:
                raise argparse.ArgumentError(self, f"Could not parse '{item}' as KEY=VALUE.")

        # check for missing or extra keys
        missing_keys = self.required_keys - parsed_values.keys()
        extra_keys = parsed_values.keys() - self.required_keys

        if missing_keys:
            raise argparse.ArgumentError(self, f"Missing required keys: {', '.join(missing_keys)}.")
        if extra_keys:
            raise argparse.ArgumentError(self, f"Unexpected keys: {', '.join(extra_keys)}.")

        setattr(namespace, self.dest, parsed_values)


## Specify command-line interface for this plugin
# to run in command line:
# python SCRIPT_NAME.py path_to_input_species path_to_iucn_habitat_csv path_to_iucn_categories_csv path_to_national_redlist_xlsx path_to_regional_redlist_csv path_to_output_csv path_to_iucn_output
# set up command-line argument parsing
parser = argparse.ArgumentParser(prog = "species_enrich", description='Harmonisation of species data (custom Red Lists), IUCN and GBIF is planned.')
"""
# REDUNDANT - IUCN data
parser.add_argument('-fetch_IUCN', type=str, choices=['yes', 'no'], required=True, help='Specify whether to fetch IUCN data: yes or no') # Default: no because it is brought through a separate tool
"""

# add input as a compound argument
parser.add_argument('input_species_list', # mandatory
                    nargs=2, 
                    action=ValidateKeyValuePairs, # call class defined above
                    required_keys={'path','name'},
                    metavar="KEY=VALUE", 
                    help='Path to the input dataset with scientific names of species (CSV). Specify the parameters as: path=path/to/file name="scientificName". Both parameters accept only one value.')

# output
parser.add_argument('output', help='Path to the output enriched dataset (CSV)') # mandatory

parser.add_argument('-IUCN', help='Path to IUCN dataset(CSV)') # optional
"""
# REDUNDANT - All IUCN data fetched in one dataset
parser.add_argument('-IUCN_categories', help='Path to IUCN categories file (CSV)') # optional argument
"""


parser.add_argument('-log_level', help='Set the logging level (e.g., DEBUG, INFO, WARNING). Default is DEBUG.', default='DEBUG') # optional argument to look up issues

# add compound arguments with subarguments using key-value pairs (optional)
# for national redlist 
parser.add_argument('-national_redlist', 
                    nargs='+', 
                    action=ValidateKeyValuePairs, # call class defined above
                    required_keys={'path', 'columns_to_join', 'name', 'protection_category'},
                    metavar="KEY=VALUE", 
                    help='Path to national redlist dataset (XSLX or CSV). Specify the parameters as: path=path/to/file columns_to_join="column_1,column_2" name="scientificName" protection_category="category". "columns to join" is not restricted by any number, while protection_category can be only one.')

# for regional redlist
parser.add_argument('-regional_redlist', 
                    nargs='+', # allow multiple key-value pairs
                    action=ValidateKeyValuePairs, # call class defined above
                    required_keys={'path', 'columns_to_join', 'name', 'protection_category'},
                    metavar="KEY=VALUE", 
                    help='Path to regional redlist dataset (CSV). Specify the parameters as: path=path/to/file columns_to_join="column_1,column_2" name="scientificName" protection_category="category". "columns to join" is not restricted by any number, while protection_category can be only one.')

# for other dataset
parser.add_argument('-other_dataset', 
                    nargs=2, 
                    action=ValidateKeyValuePairs, # call class defined above
                    required_keys={'path', 'columns_to_join'},
                    metavar="KEY=VALUE", 
                    help='Path to other dataset. Specify the parameters as: path=path/to/file columns_to_join="column_1,column_2". "columns to join" is not restricted by any number.')

# TODO - to implement multiple other datasets
# TODO - to replace 'columns_to_join' with multiple columns (just to test?) - there might be other columns, apart from the protection category. 
# so, 'columns_to_join' must contain at least the same column as for 'protection_category'

# parse arguments
args = parser.parse_args() # process arguments returned as argparse.Namespace object and write them into a variable

# REDUNDANT - previous versions
"""
parser.add_argument('input_species_list', help='Path to the input list of species (CSV)') # mandatory
parser.add_argument('-national_redlist', help='Path to national redlist dataset (XSLX or CSV)') # optional argument, CSV should be supported as well
parser.add_argument('-regional_redlist', help='Path to regional redlist dataset (CSV)') # optional argument
"""

"""
# add subparsers - or TODO - move to subarguments (class KeyValuePairsAction)
subparsers = parser.add_subparsers(dest='operation') 

# add subparser for the national redlist
national_redlist_parser = subparsers.add_parser('national_redlist', help='National redlist dataset (XSLX or CSV)') # define subparser for national redlist
national_redlist_parser.add_argument ('--path', type=str, help = 'Path to the national redlist dataset (XSLX or CSV)') 
national_redlist_parser.add_argument ('--columns_to_join', type=str, nargs='+', help = 'Columns from the national redlust dataset to be joined') # Typically it is just one column (protection category), but might be more (therefore, 'nargs' = '+'))
national_redlist_parser.add_argument('--protection_category', type=str, help='Specify which column is the protection category of species')

# TODO - to add subarguments for regional redlist as well
"""

# assign file paths from command-line arguments (see parser.add_argument)
input_species = args.input_species_list
input_path = input_species['path']
scientific_name = input_species['name']

iucn_csv = args.IUCN
"""
# REDUNDANT - All IUCN data fetched in one dataset
iucn_categories_csv = args.IUCN_categories
"""

# regional redlist
regional_redlist_csv = args.regional_redlist
regional_redlist_path = regional_redlist_csv['path']
regional_redlist_columns = regional_redlist_csv['columns_to_join']
regional_redlist_name = regional_redlist_csv['name']
regional_redlist_category = regional_redlist_csv['protection_category']

# national redlist
national_redlist_csv = args.national_redlist
national_redlist_path = national_redlist_csv['path']
national_redlist_columns = national_redlist_csv['columns_to_join']
national_redlist_name = national_redlist_csv['name']
national_redlist_category = national_redlist_csv['protection_category']

other_dataset = args.other_dataset
output_csv = args.output

# REDUNDANT - conditional requirement check on fetching data from IUCN (it became just an optional argument)
"""
if args.fetch_IUCN == 'yes':
    if not args.IUCN_habitat or not args.IUCN_categories:
        parser.error("--IUCN_habitat and --IUCN_categories are required when --fetch_iucn is 'yes'") # it will stop the script and raise the error

# assign flag on fetching data from IUCN (true or false)
fetch_iucn = args.fetch_IUCN
"""

# open the input dataset with a list of scientific names (CSV)
df = pd.read_csv(input_path)

# TODO - to add filtering by bbox of area needed

# REDUNDANT - from old version where list of species was from GBIF
"""
# drop attributes unique by record (date, coordinates, basis of record, elevation/depth)
columns_to_drop = ['yearmonth', 'lat', 'lon', 'basisofrecord', 'x_cart', 'elevation', 'depth', 'y_cart', 'bbox'] # TODO - to check columns again or just leave columns needed

# perform dropping attributes
df_filtered = df.drop(columns=columns_to_drop)
"""

# REDUNDANT - fetching IUCN data is written in a separate block
"""
# add new attributes from IUCN describing other scopes of assessment by IUCN + data on habitat importance
columns_to_add = [
    'IUCNGlobalScopeCategory',
    'IUCNEuropeScopeCategory',
    'IUCNMediterrScopeCategory', # to find categories from different scopes of assessment
    'OtherNationalCategory', # to find categories from national redlist, eg Spain
    'OtherRegionalCategory', # to find categories from regional redlist, eg Catalonia
    'IUCNHabitatCodes', # to find all habitat codes from IUCN that particular species might inhabit
    'IUCNSuitability_Suitable', # to list all habitat codes which are suitable for particular species
    'IUCNMajorImportance_Yes', # to list habitat codes only which are suitable species from the previous column
    'Analysis', # to choose whether species are suitable for calculations of habitat connectivity - boolean values
    'Note' # any other researcher-derived comments
]

# TODO - to list automatically all available columns

# perform adding attributes through pd_concat
df_filtered = pd.concat([df_filtered, pd.DataFrame(columns=columns_to_add)])

# filter to keep only rows with unique 'specieskey'
df_unique_species = df_filtered.drop_duplicates(subset=['specieskey'])


if fetch_iucn == 'yes': # if user specified to fetch data from IUCN
    print ("Fetching IUCN data...")
    # load iucn_habitat_csv into dataframe
    df_iucn_habitat = pd.read_csv(iucn_habitat_csv)

    # to choose columns if they are deriving from IUCN
    columns_to_add_iucn = [col for col in df_iucn_habitat.columns if col.lower().startswith('iucn')]
    print (f"Columns to link with GBIF data from IUCN are: {columns_to_add_iucn}")

    # to map species name with corresponding data from IUCN on habitats (currently fetched manually through IUCN search)
    # loop over columns of IUCN data to find and update matching columns in GBIF intermediate dataframe

    for col in columns_to_add:
        if col in columns_to_add_iucn:
            # map values from iucn_habitat_df to df_unique_specieskey - match of 'species' and 'speciesName'
            df_unique_species[col] = df_unique_species['species'].map(df_iucn_habitat.set_index('speciesName')[col])

    # update 'IUCNGlobalScopeCategory' with values from 'iucnredlistcategory'
    df_unique_species['IUCNGlobalScopeCategory'] = df_unique_species['iucnredlistcategory']
    # drop the 'iucnredlistcategory' column to have the same style of columns' names
    df_unique_species.drop(columns=['iucnredlistcategory'], inplace=True)
else:
    print ("Not fetching IUCN data.")
"""

# 2. HARMONISE REGIONAL REDLIST

# load regional redlist
df_regional_redlist = pd.read_csv(regional_redlist_path, encoding='utf-8')
# print heads of this dataframe
# print(df_regional_redlist.head())

"""
## THIS PART TO CHECK WHETHER THERE ANY MATCHES IN SPECIES NAME BETWEEN CSVs 
# convert species names to lowercase for case-insensitive comparison
unique_species_list = df_unique_species['species'].str.lower().tolist()
regional_redlist_list = df_regional_redlist['esp_cies_nom_cient_fic'].str.lower().tolist()
# create sets of species names in lowercase for case-insensitive comparison
unique_species_set = set(df_unique_species['species'].str.lower())
regional_redlist_set = set(df_regional_redlist['esp_cies_nom_cient_fic'].str.lower())
# find the intersection between two sets
matches = unique_species_set.intersection(regional_redlist_set)
num_matches = len(matches)
print(f"Number of matches (case-insensitive): {num_matches}")


# find matches where species names are substrings of each other (parts of names to handle cases like "Lynx pardina (= L. pardinus)")
matches = set()
for unique_species in unique_species_list:
    for regional_species in regional_redlist_list:
        if unique_species in regional_species or regional_species in unique_species:
            matches.add((unique_species, regional_species))

# print unique matches 
for match in matches:
    print(f"Matched pair: {match[0]} - {match[1]}")
# calculate the number of unique matches
num_matches = len(matches)
print(f"Number of matches (case-insensitive, including substrings): {num_matches}")
"""

## Map regional categories with the input list of species

# TODO - instead of text matching use GBIF TOOL fixing list of scientific names and fetching unique species key

# create temporary columns - convert species names to lowercase for case-insensitive comparison
df[scientific_name + '_lower'] = df[scientific_name].str.lower()
df_regional_redlist[regional_redlist_name + '_lower'] = df_regional_redlist[regional_redlist_name].str.lower()

# define function to generate possible abbreviations from a species name (genus name shorthanded, eg L. pardinus)
def generate_abbreviations(name):
    parts = name.split()
    # generate abbreviations using the first letter of each part
    abbreviations = [f"{part[0]}." for part in parts if len(part) > 1]
    return [name] + abbreviations

# build abbreviation dictionary for lookup
abbreviation_dict = {}
for name in df[scientific_name]:
    expanded_name = name.lower()
    abbreviations = generate_abbreviations(expanded_name)
    abbreviation_dict[expanded_name] = abbreviations
# debug: print (abbreviation_dict) # for troubleshooting

# define function to check if one name matches another or if their abbreviations match
def is_match(name_1, name_2, abbreviation_dict):
    # check if names match exactly
    if name_1 == name_2:
        return True
    # check if name_1 or name_2 is in the list of abbreviations for the other
    abbreviations_1 = abbreviation_dict.get(name_1, [])
    return any(abbr in name_2 for abbr in abbreviations_1) or any(name_2 in abbr for abbr in abbreviations_1)

# initialize count of successful matches
successful_match_found = 0

# iterate over dataframe rows and update OtherRegionalCategory if there is a match
for i, unique_row in df.iterrows():
    unique_species = unique_row[scientific_name + '_lower']
    for j, regional_row in df_regional_redlist.iterrows(): # i and j as indices in dataframes
        regional_species = regional_row[regional_redlist_name + '_lower']
        if is_match(unique_species, regional_species, abbreviation_dict): # is species name has been met anywhere (see function above)
            df.at[i, 'OtherRegionalCategory'] = regional_row[regional_redlist_category] # perform mapping (was 'Categoria \ncatàleg' in file downloaded directly from the website, not through API)
            successful_match_found += 1 # increment count of successful matches
            break  # stop after the first match for this species

# count unique species
total_unique_species = df[scientific_name + '_lower'].nunique()  # counts the number of unique species
# calculate the share of successful matches between input dataset and ancillary source
match_share = successful_match_found/total_unique_species

# drop temporary lowercase columns
df.drop(columns=[scientific_name + '_lower'], inplace=True)
df_regional_redlist.drop(columns=[regional_redlist_name + '_lower'], inplace=True)

# print if there was at least one successful match
if successful_match_found:
    print('-'*30)
    print(f"Share of successful matches between the input list of species and ancillary source is {match_share:.2%}")
    print("Extracted protection categories are:")
    # exclude nodata values and get unique non-null values
    unique_categories = df['OtherRegionalCategory'].dropna().unique()
    # convert the list of unique values to a comma-separated string
    unique_categories_str = ", ".join(unique_categories)
    print(unique_categories_str)  # extract unique values from categories
else:
    print("No protection categories were found for the given species.")

# 3. HARMONISE NATIONAL REDLIST (Currently not flexible and developed for the specific XLSX file schema)

# create temporary columns - convert species names to lowercase for case-insensitive comparison
df[scientific_name + '_lower'] = df[scientific_name].str.lower()

# initialize count of successful matches again
successful_match_found = 0

if national_redlist_path.endswith('.xlsx'): # if input file is xlsx

    # load national redlist - Excel file and the sheet 2 (index = 1)
    df_national_redlist = pd.read_excel(national_redlist_path, sheet_name=1) # load from the value from dictionary object
    print('-'*30)
    print(f"For debugging: printing headers in the dataset {national_redlist_path}:") # debug
    print(df_national_redlist.columns)

    # create temporary column with lowercase valies
    df_national_redlist[national_redlist_name + '_lower'] = df_national_redlist[national_redlist_name].str.lower() 

    # remove newline character from the column names
    df_national_redlist.columns = df_national_redlist.columns.str.replace('\n', ' ')

    # loop over df_unique_species and update OtherNationalCategory if there is a match
    for i, unique_row in df.iterrows():
        unique_species = unique_row[scientific_name + '_lower']  # case-insensitive temporary column
        if pd.notna(unique_species):
            for j, national_row in df_national_redlist.iterrows():
                national_species = national_row[national_redlist_name + '_lower']
                if is_match(unique_species, national_species, abbreviation_dict): # is species name has been met anywhere (see function above)
                    df.at[i, 'OtherNationalCategory'] = national_row[national_redlist_category]
                    successful_match_found += 1 # increment count of successful matches
                    break  # stop after the first match for this species

elif national_redlist_path.endswith('.csv'): # if input file is csv
    # load national redlist
    df_national_redlist = pd.read_csv(national_redlist_path, encoding='utf-8')
    # TODO - add block on reading CSV
else:
    print (f"Format of {national_redlist_path} is not supported.")

# count unique species
total_unique_species = df[scientific_name + '_lower'].nunique()  # counts the number of unique species
# calculate the share of successful matches between input dataset and ancillary source
match_share = successful_match_found/total_unique_species

# drop temporary lowercase columns
df.drop(columns=[scientific_name + '_lower'], inplace=True)
df_national_redlist.drop(columns=[national_redlist_name + '_lower'], inplace=True)

# TODO - to handle a case with extra space in 'national_redlist_category' (originally has an extra space after the main column name)
# TODO - to cast the number of EXCEL sheet to a separate subargument (required only if dataset is .xlsx)

# print if there was at least one successful match
if successful_match_found:
    print('-'*30)
    print(f"Share of successful matches between the input list of species and ancillary source is {match_share:.2%}")
    print("Extracted protection categories are:")
    # exclude nodata values and get unique non-null values
    unique_categories = df['OtherNationalCategory'].dropna().unique()
    # convert the list of unique values to a comma-separated string
    unique_categories_str = ", ".join(unique_categories)
    print(unique_categories_str)  # extract unique values from categories
else:
    print("No protection categories were found for the given species.")

# for troubleshooting
# print(df_unique_species.columns) 


# save the filtered dataframe to a new csv file
df.to_csv(output_csv, index=False, encoding = 'utf-8')
print('-'*30)
print(f"Filtered data for each unique species saved to {output_csv}")

# TODO - to check other API for regional dataset on rare and endangered species: https://datos.gob.es/en/apidata
# If it does not requires user authentication, it is more robust to use it instead of Socrata API


"""
# TO MAP manual csv with habitat codes to data on global IUCN categories
# Load the CSV and Excel files into pandas DataFrames
df1 = pd.read_csv(input_species)
df2 = pd.read_excel(iucn_xslx)

# cast column to string data type
df2['IucnGlobalScopeCategory'] = df2['IucnGlobalScopeCategory'].astype(str)

# Create a dictionary from df1 for quick lookup with zip to combine two sequences
species_to_iucn = dict(zip(df1['species'], df1['iucnredlistcategory']))

print (species_to_iucn)

# Iterate over the rows of df2 to update the 'IucnGlobalScopeCategory' column
for index, row in df2.iterrows():
    species_name = row['speciesName']
    if species_name in species_to_iucn: #if species found in
        df2.at[index, 'IucnGlobalScopeCategory'] = species_to_iucn[species_name]

# Save the updated DataFrame to the original Excel file
iucn_output = r'C:\\Users\\kriukovv\\Documents\\gbif\\output\\iucn_gbif_habitat_mapped.xlsx'
df2.to_excel(iucn_output, index=False)
print("Mapping with global IUCN categories completed.")
"""

"""
## TO DEFINE INPUT AND OUTPUT DATA PATHS MANUALLY
import os

input_dir = r'input'
output_dir = r'output'
# define input files
input_species = os.path.join(output_dir, 'filtered_datacube.csv') # GBIF occurrence data aligned with custom grid through previous preprocessing
print(input_species)
iucn_habitat_csv = os.path.join(output_dir, 'iucn_habitat.csv') # IUCN data on habitats for each species
iucn_categories_csv = os.path.join(output_dir,'iucn_categories.csv') # to add other scopes of assessment (continent, large region)
national_redlist_xlsx = os.path.join(input_dir,'national_redlist.xlsx')  # to add national redlists, eg Spain
regional_redlist_csv = os.path.join(input_dir, 'red_lists', 'regional_redlist_api.csv') # to add regional redlists, eg Catalonia
# define output data
iucn_csv = os.path.join(output_dir,'enriched_datacube.csv') # enriched GBIF ocurrence data with data on habitats and protection categories
"""
