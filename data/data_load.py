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
from typing import List, Set, Dict, Optional, Union, Any

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
        self._symbol_in_scenarios : Set[tuple] = set()
        #self._symbol_summary : dict = {}

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
                self._symbol_in_scenarios.add((scen_name, symbol_name))
        # Output data
        for scen_name, data_loader in self.output_data.items(): 
            for symbol_name in data_loader.data.keys():
                self._symbol_to_file[symbol_name] = 'output'
                self._symbol_in_scenarios.add((scen_name, symbol_name))
        # Output year data
        for scen_name, data_loader in self.output_year_data.items(): 
            for symbol_name in data_loader.data.keys():
                self._symbol_to_file[symbol_name] = 'output_year'
                self._symbol_in_scenarios.add((scen_name[0], symbol_name))

    def get_symbol(self, symbol_name: str, scenarios: Union[str, List[str]] = None) -> pd.DataFrame:
        # If no scenarios provided, consider all scenarios
        if scenarios is None:
            scenarios = self.scenarios_names
        # Else verify that the scenarios exist
        elif not all(s in self.scenarios_names for s in scenarios):
            missing = [s for s in scenarios if s not in self.scenarios_names]
            raise KeyError(f"Scenarios not found: {missing}")

        # Verify that the symbol exists in any data
        if symbol_name not in self._symbol_to_file:
            raise KeyError(f"Symbol '{symbol_name}' not found in any data.")
        
        frames = []
        data_type = self._symbol_to_file[symbol_name]
        if data_type == 'input':
            considered_data = self.input_data
        elif data_type == 'output':
            considered_data = self.output_data
        elif data_type == 'output_year':
            considered_data = self.output_year_data
        else:
            raise ValueError(f"Unknown data type '{data_type}' for symbol '{symbol_name}'.")
        
        for scen_name in scenarios:
            if scen_name not in considered_data.keys() or (scen_name, symbol_name) not in self._symbol_in_scenarios:
                print(f"Symbol '{symbol_name}' not found in scenario '{scen_name}'. Skipping.")
            else :
                data_loader = considered_data[scen_name]
                df = data_loader.get_symbol(symbol_name)
                df['Scenario'] = scen_name
                df = df[['Scenario'] + [c for c in df.columns.tolist() if c != 'Scenario']]
                frames.append(df)

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

