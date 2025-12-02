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
        BM_path : Path to the BM gdx file '*-BM.gdx'
        Basis_path : Path to the basis gdx file '*-Basis.gdx'
        input_path: Path to the input gdx file '*-input.gdx'
        output_path: Path to the output gdx file '*-output.gdx'
        output_year_path: Dict of files ending with 'output-YYYY.gdx' -> {year: path}
        output_other_path: Dict of all other GDX files
        gdx_files: Dictionary mapping ALL file basenames to full paths (for backward compatibility)
    """
    name: str
    path: Path
    balopt_path: Path
    BM_path: Path = None
    Basis_path: Path = None
    input_path: Path = None
    output_path: Path = None
    output_year_path: Dict[str, Path] = field(default_factory=dict)  # key is year string
    output_years: List[str] = field(default_factory=list)
    output_other_path: Dict[str, Path] = field(default_factory=dict)
    gdx_files: Dict[str, Path] = field(default_factory=dict)
    
    def __post_init__(self):
        """Categorize GDX files."""

        # Categorize gdx files based on naming patterns
        self._categorize_files()
        self.output_years = list(self.output_year_path.keys())
        self.key_path_map = {'BM': self.BM_path,
                             'Basis': self.Basis_path,
                             'input': self.input_path,
                             'output': self.output_path,
                             'output_year': self.output_year_path}

    def __repr__(self):
        return (f"ScenarioConfig(name='{self.name}', "
                f"gdx files={len(self.gdx_files)})")
    
    def _categorize_files(self):
        """
        Categorize GDX files based on naming patterns.
        
        Patterns:
        - *-BM.gdx -> BM_path
        - *-Basis.gdx -> Basis_path
        - *-input.gdx -> input_file
        - *-output.gdx -> output_file
        - *-output-YYYY.gdx -> output_year_file (with year extracted)
        - Everything else -> output_other_file
        """
        # Pattern to match output-year files (e.g., bb3_AHC-output-2037.gdx)
        output_year_pattern = re.compile(r'^(.+)-output-(\d{4})\.gdx$', re.IGNORECASE)
        
        for filename, filepath in self.gdx_files.items():
            
            # Check for output-year pattern first (more specific)
            match = output_year_pattern.match(filename)
            if match:
                year = match.group(2)  # Extract year
                self.output_year_path[year] = filepath
            
            # Check for output files (but not output-year)
            elif filename.endswith('-output.gdx'):
                self.output_path = filepath

            # Check for input files
            elif filename.endswith('-input.gdx'):
                self.input_path = filepath

            # Check for BM files
            elif filename.endswith('-BM.gdx'):
                self.BM_path = filepath

            # Check for Basis files
            elif filename.endswith('-Basis.gdx'):
                self.Basis_path = filepath

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
            self._discover_scenarios()
            self.scenarios_names = set(self.scenarios.keys())
            self.output_years = set([item for config in self.scenarios.values() if config.output_years != [] for item in config.output_years])
            self.key_func_map = {'input': self.get_all_input_files,
                                  'BM': self.get_all_BM_files,
                                  'Basis': self.get_all_Basis_files,
                                  'output': self.get_all_output_files,
                                  'output_year': self.get_all_output_year_files}

    def __repr__(self):
        return (f"ScenarioManager(root_path='{self.root_path}', "
                f"scenarios={len(self.scenarios)})")

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
        balopt_path = Path(balopt_files[0])
        
        # Look for output folder
        output_dir = scenario_path / "output"
        
        # Collect GDX files
        gdx_files = {}
        if output_dir.exists() and output_dir.is_dir():
            for gdx_file in output_dir.glob("*.gdx"):
                gdx_files[gdx_file.name] = Path(gdx_file)
        
        # Create scenario config
        config = ScenarioConfig(
            name=scenario_path.name,
            path=scenario_path,
            balopt_path=balopt_path,
            gdx_files=gdx_files
        )
        
        return config
    
    def _discover_scenarios(self) -> Dict[str, ScenarioConfig]:
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
    
    def get_all_gdx_files(self, filename: str) -> Dict[str, Path]:
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
    
    def get_all_BM_files(self) -> Dict[str, Path]:
        """
        Get all BM files (ending with -BM.gdx) from all scenarios.
        
        Returns:
            Dictionary mapping scenario names to their BM file paths
        """
        result = {}
        for scenario_name, config in self.scenarios.items():
            BM_file = config.BM_path
            if BM_file:
                result[scenario_name] = BM_file
        
        return result
    
    def get_all_Basis_files(self) -> Dict[str, Path]:
        """
        Get all Basis files (ending with -Basis.gdx) from all scenarios.
        
        Returns:
            Dictionary mapping scenario names to their Basis file paths
        """
        result = {}
        for scenario_name, config in self.scenarios.items():
            Basis_file = config.Basis_path
            if Basis_file:
                result[scenario_name] = Basis_file
        
        return result
    
    def get_all_input_files(self) -> Dict[str, Path]:
        """
        Get all input files (ending with -input.gdx) from all scenarios.
        
        Returns:
            Dictionary mapping scenario names to their input file paths
        """
        result = {}
        for scenario_name, config in self.scenarios.items():
            input_file = config.input_path
            if input_file:
                result[scenario_name] = input_file
        
        return result
    
    def get_all_output_files(self) -> Dict[str, Path]:
        """
        Get all output files (ending with -output.gdx) from all scenarios.
        
        Returns:
            Dictionary mapping scenario names to their output file paths
        """
        result = {}
        for scenario_name, config in self.scenarios.items():
            output_file = config.output_path
            if output_file:
                result[scenario_name] = output_file
        
        return result
    
    def get_all_output_year_files(self) -> Dict[str, Path]:
        """
        Get output-year files from all scenarios.
            
        Returns:
            Dictionary mapping scenario names to file paths
            Returns dict of dicts: {scenario: {year: path}}
        """
        result = {}
        for scenario_name, config in self.scenarios.items():
            if config.output_year_path:
                result[scenario_name] = config.output_year_path.copy()
        return result
    
    def get_common_output_years(self) -> List[str]:
        """
        Get list of years that exist in ALL scenarios.
        
        Returns:
            Sorted list of years available across all scenarios
        """
        if not self.scenarios:
            return []
        
        # Get year sets for each scenario
        year_sets = [set(config.output_years) for config in self.scenarios.values()]
        
        # Find intersection of all sets
        common_years = set.intersection(*year_sets) if year_sets else set()
        
        return sorted(common_years)

    def filter_scenarios(self, option: str = "all") -> Dict[str, ScenarioConfig]:
        """
        Filter scenarios based on a single option string.

        Args:
            option: One of:
                - 'inout' / 'io' : keep scenarios with both input and output files
                - 'yearly' / 'year' : keep scenarios with output-year files
                - 'both' : keep scenarios that have both inout AND yearly files
                - 'all' (default) : keep all scenarios

        Returns:
            Filtered dictionary of scenarios (also replaces self.scenarios)
        """
        opt = (option or "all").strip().lower()
        valid_opts = {
            "inout": ("inout", "io", "input-output", "input_output"),
            "yearly": ("yearly", "year", "output-year", "output_year"),
            "both": ("both",),
            "all": ("all", "none", "")
        }

        # Map normalized input to canonical key
        canon = None
        for k, aliases in valid_opts.items():
            if opt in aliases:
                canon = k
                break
        if canon is None:
            raise ValueError(f"Unknown option '{option}'. Valid options: inout, yearly, both, all")

        filtered: Dict[str, ScenarioConfig] = {}
        for scenario_name, config in self.scenarios.items():
            has_inout = config.input_path is not None and config.output_path is not None
            has_yearly = bool(config.output_year_path)

            if canon == "both" and has_inout and has_yearly:
                filtered[scenario_name] = config
            elif canon == "inout" and has_inout:
                filtered[scenario_name] = config
            elif canon == "yearly" and has_yearly:
                filtered[scenario_name] = config
            elif canon == "all":
                filtered[scenario_name] = config

        # Replace the internal scenarios dict with the filtered result
        self.scenarios = filtered
        self.scenarios_names = set(self.scenarios.keys())

        return self.scenarios
    
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
                lines.append(f"    - Total GDX Files: {len(config.gdx_files)}")
                
                # Show categorized files
                if config.BM_path:
                    lines.append(f"      ↳ BM file: {config.BM_path.name}")
                
                if config.Basis_path:
                    lines.append(f"      ↳ Basis file: {config.Basis_path.name}")
                
                if config.input_path:
                    lines.append(f"      ↳ Input file: {config.input_path.name}")
                
                if config.output_path:
                    lines.append(f"      ↳ Output file: {config.output_path.name}")
                
                if config.output_year_path:
                    lines.append(f"      ↳ Output-year files: {len(config.output_year_path)}")
                    for year in sorted(config.output_years):
                        filename = config.output_year_path[year].name
                        lines.append(f"        → {year}: {filename}")
                
                if config.output_other_path:
                    lines.append(f"      ↳ Other files: {len(config.output_other_path)}")
                    for filename in sorted(config.output_other_path.keys()):
                        lines.append(f"        → {filename}")
            
            lines.append("")
            
            # Show common years
            common_years = self.get_common_output_years()
            if common_years:
                lines.append(f"Common years across all scenarios ({len(common_years)}):")
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
    manager.summary()
    
    print("\n\nExample 2: Work with a specific scenario")
    print("-" * 60)
    if manager.scenarios_names:
        scenario_name = next(iter(manager.scenarios_names))
        scenario = manager.scenarios[scenario_name]
        print(f"Scenario: {scenario.name}")
        print(f"  Balopt file: {scenario.balopt_path.name}")
        print(f"  BM file: {scenario.BM_path.name if scenario.BM_path else 'None'}")
        print(f"  Basis file: {scenario.Basis_path.name if scenario.Basis_path else 'None'}")
        print(f"  Input file: {scenario.input_path.name if scenario.input_path else 'None'}")
        print(f"  Output file: {scenario.output_path.name if scenario.output_path else 'None'}")
        print(f"  Output years: {scenario.output_years}")
        print(f"  Other files: {list(scenario.output_other_path.keys())}")
    
    print("\n\nExample 3: Get all input files")
    print("-" * 60)
    input_files = manager.get_all_input_files()
    print("Input files across scenarios:")
    for scen_name, path in input_files.items():
        print(f"  • {scen_name}: {path.name}")
    
    print("\n\nExample 4: Get all output files from all scenarios")
    print("-" * 60)
    output_files = manager.get_all_output_files()
    print("Output files across scenarios:")
    for scen_name, path in output_files.items():
        print(f"  • {scen_name}: {path.name}")
    
    print("\n\nExample 5: Get all output-year files")
    print("-" * 60)
    year_files = manager.get_all_output_year_files()
    print("Output-year files by scenario:")
    for scen_name, year_dict in year_files.items():
        print(f"  • {scen_name}:")
        for year, path in sorted(year_dict.items()):
            print(f"    - {year}: {path.name}")
    
    print("\n\nExample 6: Get common years")
    print("-" * 60)
    common_years = manager.get_common_output_years()
    print(f"Common years across all scenarios: {common_years}")
    
    print("\n\nExample 7: Filter scenarios")
    print("-" * 60)
    manager2 = ScenarioManager()
    print(f"Before filtering: {len(manager2.scenarios)} scenarios")
    manager2.filter_scenarios("both")
    print(f"After filtering (both): {len(manager2.scenarios)} scenarios")
    print(f"Filtered scenarios: {manager2.scenarios_names}")

