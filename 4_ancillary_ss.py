# "pip install openpyxl" to work with xslx through pandas
import pandas as pd
import argparse
import unicodedata
import re

# import own function to fix scientific names
from gbif_lookup import fix_species_name
# TODO - implement fixing scientific names

"""
24/09/2024
Attempt to bring tabular data for the custom of list of species from ancillary sources (national and regional Red Lists) through a command line tool.

Args
- List of species with scientific names (CSV format)
Mandatory: yes
- Ancillary sources, for example national and regional Red Lists (CSV or XLSX format.)
Mandatory: at least one

Returns
- Combined table with scientific names of species and columns from ancillary sources (CSV format).
Mandatory: yes

"""

def clean_text(name: str) -> str:
    """Helper - normalise text strings (Unicode, non-printable, messy characters).
    Args:
        df (pd.DataFrame): input text string
    Returns:
        pd.DataFrame: text string with cleaned column names (in-place modification)."""
    name = unicodedata.normalize('NFC', name)          # normalize Unicode form
    name = name.strip()                                # trim spaces
    name = name.replace('\xa0', '')                   # non-breaking space to space
    name = re.sub(r'[\r\n\t]+', '', name)             # replace newlines/tabs with space
    name = name.replace('–', '-').replace('—', '-')    # normalize dashes
    return name

def clean_df(df: pd.DataFrame) -> pd.DataFrame:
    """Helper - normalise column names in dataframes (Unicode, non-printable, messy characters).""
    Args:
        df (pd.DataFrame): input dataframe
    Returns:
        pd.DataFrame: a dataframe with cleaned column names (in-place modification).
    """
    def clean(name: str) -> str:
        if not isinstance(name, str):
            return name
        name = unicodedata.normalize('NFC', name)
        name = re.sub(r'[\r\n\t]+', '', name)
        name = name.replace('\xa0', '')
        name = name.replace('–', '-').replace('—', '-')
        return name.strip()

    df.columns = [clean(col) for col in df.columns]
    return df

# for compound arguments with subarguments: to parse pairs of key (subargument) and value (value of subargument)
class ValidateKeyValuePairs(argparse.Action):
    """
    argparse action to parse KEY=VALUE pairs and validate them dynamically based on the required keys.
    This argparse action:
    -splits key-value pairs
    -validates the required keys are present
    -rejects extra or missing keys
    -returns a dictionary instead of a plain string list
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

# add input as a compound argument
parser.add_argument('input_species_list', # mandatory
                    nargs=2, 
                    action=ValidateKeyValuePairs, # call class defined above
                    required_keys={'path','name'},
                    metavar="KEY=VALUE", 
                    help='Path to the input dataset with scientific names of species (CSV). Specify the parameters as: path=path/to/file name="scientificName". Both parameters accept only one value.')

# output
parser.add_argument('output', help='Path to the output enriched dataset (CSV)') # mandatory
parser.add_argument('-log_level', help='Set the logging level (e.g., DEBUG, INFO, WARNING). Default is DEBUG.', default='DEBUG') # optional argument to look up issues

# add compound arguments with subarguments using key-value pairs (optional)
# for national redlist 
parser.add_argument('-national_redlist', 
                    nargs='+', 
                    action=ValidateKeyValuePairs, # call class defined above
                    required_keys={'path', 'columns', 'name', 'protection_category'},
                    metavar="KEY=VALUE", 
                    help='Path to national redlist dataset (XSLX or CSV). Specify the parameters as: path=path/to/file columns="column_1,column_2" name="scientificName" protection_category="category". "columns" is not restricted by any number, while protection_category can be only one.')

# for regional redlist
parser.add_argument('-regional_redlist', 
                    nargs='+', # allow multiple key-value pairs
                    action=ValidateKeyValuePairs, # call class defined above
                    required_keys={'path', 'columns', 'name', 'protection_category'},
                    metavar="KEY=VALUE", 
                    help='Path to regional redlist dataset (CSV). Specify the parameters as: path=path/to/file columns="column_1,column_2" name="scientificName" protection_category="category". "columns" is not restricted by any number, while protection_category can be only one.')

# for other dataset
parser.add_argument('-other_dataset', 
                    nargs=2, 
                    action=ValidateKeyValuePairs, # call class defined above
                    required_keys={'path', 'columns'},
                    metavar="KEY=VALUE", 
                    help='Path to other dataset. Specify the parameters as: path=path/to/file columns="column_1,column_2". "columns" is not restricted by any number.')

# TODO - to replace 'columns_to_join' with multiple columns (just to test?) - there might be other columns, apart from the protection category. 
# so, 'columns_to_join' must contain at least the same column as for 'protection_category'

# parse arguments
args = parser.parse_args() # process arguments returned as argparse.Namespace object and write them into a variable

# assign file paths from command-line arguments (see parser.add_argument)
input_species = args.input_species_list
input_path = input_species['path']
print(f"INPUT PATH IS {input_path}")
scientific_name = input_species['name']

# regional redlist
regional_redlist_csv = args.regional_redlist
regional_redlist_path = regional_redlist_csv['path']
regional_redlist_name = regional_redlist_csv['name']
regional_redlist_category = clean_text(regional_redlist_csv['protection_category']) # clean from extra characters
regional_redlist_columns = clean_text(regional_redlist_csv['columns']) # clean from extra characters
# national redlist
national_redlist_csv = args.national_redlist
national_redlist_path = national_redlist_csv['path']
national_redlist_name = national_redlist_csv['name']
national_redlist_category = clean_text(national_redlist_csv['protection_category']) # clean from extra characters
national_redlist_columns = clean_text(national_redlist_csv['columns']) # clean from extra characters

print(repr(regional_redlist_category))
print(repr(national_redlist_category))
print(repr(regional_redlist_columns))
print(repr(national_redlist_columns))

other_dataset = args.other_dataset
output_csv = args.output

# open the input dataset with a list of scientific names (CSV) and clean
df = pd.read_csv(input_path)
df = clean_df(df)

# TODO - to add filtering by bbox of area needed

# 2. HARMONISE REGIONAL REDLIST

# load regional redlist
df_regional_redlist = pd.read_csv(regional_redlist_path, encoding='utf-8')
df_regional_redlist = clean_df(df_regional_redlist)
#NOTE:DEBUG print(df_regional_redlist.head())

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

# 3. HARMONISE NATIONAL REDLIST (not flexible and developed for the specific XLSX file schema)
# create temporary columns - convert species names to lowercase for case-insensitive comparison
df[scientific_name + '_lower'] = df[scientific_name].str.lower()
# initialize count of successful matches again
successful_match_found = 0


if national_redlist_path.endswith('.xlsx'): # if input file is xlsx
    # load national redlist - Excel file and the sheet 2 (index = 1)
    df_national_redlist = pd.read_excel(national_redlist_path, sheet_name=1) # load from the value from dictionary object
    print('-'*30)
    print(f"For debugging: printing headers in the dataset {national_redlist_path}:") # debug

 
    df_national_redlist = clean_df(df_national_redlist) # clean dataframe
    print(f" Columns in the national redlist: {df_national_redlist.columns}") #NOTE:DEBUG

    # create temporary column with lowercase valies
    df_national_redlist[national_redlist_name + '_lower'] = df_national_redlist[national_redlist_name].str.lower() 
    # remove newline character from the column names
    df_national_redlist.columns = df_national_redlist.columns.str.replace('\n', '')

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

total_unique_species = df[scientific_name + '_lower'].nunique()  # count unique species
# calculate the share of successful matches between input dataset and ancillary source
match_share = successful_match_found/total_unique_species

# drop temporary lowercase columns
df.drop(columns=[scientific_name + '_lower'], inplace=True)
df_national_redlist.drop(columns=[national_redlist_name + '_lower'], inplace=True)

# TODO - to handle a case with extra space in 'national_redlist_category' (originally has an extra space after the main column name)
# TODO - to cast the number of EXCEL sheet to a separate subargument (required only if dataset is .xlsx)

# print if there was at least one successful match
if successful_match_found:
    print('*'*30)
    print(f"Share of successful matches between the input list of species and ancillary source is {match_share:.2%}")
    print("Extracted protection categories are:")
    # exclude nodata values and get unique non-null values
    unique_categories = df['OtherNationalCategory'].dropna().unique()
    # convert the list of unique values to a comma-separated string
    unique_categories_str = ", ".join(unique_categories)
    print(unique_categories_str)  # extract unique values from categories
else:
    print("No protection categories were found for the given species.")
# NOTE:DEBUG print(df_unique_species.columns) 

# save the filtered dataframe to a new csv file
df.to_csv(output_csv, index=False, encoding = 'utf-8')
print('-'*30)
print(f"Filtered data for each unique species saved to {output_csv}")