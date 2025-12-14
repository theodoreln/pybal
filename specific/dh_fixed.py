### Module loading
# Add parent directory to path to import pybal module
import sys
from pathlib import Path
from typing import List, Dict, Optional, Union

# Import pybal modules
sys.path.append(str(Path(__file__).parent.parent))
from data.scenario import ScenarioManager, ScenarioConfig
from data.data_load import DataLoader, DataManager

# Import other common libraries
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

### Configuration 
def create_dh_fixed(input_results_path: Union[str, Path], output_inc_path: Union[str, Path]) :

    ### Configuration 
    years_value = list(range(2025, 2051))
    years = [str(year) for year in years_value]

    HeatSto_list = [0,0.02,0.04,0.06,0.08,0.1,0.105,0.11,0.115,0.12,0.125,0.13,0.135,0.14,0.145,0.15,0.155,0.16,0.165,0.17,0.175,0.18,0.185,0.19,0.195,0.2]
    HeatSto_dict = dict(zip(years, HeatSto_list))

    HeatPeak_list = [0.15,0.15,0.15,0.15,0.15,1.2,1.2,1.2,1.2,1.2,1.2,1.2,1.2,1.2,1.2,1.2,1.2,1.2,1.2,1.2,1.2,1.2,1.2,1.2,1.2,1.2]
    HeatPeak_dict = dict(zip(years, HeatPeak_list))

    GGG_factor = {'SolarDH-25_29': 0.00042}

    ### Load data
    Manager = ScenarioManager(input_results_path)
    Data = DataManager(Manager)

    ### Extract data 
    # Extract peak heat demand data
    peak_heat_demand_df = Data.get_symbol('AREARESULTS')
    peak_heat_demand_df = peak_heat_demand_df[peak_heat_demand_df['AREA_MEASURES'] =='Peak heat demand (MW)'].reset_index(drop=True)

    # Keep only relevant columns
    peak_heat_demand_df = peak_heat_demand_df[['AAA', 'YYY', 'value']].reset_index(drop=True)

    # Remove all INDH areas
    peak_heat_demand_df = peak_heat_demand_df[~peak_heat_demand_df['AAA'].str.contains('INDH')].reset_index(drop=True)

    # Extract all DH areas
    dh_areas = peak_heat_demand_df['AAA'].unique().tolist()

    # Extract years available in the results
    results_years = peak_heat_demand_df['YYY'].unique().tolist()

    # Extract capacity data
    capacity_df = Data.get_symbol('UNITRESULTS')

    # Filter on ECONSET on values in ['Invested heat capacity (MW)', Invested power capacity (MW), Installed heat capacity (MW), Installed power capacity (MW)]
    capacity_df = capacity_df[capacity_df['ECONSET'].isin(['Invested heat capacity (MW)', 'Invested power capacity (MW)', 'Installed heat capacity (MW)', 'Installed power capacity (MW)'])].reset_index(drop=True)

    # Pivot the dataframe to have ECONSET as columns
    capacity_df = capacity_df.pivot_table(index=['AAA', 'GGG', 'YYY'], columns='ECONSET', values='value').reset_index()

    # Delete rows that have no values in Invested heat capacity (MW)
    capacity_df = capacity_df[~capacity_df['Invested heat capacity (MW)'].isna()].reset_index(drop=True)

    # Delete rows that have 'G-HSTORE' in GGG
    capacity_df = capacity_df[~capacity_df['GGG'].str.contains('G-HSTORE')].reset_index(drop=True)

    # Put 0 when no data
    capacity_df['Invested power capacity (MW)'] = capacity_df['Invested power capacity (MW)'].fillna(0)
    capacity_df['Installed heat capacity (MW)'] = capacity_df['Installed heat capacity (MW)'].fillna(0)
    capacity_df['Installed power capacity (MW)'] = capacity_df['Installed power capacity (MW)'].fillna(0)

    # Verify areas in capacity_df are in dh_areas
    capacity_areas = capacity_df['AAA'].unique().tolist()
    for area in capacity_areas:
        if area not in dh_areas:
            print(f"Warning: Area {area} in capacity_df not found in dh_areas")

    # Extract all combinations of AAA and GGG in a list 
    area_ggg_combinations = capacity_df[['AAA', 'GGG']].drop_duplicates().values.tolist()

    ### Create GKFX_AddHcap 
    # Create a DataFrame to store heat storage capacities
    GKFX_AddHcap_Sto_df = pd.DataFrame([(area, year, 0) for area in dh_areas for year in results_years], columns=['AAA', 'YYY', 'value'])

    # Then for each row, get the heat storage capacity from the corresponding peak heat demand multiply by the HeatSto_dict and times 8
    GKFX_AddHcap_Sto_df['value'] = GKFX_AddHcap_Sto_df.apply(
        lambda row: peak_heat_demand_df[
            (peak_heat_demand_df['AAA'] == row['AAA']) & 
            (peak_heat_demand_df['YYY'] == row['YYY'])
        ]['value'].values[0] * HeatSto_dict[row['YYY']] * 8, axis=1)

    # Add heat storage in years that are not in the results years by interpolating the values
    new_df = pd.DataFrame()
    for area in dh_areas:
        area_df = GKFX_AddHcap_Sto_df[GKFX_AddHcap_Sto_df['AAA'] == area].reset_index(drop=True)
        area_years = area_df['YYY'].tolist()
        area_values = area_df['value'].tolist()
        
        # Create a full range of years from 2025 to 2050
        full_years = [str(year) for year in range(2025, 2051)]
        
        # Interpolate values for missing years
        full_values = np.interp(
            [int(year) for year in full_years],
            [int(year) for year in area_years],
            area_values
        )
        
        # Update GKFX_AddHcap_Sto_df with interpolated values
        for i, year in enumerate(full_years):
            df = pd.DataFrame({'AAA': area, 'YYY': year, 'value': full_values[i]}, index=[0])
            new_df = pd.concat([new_df, df], ignore_index=True)
    GKFX_AddHcap_Sto_df = new_df.copy()

    # Add a column 'GGG' after 'AAA' with the same value everywhere 'G-HSTORE'
    GKFX_AddHcap_Sto_df.insert(1, 'GGG', 'G-HSTORE')

    # Pivot the dataframes to have years as columns
    GKFX_AddHcap_Sto_df = GKFX_AddHcap_Sto_df.pivot_table(index=['AAA', 'GGG'], columns='YYY', values='value').reset_index()

    # Create a DataFrame to store DH plants capacities, from area_ggg_combinations
    GKFX_AddHcap_DH_df = pd.DataFrame([(area, ggg, year, 0) for area, ggg in area_ggg_combinations for year in results_years], columns=['AAA', 'GGG', 'YYY', 'value'])

    # Function to get capacity value
    def get_capacity_value(row):
        # Filter capacity_df for matching AAA, GGG, YYY
        matching_rows = capacity_df[
            (capacity_df['AAA'] == row['AAA']) & 
            (capacity_df['GGG'] == row['GGG']) & 
            (capacity_df['YYY'] == row['YYY'])
        ]
            
        # If no matching row found, return 0
        if matching_rows.empty:
            return 0
        
        # Get the first matching row
        match = matching_rows.iloc[0]
        
        # Check Invested power capacity first
        power_capacity = match['Invested power capacity (MW)']
        if power_capacity != 0:
            capacity = power_capacity
        else:
            # If power capacity is 0, use heat capacity
            capacity = match['Invested heat capacity (MW)']
        
        # Divide by GGG_factor if it exists, otherwise divide by 1
        factor = GGG_factor.get(row['GGG'], 1)
        return capacity / factor

    # Apply the function to each row
    GKFX_AddHcap_DH_df['value'] = GKFX_AddHcap_DH_df.apply(get_capacity_value, axis=1)

    # Add DH plant in years that are not in the results years by interpolating the values
    new_df = pd.DataFrame()
    for area, ggg in area_ggg_combinations:
        area_ggg_df = GKFX_AddHcap_DH_df[(GKFX_AddHcap_DH_df['AAA'] == area) & (GKFX_AddHcap_DH_df['GGG'] == ggg)].reset_index(drop=True)
        area_years = area_ggg_df['YYY'].tolist()
        area_values = area_ggg_df['value'].tolist()
        
        # Create a full range of years from 2025 to 2050
        full_years = [str(year) for year in range(2025, 2051)]
        
        # Interpolate values for missing years
        full_values = np.interp(
            [int(year) for year in full_years],
            [int(year) for year in area_years],
            area_values
        )
        
        # Update GKFX_AddHcap_DH_df with interpolated values
        for i, year in enumerate(full_years):
            df = pd.DataFrame({'AAA': area, 'GGG': ggg, 'YYY': year, 'value': full_values[i]}, index=[0])
            new_df = pd.concat([new_df, df], ignore_index=True)
    GKFX_AddHcap_DH_df = new_df.copy()

    # Pivot the dataframes to have years as columns
    GKFX_AddHcap_DH_df = GKFX_AddHcap_DH_df.pivot_table(index=['AAA', 'GGG'], columns='YYY', values='value').reset_index() 

    ### Create GKFX_AddPeak
    # Create a DataFrame to store peak heat capacities
    GKFX_AddPeak_df = pd.DataFrame([(area, year, 0) for area in dh_areas for year in results_years], columns=['AAA', 'YYY', 'value'])

    # Then for each row, get the peak heat capacity from the corresponding peak heat demand multiply by the HeatPeak_dict
    GKFX_AddPeak_df['value'] = GKFX_AddPeak_df.apply(
        lambda row: peak_heat_demand_df[
            (peak_heat_demand_df['AAA'] == row['AAA']) & 
            (peak_heat_demand_df['YYY'] == row['YYY'])
        ]['value'].values[0] * HeatPeak_dict[row['YYY']], axis=1)

    # Add heat storage in years that are not in the results years by interpolating the values
    new_df = pd.DataFrame()
    for area in dh_areas:
        area_df = GKFX_AddPeak_df[GKFX_AddPeak_df['AAA'] == area].reset_index(drop=True)
        area_years = area_df['YYY'].tolist()
        area_values = area_df['value'].tolist()
        
        # Create a full range of years from 2025 to 2050
        full_years = [str(year) for year in range(2025, 2051)]
        
        # Interpolate values for missing years
        full_values = np.interp(
            [int(year) for year in full_years],
            [int(year) for year in area_years],
            area_values
        )
        
        # Update GKFX_AddPeak_df with interpolated values
        for i, year in enumerate(full_years):
            df = pd.DataFrame({'AAA': area, 'YYY': year, 'value': full_values[i]}, index=[0])
            new_df = pd.concat([new_df, df], ignore_index=True)
    GKFX_AddPeak_df = new_df.copy()

    # Add a column 'GGG' after 'AAA' with the same value everywhere 'G-HSTORE'
    GKFX_AddPeak_df.insert(1, 'GGG', 'Boiler-NG')

    # Pivot the dataframe to have the years in columns
    GKFX_AddPeak_df = GKFX_AddPeak_df.pivot_table(index=['AAA', 'GGG'], columns='YYY', values='value').reset_index()

    ### Export as an inc file 
    # First, find the maximum width needed for the AAA.GGG column
    max_aaa_ggg_width = max(len(f"{row['AAA']}.{row['GGG']}") for _, row in GKFX_AddHcap_DH_df.iterrows())

    # Determine column width for year values (format: "1234.56" = 7 chars minimum)
    max_value_width = max(len(f"{row[year]:.2f}") for _, row in GKFX_AddHcap_DH_df.iterrows() for year in years)
    max_value_width = max_value_width + 2  # Add some padding

    # Ensure output_inc_path is a Path object and create the output file path
    output_inc_path = Path(output_inc_path)
    output_file = output_inc_path / 'data' / 'GKFX_DHfixed.inc'
    
    with open(output_file, 'w') as f:
        f.write('$onMulti' + '\n')
        f.write('* Fixed DH capacity to improve run speen. Use global "DHFIXED".' + '\n')
        f.write('\n')
        f.write('* Heat storage capacity (MWh)' + '\n')
        f.write('Table GKFX_AddHcap(AAA,GGG,YYY)' + '\n')

        # Write header (align year names with their columns)
        header = ' ' * (max_aaa_ggg_width + 2)  # Space for AAA.GGG column plus separator
        header += ''.join([year.ljust(max_value_width) for year in years]) + '\n'
        f.write(header)
        
        # Write each row with aligned columns
        for index, row in GKFX_AddHcap_Sto_df.iterrows():
            # Format AAA.GGG with padding to align all values
            aaa_ggg = f"{row['AAA']}.{row['GGG']}".ljust(max_aaa_ggg_width + 2)
            # Format values with consistent width
            values = ''.join([f"{row[year]:.2f}".ljust(max_value_width) for year in years])
            line = aaa_ggg + values + '\n'
            f.write(line)

        f.write('\n')
        f.write('* Modelled optimized capacity for DH plants' + '\n')

        # Write header (align year names with their columns)
        header = '*' + ' ' * (max_aaa_ggg_width + 1)  # Space for AAA.GGG column plus separator
        header += ''.join([year.ljust(max_value_width) for year in years]) + '\n'
        f.write(header)
        
        # Write each row with aligned columns
        for index, row in GKFX_AddHcap_DH_df.iterrows():
            # Format AAA.GGG with padding to align all values
            aaa_ggg = f"{row['AAA']}.{row['GGG']}".ljust(max_aaa_ggg_width + 2)
            # Format values with consistent width
            values = ''.join([f"{row[year]:.2f}".ljust(max_value_width) for year in years])
            line = aaa_ggg + values + '\n'
            f.write(line)
        
        f.write(';' + '\n')
        f.write('GKFX(Y,IA,G)=GKFX(Y,IA,G)+GKFX_AddHcap(IA,G,Y);' + '\n')
        f.write('\n')

        f.write('* Additional peaker capacity' + '\n')
        f.write('Table GKFX_AddPeak(AAA,GGG,YYY)' + '\n')
        # Write header (align year names with their columns)
        header = ' ' * (max_aaa_ggg_width + 2)  # Space for AAA.GGG column plus separator
        header += ''.join([year.ljust(max_value_width) for year in years]) + '\n'
        f.write(header)
        
        # Write each row with aligned columns
        for index, row in GKFX_AddPeak_df.iterrows():
            # Format AAA.GGG with padding to align all values
            aaa_ggg = f"{row['AAA']}.{row['GGG']}".ljust(max_aaa_ggg_width + 2)
            # Format values with consistent width
            values = ''.join([f"{row[year]:.2f}".ljust(max_value_width) for year in years])
            line = aaa_ggg + values + '\n'
            f.write(line)

        f.write(';' + '\n')
        f.write('GKFX(Y,IA,G)=GKFX(Y,IA,G)+GKFX_AddPeak(IA,G,Y);' + '\n')
        f.write('\n')

if __name__ == "__main__":
    # Input and output path
    #input = Path('K:/Projects/25117_SMR_in_DK/Scenarios_Bal/KapMek_SMR1500_Bal')
    #output = Path('K:/Projects/25117_SMR_in_DK/Scenarios_Bal/Test_SMR600_DHFixed_Python')
    #create_dh_fixed(input, output)
    # # Bal model paths
    # Bal_input = [Path('K:\Projects\25117_SMR_in_DK\Scenarios_Bal\KapMek_SMR0_Bal'),
    #              Path('K:\Projects\25117_SMR_in_DK\Scenarios_Bal\KapMek_SMR600_Bal'),
    #              Path('K:\Projects\25117_SMR_in_DK\Scenarios_Bal\KapMek_SMR1500_Bal'),
    #              Path('K:\Projects\25117_SMR_in_DK\Scenarios_Bal\SMR0_Bal'),
    #              Path('K:\Projects\25117_SMR_in_DK\Scenarios_Bal\SMR600_Bal'),
    #              Path('K:\Projects\25117_SMR_in_DK\Scenarios_Bal\SMR1500_Bal')]
    # Bal_output = [Path('K:\Projects\25117_SMR_in_DK\Scenarios_Bal\KapMek_SMR0_Bal_DHF'),
    #               Path('K:\Projects\25117_SMR_in_DK\Scenarios_Bal\KapMek_SMR600_Bal_DHF'),
    #               Path('K:\Projects\25117_SMR_in_DK\Scenarios_Bal\KapMek_SMR1500_Bal_DHF'),
    #               Path('K:\Projects\25117_SMR_in_DK\Scenarios_Bal\SMR0_Bal_DHF'),
    #               Path('K:\Projects\25117_SMR_in_DK\Scenarios_Bal\SMR600_Bal_DHF'),
    #               Path('K:\Projects\25117_SMR_in_DK\Scenarios_Bal\SMR1500_Bal_DHF')]
    # AF25 model paths
    AF25_input = [Path('K:/Projects/25117_SMR_in_DK/Scenarios_AF25/SMR0_AF25'),
                  Path('K:/Projects/25117_SMR_in_DK/Scenarios_AF25/SMR600_AF25'),
                  Path('K:/Projects/25117_SMR_in_DK/Scenarios_AF25/SMR1500_AF25')]
    AF25_output = [Path('K:/Projects/25117_SMR_in_DK/Scenarios_AF25/SMR0_AF25_DHF'),
                   Path('K:/Projects/25117_SMR_in_DK/Scenarios_AF25/SMR600_AF25_DHF'),
                   Path('K:/Projects/25117_SMR_in_DK/Scenarios_AF25/SMR1500_AF25_DHF')]
    # KF25 model paths
    KF25_input = [Path('K:/Projects/25117_SMR_in_DK/Scenarios_KF25/SMR0_KF25'),
                  Path('K:/Projects/25117_SMR_in_DK/Scenarios_KF25/SMR600_KF25'),
                  Path('K:/Projects/25117_SMR_in_DK/Scenarios_KF25/SMR1500_KF25')]
    KF25_output = [Path('K:/Projects/25117_SMR_in_DK/Scenarios_KF25/SMR0_KF25_DHF'),
                   Path('K:/Projects/25117_SMR_in_DK/Scenarios_KF25/SMR600_KF25_DHF'),
                   Path('K:/Projects/25117_SMR_in_DK/Scenarios_KF25/SMR1500_KF25_DHF')]
    # EURSMR model paths
    EURSMR_input = [Path('K:/Projects/25117_SMR_in_DK/Scenarios_EURSMR/LowPrice_EURSMR'),
                  Path('K:/Projects/25117_SMR_in_DK/Scenarios_EURSMR/MidPrice_EURSMR'),
                  Path('K:/Projects/25117_SMR_in_DK/Scenarios_EURSMR/HighPrice_EURSMR')]
    EURSMR_output = [Path('K:/Projects/25117_SMR_in_DK/Scenarios_EURSMR/LowPrice_EURSMR_DHF'),
                   Path('K:/Projects/25117_SMR_in_DK/Scenarios_EURSMR/MidPrice_EURSMR_DHF'),
                   Path('K:/Projects/25117_SMR_in_DK/Scenarios_EURSMR/HighPrice_EURSMR_DHF')]
    # Map necessary input and output paths
    options_dict = {
    #    'Bal': (Bal_input, Bal_output),
        'AF25': (AF25_input, AF25_output),
        'KF25': (KF25_input, KF25_output),
        'EURSMR': (EURSMR_input, EURSMR_output)
    }
    options = ['AF25', 'KF25', 'EURSMR']
    # Loop through each scenario type and process all models
    for scenario_type in options:
        input_paths, output_paths = options_dict[scenario_type]
        for input_path, output_path in zip(input_paths, output_paths):
            print(f"Processing {scenario_type} model: {input_path.name}")
            create_dh_fixed(input_path, output_path)