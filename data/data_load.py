# Loading data for the pybal package
import os
import re
import sys
import gams
import warnings
import pandas as pd
import gams.transfer as gt

from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Union, Any

# Import from data module
sys.path.append(str(Path(__file__).parent.parent))
from data.scenario import ScenarioManager, ScenarioConfig

@dataclass
class DataLoader:
    path : Path 
    container : Optional[gt.Container] = None
    data : Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.container = gt.Container(str(self.path))
        self.data = self.container.data

    def __repr__(self):
        return f"DataLoader(path={self.path.name}, symbols={len(self.container.data)})"
    
    def get_symbol(self, symbol_name: str) -> pd.DataFrame:
        """
        Get a specific symbol from the container as a DataFrame.
        
        Args:
            symbol_name: Name of the symbol to extract
        Returns:
            DataFrame containing the symbol data
        """
        if symbol_name not in self.container.data:
            raise KeyError(f"Symbol '{symbol_name}' not found in container.")
        
        symbol = self.container[symbol_name]
        
        # Return the records DataFrame directly
        if hasattr(symbol, 'records') and symbol.records is not None:
            return symbol.records.copy()
        else:
            return pd.DataFrame()  # Return empty DataFrame if no records

class DataManager:
    def __init__(self, scenario_manager: ScenarioManager):
        self.manager = scenario_manager
        self.scenarios_names = scenario_manager.scenarios_names
        self.output_years = scenario_manager.output_years

        self.input_data : Dict[str, DataLoader] = {}
        self.output_data : Dict[str, DataLoader] = {}
        self.output_year_data : Dict[str, DataLoader] = {}

        self._symbol_to_file : dict = {}
        self._symbol_summary : dict = {}

        if scenario_manager :
            self._initialyze_data()
            self._symbol_mapping()

    def __repr__(self):
        return f"DataManager(scenarios={len(self.manager.scenarios)})"
    
    def _initialyze_data(self):
        # Load input data for all scenarios
        dict = self.manager.get_all_input_files()
        for scenario_name, path in dict.items():
            self.input_data[scenario_name] = DataLoader(path)

        # Load output data for all scenarios
        dict = self.manager.get_all_output_files()
        for scenario_name, path in dict.items():
            self.output_data[scenario_name] = DataLoader(path)

        # Load output year data for all scenarios
        dict = self.manager.get_all_output_year_files()
        for scenario_name, year_dict in dict.items():
            for year, path in year_dict.items():
                self.output_year_data[(scenario_name, year)] = DataLoader(path)

    def _symbol_mapping(self):
        # Input data
        for scen_name, data_loader in self.input_data.items():
            for symbol_name in data_loader.data.keys():
                self._symbol_to_file[symbol_name] = 'input'
        # Output data
        for scen_name, data_loader in self.output_data.items(): 
            for symbol_name in data_loader.data.keys():
                self._symbol_to_file[symbol_name] = 'output'
        # Output year data
        for scen_name, data_loader in self.output_year_data.items(): 
            for symbol_name in data_loader.data.keys():
                self._symbol_to_file[symbol_name] = 'output_year'

    def get_symbol(self, symbol_name: str) -> pd.DataFrame:
        if symbol_name not in self._symbol_to_file:
            raise KeyError(f"Symbol '{symbol_name}' not found in any data.")
        data_type = self._symbol_to_file[symbol_name]

        frames = []
        if data_type == 'input':
            for scen_name, data_loader in self.input_data.items():
                if symbol_name in data_loader.data:
                    df = data_loader.get_symbol(symbol_name)
                    df['Scenario'] = scen_name
                    cols = df.columns.tolist()
                    if cols[0] != 'Scenario':
                        cols = ['Scenario'] + [c for c in cols if c != 'Scenario']
                        df = df[cols]
                    frames.append(df)
        elif data_type == 'output':
            for scen_name, data_loader in self.output_data.items():
                if symbol_name in data_loader.data:
                    df = data_loader.get_symbol(symbol_name)
                    df['Scenario'] = scen_name
                    cols = df.columns.tolist()
                    if cols[0] != 'Scenario':
                        cols = ['Scenario'] + [c for c in cols if c != 'Scenario']
                        df = df[cols]
                    frames.append(df)
        elif data_type == 'output_year':
            for (scen_name, year), data_loader in self.output_year_data.items():
                if symbol_name in data_loader.data:
                    df = data_loader.get_symbol(symbol_name)
                    df['Scenario'] = scen_name
                    df['Year'] = year
                    cols = df.columns.tolist()
                    # Ensure Scenario is first and Year is second
                    new_cols = ['Scenario', 'Year'] + [c for c in cols if c not in ('Scenario', 'Year')]
                    df = df[new_cols]
                    frames.append(df)
        else:
            raise ValueError(f"Unknown data type '{data_type}' for symbol '{symbol_name}'.")
        if frames:
            return pd.concat(frames, ignore_index=True)
        else:
            return pd.DataFrame()  # Return empty DataFrame if no data found



if __name__ == "__main__":
    print("Load all scenarios and show categorized files")
    print("-" * 60)
    Manager = ScenarioManager()
    Data = DataManager(Manager)
    ScenData = Data.input_data["Scen1"]
    df = ScenData.get_symbol("IHOURSINST")
    print(df.head())

