import yaml
import os

def load_yaml(path:str) -> dict:
        """
        Load a yaml file from the given path to a dictionary

        Args:
            path (str): path to the yaml file

        Returns:
            dict: dictionary containing the yaml file content
        """
        with open(path , 'r') as file:
            return yaml.safe_load(file)
        
def save_yaml(data:dict, path:str) -> None:
    with open(path, 'w') as f:
        yaml.dump(data, f, default_flow_style=False)
        print("Updated YAML configuration saved to:", path)