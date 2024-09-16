import pandas as pd
import os

class GBIF_IUCN_ScientificName_Mapper:
    """
    Maps GBIF and IUCN data on the basis of scientific names.
    """

    def __init__(self, gbif_csv_path:str, iucn_csv_path:str , gbif_dict:dict, iucn_dict:dict, add_prefix:bool=True):
        """
        Initializes the class with the GBIF and IUCN dataframes.

        Args:
            gbif_csv_path (str): Path to the GBIF data CSV file.
            iucn_csv_path (str): Path to the IUCN data CSV file.
        """

        gbif_index = list(gbif_dict.keys())[0]
        iucn_index = list(iucn_dict.keys())[0]
        # Renaming the columns to make them consistent for joining later.
        self.gbif_df = pd.read_csv(gbif_csv_path, sep=',').set_index(gbif_index)
        self.iucn_df = pd.read_csv(iucn_csv_path, sep='|').set_index(iucn_index)

        # filtering out the columns we don't care about
        if gbif_dict[gbif_index] is not None:
           self.gbif_df = self.gbif_df.drop(columns=gbif_dict[gbif_index])
        if iucn_dict[iucn_index] is not None:
            self.iucn_df = self.iucn_df.drop(columns=iucn_dict[iucn_index])

        # add prefix to GBIF columns and iucn columns
        if add_prefix:
            self.gbif_df = self.gbif_df.add_prefix('gbif_')
            self.iucn_df = self.iucn_df.add_prefix('iucn_')
   
    def map_data(self)-> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Maps the GBIF and IUCN data on the basis of scientific names.

        Returns:
            pd.DataFrame: Mapped IUCN and GBIF data in a DataFrame.
            pd.DataFrame: Unmatched species in a DataFrame
        """
        # Mapping GBIF and IUCN data on the basis of scientific names (canonicalName and binomial - now the index)
        mapped_df = pd.merge(self.gbif_df, self.iucn_df, left_index=True, right_index=True, how='inner')

        # get the unmatched iucn records
        iucn_unmatched_records = self.iucn_df[~self.iucn_df.index.isin(mapped_df.index)]
     
        return mapped_df, iucn_unmatched_records
    
    def save_mapped_data_to_csv(self, mapped_df:pd.DataFrame, iucn_unmatched_records:pd.DataFrame, output_path:str):
        """
        Writes the mapped data to a CSV file.

        Args:
            mapped_df (pd.DataFrame): Mapped IUCN and GBIF data in a DataFrame.
            iucn_unmatched_records (pd.DataFrame): Unmatched species in a DataFrame.
            output_path (str): Path to the output CSV file.
        """
        # only keep the keys we care about
        mapped_df.to_csv(os.path.join(output_path, 'IUCN-GBIF_mapped_species.csv'), index=True, index_label='scientificName_mapped')
        iucn_unmatched_records.to_csv(os.path.join(output_path, 'IUCN_unmatched_species.csv'), index=True, index_label='scientificName_unmatched')

if __name__ == '__main__':
    gbif_csv_path = '.\\output\\mapped_species_GBIF.csv'
    iucn_csv_path = '.\\output\\concat_species_IUCN.csv'


    # dict = {index col: [list of column names we want to filter out]}
    # for gbif all except gbifKey,acceptedUsageKey and canonicalName (this is the index)
    gbif_dict = {'canonicalName':['gbifKey', 'acceptedUsageKey']}
    # for iucn all except bionomial (this is the index) #TODO drop id_no because it doesn't match?
    iucn_dict = {'binomial':None}
    # TODO add addtional columns to ignore for gbif and iucn in the respective dictionaries above

    mapping = GBIF_IUCN_ScientificName_Mapper(gbif_csv_path, iucn_csv_path, gbif_dict, iucn_dict, add_prefix=True)
    (mapped_df,iucn_unmatched_records)= mapping.map_data()
    
    # print the unmatched species in the IUCN data
    print(f"Unmatched species: {iucn_unmatched_records.index.values}")

    #write mapped data to csv
    mapping.save_mapped_data_to_csv(mapped_df, iucn_unmatched_records, '.\\output')
    print(mapped_df.head())