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
    """
    Manages data detection and data loading
    Can be initialized from a path or a ScenarioManager

    Automatically detects existing data files and find its location
    """
    def __init__(self, scenario_init: Union[str, Path, ScenarioManager, None] = None):
        """
        Initialize DataManager

        Args:
            scenario_init : Path to scenario directory or ScenarioManager instance
        """
        if isinstance(scenario_init, ScenarioManager):
            scenario_manager = scenario_init
        else:
            scenario_manager = ScenarioManager(scenario_init)
            scenario_manager.summary()
        
        # Store scenario manager and properties
        self.manager = scenario_manager
        self.root_path = scenario_manager.root_path
        self.scenarios = scenario_manager.scenarios
        self.is_single_scenario = scenario_manager.is_single_scenario
        self.scenarios_names = scenario_manager.scenarios_names
        self.output_years = scenario_manager.output_years
        self.key_func_map = scenario_manager.key_func_map

        # Store data containers
        self.BM_data : Dict[str, DataLoader] = {}
        self.Basis_data : Dict[str, DataLoader] = {}
        self.input_data : Dict[str, DataLoader] = {}
        self.output_data : Dict[str, DataLoader] = {}
        self.output_year_data : Dict[str, DataLoader] = {}

        # Store data mappings
        self._symbol_to_file : dict = {}
        self._symbol_in_scenarios : Set[tuple] = set()
        #self._symbol_summary : dict = {}

        if scenario_manager :
            self._symbol_mapping()
            self.key_data_map = {'BM': self.BM_data,
                                 'Basis': self.Basis_data,
                                 'input': self.input_data,
                                 'output': self.output_data,
                                 'output_year': self.output_year_data}

    def __repr__(self):
        return f"DataManager(scenarios={len(self.scenarios)})"
    
    def _symbol_mapping(self):
        lines = [
            "=" * 60,
            f"Mapping symbols to data files for {len(self.scenarios)} scenarios:",
            "=" * 60,]
        print("\n".join(lines))

        # We will not load all data at once to save memory
        for key, func in self.key_func_map.items():
            print(f'Processing data type: {key}')
            dict = func()
            # Special case for output year files
            if key == 'output_year':
                for scenario_name, year_dict in dict.items():
                    for year, path in year_dict.items():
                        container = gt.Container(str(path))
                        for symbol_name in container.data.keys():
                            if self._verify_symbol(container, symbol_name, key):
                                self._symbol_to_file[symbol_name] = key
                                self._symbol_in_scenarios.add(((scenario_name, year), symbol_name))
            else :
                for scenario_name, path in dict.items():
                    container = gt.Container(str(path))
                    for symbol_name in container.data.keys():
                        if self._verify_symbol(container, symbol_name, key):
                            self._symbol_to_file[symbol_name] = key
                            self._symbol_in_scenarios.add((scenario_name, symbol_name))

    def _verify_symbol(self, container: gt.Container, symbol_name: str, key: str) -> bool:
        # Alert if symbol already exists
        if symbol_name in self._symbol_to_file and self._symbol_to_file[symbol_name] != key:
            print(f"Warning: Symbol '{symbol_name}' already exists in '{self._symbol_to_file[symbol_name]}' file.")

        # Verify if there is data for the symbol in the container
        symbol = container[symbol_name].records
        if symbol is not None and not symbol.empty:
            return True
        return False
        
    def _load_all_data(self):
        for key, func in self.key_func_map.items():
            dict = func()
            # Special case for output year files
            if key == 'output_year':
                for scenario_name, year_dict in dict.items():
                    for year, path in year_dict.items():
                        self.key_data_map[key][(scenario_name, year)] = DataLoader(path)
            else :
                for scenario_name, path in dict.items():
                    self.key_data_map[key][scenario_name] = DataLoader(path)

    def get_symbol(self, symbol_name: str, scenarios: Union[str, List[str]] = None) -> pd.DataFrame:
        lines = [
            "=" * 60,
            f"Loading symbol '{symbol_name}' for scenarios: {scenarios if scenarios else 'All Scenarios'}",
            "=" * 60,]
        print("\n".join(lines))

        # If no scenarios provided, consider all scenarios
        scenarios = [scenarios] if isinstance(scenarios, str) else scenarios
        if scenarios is None:
            scenarios = self.scenarios_names
        elif not all(s in self.scenarios_names for s in scenarios):
            missing = [s for s in scenarios if s not in self.scenarios_names]
            raise KeyError(f"Scenarios not found: {missing}")
        else:
            scenarios = set(scenarios)

        # Verify that the symbol exists in any data
        if symbol_name not in self._symbol_to_file:
            raise KeyError(f"Symbol '{symbol_name}' not found in any data.")
        
        # Initialization to collect data frames
        frames = []
        key = self._symbol_to_file[symbol_name]
        if key == 'output_year':
            scenarios = set((s, y) for s in scenarios for y in self.output_years)
        
        # Collect data from each scenario
        for scen_name in scenarios:
            if (scen_name, symbol_name) not in self._symbol_in_scenarios:
                print(f"Symbol '{symbol_name}' not found in scenario '{scen_name}'. Skipping.")
            else :
                # If the data is not loaded yet, load it
                if scen_name not in self.key_data_map[key].keys() :
                    scen_config = self.scenarios[scen_name[0]] if key == 'output_year' else self.scenarios[scen_name]
                    if key == 'output_year':
                        year_path = scen_config.key_path_map[key][scen_name[1]]
                        self.key_data_map[key][scen_name] = DataLoader(year_path)
                    else :
                        path = scen_config.key_path_map[key]
                        self.key_data_map[key][scen_name] = DataLoader(path)
                # Load the data frame and add scenario column if needed
                data_loader = self.key_data_map[key][scen_name]
                df = data_loader.get_symbol(symbol_name)
                if len(scenarios) > 1:
                    scen = scen_name[0] if key == 'output_year' else scen_name
                    df['Scenario'] = scen
                    df = df[['Scenario'] + [c for c in df.columns.tolist() if c != 'Scenario']]
                frames.append(df)

        if frames:
            return pd.concat(frames, ignore_index=True)
        else:
            return pd.DataFrame()  # Return empty DataFrame if no data found

