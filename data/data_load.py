# Loading data for the pybal package
import os
import gams
import pandas as pd
import gams.transfer as gt

from pathlib import Path

class DataLoader:
    """
    DataLoader class to load and process GDX files from GAMS.
    """
    
    # Default data directory relative to this file
    DEFAULT_DATA_DIR = Path(__file__).parent.parent / "pybal_test" / "files"
    
    def __init__(self, file_path=None, data_dir=None):
        """
        Initialize DataLoader.
        
        Args:
            file_path: Specific file to load (can be relative to data_dir or absolute)
            data_dir: Directory containing data files (defaults to ../pybal_test/files/)
        """
        self.data_dir = Path(data_dir) if data_dir else self.DEFAULT_DATA_DIR
        self.file_path = file_path
        self.container = None  # Will hold the gams.transfer Container
    
    # We could put that in utils later
    def get_file_path(self, filename=None):
        """
        Get the full path to a file in the data directory.
        
        Args:
            filename: Name of the file (if None, uses self.file_path)
            
        Returns:
            Path object to the file
        """
        fname = filename if filename else self.file_path
        if fname is None:
            raise ValueError("No file specified")
        
        file_path = Path(fname)
        
        # If not absolute, treat as relative to data_dir
        if not file_path.is_absolute():
            file_path = self.data_dir / file_path
        
        if not file_path.exists():
            raise FileNotFoundError(f"The file {file_path} does not exist.")
        
        return file_path
    
    # We could put that in utils later
    def list_available_files(self, pattern="*.gdx"):
        """
        List all available files in the data directory.
        
        Args:
            pattern: Glob pattern to match files (default: *.gdx)
            
        Returns:
            List of file paths
        """
        if not self.data_dir.exists():
            raise FileNotFoundError(f"Data directory {self.data_dir} does not exist.")
        
        return list(self.data_dir.glob(pattern))
    
    def load_gdx(self, filename=None):
        """
        Load a GDX file and return the GAMS transfer Container.
        
        Args:
            filename: Name of the GDX file to load
            
        Returns:
            gams.transfer Container object
        """
        file_path = self.get_file_path(filename)
        
        # Load GDX file into GAMS transfer Container
        container = gt.Container(str(file_path))
        self.container = container
        
        return container
    
    def gdx_to_dataframes(self, filename=None):
        """
        Convert all symbols in a GDX file to pandas DataFrames.
        
        Args:
            filename: Name of the GDX file to load
            
        Returns:
            Dictionary mapping symbol names to DataFrames
        """
        container = self.load_gdx(filename) if filename else self.container
        
        if container is None:
            raise ValueError("No container loaded. Call load_gdx() first or provide filename.")
        
        dataframes = {}
        
        # Extract all symbols from the container
        # gams.transfer makes this much simpler - each symbol has a .records attribute
        # that is already a pandas DataFrame
        for symbol_name in container.data.keys():
            symbol = container[symbol_name]
            
            # Get the records as a DataFrame
            # For Sets, Parameters, Variables, and Equations
            if hasattr(symbol, 'records') and symbol.records is not None:
                dataframes[symbol_name] = symbol.records.copy()
        
        return dataframes
    
    def get_symbol_as_dataframe(self, symbol_name, filename=None):
        """
        Get a specific symbol from a GDX file as a DataFrame.
        
        Args:
            symbol_name: Name of the symbol to extract
            filename: Name of the GDX file (if not already loaded)
            
        Returns:
            DataFrame containing the symbol data
        """
        if filename:
            self.load_gdx(filename)
        
        if self.container is None:
            raise ValueError("No container loaded.")
        
        if symbol_name not in self.container.data:
            raise KeyError(f"Symbol '{symbol_name}' not found in container.")
        
        symbol = self.container[symbol_name]
        
        # Return the records DataFrame directly
        if hasattr(symbol, 'records') and symbol.records is not None:
            return symbol.records.copy()
        else:
            return pd.DataFrame()  # Return empty DataFrame if no records
    
    def get_symbol_info(self, symbol_name=None):
        """
        Get information about symbols in the container.
        
        Args:
            symbol_name: Name of specific symbol (if None, returns info for all symbols)
            
        Returns:
            Dictionary with symbol information (type, dimension, number of records, etc.)
        """
        if self.container is None:
            raise ValueError("No container loaded.")
        
        if symbol_name:
            if symbol_name not in self.container.data:
                raise KeyError(f"Symbol '{symbol_name}' not found in container.")
            
            symbol = self.container[symbol_name]
            return {
                'name': symbol.name,
                'type': type(symbol),
                'dimension': symbol.dimension,
                'number_records': symbol.number_records,
                'domain_names': symbol.domain_names if hasattr(symbol, 'domain_names') else None,
                'description': symbol.description if hasattr(symbol, 'description') else None
            }
        else:
            # Return info for all symbols
            info = {}
            for name in self.container.data.keys():
                symbol = self.container[name]
                info[name] = {
                    'type': type(symbol),
                    'dimension': symbol.dimension,
                    'number_records': symbol.number_records,
                    'domain_names': symbol.domain_names if hasattr(symbol, 'domain_names') else None,
                    'description': symbol.description if hasattr(symbol, 'description') else None
                }
            return info


if __name__ == "__main__":
    # Example usage
    loader = DataLoader()
    
    # List available files
    print("Available GDX files:")
    for file in loader.list_available_files():
        print(f"  - {file.name}")
    
    # Load a specific file
    print("\nLoading bb3_AHC-output.gdx...")
    container = loader.load_gdx("bb3_AHC-output.gdx")
    print(f"Loaded container with {len(container.data)} symbols")

    # # Get info about all symbols
    # print("\nSymbol Information:")
    # info = loader.get_symbol_info()
    # for name, details in info.items():
    #     print(f"  - {name}: {details['type']}, dimension={details['dimension']}, records={details['number_records']}")
    
    # # Convert all symbols to dataframes
    # print("\nConverting to DataFrames...")
    # dfs = loader.gdx_to_dataframes()
    # print(f"Created {len(dfs)} DataFrames")
    # for name, df in dfs.items():
    #     print(f"  - {name}: {df.shape}")
