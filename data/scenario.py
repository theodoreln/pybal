# Scenario management for the pybal package
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Union
import warnings
import re


@dataclass
class ScenarioConfig:
    """
    Configuration for a single scenario.
    
    Attributes:
        name: Scenario name (folder name)
        path: Path to the scenario folder
        balopt_path: Path to the balopt.opt file
        input_path: Path to the input gdx file '*-input.gdx'
        output_path: Path to the output gdx file '*-output.gdx'
        output_yearly_path: Dict of files ending with 'output-YYYY.gdx' -> {year: path}
        output_other_path: Dict of all other GDX files
        gdx_files: Dictionary mapping ALL file basenames to full paths (for backward compatibility)
    """
    name: str
    path: Path
    balopt_path: Path
    input_path: Path = None
    output_path: Path = None
    output_yearly_path: Dict[str, Path] = field(default_factory=dict)  # key is year string
    output_other_path: Dict[str, Path] = field(default_factory=dict)
    gdx_files: Dict[str, Path] = field(default_factory=dict)
    
    def __post_init__(self):
        """Convert paths to Path objects and categorize GDX files."""
        self.path = Path(self.path)
        self.balopt_path = Path(self.balopt_path)
        
        # Convert all paths to Path objects
        self.gdx_files = {name: Path(path) for name, path in self.gdx_files.items()}
        
        # Categorize files if gdx_files is provided but categories are empty
        if self.gdx_files and not (self.input_path or self.output_path or
                                    self.output_yearly_path or self.output_other_path):
            self._categorize_files()
    
    def _categorize_files(self):
        """
        Categorize GDX files based on naming patterns.
        
        Patterns:
        - *-input.gdx -> input_file
        - *-output.gdx -> output_file
        - *-output-YYYY.gdx -> output_yearly_file (with year extracted)
        - Everything else -> output_other_file
        """
        # Pattern to match output-year files (e.g., bb3_AHC-output-2037.gdx)
        output_year_pattern = re.compile(r'^(.+)-output-(\d{4})\.gdx$', re.IGNORECASE)
        
        for filename, filepath in self.gdx_files.items():
            filepath = Path(filepath)
            filename_lower = filename.lower()
            
            # Check for output-year pattern first (more specific)
            match = output_year_pattern.match(filename)
            if match:
                year = match.group(2)  # Extract year
                self.output_yearly_path[year] = filepath
            
            # Check for output files (but not output-year)
            elif filename_lower.endswith('-output.gdx'):
                self.output_path = filepath

            # Check for input files
            elif filename_lower.endswith('-input.gdx'):
                self.input_path = filepath

            # Everything else
            else:
                self.output_other_path[filename] = filepath

    def get_gdx_file(self, filename: str) -> Optional[Path]:
        """
        Get path to a specific GDX file by name.
        
        Args:
            filename: Name of the GDX file (with or without .gdx extension)
            
        Returns:
            Path to the file or None if not found
        """
        # Handle with or without .gdx extension
        if not filename.endswith('.gdx'):
            filename += '.gdx'
        
        return self.gdx_files.get(filename)
    
    def get_output_yearly_file(self, year: Union[str, int]) -> Optional[Path]:
        """
        Get output file for a specific year.
        
        Args:
            year: Year as string or int (e.g., '2037' or 2037)
            
        Returns:
            Path to the file or None if not found
        """
        year_str = str(year)
        return self.output_yearly_path.get(year_str)
    
    def __repr__(self):
        return (f"ScenarioConfig(name='{self.name}', "
                f"gdx files={len(self.gdx_files)})")


class ScenarioManager:
    """
    Manages scenario detection and file discovery.
    
    Automatically detects scenarios based on folder structure:
    - Each scenario must have a balopt.opt file
    - GDX files are expected in an 'output' subfolder
    """
    
    DEFAULT_TEST_DIR = Path(__file__).parent.parent / "pybal_test"
    
    def __init__(self, path: Union[str, Path, None] = None, auto_discover: bool = True):
        """
        Initialize ScenarioManager.
        
        Args:
            path: Path to either:
                  - A scenarios folder (containing multiple scenario folders)
                  - A specific scenario folder
                  - None (uses default: ../pybal_test)
            auto_discover: If True, automatically discover scenarios on initialization
        """
        self.root_path = Path(path) if path else self.DEFAULT_TEST_DIR
        self.scenarios: Dict[str, ScenarioConfig] = {}
        self.is_single_scenario = False
        
        if not self.root_path.exists():
            raise FileNotFoundError(f"Path does not exist: {self.root_path}")
        
        if auto_discover:
            self.discover_scenarios()
            self.scenarios_names = list(self.scenarios.keys())
    
    def _is_valid_scenario_folder(self, folder_path: Path) -> bool:
        """
        Check if a folder is a valid scenario folder.
        
        A valid scenario folder must contain a balopt.opt file.
        
        Args:
            folder_path: Path to check
            
        Returns:
            True if valid scenario folder, False otherwise
        """
        if not folder_path.is_dir():
            return False
        
        # Check for balopt.opt file (case-insensitive on Windows)
        balopt_files = list(folder_path.glob('balopt.opt')) + list(folder_path.glob('balopt.OPT'))
        
        return len(balopt_files) > 0
    
    def _scan_scenario_folder(self, scenario_path: Path) -> Optional[ScenarioConfig]:
        """
        Scan a single scenario folder and create ScenarioConfig.
        
        Args:
            scenario_path: Path to the scenario folder
            
        Returns:
            ScenarioConfig object or None if invalid
        """
        if not self._is_valid_scenario_folder(scenario_path):
            return None
        
        # Find balopt file
        balopt_files = list(scenario_path.glob('balopt.opt')) + list(scenario_path.glob('balopt.OPT'))
        balopt_path = balopt_files[0]
        
        # Look for output folder
        output_dir = scenario_path / "output"
        
        # Collect GDX files
        gdx_files = {}
        if output_dir.exists() and output_dir.is_dir():
            for gdx_file in output_dir.glob("*.gdx"):
                gdx_files[gdx_file.name] = gdx_file
        
        # Create scenario config
        config = ScenarioConfig(
            name=scenario_path.name,
            path=scenario_path,
            balopt_path=balopt_path,
            gdx_files=gdx_files
        )
        
        return config
    
    def discover_scenarios(self) -> Dict[str, ScenarioConfig]:
        """
        Auto-detect all scenarios in the given path.
        
        Checks if the path is:
        1. A single scenario folder (has balopt.opt)
        2. A folder containing multiple scenario folders
        
        Returns:
            Dictionary mapping scenario names to ScenarioConfig objects
        """
        self.scenarios = {}
        
        # Check if root_path itself is a scenario folder
        if self._is_valid_scenario_folder(self.root_path):
            self.is_single_scenario = True
            config = self._scan_scenario_folder(self.root_path)
            if config:
                self.scenarios[config.name] = config
                print(f"✓ Detected single scenario: {config.name}")
        else:
            # Root path is a folder containing multiple scenarios
            self.is_single_scenario = False
            
            # Scan all subdirectories
            for item in self.root_path.iterdir():
                if item.is_dir():
                    config = self._scan_scenario_folder(item)
                    
                    if config:
                        self.scenarios[config.name] = config
                        print(f"✓ Found scenario: {config.name} ({len(config.gdx_files)} GDX files)")
                    else:
                        # Folder doesn't have balopt.opt
                        warnings.warn(f"⚠ Skipping folder '{item.name}': No balopt.opt file found")
        
        if not self.scenarios:
            warnings.warn(f"⚠ No valid scenarios found in {self.root_path}")
        
        return self.scenarios
    
    def get_scenario(self, name: str) -> ScenarioConfig:
        """
        Get configuration for a specific scenario.
        
        Args:
            name: Scenario name
            
        Returns:
            ScenarioConfig object
            
        Raises:
            KeyError: If scenario not found
        """
        if name not in self.scenarios:
            available = ', '.join(self.scenarios.keys())
            raise KeyError(f"Scenario '{name}' not found. Available scenarios: {available}")
        
        return self.scenarios[name]
    
    def get_common_files(self) -> List[str]:
        """
        Get list of GDX files that exist in ALL scenarios.
        
        Returns:
            List of filenames that are common across all scenarios
        """
        if not self.scenarios:
            return []
        
        # Get file sets for each scenario
        file_sets = [set(config.list_gdx_files()) for config in self.scenarios.values()]
        
        # Find intersection of all sets
        common_files = set.intersection(*file_sets) if file_sets else set()
        
        return sorted(common_files)
    
    def get_file_across_scenarios(self, filename: str) -> Dict[str, Path]:
        """
        Get the same file from all scenarios that have it.
        
        Args:
            filename: Name of the GDX file (with or without .gdx extension)
            
        Returns:
            Dictionary mapping scenario names to file paths
        """
        if not filename.endswith('.gdx'):
            filename += '.gdx'
        
        result = {}
        for scenario_name, config in self.scenarios.items():
            file_path = config.get_gdx_file(filename)
            if file_path:
                result[scenario_name] = file_path
        
        return result
    
    def get_all_output_files(self) -> Dict[str, Path]:
        """
        Get all output files (ending with -output.gdx) from all scenarios.
        
        Returns:
            Dictionary mapping scenario names to their output file paths
        """
        result = {}
        for scenario_name, config in self.scenarios.items():
            output_file = config.get_output_file()
            if output_file:
                result[scenario_name] = output_file
        
        return result
    
    def get_all_output_year_files(self, year: Union[str, int] = None) -> Dict[str, Path]:
        """
        Get output-year files from all scenarios.
        
        Args:
            year: Specific year to get (if None, returns all output-year files)
            
        Returns:
            Dictionary mapping scenario names to file paths
            If year is specified, only that year is returned
            If year is None, returns dict of dicts: {scenario: {year: path}}
        """
        if year is not None:
            # Get specific year from all scenarios
            result = {}
            for scenario_name, config in self.scenarios.items():
                file_path = config.get_output_year_file(year)
                if file_path:
                    result[scenario_name] = file_path
            return result
        else:
            # Get all years from all scenarios
            result = {}
            for scenario_name, config in self.scenarios.items():
                if config.output_year_files:
                    result[scenario_name] = config.output_year_files.copy()
            return result
    
    def get_all_input_files(self) -> Dict[str, Path]:
        """
        Get all input files (ending with -input.gdx) from all scenarios.
        
        Returns:
            Dictionary mapping scenario names to their input file paths
        """
        result = {}
        for scenario_name, config in self.scenarios.items():
            input_file = config.get_input_file()
            if input_file:
                result[scenario_name] = input_file
        
        return result
    
    def get_common_years(self) -> List[str]:
        """
        Get list of years that exist in ALL scenarios.
        
        Returns:
            Sorted list of years available across all scenarios
        """
        if not self.scenarios:
            return []
        
        # Get year sets for each scenario
        year_sets = [set(config.list_output_years()) for config in self.scenarios.values()]
        
        # Find intersection of all sets
        common_years = set.intersection(*year_sets) if year_sets else set()
        
        return sorted(common_years)
    
    def summary(self) -> str:
        """
        Generate a summary of detected scenarios and files.
        
        Returns:
            Formatted string with summary information
        """
        lines = [
            "=" * 60,
            f"Scenario Manager Summary",
            "=" * 60,
            f"Root Path: {self.root_path}",
            f"Type: {'Single Scenario' if self.is_single_scenario else 'Multiple Scenarios'}",
            f"Total Scenarios: {len(self.scenarios)}",
            ""
        ]
        
        if self.scenarios:
            lines.append("Scenarios:")
            for name, config in sorted(self.scenarios.items()):
                lines.append(f"  • {name}")
                lines.append(f"    - Path: {config.path}")
                lines.append(f"    - Balopt: {config.balopt_path.name}")
                lines.append(f"    - Total GDX Files: {len(config.gdx_files)}")
                
                # Show categorized files
                if config.output_files:
                    lines.append(f"      ↳ Output files: {len(config.output_files)}")
                    for filename in config.list_output_files():
                        lines.append(f"        → {filename}")
                
                if config.output_year_files:
                    lines.append(f"      ↳ Output-year files: {len(config.output_year_files)}")
                    for year in config.list_output_years():
                        filename = config.output_year_files[year].name
                        lines.append(f"        → {year}: {filename}")
                
                if config.input_files:
                    lines.append(f"      ↳ Input files: {len(config.input_files)}")
                    for filename in config.list_input_files():
                        lines.append(f"        → {filename}")
                
                if config.other_files:
                    lines.append(f"      ↳ Other files: {len(config.other_files)}")
                    for filename in config.list_other_files():
                        lines.append(f"        → {filename}")
            
            lines.append("")
            
            # Show common files
            common = self.get_common_files()
            if common:
                lines.append(f"Common files across all scenarios ({len(common)}):")
                for filename in common:
                    lines.append(f"  • {filename}")
            
            # Show common years
            common_years = self.get_common_years()
            if common_years:
                lines.append(f"\nCommon years across all scenarios ({len(common_years)}):")
                for year in common_years:
                    lines.append(f"  • {year}")
        else:
            lines.append("No scenarios detected.")
        
        lines.append("=" * 60)
        
        print("\n".join(lines))


if __name__ == "__main__":
    # Example usage
    
    print("Example 1: Load all scenarios and show categorized files")
    print("-" * 60)
    manager = ScenarioManager()
    # manager.summary()
    
    # print("\n\nExample 2: Work with specific scenario and file categories")
    # print("-" * 60)
    # if manager.scenarios_names:
    #     scenario_name = manager.scenarios_names[0]
    #     scenario = manager.get_scenario(scenario_name)
    #     print(f"Scenario: {scenario.name}")
    #     print(f"Output files: {scenario.list_output_files()}")
    #     print(f"Output years available: {scenario.list_output_years()}")
    #     print(f"Input files: {scenario.list_input_files()}")
    #     print(f"Other files: {scenario.list_other_files()}")
    
    # print("\n\nExample 3: Get all output files from all scenarios")
    # print("-" * 60)
    # output_files = manager.get_all_output_files()
    # print("Output files across scenarios:")
    # for scen_name, path in output_files.items():
    #     print(f"  • {scen_name}: {path.name}")
    
    # print("\n\nExample 4: Get output files for specific year")
    # print("-" * 60)
    # common_years = manager.get_common_years()
    # if common_years:
    #     year = common_years[0]
    #     year_files = manager.get_all_output_year_files(year)
    #     print(f"Output files for year {year}:")
    #     for scen_name, path in year_files.items():
    #         print(f"  • {scen_name}: {path.name}")
    
    # print("\n\nExample 5: Get all input files")
    # print("-" * 60)
    # input_files = manager.get_all_input_files()
    # print("Input files across scenarios:")
    # for scen_name, path in input_files.items():
    #     print(f"  • {scen_name}: {path.name}")
